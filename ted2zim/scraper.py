#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import dateutil.parser
import json
import time
import pathlib
import shutil
import datetime
import urllib.parse

import jinja2
from bs4 import BeautifulSoup
from zimscraperlib.zim import ZimInfo, make_zim_file
from zimscraperlib.i18n import get_language_details
from zimscraperlib.download import save_large_file
from zimscraperlib.video.presets import VideoWebmLow, VideoMp4Low
from kiwixstorage import KiwixStorage
from pif import get_public_ip

from .utils import download_link, update_subtitles_list, WebVTT
from .constants import (
    ROOT_DIR,
    SCRAPER,
    BASE_URL,
    NONE,
    MATCHING,
    TEDLANGS,
    ALL,
    getLogger,
)
from .processing import post_process_video


logger = getLogger()


class Ted2Zim:
    def __init__(
        self,
        max_videos_per_topic,
        topics,
        debug,
        name,
        video_format,
        low_quality,
        output_dir,
        no_zim,
        fname,
        languages,
        title,
        description,
        creator,
        publisher,
        tags,
        keep_build_dir,
        autoplay,
        use_any_optimized_version,
        s3_url_with_credentials,
        playlist,
        subtitles_enough,
        subtitles_setting,
    ):

        # video-encoding info
        self.video_format = video_format
        self.low_quality = low_quality

        # zim params
        self.fname = fname
        self.languages = (
            [] if languages is None else [l.strip() for l in languages.split(",")]
        )
        self.tags = [] if tags is None else [t.strip() for t in tags.split(",")]
        self.title = title
        self.description = description
        self.creator = creator
        self.publisher = publisher
        self.name = name

        # output directory
        self.output_dir = pathlib.Path(output_dir).expanduser().resolve()

        # scraper options
        self.topics = (
            []
            if not topics
            else [c.strip().replace(" ", "+") for c in topics.split(",")]
        )
        self.max_videos_per_topic = max_videos_per_topic
        self.autoplay = autoplay
        self.playlist = playlist
        self.subtitles_enough = subtitles_enough
        self.subtitles_setting = (
            subtitles_setting
            if subtitles_setting == ALL
            or subtitles_setting == MATCHING
            or subtitles_setting == NONE
            else self.to_ted_langcodes(
                [lang.strip() for lang in subtitles_setting.split(",")]
            )
        )

        # zim info
        self.zim_info = ZimInfo(
            homepage="index.html",
            tags=self.tags + ["_category:ted", "ted", "_videos:yes"],
            creator=self.creator,
            publisher=self.publisher,
            name=self.name,
            scraper=SCRAPER,
            favicon="favicon.png",
        )

        # optimization cache
        self.s3_url_with_credentials = s3_url_with_credentials
        self.use_any_optimized_version = use_any_optimized_version
        self.s3_storage = None
        self.video_quality = "low" if self.low_quality else "high"

        # debug/developer options
        self.no_zim = no_zim
        self.keep_build_dir = keep_build_dir
        self.debug = debug

        # class members
        self.videos = []
        self.playlist_title = None
        self.playlist_description = None
        self.source_languages = (
            [] if not self.languages else self.to_ted_langcodes(self.languages)
        )
        self.zim_lang = None

    @property
    def templates_dir(self):
        return ROOT_DIR.joinpath("templates")

    @property
    def build_dir(self):
        return self.output_dir.joinpath("build")

    @property
    def videos_dir(self):
        return self.build_dir.joinpath("videos")

    @property
    def ted_videos_json(self):
        return self.output_dir.joinpath("ted_videos.json")

    @property
    def ted_topics_json(self):
        return self.output_dir.joinpath("ted_topics.json")

    @property
    def talks_base_url(self):
        return BASE_URL + "talks"

    @property
    def playlists_base_url(self):
        return BASE_URL + "playlists"

    def append_part1_or_part3(self, lang_code_list, lang_info):
        """ Fills missing ISO languages codes for all in list

            lang_code_list: list og lang codes
            lang_info: see zimscraperlib.i18n """

        # ignore extra language mappings if supplied query was an iso-639-1 code
        if "part1" in lang_info["iso_types"]:
            lang_code_list.append(lang_info["iso-639-1"])

        # supplied query was not iso-639-1
        else:
            if lang_info["iso-639-1"]:
                lang_code_list.append(lang_info["iso-639-1"])
                # check for extra language codes to include
                if lang_info["iso-639-1"] in TEDLANGS["mappings"]:
                    for code in TEDLANGS["mappings"][lang_info["iso-639-1"]]:
                        lang_code_list.append(code)
            elif lang_info["iso-639-3"]:
                lang_code_list.append(lang_info["iso-639-3"])
            else:
                supplied_lang = lang_info["query"]
                logger.error(f"Language {supplied_lang} is not supported by TED")

    def to_ted_langcodes(self, languages):
        """ Converts languages queries into TED language codes

            Examples:
                ["English", "fr", "hin"] => ["en", "fr", "hi"]
                ["chi", "fake"] => ["zh", "zh-cn", "zh-tw"]
        """

        lang_code_list = []
        for lang in languages:
            lang_info = get_language_details(lang, failsafe=True)
            if lang_info:
                if lang_info["querytype"] == "purecode":
                    self.append_part1_or_part3(lang_code_list, lang_info)
                elif lang_info["querytype"] == "locale":
                    query = lang_info["query"].replace("_", "-")
                    if query in TEDLANGS["locales"]:
                        lang_code_list.append(query)
                    else:
                        self.append_part1_or_part3(lang_code_list, lang_info)
                else:
                    self.append_part1_or_part3(lang_code_list, lang_info)
        return list(set(lang_code_list))

    def extract_videos_from_playlist(self):
        """ extracts metadata for all videos in the given playlist

            calls extract_video_info on all links to get this data
        """

        playlist_url = f"{self.playlists_base_url}/{self.playlist}"
        soup = BeautifulSoup(download_link(playlist_url).text, features="html.parser")
        video_elements = soup.find_all("a", attrs={"class": "hover/appear"})
        self.playlist_title = soup.find("h1", attrs={"class": "f:4"}).string
        self.playlist_description = soup.find("p", attrs={"class": "m-b:2"}).string

        for element in video_elements:
            relative_path = element.get("href")
            url = urllib.parse.urljoin(self.talks_base_url, relative_path)
            if self.extract_video_info(url):
                if self.source_languages:
                    other_lang_urls = self.generate_urls_for_other_languages(url)
                    logger.debug(
                        f"Searching info for the video in other {len(other_lang_urls)} language(s)"
                    )
                    for lang_url in other_lang_urls:
                        self.extract_video_info(lang_url)
            logger.debug(f"Seen {relative_path}")
        logger.debug(f"Total videos found on playlist: {len(video_elements)}")
        if not video_elements:
            raise ValueError("Wrong playlist ID supplied. No videos found")

    def extract_videos_from_topics(self):
        """ extracts metadata for required number of videos on different topics """
        for topic in self.topics:
            logger.debug(f"Fetching video links for topic: {topic}")
            topic_url = f"{self.talks_base_url}?topics%5B%5D={topic}"
            total_videos_scraped = 0
            video_allowance = self.max_videos_per_topic

            if self.source_languages:
                for lang in self.source_languages:
                    topic_url = topic_url + f"&language={lang}"
                    page = 1
                    while video_allowance:
                        html = download_link(f"{topic_url}&page={page}").text
                        num_videos_extracted = self.extract_videos_on_topic_page(
                            html, video_allowance,
                        )
                        if num_videos_extracted == 0:
                            break
                        video_allowance -= num_videos_extracted
                        total_videos_scraped += num_videos_extracted
                        page += 1
            else:
                page = 1
                while video_allowance:
                    html = download_link(f"{topic_url}&page={page}").text
                    num_videos_extracted = self.extract_videos_on_topic_page(
                        html, video_allowance,
                    )
                    if num_videos_extracted == 0:
                        break
                    video_allowance -= num_videos_extracted
                    total_videos_scraped += num_videos_extracted
                    page += 1
            logger.info(f"Total video links found in {topic}: {total_videos_scraped}")
            if total_videos_scraped == 0:
                self.topics.remove(topic)
                logger.debug(f"Removed topic {topic} from list as it had no videos")
        if not self.topics:
            if self.source_languages:
                raise ValueError(
                    "No videos found for any topic in the language(s) requested. Check topic(s) and/or language code supplied to --languages"
                )
            raise ValueError("Wrong topic(s) were supplied. No videos found")

    def update_zim_metadata(self):

        if not self.languages:
            self.zim_lang = "eng"
        else:
            if len(self.source_languages) > 1:
                self.zim_lang = "mul"
            else:
                self.zim_lang = get_language_details(
                    self.source_languages[0], failsafe=True
                )["iso-639-3"]

        if self.playlist:
            if not self.title:
                self.title = self.playlist_title
            if not self.description:
                self.description = self.playlist_description
        else:
            if len(self.topics) > 1:
                if not self.title:
                    self.title = "TED Collection"
                if not self.description:
                    self.description = "A selection of TED videos from several topics"
            else:
                if not self.title:
                    topic_str = self.topics[0].replace("+", " ")
                    self.title = f"{topic_str.capitalize()} from TED"
                if not self.description:
                    self.description = f"A selection of {topic_str} videos from TED"

    def get_display_name(self, lang_code, lang_name):
        """ Display name for language """
        if lang_code != "en":
            return (
                get_language_details(lang_code, failsafe=True)["native"]
                + " - "
                + lang_name
            )
        return lang_name

    def get_subtitle_dict(self, lang):
        """ dict of language name and code from a larger dict lang

        Example:
        {
            'languageCode': 'en',
            'languageName': 'English'
        }
        """

        return {
            "languageName": self.get_display_name(
                lang["languageCode"], lang["languageName"]
            ),
            "languageCode": lang["languageCode"],
        }

    def generate_subtitle_list(self, video_id, langs, page_lang):
        """ List of all subtitle languages with link to their pages """

        subtitles = []
        if self.subtitles_setting == ALL or (not self.source_languages and self.topics):
            subtitles = [self.get_subtitle_dict(lang) for lang in langs]
        elif self.subtitles_setting == MATCHING or (
            self.subtitles_enough and self.subtitles_setting == NONE
        ):
            subtitles = [
                self.get_subtitle_dict(lang)
                for lang in langs
                if lang["languageCode"] == page_lang
            ]
        elif self.subtitles_setting and self.subtitles_setting != NONE:
            if not self.subtitles_enough and self.topics:
                subtitles = [
                    self.get_subtitle_dict(lang)
                    for lang in langs
                    if lang["languageCode"] in self.subtitles_setting
                ]
            else:
                subtitles = [
                    self.get_subtitle_dict(lang)
                    for lang in langs
                    if lang["languageCode"] in self.subtitles_setting
                    or lang["languageCode"] in self.source_languages
                ]

        return update_subtitles_list(video_id, subtitles)

    def generate_urls_for_other_languages(self, url):
        """ Possible URLs for other requested languages based on a video url """

        urls = []
        page_lang, query = self.get_lang_code_from_url(url, with_full_query=True)
        url_parts = list(urllib.parse.urlparse(url))

        # update the language query field value with other languages and form URLs
        for language in self.source_languages:
            if language != page_lang:
                query.update({"language": language})
                url_parts[4] = urllib.parse.urlencode(query)
                urls.append(urllib.parse.urlunparse(url_parts))
        return urls

    def extract_videos_on_topic_page(self, page_html, video_allowance):

        # all videos are embedded in a <div> with the class name 'row'.
        # we are searching for the div inside this div, that has an <a>-tag
        # with the class name 'media__image', because this is the relative
        # link to the representative TED talk. It turns this relative link to
        # an absolute link and calls extract_video_info for them
        soup = BeautifulSoup(page_html, features="html.parser")
        video_links = soup.select("div.row div.media__image a")
        nb_extracted = 0
        logger.debug(f"{str(len(video_links))} video(s) found on current page")
        for video_link in video_links:
            url = urllib.parse.urljoin(self.talks_base_url, video_link["href"])
            if not [
                video
                for video in self.videos
                if video.get("tedpath", None) == video_link["href"]
            ]:
                if self.extract_video_info(url):
                    nb_extracted += 1
                    if self.source_languages:
                        other_lang_urls = self.generate_urls_for_other_languages(url)
                        logger.debug(
                            f"Searching info for video in other {len(other_lang_urls)} language(s)"
                        )
                        for lang_url in other_lang_urls:
                            self.extract_video_info(lang_url)
                    if nb_extracted == video_allowance:
                        break
                logger.debug(f"Seen {video_link['href']}")
        return nb_extracted

    def get_lang_code_from_url(self, url, with_full_query=False):
        """ gets the queried language code from a ted talk url """

        # sample - https://www.ted.com/talks/alex_rosenthal_the_gauntlet_think_like_a_coder_ep_8?language=ja
        url_parts = list(urllib.parse.urlparse(url))

        # explode url to extract `language` query field value
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        current_lang = query.get("language")
        if with_full_query:
            return current_lang, query
        return current_lang

    def extract_video_info(self, url):
        """ extract all info from a TED video url and updates self.videos """

        # Extract the meta-data of the video:
        # Speaker, the profession of the speaker, a short biography of
        # the speaker, the link to a picture of the speaker, title,
        # publishing date, view count, description of the TED talk,
        # direct download link to the video, download link to the subtitle
        # files and a link to a thumbnail of the video.
        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        # returns True if successfully scraped new video
        soup = BeautifulSoup(download_link(url).text, features="html.parser")
        div = soup.find("div", attrs={"class": "talks-main"})
        script_tags_within_div = div.find_all("script")
        if len(script_tags_within_div) == 0:
            logger.error("The required script tag containing video meta is not present")
            return False
        json_data_tag = script_tags_within_div[-1]
        json_data = json_data_tag.string
        json_data = json.loads(json_data[18:-1])["__INITIAL_DATA__"]
        lang_code = json_data["language"]

        requested_lang_code = self.get_lang_code_from_url(url)
        if requested_lang_code and lang_code != requested_lang_code:
            logger.error(
                f"Video has not yet been translated into {requested_lang_code}"
            )
            return False
        lang_name = json_data["requested_language_english_name"]
        talk_info = json_data["talks"][0]
        native_talk_language = talk_info["player_talks"][0]["nativeLanguage"]
        if (
            not self.subtitles_enough
            and self.source_languages
            and native_talk_language != lang_code
            and self.topics
        ):
            return False

        # Extract the speaker of the TED talk
        if len(talk_info["speakers"]) != 0:
            speaker_info = talk_info["speakers"][0]
            speaker = " ".join(
                [
                    speaker_info.get("firstname"),
                    speaker_info.get("middleinitial"),
                    speaker_info.get("lastname"),
                ]
            )
        else:
            speaker_info = {
                "description": "None",
                "whotheyare": "None",
                "photo_url": "None",
            }
            if "speaker_name" in talk_info:
                speaker = talk_info["speaker_name"]
            else:
                speaker = "None"

        # Extract the profession of the speaker of the TED talk
        speaker_profession = speaker_info["description"]

        # Extract the short biography of the speaker of the TED talk
        speaker_bio = speaker_info["whotheyare"]

        # Extract the Url to the picture of the speaker of the TED talk
        speaker_picture = speaker_info["photo_url"]

        # Extract the title of the TED talk
        title = talk_info["title"]

        # Extract the description of the TED talk
        description = talk_info["description"]

        # Extract the upload date of the TED talk
        date = dateutil.parser.parse(talk_info["recorded_at"]).strftime("%d %B %Y")

        # Extract the length of the TED talk in minutes
        length = int(talk_info["duration"]) // 60

        # Extract the thumbnail of the of the TED talk video
        thumbnail = talk_info["player_talks"][0]["thumb"]

        # Extract the download link of the TED talk video
        download_links = talk_info["downloads"]["nativeDownloads"]
        if not download_links:
            logger.error("No direct download links found for the video")
            return False
        video_link = download_links["medium"]
        if not video_link:
            logger.error("No link to download video in medium quality")
            return False

        # Extract the video Id of the TED talk video.
        # We need this to generate the subtitle page.
        video_id = talk_info["id"]

        langs = talk_info["player_talks"][0]["languages"]
        subtitles = self.generate_subtitle_list(video_id, langs, lang_code)

        # Extract the keywords for the TED talk
        keywords = soup.find("meta", attrs={"name": "keywords"})["content"]
        keywords = [key.strip() for key in keywords.split(",")]

        # append to self.videos and return if not present
        if not [video for video in self.videos if video.get("id", None) == video_id]:
            self.videos.append(
                {
                    "id": video_id,
                    "languages": [
                        {
                            "languageCode": lang_code,
                            "languageName": self.get_display_name(lang_code, lang_name),
                        }
                    ],
                    "title": [{"lang": lang_code, "text": title}],
                    "description": [{"lang": lang_code, "text": description}],
                    "speaker": speaker,
                    "speaker_profession": speaker_profession,
                    "speaker_bio": speaker_bio,
                    "speaker_picture": speaker_picture,
                    "date": date,
                    "thumbnail": thumbnail,
                    "video_link": video_link,
                    "length": length,
                    "subtitles": subtitles,
                    "keywords": keywords,
                    "tedpath": urllib.parse.urlparse(url)[2],
                }
            )
            logger.debug(f"Successfully inserted video {video_id} into video list")
            return True

        # update localized meta for video if already in self.videos
        # based on --subtitles=matching
        logger.debug(f"Video {video_id} already present in video list")
        for index, video in enumerate(self.videos):
            if video.get("id", None) == video_id:
                if {"lang": lang_code, "text": title} not in video["title"]:
                    self.videos[index]["title"].append(
                        {"lang": lang_code, "text": title}
                    )
                    self.videos[index]["description"].append(
                        {"lang": lang_code, "text": description}
                    )
                    self.videos[index]["languages"].append(
                        {
                            "languageCode": lang_code,
                            "languageName": self.get_display_name(lang_code, lang_name),
                        }
                    )
                if self.subtitles_setting == MATCHING:
                    self.videos[index]["subtitles"] += subtitles
        return False

    def add_default_language(self):
        """ add metatada in default language (english or first avail) on all videos """

        for video in self.videos:
            en_found = False
            for index, lang in enumerate(video["languages"]):
                if lang["languageCode"] == "en":
                    en_found = True
                    video["title"] = [
                        {"lang": "default", "text": video["title"][index]["text"]}
                    ] + video["title"]
                    video["description"] = [
                        {"lang": "default", "text": video["description"][index]["text"]}
                    ] + video["description"]
                    break
            if not en_found:
                video["title"] = [
                    {"lang": "default", "text": video["title"][0]["text"]}
                ] + video["title"]
                video["description"] = [
                    {"lang": "default", "text": video["description"][0]["text"]}
                ] + video["description"]

    def render_video_pages(self):

        # Render static html pages from the scraped video data and
        # save the pages in build_dir/<video-id>/index.html
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        for video in self.videos:
            video_id = str(video["id"])

            html = env.get_template("article.html").render(
                speaker=video["speaker"],
                languages=video["subtitles"],
                speaker_bio=video["speaker_bio"].replace("Full bio", ""),
                speaker_img=video["speaker_picture"],
                date=video["date"],
                profession=video["speaker_profession"],
                video_format=self.video_format,
                autoplay=self.autoplay,
                video_id=video_id,
                titles=video["title"],
                descriptions=video["description"],
            )
            html_path = self.build_dir.joinpath(f"{video_id}.html")
            with open(html_path, "w", encoding="utf-8") as html_page:
                html_page.write(html)

    def render_home_page(self):

        # Render the homepage
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        languages = []
        for video in self.videos:
            for language in video["subtitles"]:
                languages.append(
                    {
                        "languageCode": language["languageCode"],
                        "languageName": language["languageName"],
                    }
                )
            languages += video["languages"]
        languages = [
            dict(tpl) for tpl in set(tuple(item.items()) for item in languages)
        ]
        languages = sorted(languages, key=lambda x: x["languageName"])
        html = env.get_template("home.html").render(languages=languages)
        home_page_path = self.build_dir.joinpath("index.html")
        with open(home_page_path, "w", encoding="utf-8") as html_page:
            html_page.write(html)

    def copy_files_to_build_directory(self):

        # Copy files from template_dir to build_dir
        assets_dir = self.templates_dir.joinpath("assets")
        if assets_dir.exists():
            shutil.copytree(
                assets_dir, self.build_dir.joinpath("assets"), dirs_exist_ok=True
            )
        shutil.copy(
            self.templates_dir.joinpath("favicon.png"),
            self.build_dir.joinpath("favicon.png"),
        )

    def generate_datafile(self):
        """ Generate data.js inside assets folder """

        video_list = []
        for video in self.videos:
            lang_codes = [lang["languageCode"] for lang in video["subtitles"]] + [
                lang["languageCode"] for lang in video["languages"]
            ]
            json_data = {
                "languages": [lang_code for lang_code in set(lang_codes)],
                "id": video["id"],
                "description": video["description"],
                "title": video["title"],
                "speaker": video["speaker"],
            }
            video_list.append(json_data)
        assets_path = self.build_dir.joinpath("assets")
        if not assets_path.exists():
            assets_path.mkdir(parents=True)

        with open(assets_path.joinpath("data.js"), "w") as data_file:
            data_file.write("json_data = " + json.dumps(video_list, indent=4))

    def download_video_files(self):
        """ download all video files (video, thumbnail, speaker) """

        # Download all the TED talk videos and the meta-data for it.
        # Save the videos in build_dir/{video id}/video.mp4.
        # Save the thumbnail for the video in build_dir/{video id}/thumbnail.jpg.
        # Save the image of the speaker in build_dir/{video id}/speaker.jpg.
        for video in self.videos:
            # set up variables
            video_id = str(video["id"])
            # Take the english version of title or else whatever language it's available in
            video_title = video["title"][0]["text"]
            video_link = video["video_link"]
            video_speaker = video["speaker_picture"]
            video_thumbnail = video["thumbnail"]
            video_dir = self.videos_dir.joinpath(video_id)
            org_video_file_path = video_dir.joinpath("video.mp4")
            req_video_file_path = video_dir.joinpath(f"video.{self.video_format}")
            speaker_path = video_dir.joinpath("speaker.jpg")
            thumbnail_path = video_dir.joinpath("thumbnail.jpg")

            # ensure that video directory exists
            if not video_dir.exists():
                video_dir.mkdir(parents=True)

            # set preset
            preset = {"mp4": VideoMp4Low}.get(self.video_format, VideoWebmLow)()

            # download video
            downloaded_from_cache = False
            logger.debug(f"Downloading {video_title}")
            if self.s3_storage:
                s3_key = f"{self.video_format}/{self.video_quality}/{video_id}"
                downloaded_from_cache = self.download_from_cache(
                    s3_key, req_video_file_path, preset.VERSION
                )
            if not downloaded_from_cache:
                try:
                    save_large_file(video_link, org_video_file_path)
                except Exception:
                    logger.error(f"Could not download {org_video_file_path}")

            # download an image of the speaker
            if video_speaker == "None" or video_speaker == "":
                logger.debug("Speaker doesn't have an image")
            else:
                logger.debug(f"Downloading Speaker image for {video_title}")
                save_large_file(video_speaker, speaker_path)

            # download the thumbnail of the video
            logger.debug(f"Downloading thumbnail for {video_title}")
            save_large_file(video_thumbnail, thumbnail_path)

            # recompress if necessary
            try:
                post_process_video(
                    video_dir,
                    video_id,
                    preset,
                    self.video_format,
                    self.low_quality,
                    downloaded_from_cache,
                )
            except Exception as e:
                logger.error(f"Failed to post process video {video_id}")
                logger.debug(e)
            else:
                # upload to cache only if recompress was successful
                if self.s3_storage and not downloaded_from_cache:
                    self.upload_to_cache(s3_key, req_video_file_path, preset.VERSION)

    def download_subtitles(self):
        """ download, converts and writes VTT subtitles for all videos """
        # Download the subtitle files, generate a WebVTT file
        # and save the subtitles in
        # build_dir/{video id}/subs/subs_{language code}.vtt
        for index, video in enumerate(self.videos):
            if not video["subtitles"]:
                continue
            video_dir = self.videos_dir.joinpath(video["id"])
            subs_dir = video_dir.joinpath("subs")
            if not subs_dir.exists():
                subs_dir.mkdir(parents=True)
            else:
                logger.debug(f"Subs dir exists already")

            # download subtitles
            logger.debug(f"Downloading subtitles for {video['title'][0]['text']}")
            valid_subs = []
            for subtitle in video["subtitles"]:
                time.sleep(0.5)  # throttling
                vtt_subtitle = WebVTT(subtitle["link"]).convert()
                if not vtt_subtitle:
                    logger.error(
                        f"Subtitle file for {subtitle['languageCode']} could not be created"
                    )
                    continue
                valid_subs.append(subtitle)
                vtt_path = subs_dir.joinpath(f"subs_{subtitle['languageCode']}.vtt")
                with open(vtt_path, "w", encoding="utf-8") as sub_file:
                    sub_file.write(vtt_subtitle)
            self.videos[index]["subtitles"] = valid_subs

    def s3_credentials_ok(self):
        logger.info("Testing S3 Optimization Cache credentials")
        self.s3_storage = KiwixStorage(self.s3_url_with_credentials)
        if not self.s3_storage.check_credentials(
            list_buckets=True, bucket=True, write=True, read=True, failsafe=True
        ):
            logger.error("S3 cache connection error testing permissions.")
            logger.error(f"  Server: {self.s3_storage.url.netloc}")
            logger.error(f"  Bucket: {self.s3_storage.bucket_name}")
            logger.error(f"  Key ID: {self.s3_storage.params.get('keyid')}")
            logger.error(f"  Public IP: {get_public_ip()}")
            return False
        return True

    def download_from_cache(self, key, video_path, encoder_version):
        """ whether it downloaded from S3 cache """

        if self.use_any_optimized_version:
            if not self.s3_storage.has_object(key, self.s3_storage.bucket_name):
                return False
        else:
            if not self.s3_storage.has_object_matching_meta(
                key, tag="encoder_version", value=f"v{encoder_version}"
            ):
                return False
        video_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.s3_storage.download_file(key, video_path)
        except Exception as exc:
            logger.error(f"{key} failed to download from cache: {exc}")
            return False
        logger.info(f"downloaded {video_path} from cache at {key}")
        return True

    def upload_to_cache(self, key, video_path, encoder_version):
        """ whether it uploaded from S3 cache """

        try:
            self.s3_storage.upload_file(
                video_path, key, meta={"encoder_version": f"v{encoder_version}"}
            )
        except Exception as exc:
            logger.error(f"{key} failed to upload to cache: {exc}")
            return False
        logger.info(f"uploaded {video_path} to cache at {key}")
        return True

    def run(self):
        logger.info(
            f"Starting scraper with:\n"
            f"  langs: {', '.join(self.source_languages)}\n"
            f"  subtitles : {', '.join(self.subtitles_setting) if isinstance(self.subtitles_setting, list) else self.subtitles_setting}\n"
            f"  video format : {self.video_format}"
        )

        if self.s3_url_with_credentials and not self.s3_credentials_ok():
            raise ValueError("Unable to connect to Optimization Cache. Check its URL.")
        if self.s3_storage:
            logger.info(
                f"Using cache: {self.s3_storage.url.netloc} with bucket: {self.s3_storage.bucket_name}"
            )

        if self.playlist:
            self.extract_videos_from_playlist()
        else:
            self.extract_videos_from_topics()

        self.add_default_language()
        self.update_zim_metadata()

        # clean the build directory if it already exists
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)

        self.download_video_files()
        self.download_subtitles()
        self.render_home_page()
        self.render_video_pages()
        self.copy_files_to_build_directory()
        self.generate_datafile()

        # create ZIM file
        if not self.no_zim:
            period = datetime.datetime.now().strftime("%Y-%m")
            self.fname = pathlib.Path(
                self.fname if self.fname else f"{self.name}_{period}.zim"
            )
            logger.info("building ZIM file")
            self.zim_info.update(
                title=self.title, description=self.description, language=self.zim_lang
            )
            logger.debug(self.zim_info.to_zimwriterfs_args())
            make_zim_file(self.build_dir, self.output_dir, self.fname, self.zim_info)
            if not self.keep_build_dir:
                logger.info("removing build directory")
                shutil.rmtree(self.build_dir, ignore_errors=True)
        logger.info("Done Everything")
