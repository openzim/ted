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

from .utils import download_from_site, build_subtitle_pages
from .constants import ROOT_DIR, SCRAPER, logger
from .converter import post_process_video
from .WebVTTcreator import WebVTTcreator


class Ted2Zim:

    # The base Url. The link gives you a grid of all TED talks.
    BASE_URL = "https://ted.com/talks"
    # BeautifulSoup instance
    soup = None
    # Page count
    pages = None
    # List of links to all TED talks
    videos = []

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
        self.topics = [c.strip().replace(" ", "+") for c in topics.split(",")]
        self.max_videos_per_topic = max_videos_per_topic

        # zim info
        self.zim_info = ZimInfo(
            homepage="index.html",
            language=self.language,
            tags=self.tags + ["_category:ted", "ted", "_videos:yes"],
            title=self.title,
            description=self.description,
            creator=self.creator,
            publisher=self.publisher,
            name=self.name,
            scraper=SCRAPER,
            favicon="favicon.png",
        )

        # debug/developer options
        self.no_zim = no_zim
        self.keep_build_dir = keep_build_dir
        self.debug = debug

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
    def ted_videos_json(self):
        return self.output_dir.joinpath("ted_videos.json")

    @property
    def ted_topics_json(self):
        return self.output_dir.joinpath("ted_topics.json")

    def extract_all_video_links(self):

        # extracts all video links for different topics
        # it iterates over the topics and then over pages to get required number of video links
        for topic in self.topics:
            logger.debug(f"Fetching video links for topic: {topic}")
            topic_url = f"{self.BASE_URL}?topics%5B%5D={topic}"
            self.soup = BeautifulSoup(
                download_from_site(topic_url).text, features="html.parser"
            )
            page = 1
            tot_videos_scraped = 0
            video_allowance = self.max_videos_per_topic
            while video_allowance:
                url = f"{topic_url}&page={page}"
                html = download_from_site(url).text
                self.soup = BeautifulSoup(html, features="html.parser")
                num_videos_extracted = self.extract_videos(video_allowance)
                if num_videos_extracted == 0:
                    break
                video_allowance -= num_videos_extracted
                tot_videos_scraped += num_videos_extracted
                page += 1
            logger.info(f"Total video links found in {topic}: {tot_videos_scraped}")

    def extract_videos(self, video_allowance):

        # all videos are embedded in a <div> with the class name 'row'.
        # we are searching for the div inside this div, that has an <a>-tag
        # with the class name 'media__image', because this is the relative
        # link to the representative TED talk. We have to turn this relative
        # link to an absolute link. This is done through the `utils` class
        videos = self.soup.select("div.row div.media__image a")
        if len(videos) > video_allowance:
            videos = videos[0:video_allowance]
        logger.debug(f"{str(len(videos))} videos found on current page")
        for video in videos:
            url = urljoin(self.BASE_URL, video["href"])
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
        self.soup = BeautifulSoup(download_from_site(url).text, features="html.parser")
        div = self.soup.find("div", attrs={"class": "talks-main"})
        script_tags_within_div = div.find_all("script")
        if len(script_tags_within_div) == 0:
            logger.error("The required script tag containing video meta is not present")
            return
        json_data_tag = script_tags_within_div[-1]
        json_data = json_data_tag.string
        json_data = " ".join(json_data.split(",", 1)[1].split(")")[:-1])
        json_data = json.loads(json_data)["__INITIAL_DATA__"]

        # Extract the speaker of the TED talk
        talk_info = json_data["talks"][0]
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
        subtitles = [
            {"languageName": lang["languageName"], "languageCode": lang["languageCode"]}
            for lang in talk_info["player_talks"][0]["languages"]
        ]
        subtitles = build_subtitle_pages(video_id, subtitles)

        # Extract the keywords for the TED talk
        keywords = self.soup.find("meta", attrs={"name": "keywords"})["content"]
        keywords = [key.strip() for key in keywords.split(",")]

        # Check if video ID already exists. If not, append data to self.videos
        if not any(video.get("id", None) == video_id for video in self.videos):
            self.videos.append(
                {
                    "id": video_id,
                    "title": title,
                    "description": description,
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

    def dump_data(self):

        # Dump all the data about every TED talk in a json file
        # inside the 'build' folder.
        logger.debug(
            f"Dumping {len(self.videos)} videos into {self.ted_videos_json} and {len(self.topics)} topics into {self.ted_topics_json}"
        )
        video_data = json.dumps(self.videos, indent=4)
        topics_data = json.dumps(self.topics, indent=4)

        # Check, if the folder exists. Create it, if it doesn't.
        if not self.build_dir.exists():
            self.build_dir.mkdir(parents=True)

        # Create or override the json files in the build
        # directory with the video data gathered from the scraper
        # and topic data.
        with open(self.ted_videos_json, "w") as f:
            f.write(video_data)
        with open(self.ted_topics_json, "w") as f:
            f.write(topics_data)

    def render_video_pages(self):

        # Render static html pages from the scraped video data and
        # save the pages in build_dir/<video-id>/index.html
        # Load data from json files
        self.load_meta_from_file()
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        for video in self.videos:
            video_id = str(video["id"])
            video_path = self.build_dir.joinpath(video_id)
            if not video_path.exists():
                video_path.mkdir(parents=True)

            html = env.get_template("video.html").render(
                title=video["title"],
                speaker=video["speaker"],
                description=video["description"],
                languages=video["subtitles"],
                speaker_bio=video["speaker_bio"].replace("Full bio", ""),
                speaker_img=video["speaker_picture"],
                date=video["date"],
                profession=video["speaker_profession"],
                video_format=self.video_format,
            )
            index_path = video_path.joinpath("index.html")
            with open(index_path, "w", encoding="utf-8") as html_page:
                html_page.write(html)

    def render_welcome_page(self):

        # Render the homepage
        # Load data from json files
        self.load_meta_from_file()
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        if not self.build_dir.exists():
            self.build_dir.mkdir(parents=True)
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
        html = env.get_template("welcome.html").render(languages=languages)
        welcome_page_path = self.build_dir.joinpath("index.html")
        with open(welcome_page_path, "w", encoding="utf-8") as html_page:
            html_page.write(html)

    def copy_files_to_build_directory(self):

        # Copy files from template_dir to build_dir
        css_dir = self.templates_dir.joinpath("CSS")
        js_dir = self.templates_dir.joinpath("JS")
        copy_css_dir = self.build_dir.joinpath("CSS")
        copy_js_dir = self.build_dir.joinpath("JS")
        if css_dir.exists():
            shutil.copytree(css_dir, copy_css_dir, dirs_exist_ok=True)
        if js_dir.exists():
            shutil.copytree(js_dir, copy_js_dir, dirs_exist_ok=True)
        favicon_file = self.templates_dir.joinpath("favicon.png")
        copy_favicon_file = self.build_dir.joinpath("favicon.png")
        shutil.copy(favicon_file, copy_favicon_file)

    def generate_datafile(self):

        # Generate data.js inside the JS folder
        self.load_meta_from_file()
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
        js_path = self.build_dir.joinpath("JS")
        data_path = js_path.joinpath("data.js")
        if not js_path.exists():
            js_path.mkdir(parents=True)
        with open(data_path, "w") as page_file:
            json_data = json.dumps(video_list, indent=4)
            json_data = "json_data = " + json_data
            page_file.write(json_data)

    def download_video_data(self):

        # Download all the TED talk videos and the meta-data for it.
        # Save the videos in build_dir/{video id}/video.mp4.
        # Save the thumbnail for the video in build_dir/{video id}/thumbnail.jpg.
        # Save the image of the speaker in build_dir/{video id}/speaker.jpg.
        # load the dumped metadata
        self.load_meta_from_file()
        for video in self.videos:
            # set up variables
            video_id = str(video["id"])
            video_title = video["title"]
            video_link = video["video_link"]
            video_speaker = video["speaker_picture"]
            video_thumbnail = video["thumbnail"]
            video_dir = self.build_dir.joinpath(video_id)
            video_file_path = video_dir.joinpath("video.mp4")
            speaker_path = video_dir.joinpath("speaker.jpg")
            thumbnail_path = video_dir.joinpath("thumbnail.jpg")

            # ensure that video directory exists
            if not video_dir.exists():
                video_dir.mkdir(parents=True)

            # download video
            if not video_file_path.exists():
                logger.debug(f"Downloading {video_title}")
                try:
                    save_large_file(video_link, video_file_path)
                except Exception:
                    logger.error(f"Could not download {video_file_path}")
            else:
                logger.debug(f"video.mp4 already exists. Skipping video {video_title}")

            # download an image of the speaker
            if not speaker_path.exists():
                if video_speaker == "None" or video_speaker == "":
                    logger.debug("Speaker doesn't have an image")
                else:
                    logger.debug(f"Downloading Speaker image for {video_title}")
                    save_large_file(video_speaker, speaker_path)
            else:
                logger.debug(f"speaker.jpg already exists for {video_title}")

            # download the thumbnail of the video
            if not thumbnail_path.exists():
                logger.debug(f"Downloading thumbnail for {video_title}")
                save_large_file(video_thumbnail, thumbnail_path)
            else:
                logger.debug(f"Thumbnail already exists for {video_title}")

            # recompress if necessary
            post_process_video(
                video_dir, video_id, self.video_format, self.low_quality,
            )

    def download_subtitles(self):
        # Download the subtitle files, generate a WebVTT file
        # and save the subtitles in
        # build_dir/{video id}/subs/subs_{language code}.vtt
        self.load_meta_from_file()
        for video in self.videos:
            video_id = str(video["id"])
            video_title = video["title"]
            video_subtitles = video["subtitles"]
            video_dir = self.build_dir.joinpath(video_id)
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
                    video["subtitles"].remove(subtitle)
                    logger.error(
                        f"Subtitle file for {subtitle['languageCode']} could not be created"
                    )
                    continue
                subtitle_file_name = subs_dir.joinpath(
                    f"subs_{subtitle['languageCode']}.vtt"
                )
                with open(subtitle_file_name, "w", encoding="utf-8") as sub_file:
                    sub_file.write(subtitle_file)

        # save the info that some videos don't have subtitle file created successfully
        self.dump_data()

    def load_meta_from_file(self):
        # Load the dumped json meta-data file.
        with open(self.ted_videos_json) as data_file:
            self.videos = json.load(data_file)
        with open(self.ted_topics_json) as data_file:
            self.topics = json.load(data_file)

    def run(self):
        self.extract_all_video_links()
        self.dump_data()
        self.download_video_data()
        self.download_subtitles()
        self.render_welcome_page()
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
            logger.debug(self.zim_info.to_zimwriterfs_args())
            make_zim_file(self.build_dir, self.output_dir, self.fname, self.zim_info)
            if not self.keep_build_dir:
                logger.info("removing build directory")
                shutil.rmtree(self.build_dir, ignore_errors=True)
        logger.info("Done Everything")
