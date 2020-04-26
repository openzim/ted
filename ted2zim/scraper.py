#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import dateutil.parser
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from time import sleep
import requests
from .utils import create_absolute_link, download_from_site, build_subtitle_pages
import json
import pathlib
from .constants import ROOT_DIR


class Ted2Zim:

    # The base Url. The link gives you a grid of all TED talks.
    BASE_URL = "https://ted.com/talks"
    # BeautifulSoup instance
    soup = None
    # Page count
    pages = None
    # List of links to all TED talks
    videos = []

    def __init__(self, max_pages, categories, debug):
        self.build_dir = pathlib.Path.cwd().joinpath("build")
        self.scraper_dir = self.build_dir.joinpath("TED").joinpath("scraper")
        self.html_dir = self.build_dir.joinpath("TED").joinpath("html")
        self.zim_dir = self.build_dir.joinpath("TED").joinpath("zim")
        self.ted_json = self.scraper_dir.joinpath("TED.json")
        if max_pages.isdigit():
            self.max_pages = int(max_pages)
        elif max_pages == "max":
            self.max_pages = "max"
        self.categories = categories
        self.debug = debug
        self.templates_dir = ROOT_DIR.joinpath("templates")

    def extract_page_number(self):
        # Extract the number of video pages by looking at the
        # pagination div at the bottom. Select all <a>-tags in it and
        # return the last element in the list. That's our total count
        pages = self.soup.select("div.pagination a.pagination__item")[-1]
        return int(pages.text)

    def extract_all_video_links(self):
        # This method will build the specifiv video site by appending
        # the page number to the 'page' parameter to the url.
        # We will iterate through every page and extract every
        # video link. The video link is extracted in `extract_videos()`.
        for category in self.categories:
            print(category)
            category_url = f"{self.BASE_URL}?topics%5B%5D={category}"
            self.soup = BeautifulSoup(
                download_from_site(category_url).text, features="html.parser"
            )
            max_page_no = None
            if self.max_pages == "max":
                max_page_no = self.extract_page_number()
            else:
                max_page_no = min(self.max_pages, self.extract_page_number())
            for page in range(1, max_page_no + 1):
                url = f"{category_url}&page={page}"
                html = download_from_site(url).text
                self.soup = BeautifulSoup(html, features="html.parser")
                # print(f"{page} {category}")
                self.extract_videos()

    def extract_videos(self):
        # All videos are embedded in a <div> with the class name 'row'.
        # We are searching for the div inside this div, that has an <a>-tag
        # with the class name 'media__image', because this is the relative
        # link to the representative TED talk. We have to turn this relative
        # link to an absolute link. This is done through the `utils` class.
        print(
            "Videos found : " + str(len(self.soup.select("div.row div.media__image a")))
        )  # DEBUG
        for video in self.soup.select("div.row div.media__image a"):
            url = create_absolute_link(self.BASE_URL, video["href"])
            self.extract_video_info(url)
            print(f"Done {video['href']}")

    def extract_video_info(self, url):

        # Extract the meta-data of the video:
        # Speaker, the profession of the speaker, a short biography of
        # the speaker, the link to a picture of the speaker, title,
        # publishing date, view count, description of the TED talk,
        # direct download link to the video, download link to the subtitle
        # files and a link to a thumbnail of the video.
        self.soup = BeautifulSoup(download_from_site(url).text, features="html.parser")
        # print(self.soup.prettify())

        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        # json_data = self.soup.select('div.talks-main script')
        div = self.soup.find("div", attrs={"class": "talks-main"})
        script_tags_within_div = div.find_all("script")
        if len(script_tags_within_div) == 0:
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
            return
        video_link = downloads["medium"]
        if not video_link:
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

        # Extract the ratings list for the TED talk
        # ratings = talk_info['ratings']

        # Check ifvideo ID already exists. If not, append data to self.videos
        if not any(video[0].get("id", None) == video_id for video in self.videos):
            self.videos.append(
                [
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
                ]
            )

    def dump_data(self):

        # Dump all the data about every TED talk in a json file
        # inside the 'build' folder.
        data = json.dumps(self.videos, indent=4, separators=(",", ": "))

        # Check, if the folder exists. Create it, if it doesn't.
        if not self.scraper_dir.exists():
            self.scraper_dir.mkdir(parents=True)

        # Create or override the 'TED.json' file in the build
        # directory with the video data gathered from the scraper.
        with open(self.ted_json, "w") as f:
            f.write(data)
