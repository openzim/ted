#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import dateutil.parser
import json
import pathlib
import jinja2
import shutil
import datetime

from bs4 import BeautifulSoup
from urllib.parse import urljoin
from time import sleep
from zimscraperlib.zim import ZimInfo, make_zim_file
from zimscraperlib.download import save_large_file
from kiwixstorage import KiwixStorage
from pif import get_public_ip

from .utils import download_from_site, build_subtitle_pages
from .constants import (
    ROOT_DIR,
    SCRAPER,
    ENCODER_VERSION,
    BASE_URL,
    NONE,
    MATCHING,
    ALL,
    logger,
)
from .converter import post_process_video
from .WebVTTcreator import WebVTTcreator


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
        language,
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
        source_language,
        subtitles_enough,
        subtitles_setting,
    ):

        # video-encoding info
        self.video_format = video_format
        self.low_quality = low_quality

        # zim params
        self.fname = fname
        self.language = language
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
        self.source_language = source_language
        self.subtitles_enough = subtitles_enough
        self.subtitles_setting = (
            subtitles_setting
            if subtitles_setting == ALL
            or subtitles_setting == MATCHING
            or subtitles_setting == NONE
            else [lang.strip() for lang in subtitles_setting.split(",")]
        )

        # zim info
        self.zim_info = ZimInfo(
            homepage="index.html",
            language=self.language,
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

    @property
    def root_dir(self):
        return ROOT_DIR

    @property
    def templates_dir(self):
        return self.root_dir.joinpath("templates")

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

    def extract_videos_from_playlist(self):

        # extracts metadata for all videos in the given playlist
        # it calls extract_video_info on all links to get this data
        playlist_url = f"{self.playlists_base_url}/{self.playlist}"
        soup = BeautifulSoup(
            download_from_site(playlist_url).text, features="html.parser"
        )
        video_elements = soup.find_all("a", attrs={"class": "hover/appear"})
        self.playlist_title = soup.find("h1", attrs={"class": "f:4"}).string
        self.playlist_description = soup.find("p", attrs={"class": "m-b:2"}).string
        for element in video_elements:
            relative_path = element.get("href")
            url = urljoin(self.talks_base_url, relative_path)
            self.extract_video_info(url)
            logger.debug(f"Done {relative_path}")
        logger.debug(f"Total videos found on playlist: {len(video_elements)}")
        if not video_elements:
            raise ValueError("Wrong playlist ID supplied. No videos found")

    def extract_videos_from_topics(self):

        # extracts metadata for required number of videos on different topics
        # it iterates over the topics and then over pages to get required number of videos
        for topic in self.topics:
            logger.debug(f"Fetching video links for topic: {topic}")
            topic_url = f"{self.talks_base_url}?topics%5B%5D={topic}"
            if self.source_language:
                topic_url = topic_url + f"&language={self.source_language}"
            soup = BeautifulSoup(
                download_from_site(topic_url).text, features="html.parser"
            )
            page = 1
            tot_videos_scraped = 0
            video_allowance = self.max_videos_per_topic
            while video_allowance:
                url = f"{topic_url}&page={page}"
                html = download_from_site(url).text
                num_videos_extracted = self.extract_videos_on_page(
                    html, video_allowance,
                )
                if num_videos_extracted == 0:
                    break
                video_allowance -= num_videos_extracted
                tot_videos_scraped += num_videos_extracted
                page += 1
            logger.info(f"Total video links found in {topic}: {tot_videos_scraped}")
            if tot_videos_scraped == 0:
                self.topics.remove(topic)
                logger.debug(
                    f"Removed topic {topic} from topic list as it had no videos"
                )
        if not self.topics:
            if self.source_language:
                raise ValueError(
                    "No videos found for any topic in the language requested. Check topic(s) and/or language code supplied to --only-videos-in"
                )
            raise ValueError("Wrong topic(s) were supplied. No videos found")

    def update_title_and_description(self):
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

    def extract_videos_on_page(self, page_html, video_allowance):

        # all videos are embedded in a <div> with the class name 'row'.
        # we are searching for the div inside this div, that has an <a>-tag
        # with the class name 'media__image', because this is the relative
        # link to the representative TED talk. It turns this relative link to
        # an absolute link and calls extract_video_info for them
        soup = BeautifulSoup(page_html, features="html.parser")
        videos = soup.select("div.row div.media__image a")
        if len(videos) > video_allowance:
            videos = videos[0:video_allowance]
        logger.debug(f"{str(len(videos))} video(s) found on current page")
        for video in videos:
            url = urljoin(self.talks_base_url, video["href"])
            self.extract_video_info(url)
            logger.debug(f"Done {video['href']}")
        return len(videos)

    def extract_video_info(self, url):

        # Extract the meta-data of the video:
        # Speaker, the profession of the speaker, a short biography of
        # the speaker, the link to a picture of the speaker, title,
        # publishing date, view count, description of the TED talk,
        # direct download link to the video, download link to the subtitle
        # files and a link to a thumbnail of the video.
        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        soup = BeautifulSoup(download_from_site(url).text, features="html.parser")
        div = soup.find("div", attrs={"class": "talks-main"})
        script_tags_within_div = div.find_all("script")
        if len(script_tags_within_div) == 0:
            logger.error("The required script tag containing video meta is not present")
            return
        json_data_tag = script_tags_within_div[-1]
        json_data = json_data_tag.string
        json_data = " ".join(json_data.split(",", 1)[1].split(")")[:-1])
        json_data = json.loads(json_data)["__INITIAL_DATA__"]
        lang_code = json_data["language"]
        talk_info = json_data["talks"][0]
        native_talk_language = talk_info["player_talks"][0]["nativeLanguage"]
        if (
            not self.subtitles_enough
            and self.source_language
            and native_talk_language not in self.source_language
        ):
            return

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
            if talk_info.has_key("speaker_name"):
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
        date = dateutil.parser.parse(talk_info["recorded_at"]).strftime("%d.%B %Y")

        # Extract the length of the TED talk in minutes
        length = int(talk_info["duration"])
        length = divmod(length, 60)[0]

        # Extract the thumbnail of the of the TED talk video
        thumbnail = talk_info["player_talks"][0]["thumb"]

        # Extract the download link of the TED talk video
        downloads = talk_info["downloads"]["nativeDownloads"]
        if not downloads:
            logger.error("No direct download links found for the video")
            return
        video_link = downloads["medium"]
        if not video_link:
            logger.error("No link to download video in medium quality")
            return

        # Extract the video Id of the TED talk video.
        # We need this to generate the subtitle page.
        video_id = talk_info["id"]

        # Generate a list of all subtitle languages with the link to
        # its subtitles page. It will be in this format:
        # [
        #     {
        #         'languageCode': u'en',
        #         'link': 'https://www.ted.com/talks/subtitles/id/1907/lang/en',
        #         'languageName': u'English'
        #     }
        # ]
        subtitles = []
        if self.subtitles_setting == ALL:
            subtitles = [
                {
                    "languageName": lang["languageName"],
                    "languageCode": lang["languageCode"],
                }
                for lang in talk_info["player_talks"][0]["languages"]
            ]
        elif self.subtitles_setting == MATCHING:
            subtitles = [
                {
                    "languageName": lang["languageName"],
                    "languageCode": lang["languageCode"],
                }
                for lang in talk_info["player_talks"][0]["languages"]
                and lang["languageCode"] in self.source_language
            ]
        else:
            subtitles = [
                {
                    "languageName": lang["languageName"],
                    "languageCode": lang["languageCode"],
                }
                for lang in talk_info["player_talks"][0]["languages"]
                and lang["languageCode"] in self.subtitles_setting
            ]
        subtitles = build_subtitle_pages(video_id, subtitles)

        # Extract the keywords for the TED talk
        keywords = soup.find("meta", attrs={"name": "keywords"})["content"]
        keywords = [key.strip() for key in keywords.split(",")]

        # Check if video ID already exists. If not, append data to self.videos
        if not any(video.get("id", None) == video_id for video in self.videos):
            self.videos.append(
                {
                    "id": video_id,
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
                }
            )
            logger.debug(f"Successfully inserted video {video_id} into video list")
        else:
            logger.debug(f"Video {video_id} already present in video list")
            for i, video in enumerate(self.videos):
                if video.get("id", None) == video_id:
                    if {"lang": lang_code, "text": title} not in video["title"]:
                        self.videos[i]["title"].append(
                            {"lang": lang_code, "text": title}
                        )
                        self.videos[i]["description"].append(
                            {"lang": lang_code, "text": description}
                        )
                    if self.subtitles_setting == MATCHING:
                        self.videos[i]["subtitles"] += subtitles

    def render_video_pages(self):

        # Render static html pages from the scraped video data and
        # save the pages in build_dir/<video-id>/index.html
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        for video in self.videos:
            video_id = str(video["id"])

            html = env.get_template("article.html").render(
                title=video["title"],
                speaker=video["speaker"],
                description=video["description"],
                languages=video["subtitles"],
                speaker_bio=video["speaker_bio"].replace("Full bio", ""),
                speaker_img=video["speaker_picture"],
                date=video["date"],
                profession=video["speaker_profession"],
                video_format=self.video_format,
                autoplay=self.autoplay,
                video_id=video_id,
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
        copy_assets_dir = self.build_dir.joinpath("assets")
        if assets_dir.exists():
            shutil.copytree(assets_dir, copy_assets_dir, dirs_exist_ok=True)
        favicon_file = self.templates_dir.joinpath("favicon.png")
        copy_favicon_file = self.build_dir.joinpath("favicon.png")
        shutil.copy(favicon_file, copy_favicon_file)

    def generate_datafile(self):

        # Generate data.js inside the assets folder
        video_list = []
        for video in self.videos:
            json_data = {
                "languages": [lang["languageCode"] for lang in video["subtitles"]],
                "id": video["id"],
                "description": video["description"],
                "title": video["title"],
                "speaker": video["speaker"],
            }
            video_list.append(json_data)
        assets_path = self.build_dir.joinpath("assets")
        data_path = assets_path.joinpath("data.js")
        if not assets_path.exists():
            assets_path.mkdir(parents=True)
        with open(data_path, "w") as data_file:
            json_data = json.dumps(video_list, indent=4)
            json_data = "json_data = " + json_data
            data_file.write(json_data)

    def download_video_data(self):

        # Download all the TED talk videos and the meta-data for it.
        # Save the videos in build_dir/{video id}/video.mp4.
        # Save the thumbnail for the video in build_dir/{video id}/thumbnail.jpg.
        # Save the image of the speaker in build_dir/{video id}/speaker.jpg.
        for video in self.videos:
            # set up variables
            video_id = str(video["id"])
            video_title = video["title"]
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

            # download video
            downloaded_from_cache = False
            logger.debug(f"Downloading {video_title}")
            if self.s3_storage:
                s3_key = f"{self.video_format}/{self.video_quality}/{video_id}"
                downloaded_from_cache = self.download_from_cache(
                    s3_key, req_video_file_path
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
                    self.video_format,
                    self.low_quality,
                    skip_recompress=downloaded_from_cache,
                )
            except Exception as e:
                logger.error(f"Failed to post process video {video_id}")
                logger.debug(e)
            else:
                # upload to cache only if recompress was successful
                if self.s3_storage and not downloaded_from_cache:
                    self.upload_to_cache(s3_key, req_video_file_path)

    def download_subtitles(self):
        # Download the subtitle files, generate a WebVTT file
        # and save the subtitles in
        # build_dir/{video id}/subs/subs_{language code}.vtt
        for i, video in enumerate(self.videos):
            video_id = str(video["id"])
            video_title = video["title"]
            video_subtitles = video["subtitles"]
            video_dir = self.videos_dir.joinpath(video_id)
            subs_dir = video_dir.joinpath("subs")
            if not subs_dir.exists():
                subs_dir.mkdir(parents=True)
            else:
                logger.debug(f"Subs dir exists already")
                continue

            # download subtitles
            logger.debug(f"Downloading subtitles for {video_title}")
            for subtitle in video_subtitles:
                sleep(0.5)
                subtitle_file = WebVTTcreator(subtitle["link"], 11820).get_content()
                if not subtitle_file:
                    self.videos[i]["subtitles"].remove(subtitle)
                    logger.error(
                        f"Subtitle file for {subtitle['languageCode']} could not be created"
                    )
                    continue
                subtitle_file_name = subs_dir.joinpath(
                    f"subs_{subtitle['languageCode']}.vtt"
                )
                with open(subtitle_file_name, "w", encoding="utf-8") as sub_file:
                    sub_file.write(subtitle_file)

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

    def download_from_cache(self, key, video_path):

        # Checks if file is in cache and returns true if
        # successfully downloaded from cache
        if self.use_any_optimized_version:
            if not self.s3_storage.has_object(key, self.s3_storage.bucket_name):
                return False
        else:
            if not self.s3_storage.has_object_matching_meta(
                key, tag="encoder_version", value=ENCODER_VERSION
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

    def upload_to_cache(self, key, video_path):

        # returns true if successfully uploaded to cache
        try:
            self.s3_storage.upload_file(
                video_path, key, meta={"encoder_version": ENCODER_VERSION}
            )
        except Exception as exc:
            logger.error(f"{key} failed to upload to cache: {exc}")
            return False
        logger.info(f"uploaded {video_path} to cache at {key}")
        return True

    def run(self):
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

        self.update_title_and_description()

        # clean the build directory if it already exists
        if self.build_dir.exists():
            shutil.rmtree(self.build_dir)
        self.build_dir.mkdir(parents=True)

        self.download_video_data()
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
            self.zim_info.update(title=self.title, description=self.description)
            logger.debug(self.zim_info.to_zimwriterfs_args())
            make_zim_file(self.build_dir, self.output_dir, self.fname, self.zim_info)
            if not self.keep_build_dir:
                logger.info("removing build directory")
                shutil.rmtree(self.build_dir, ignore_errors=True)
        logger.info("Done Everything")
