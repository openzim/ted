#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import concurrent.futures
import datetime
import json
import locale
import pathlib
import shutil
import tempfile
import time
import urllib.parse

import dateutil.parser
import jinja2
from bs4 import BeautifulSoup
from slugify import slugify
from kiwixstorage import KiwixStorage
from pif import get_public_ip
from zimscraperlib.download import BestMp4, BestWebm, YoutubeDownloader, save_large_file
from zimscraperlib.i18n import get_language_details, setlocale, _
from zimscraperlib.image.optimization import optimize_image
from zimscraperlib.image.presets import WebpMedium
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.video.presets import VideoMp4Low, VideoWebmLow
from zimscraperlib.zim import make_zim_file

from .constants import (
    ALL,
    BASE_URL,
    MATCHING,
    NONE,
    ROOT_DIR,
    SCRAPER,
    TEDLANGS,
    getLogger,
)
from .processing import post_process_video
from .utils import WebVTT, download_link, update_subtitles_list, get_main_title

logger = getLogger()


class Ted2Zim:
    def __init__(
        self,
        topics,
        debug,
        name,
        video_format,
        low_quality,
        output_dir,
        no_zim,
        fname,
        languages,
        locale_name,
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
        tmp_dir,
        threads,
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

        # directory setup
        self.output_dir = pathlib.Path(output_dir).expanduser().resolve()
        if tmp_dir:
            pathlib.Path(tmp_dir).mkdir(parents=True, exist_ok=True)
        self.build_dir = pathlib.Path(tempfile.mkdtemp(dir=tmp_dir))

        # scraper options
        self.topics = (
            []
            if not topics
            else [c.strip().replace(" ", "+") for c in topics.split(",")]
        )
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
        self.threads = threads
        self.yt_downloader = None

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
        self.already_visited = []

        # set and record locale for translations
        locale_details = get_language_details(locale_name)
        if locale_details["querytype"] != "locale":
            locale_name = locale_details["iso-639-1"]
        try:
            self.locale = setlocale(ROOT_DIR, locale_name)
        except locale.Error:
            logger.error(
                f"No locale for {locale_name}. Use --locale to specify it. "
                "defaulting to en_US"
            )
            self.locale = setlocale(ROOT_DIR, "en")
        # locale's language code
        self.locale_name = self.to_ted_langcodes(locale_name)

    @property
    def templates_dir(self):
        return ROOT_DIR.joinpath("templates")

    @property
    def videos_dir(self):
        return self.build_dir.joinpath("videos")

    @property
    def ted_videos_json(self):
        return self.build_dir.joinpath("ted_videos.json")

    @property
    def ted_topics_json(self):
        return self.build_dir.joinpath("ted_topics.json")

    @property
    def talks_base_url(self):
        return BASE_URL + "talks"

    @property
    def playlists_base_url(self):
        return BASE_URL + "playlists"

    def append_part1_or_part3(self, lang_code_list, lang_info):
        """Fills missing ISO languages codes for all in list

        lang_code_list: list og lang codes
        lang_info: see zimscraperlib.i18n"""

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
        """Converts languages queries into TED language codes

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

    def extract_videos_from_playlist(self, playlist):
        """extracts metadata for all videos in the given playlist

        calls extract_video_info on all links to get this data
        """

        playlist_url = f"{self.playlists_base_url}/{playlist}"
        logger.debug(f"extract_videos_from_playlist: {playlist_url}")
        soup = BeautifulSoup(download_link(playlist_url).text, features="html.parser")
        video_elements = soup.find_all("a", attrs={"class": "group"})
        self.playlist_title = soup.find("h1").string
        self.playlist_description = soup.find("p", attrs={"class": "text-base"}).string

        for element in video_elements:
            relative_path = element.get("href")
            url = urllib.parse.urljoin(self.talks_base_url, relative_path)
            if self.extract_info_from_video_page(url):
                if self.source_languages and len(self.source_languages) > 1:
                    other_lang_urls = self.generate_urls_for_other_languages(url)
                    logger.debug(
                        f"Searching info for the video in other {len(other_lang_urls)} language(s)"
                    )
                    for lang_url in other_lang_urls:
                        self.extract_info_from_video_page(lang_url)
                    self.already_visited.append(urllib.parse.urlparse(url)[2])
            logger.debug(f"Seen {relative_path}")
        logger.debug(f"Total videos found on playlist: {len(video_elements)}")
        if not video_elements:
            raise ValueError("Wrong playlist ID supplied. No videos found")

    def generate_search_result_and_scrape(self, topic_url, total_videos_scraped):
        """generates a search result and returns the total number of videos scraped"""

        page = 1
        while True:
            logger.debug(f"generate_search_result_and_scrape: {topic_url}&page={page}")
            html = download_link(f"{topic_url}&page={page}").text
            nb_videos_extracted, nb_videos_on_page = self.extract_videos_on_topic_page(
                html
            )
            if nb_videos_on_page == 0:
                break
            total_videos_scraped += nb_videos_extracted
            page += 1
        return total_videos_scraped

    def extract_videos_from_topics(self, topic):
        """extracts metadata for required number of videos on different topics"""

        logger.debug(f"Fetching video links for topic: {topic}")
        topic_url = f"{self.talks_base_url}?topics%5B%5D={topic}"
        total_videos_scraped = 0

        if self.source_languages:
            for lang in self.source_languages:
                topic_url = topic_url + f"&language={lang}"
                total_videos_scraped = self.generate_search_result_and_scrape(
                    topic_url, total_videos_scraped
                )

        else:
            total_videos_scraped = self.generate_search_result_and_scrape(
                topic_url, total_videos_scraped
            )

        logger.info(f"Total video links found in {topic}: {total_videos_scraped}")
        if total_videos_scraped == 0:
            return False
        return True

    def update_zim_metadata(self):

        if not self.languages:
            self.zim_lang = "eng"
        else:
            if len(self.source_languages) > 1:
                self.zim_lang = "mul"
            else:
                lang_info = get_language_details(
                    self.source_languages[0], failsafe=True
                )
                if lang_info:
                    self.zim_lang = lang_info["iso-639-3"]
                else:
                    self.zim_lang = "eng"

        if self.playlist:
            if not self.title:
                self.title = self.playlist_title.strip()
            if not self.description:
                self.description = self.playlist_description.strip()
        else:
            if len(self.topics) > 1:
                if not self.title:
                    self.title = "TED Collection"
                if not self.description:
                    self.description = "A selection of TED videos from several topics"
            else:
                topic_str = self.topics[0].replace("+", " ")
                if not self.title:
                    self.title = f"{topic_str.capitalize()} from TED"
                if not self.description:
                    self.description = f"A selection of {topic_str} videos from TED"

    def get_display_name(self, lang_code, lang_name):
        """Display name for language"""

        lang_info = get_language_details(lang_code, failsafe=True)
        if lang_code != "en" and lang_info:

            return lang_info["native"] + " - " + lang_name
        return lang_name

    def get_subtitle_dict(self, lang):
        """dict of language name and code from a larger dict lang

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

    def generate_subtitle_list(self, video_id, langs, page_lang, audio_lang):
        """List of all subtitle languages with link to their pages"""

        subtitles = []
        if self.subtitles_setting == ALL or (
            not self.source_languages and self.topics and self.subtitles_setting != NONE
        ):
            subtitles = [self.get_subtitle_dict(lang) for lang in langs]
        elif self.subtitles_setting == MATCHING or (
            self.subtitles_enough
            and self.subtitles_setting == NONE
            and page_lang != audio_lang
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
        """Possible URLs for other requested languages based on a video url"""

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

    def extract_videos_on_topic_page(self, page_html):

        # all videos are embedded in a <div> with the class name 'row'.
        # we are searching for the div inside this div, that has an <a>-tag
        # with the class name 'media__image', because this is the relative
        # link to the representative TED talk. It turns this relative link to
        # an absolute link and calls extract_video_info for them
        soup = BeautifulSoup(page_html, features="html.parser")
        video_links = soup.select("div.row div.media__image a")
        nb_extracted = 0
        nb_listed = len(video_links)
        logger.debug(f"{nb_listed} video(s) found on current page")
        for video_link in video_links:
            url = urllib.parse.urljoin(self.talks_base_url, video_link["href"])
            if self.extract_info_from_video_page(url):
                nb_extracted += 1
                if self.source_languages and len(self.source_languages) > 1:
                    other_lang_urls = self.generate_urls_for_other_languages(url)
                    logger.debug(
                        f"Searching info for video in other {len(other_lang_urls)} language(s)"
                    )
                    for lang_url in other_lang_urls:
                        self.extract_info_from_video_page(lang_url)
                    self.already_visited.append(urllib.parse.urlparse(url)[2])
            logger.debug(f"Seen {video_link['href']}")
        return nb_extracted, nb_listed

    def get_lang_code_from_url(self, url, with_full_query=False):
        """gets the queried language code from a ted talk url"""

        # sample - https://www.ted.com/talks/alex_rosenthal_the_gauntlet_think_like_a_coder_ep_8?language=ja
        url_parts = list(urllib.parse.urlparse(url))

        # explode url to extract `language` query field value
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        current_lang = query.get("language")
        if with_full_query:
            return current_lang, query
        return current_lang

    def extract_download_link(self, talk_info):
        """Returns download link / youtube video ID for a TED video"""

        download_links = talk_info["downloads"]["nativeDownloads"]
        if download_links:
            for size in ("medium", "low", "high"):
                if size in download_links:
                    return download_links[size]
            logger.error("No link to download video while we should have")
            return None

        talk_data = talk_info["player_talks"][0]
        if talk_data.get("external", {}).get("service") == "YouTube" and talk_data[
            "external"
        ].get("code"):
            logger.debug("Using Youtube link")
            return talk_data["external"]["code"]

        if (
            isinstance(talk_data.get("resources", {}).get("h264"), list)
            and len(talk_data["resources"]["h264"]) > 0
            and talk_data["resources"]["h264"][0].get("file")
        ):
            logger.debug("Using h264 resource link")
            return talk_data["resources"]["h264"][0]["file"]

        logger.error("No download link found for the video")
        return None

    def update_videos_list(
        self,
        video_id,
        lang_code,
        lang_name,
        title,
        description,
        speaker,
        speaker_profession,
        speaker_bio,
        speaker_picture,
        date,
        thumbnail,
        video_link,
        length,
        subtitles,
    ):
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
                if self.subtitles_setting == MATCHING or self.subtitles_setting == NONE:
                    self.videos[index]["subtitles"] += subtitles
        return False

    def extract_video_info_from_json(self, json_data):
        lang_code = json_data["language"]
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
                "photo_url": "",
            }
            if "speaker_name" in talk_info:
                speaker = talk_info["speaker_name"]
            else:
                speaker = "None"

        # Extract the ted talk details from json
        video_id = talk_info["id"]
        speaker_profession = speaker_info["description"]
        speaker_bio = speaker_info["whotheyare"]
        speaker_picture = speaker_info["photo_url"]
        title = talk_info["title"]
        description = talk_info["description"]
        date = dateutil.parser.parse(talk_info["recorded_at"]).strftime("%d %B %Y")
        length = int(talk_info["duration"]) // 60
        thumbnail = talk_info["player_talks"][0]["thumb"]
        video_link = self.extract_download_link(talk_info)
        if not video_link:
            logger.error("No suitable download link found. Skipping video")
            return False

        langs = talk_info["player_talks"][0]["languages"]
        subtitles = self.generate_subtitle_list(
            video_id, langs, lang_code, native_talk_language
        )
        return self.update_videos_list(
            video_id=video_id,
            lang_code=lang_code,
            lang_name=lang_name,
            title=title,
            description=description,
            speaker=speaker,
            speaker_profession=speaker_profession,
            speaker_bio=speaker_bio,
            speaker_picture=speaker_picture,
            date=date,
            thumbnail=thumbnail,
            video_link=video_link,
            length=length,
            subtitles=subtitles,
        )

    def extract_info_from_video_page(self, url, retry_count=0):
        """extract all info from a TED video page url and update self.videos"""

        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        # returns True if successfully scraped new video

        # don't scrape if URL already visited
        if urllib.parse.urlparse(url)[2] in self.already_visited:
            return False

        # don't scrape if maximum retry count is reached
        if retry_count > 5:
            logger.error("Max retries exceeded. Skipping video")
            return False

        logger.debug(f"extract_info_from_video_page: {url}")
        soup = BeautifulSoup(download_link(url).text, features="html.parser")
        div = soup.find("div", attrs={"class": "talks-main"})

        # TED is sometimes inconsistant in sending HTML content
        # it sometimes sends the HTML without the required div containing the talks data
        # so we retry after 5 seconds
        if not div:
            logger.debug(
                "Potentially insufficient data returned by server. Retrying in 5 seconds..."
            )
            time.sleep(5)
            return self.extract_info_from_video_page(url, retry_count=retry_count + 1)

        script_tags_within_div = div.find_all("script")
        if len(script_tags_within_div) == 0:
            logger.error("The required script tag containing video meta is not present")
            return False
        json_data = script_tags_within_div[-1].string
        json_data = json.loads(json_data[18:-1])["__INITIAL_DATA__"]
        requested_lang_code = self.get_lang_code_from_url(url)
        if requested_lang_code and json_data["language"] != requested_lang_code:
            logger.error(
                f"Video has not yet been translated into {requested_lang_code}"
            )
            return False
        return self.extract_video_info_from_json(json_data)

    def add_default_language(self):
        """add metatada in default language (english or first avail) on all videos"""

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

            if not en_found:
                video["title"] = [
                    {"lang": "default", "text": video["title"][0]["text"]}
                ] + video["title"]
                video["description"] = [
                    {"lang": "default", "text": video["description"][0]["text"]}
                ] + video["description"]

            # update video slug
            video["slug"] = slugify(video["title"][0]["text"], separator="-")

    def render_video_pages(self):

        # Render static html pages from the scraped video data and
        # save the pages in build_dir/<video-id>/index.html
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        for video in self.videos:
            titles = video["title"]
            html = env.get_template("article.html").render(
                speaker=video["speaker"],
                languages=video["subtitles"],
                speaker_bio=video["speaker_bio"].replace("Full bio", ""),
                speaker_img=video["speaker_picture"],
                date=video["date"],
                profession=video["speaker_profession"],
                video_format=self.video_format,
                autoplay=self.autoplay,
                video_id=str(video["id"]),
                title=get_main_title(titles, self.locale_name),
                titles=titles,
                descriptions=video["description"],
                back_to_list=_("Back to the list"),
            )
            html_path = self.build_dir.joinpath(video["slug"])
            with open(html_path, "w", encoding="utf-8") as html_page:
                html_page.write(html)

    def render_home_page(self):

        # Render the homepage
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        all_langs = {
            language["languageCode"]: language["languageName"]
            for video in self.videos
            for language in video["subtitles"] + video["languages"]
        }
        languages = [
            {"languageName": value, "languageCode": key}
            for key, value in all_langs.items()
        ]
        languages = sorted(languages, key=lambda x: x["languageName"])
        html = env.get_template("home.html").render(
            languages=languages,
            page_title=_("TED Talks"),
            language_filter_text=_("Filter by language"),
            back_to_top=_("Back to the top"),
            pagination_text=_("Page"),
        )
        home_page_path = self.build_dir.joinpath("index")
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
        """Generate data.js inside assets folder"""

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
                "slug": video["slug"],
            }
            video_list.append(json_data)
        assets_path = self.build_dir.joinpath("assets")
        if not assets_path.exists():
            assets_path.mkdir(parents=True)

        with open(assets_path.joinpath("data.js"), "w") as data_file:
            data_file.write("json_data = " + json.dumps(video_list, indent=4))

    def download_jpeg_image_and_convert(
        self, url, fpath, preset_options={}, resize=None
    ):
        """downloads a JPEG image and converts and optimizes it into desired format detected from fpath"""

        org_jpeg_path = pathlib.Path(
            tempfile.NamedTemporaryFile(delete=False, suffix=".jpg").name
        )
        save_large_file(url, org_jpeg_path)
        if resize is not None:
            resize_image(
                org_jpeg_path,
                width=resize[0],
                height=resize[1],
                method="cover",
            )
        optimize_image(
            org_jpeg_path, fpath, convert=True, delete_src=True, **preset_options
        )
        logger.debug(f"Converted {org_jpeg_path} to {fpath} and optimized ")

    def download_speaker_image(
        self, video_id, video_title, video_speaker, speaker_path
    ):
        """downloads the speaker image"""

        downloaded_from_cache = False
        preset = WebpMedium()
        if self.s3_storage:
            s3_key = f"speaker_image/{video_id}"
            downloaded_from_cache = self.download_from_cache(
                s3_key, speaker_path, preset.VERSION
            )
        if not downloaded_from_cache:
            try:
                # download an image of the speaker
                if not video_speaker:
                    logger.debug("Speaker doesn't have an image")
                else:
                    logger.debug(f"Downloading Speaker image for {video_title}")
                    self.download_jpeg_image_and_convert(
                        video_speaker, speaker_path, preset_options=preset.options
                    )
            except Exception:
                logger.error(f"Could not download speaker image for {video_title}")
            else:
                if self.s3_storage and video_speaker:
                    self.upload_to_cache(s3_key, speaker_path, preset.VERSION)

    def download_thumbnail(
        self, video_id, video_title, video_thumbnail, thumbnail_path
    ):
        """download the thumbnail"""

        downloaded_from_cache = False
        preset = WebpMedium()
        if self.s3_storage:
            s3_key = f"thumbnail/{video_id}"
            downloaded_from_cache = self.download_from_cache(
                s3_key, thumbnail_path, preset.VERSION
            )
        if not downloaded_from_cache:
            try:
                # download the thumbnail of the video
                logger.debug(f"Downloading thumbnail for {video_title}")
                self.download_jpeg_image_and_convert(
                    video_thumbnail,
                    thumbnail_path,
                    preset_options=preset.options,
                    resize=(248, 187),
                )
            except Exception:
                logger.error(f"Could not download thumbnail for {video_title}")
            else:
                if self.s3_storage:
                    self.upload_to_cache(s3_key, thumbnail_path, preset.VERSION)

    def download_video_files(self, video):
        """download all video files (video, thumbnail, speaker)"""

        # Download all the TED talk videos and the meta-data for it.
        # Save the videos in build_dir/{video id}/video.mp4.
        # Save the thumbnail for the video in build_dir/{video id}/thumbnail.jpg.
        # Save the image of the speaker in build_dir/{video id}/speaker.jpg.

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
        speaker_path = video_dir.joinpath("speaker.webp")
        thumbnail_path = video_dir.joinpath("thumbnail.webp")

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
                if "https://" not in video_link:
                    options = (
                        BestWebm if self.video_format == "webm" else BestMp4
                    ).get_options(
                        target_dir=video_dir, filepath=pathlib.Path("video.%(ext)s")
                    )
                    self.yt_downloader.download(video_link, options)
                else:
                    save_large_file(video_link, org_video_file_path)
            except Exception:
                logger.error(f"Could not download {org_video_file_path}")

        # download speaker and thumbnail images
        self.download_speaker_image(video_id, video_title, video_speaker, speaker_path)
        self.download_thumbnail(video_id, video_title, video_thumbnail, thumbnail_path)

        # recompress if necessary
        try:
            if not downloaded_from_cache:
                post_process_video(
                    video_dir,
                    video_id,
                    preset,
                    self.video_format,
                    self.low_quality,
                )
        except Exception as e:
            logger.error(f"Failed to post process video {video_id}")
            logger.debug(e)
        else:
            # upload to cache only if recompress was successful
            if self.s3_storage and not downloaded_from_cache:
                self.upload_to_cache(s3_key, req_video_file_path, preset.VERSION)

    def download_video_files_parallel(self):
        """download videos and images parallely"""

        self.yt_downloader = YoutubeDownloader(threads=1)
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.threads
        ) as executor:
            fs = [
                executor.submit(self.download_video_files, video)
                for video in self.videos
            ]
            concurrent.futures.wait(fs, return_when=concurrent.futures.ALL_COMPLETED)
        self.yt_downloader.shutdown()

    def download_subtitles(self, index, video):
        """download, converts and writes VTT subtitles for a video at a specific index in self.videos"""

        # Download the subtitle files, generate a WebVTT file
        # and save the subtitles in
        # build_dir/{video id}/subs/subs_{language code}.vtt
        if not video["subtitles"]:
            return
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

    def download_subtitles_parallel(self):
        """download subtitles for all videos parallely"""

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.threads
        ) as executor:
            fs = [
                executor.submit(self.download_subtitles, index, video)
                for index, video in enumerate(self.videos)
            ]
            concurrent.futures.wait(fs, return_when=concurrent.futures.ALL_COMPLETED)

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

    def download_from_cache(self, key, object_path, encoder_version):
        """whether it downloaded from S3 cache"""

        if self.use_any_optimized_version:
            if not self.s3_storage.has_object(key, self.s3_storage.bucket_name):
                return False
        else:
            if not self.s3_storage.has_object_matching_meta(
                key, tag="encoder_version", value=f"v{encoder_version}"
            ):
                return False
        object_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.s3_storage.download_file(key, object_path)
        except Exception as exc:
            logger.error(f"{key} failed to download from cache: {exc}")
            return False
        logger.info(f"downloaded {object_path} from cache at {key}")
        return True

    def upload_to_cache(self, key, object_path, encoder_version):
        """whether it uploaded from S3 cache"""

        try:
            self.s3_storage.upload_file(
                object_path, key, meta={"encoder_version": f"v{encoder_version}"}
            )
        except Exception as exc:
            logger.error(f"{key} failed to upload to cache: {exc}")
            return False
        logger.info(f"uploaded {object_path} to cache at {key}")
        return True

    def remove_failed_topics_and_check_extraction(self, failed_topics):
        """removes failed topics from topics list and raises error if scraper cannot continue"""

        for topic in failed_topics:
            self.topics.remove(topic)
        if not self.topics:
            if self.source_languages:
                raise ValueError(
                    "No videos found for any topic in the language(s) requested. Check topic(s) and/or language code supplied to --languages"
                )
            raise ValueError("Wrong topic(s) were supplied. No videos found")

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

        # playlist mode requested
        if self.playlist:
            self.extract_videos_from_playlist(self.playlist)
        # topic(s) mode requested
        else:
            failed = []
            for topic in self.topics:
                if not self.extract_videos_from_topics(topic):
                    failed.append(topic)
                else:
                    logger.debug(f"Successfully scraped {topic}")
            self.remove_failed_topics_and_check_extraction(failed)

        self.add_default_language()
        self.update_zim_metadata()
        self.download_video_files_parallel()
        self.download_subtitles_parallel()
        self.render_home_page()
        self.render_video_pages()
        self.copy_files_to_build_directory()
        self.generate_datafile()

        # zim creation and cleanup
        if not self.no_zim:
            self.fname = (
                self.fname or f"{self.name.replace(' ', '-')}_{{period}}.zim"
            ).format(period=datetime.datetime.now().strftime("%Y-%m"))
            logger.info("building ZIM file")
            if not self.output_dir.exists():
                self.output_dir.mkdir(parents=True)
            make_zim_file(
                build_dir=self.build_dir,
                fpath=self.output_dir.joinpath(self.fname),
                name=self.name,
                main_page="index",
                favicon="favicon.png",
                title=self.title,
                description=self.description,
                language=self.zim_lang,
                creator=self.creator,
                publisher=self.publisher,
                tags=self.tags + ["_category:ted", "ted", "_videos:yes"],
                scraper=SCRAPER,
            )
            if not self.keep_build_dir:
                logger.info("removing temp folder")
                shutil.rmtree(self.build_dir, ignore_errors=True)

        logger.info("Done Everything")
