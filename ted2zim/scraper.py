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
from PIL import Image
import jinja2
from .WebVTTcreator import WebVTTcreator
import shutil


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

    def render_video_pages(self):
        # Render static html pages from the scraped video data and
        # save the pages in TED/build/{video id}/index.html.
        print("Rendering Template")

        if not self.ted_json.exists():
            sys.exit("TED.json file not found. Run the script with the '-m' flag")
        # load data from file
        self.load_meta_from_file()

        # if transcode2webm:
        #     format="webm"
        # else:
        #     format="mp4"

        format = "mp4"

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        for video in self.videos:
            video_id = str(video[0]["id"])
            video_path = self.html_dir.joinpath(video_id)
            if not video_path.exists():
                video_path.mkdir(parents=True)

            html = env.get_template("video.html").render(
                title=video[0]["title"],
                speaker=video[0]["speaker"],
                description=video[0]["description"],
                languages=video[0]["subtitles"],
                speaker_bio=video[0]["speaker_bio"].replace("Full bio", ""),
                speaker_img=video[0]["speaker_picture"],
                date=video[0]["date"],
                profession=video[0]["speaker_profession"],
                format=format,
            )
            index_path = video_path.joinpath("index.html")
            with open(index_path, "w", encoding="utf-8") as html_page:
                html_page.write(html)

    def render_welcome_page(self):
        if not self.ted_json.exists():
            sys.exit("TED.json file not found. Run the script with the '-m' flag")

        self.load_meta_from_file()

        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )

        if not self.html_dir.exists():
            self.html_dir.mkdir(parents=True)
        languages = []
        for video in self.videos:
            for language in video[0]["subtitles"]:
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
        welcome_page_path = self.html_dir.joinpath("index.html")
        with open(welcome_page_path, "w", encoding="utf-8") as html_page:
            html_page.write(html)

    def copy_files_to_rendering_directory(self):
        # Copy files from the /scraper directory to the /html/{zimfile} directory.
        css_dir = self.templates_dir.joinpath("CSS")
        js_dir = self.templates_dir.joinpath("JS")
        copy_css_dir = self.html_dir.joinpath("CSS")
        copy_js_dir = self.html_dir.joinpath("JS")
        if css_dir.exists():
            shutil.copytree(css_dir, copy_css_dir, dirs_exist_ok=True)
        if js_dir.exists():
            shutil.copytree(js_dir, copy_js_dir, dirs_exist_ok=True)
        favicon_file = self.templates_dir.joinpath("favicon.png")
        copy_favicon_file = self.html_dir.joinpath("favicon.png")
        shutil.copy(favicon_file, copy_favicon_file)
        for video in self.videos:
            video_id = str(video[0]["id"])
            video_path = self.scraper_dir.joinpath(video_id)
            copy_video_path = self.html_dir.joinpath(video_id)
            copy_subs_path = copy_video_path.joinpath("subs")
            thumbnail = video_path.joinpath("thumbnail.jpg")
            subs = video_path.joinpath("subs")
            speaker = video_path.joinpath("speaker.jpg")
            video_ = video_path.joinpath("video.mp4")
            if thumbnail.exists():
                shutil.copy(thumbnail, copy_video_path)
            if subs.exists():
                shutil.copytree(subs, copy_subs_path, dirs_exist_ok=True)
            if speaker.exists():
                shutil.copy(speaker, copy_video_path)
            if video_.exists():
                shutil.copy(video_, copy_video_path)

    def generate_category_data(self):
        # Generate the json page data for every category.

        self.load_meta_from_file()
        video_list = []

        for video in self.videos:
            json_data = {
                "languages": [lang["languageCode"] for lang in video[0]["subtitles"]],
                "id": video[0]["id"],
                "description": video[0]["description"],
                "title": video[0]["title"],
                "speaker": video[0]["speaker"],
            }
            video_list.append(json_data)

        js_path = self.html_dir.joinpath("JS")
        data_path = js_path.joinpath("data.js")
        if not js_path.exists():
            js_path.mkdir(parents=True)
        with open(data_path, "w") as page_file:
            json_data = json.dumps(video_list, indent=4, separators=(",", ": "))
            json_data = "json_data = " + json_data
            page_file.write(json_data)

    # def resize_thumbnails(self):
    #     try:
    #         thumbnails = [path.join(root, name)
    #                   for root, dirs, files in os.walk(self.html_dir)
    #                   for name in files
    #                   if name == 'thumbnail.jpg']

    #         for thumbnail in thumbnails:
    #             resize_image(thumbnail)
    #             print 'Resizing ' + thumbnail.encode('utf-8')
    #     except Exception, e:
    #         raise e

    # def encode_videos(self,transcode2webm):
    #     # Encode the videos from mp4 to webm. We will use ffmpeg over the
    #     # command line for this. There is a static binary version
    #     # in the kiwix-other/TED/ directory, that we will use on macs.

    #     self.load_meta_from_file()
    #     for video in self.videos:
    #         for i in self.categories:
    #             if i in video[0]['keywords']:
    #                 video_id =  str(video[0]['id'])
    #                 video_path = path.join(self.scraper_dir, video_id, 'video.mp4')
    #                 if transcode2webm:
    #                     video_copy_path = path.join(self.html_dir, i, video_id, 'video.webm')
    #                 else:
    #                     video_copy_path = path.join(self.html_dir, i, video_id, 'video.mp4')

    #                 if path.exists(video_copy_path):
    #                     print 'Video already encoded. Skipping.'
    #                     continue

    #                 if path.exists(video_path):
    #                     self.convert_video_and_move_to_rendering(video_path, video_copy_path,transcode2webm)
    #                     print 'Converting Video... ' + video[0]['title'].encode('utf-8')

    # def convert_video_and_move_to_rendering(self, from_path, to_path,transcode2webm):
    #     ffmpeg = ''
    #     if _platform == "linux" or _platform == "linux2":
    #         ffmpeg = 'ffmpeg'
    #     elif _platform == "darwin":
    #         ffmpeg = path.join(os.getcwd(), '..', 'ffmpeg')

    #     if transcode2webm:
    #         command = ''.join(("""{} -i "{}" -codec:v libvpx -quality best -cpu-used 0 -b:v 300k""",
    #             """ -qmin 30 -qmax 42 -maxrate 300k -bufsize 1000k -threads 8 -vf scale=480:-1""",
    #             """ -codec:a libvorbis -b:a 128k -f webm "{}" """)).format(
    #             ffmpeg, from_path, to_path)
    #     else:
    #         command = ''.join(("""{} -i "{}" -codec:v h264 -quality best -cpu-used 0 -b:v 300k""",
    #             """ -qmin 30 -qmax 42 -maxrate 300k -bufsize 1000k -threads 8 -vf scale=480:-1""",
    #             """ -codec:a mp3 -b:a 128k -movflags +faststart -f mp4 "{}" """)).format(
    #             ffmpeg, from_path, to_path)

    #     os.system(command)

    def download_video_data(self):
        # Download all the TED talk videos and the meta-data for it.
        # Save the videos in the TED/build/{video id}/video.mp4.
        # Save the thumbnail for the video in
        # TED/build/{video id}/thumbnail.jpg.
        # Save the image of the speaker in TED/build/{video id}/speaker.jpg.

        # load the dumped metadata
        self.load_meta_from_file()

        for video in self.videos:
            # set up variables
            video_id = str(video[0]["id"])
            video_title = video[0]["title"]
            video_link = video[0]["video_link"]
            video_speaker = video[0]["speaker_picture"]
            video_thumbnail = video[0]["thumbnail"]
            video_dir = self.scraper_dir.joinpath(video_id)
            video_file_path = video_dir.joinpath("video.mp4")
            speaker_path = video_dir.joinpath("speaker.jpg")
            thumbnail_path = video_dir.joinpath("thumbnail.jpg")

            # ensure that video directory exists
            if not video_dir.exists():
                video_dir.mkdir(parents=True)

            # download video
            if not video_file_path.exists():
                print(f"Downloading {video_title}")
                for i in range(5):
                    while True:
                        try:
                            r = download_from_site(video_link)
                            with open(video_file_path, "wb") as code:
                                code.write(r.content)
                        except Exception as e:
                            raise e
                            sleep(5)
                            continue
                        break
            else:
                print("video.mp4 already exists. Skipping video " + video_title)

            # download an image of the speaker
            if not speaker_path.exists() and video_speaker != "":
                if video_speaker == "None":
                    print("Speaker doesn't have an image")
                else:
                    print(f"Downloading Speaker image for {video_title}")
                    r = download_from_site(video_speaker)
                    with open(speaker_path, "wb") as f:
                        f.write(r.content)
            else:
                print(f"Speaker.jpg already exists for {video_title}")

            # download the thumbnail of the video
            if not thumbnail_path.exists():
                print(f"Downloading thumbnail for {video_title}")
                r = download_from_site(video_thumbnail)
                with open(thumbnail_path, "wb") as f:
                    f.write(r.content)
            else:
                print(f"Thumbnail already exists for {video_title}")

    def download_subtitles(self):
        # Download the subtitle files, generate a WebVTT file
        # and save the subtitles in
        # TED/build/{video id}/subs_{language code}.vtt
        self.load_meta_from_file()
        for video in self.videos:
            video_id = str(video[0]["id"])
            video_title = video[0]["title"]
            video_subtitles = video[0]["subtitles"]
            video_dir = self.scraper_dir.joinpath(video_id)
            subs_dir = video_dir.joinpath("subs")
            if not subs_dir.exists():
                subs_dir.mkdir(parents=True)
            else:
                print(f"Subs dir exists already")
                continue

            # download subtitles
            print("Downloading subtitles... " + video_title)
            for subtitle in video_subtitles:
                sleep(0.5)
                subtitle_file = WebVTTcreator(subtitle["link"], 11820).get_content()
                if subtitle_file == False:
                    video[0]["subtitles"].remove(subtitle)
                    pass
                subtitle_file_name = subs_dir.joinpath(
                    f"subs_{subtitle['languageCode']}.vtt"
                )
                with open(subtitle_file_name, "w", encoding="utf-8") as sub_file:
                    sub_file.write(subtitle_file)
        # save the info that some videos don't have subtitles
        self.dump_data()

    def load_meta_from_file(self):
        # Load the dumped json meta-data file.
        with open(self.ted_json) as data_file:
            self.videos = json.load(data_file)

    def resize_image(self, image_path):
        image = Image.open(image_path)
        w, h = image.size
        image = image.resize((248, 187), Image.ANTIALIAS)
        image.save(image_path)

    def run(self):
        self.extract_all_video_links()
        self.dump_data()
        self.download_video_data()
        self.download_subtitles()
        self.render_welcome_page()
        self.render_video_pages()
        self.copy_files_to_rendering_directory()
        self.generate_category_data()
        print("DONE")
