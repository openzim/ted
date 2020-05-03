#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import dateutil.parser
import requests
import json
import pathlib
import jinja2
import shutil
import datetime
import sys

from bs4 import BeautifulSoup
from urllib.parse import urljoin
from time import sleep
from os import path  # to be removed soon

from .utils import download_from_site, build_subtitle_pages
from .constants import ROOT_DIR, SCRAPER, MAX_SOURCE_VIDEOS_PER_PAGE, logger
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
        self, max_videos_per_topic, topics, output_dir, transcode2webm, debug,
    ):

        # output directory
        self.output_dir = pathlib.Path(output_dir).expanduser().resolve()

        # scraper options
        self.topics = [c.strip().replace(" ", "+") for c in topics.split(",")]
        self.max_videos_per_topic = max_videos_per_topic
        self.transcode2webm = transcode2webm

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
        """
        Render static html pages from the scraped video data and
        save the pages in TED/build/{video id}/index.html.
        """
        print("Rendering template...")

        if not path.exists(self.meta_data_dir):
            sys.exit("TED.json file not found. Run the script with the '-m' flag")

        self.load_metadata()

        if self.transcode2webm:
            format = "webm"
        else:
            format = "mp4"
        env = Environment(
            loader=FileSystemLoader(
                os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates")
            )
        )
        template = env.get_template("video.html")

        for video in self.videos:
            for i in self.topics:
                if i in video[0]["keywords"]:
                    video_id = str(video[0]["id"])
                    video_path = path.join(self.html_dir, i, video_id)
                    if not path.exists(video_path):
                        os.makedirs(video_path)

                    html = template.render(
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

                    html = html.encode("utf-8")
                    index_path = path.join(video_path, "index.html")
                    with open(index_path, "w") as html_page:
                        html_page.write(html)

    def render_welcome_page(self):
        """
        Create the data for the index.html page (the summary page).
        """
        if not path.exists(self.meta_data_dir):
            sys.exit("TED.json file not found. Run the script with the '-m' flag")

        self.load_metadata()

        env = Environment(
            loader=FileSystemLoader(
                os.path.join(os.path.abspath(os.path.dirname(__file__)), "templates")
            )
        )
        template = env.get_template("welcome.html")

        for i in self.topics:
            video_path = path.join(self.html_dir, i)
            if not path.exists(video_path):
                os.makedirs(video_path)

            index_path = path.join(video_path, "index.html")
            with open(index_path, "w") as html_page:
                html_page.write(self.create_welcome_page_data(i, template))

    def create_welcome_page_data(self, keyword, template):
        """
        Create the data for the index.html page (the summary page).
        """
        languages = []

        for video in self.videos:
            if not keyword in video[0]["keywords"]:
                continue

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

        html = template.render(languages=languages)
        html = html.encode("utf-8")
        return html

    def copy_files_to_rendering_directory(self):
        """
        Copy files from the /scraper directory to the /html/{zimfile} directory.
        """

        for i in self.topics:
            copy_dir = path.join(self.html_dir, i)
            css_dir = path.join(self.templates_dir, "CSS")
            js_dir = path.join(self.templates_dir, "JS")

            copy_css_dir = path.join(copy_dir, "CSS")
            copy_js_dir = path.join(copy_dir, "JS")

            if path.exists(css_dir):
                distutils.dir_util.copy_tree(css_dir, copy_css_dir)
            if path.exists(js_dir):
                distutils.dir_util.copy_tree(js_dir, copy_js_dir)

            favicon_file = path.join(self.templates_dir, "favicon.png")
            copy_favicon_file = path.join(copy_dir, "favicon.png")
            shutil.copy(favicon_file, copy_favicon_file)

        for video in self.videos:
            for i in self.topics:
                if i in video[0]["keywords"]:
                    video_id = str(video[0]["id"])
                    video_path = path.join(self.scraper_dir, video_id)
                    copy_video_path = path.join(self.html_dir, i, video_id)
                    copy_subs_path = path.join(copy_video_path, "subs")
                    thumbnail = path.join(video_path, "thumbnail.jpg")
                    subs = path.join(video_path, "subs")
                    speaker = path.join(video_path, "speaker.jpg")
                    video_ = path.join(video_path, "video.mp4")

                    if path.exists(thumbnail):
                        shutil.copy(thumbnail, copy_video_path)

                    if path.exists(subs):
                        distutils.dir_util.copy_tree(subs, copy_subs_path)

                    if path.exists(speaker):
                        shutil.copy(speaker, copy_video_path)

    def generate_topic_data(self):
        """
        Generate the json page data for every topic.
        """

        self.load_metadata()
        video_list = defaultdict(list)

        for video in self.videos:
            for i in self.topics:
                if i in video[0]["keywords"]:
                    json_data = {
                        "languages": [
                            lang["languageCode"] for lang in video[0]["subtitles"]
                        ],
                        "id": video[0]["id"],
                        "description": video[0]["description"],
                        "title": video[0]["title"],
                        "speaker": video[0]["speaker"],
                    }
                    video_list[i].append(json_data)

        for k, v in video_list.items():
            js_path = path.join(self.html_dir, k, "JS")
            data_path = path.join(js_path, "data.js")

            if not path.exists(js_path):
                os.makedirs(js_path)

            with open(data_path, "w") as page_file:
                json_data = json.dumps(v, indent=4)
                json_data = "json_data = " + json_data
                page_file.write(json_data)

    def resize_thumbnails(self):
        try:
            thumbnails = [
                path.join(root, name)
                for root, dirs, files in os.walk(self.html_dir)
                for name in files
                if name == "thumbnail.jpg"
            ]

            for thumbnail in thumbnails:
                resize_image(thumbnail)
                print("Resizing " + thumbnail.encode("utf-8"))
        except Exception as e:
            raise e

    def encode_videos(self):
        """
        Encode the videos from mp4 to webm. We will use ffmpeg over the
        command line for this. There is a static binary version
        in the kiwix-other/TED/ directory, that we will use on macs.
        """

        self.load_metadata()
        for video in self.videos:
            for i in self.topics:
                if i in video[0]["keywords"]:
                    video_id = str(video[0]["id"])
                    video_path = path.join(self.scraper_dir, video_id, "video.mp4")
                    if self.transcode2webm:
                        video_copy_path = path.join(
                            self.html_dir, i, video_id, "video.webm"
                        )
                    else:
                        video_copy_path = path.join(
                            self.html_dir, i, video_id, "video.mp4"
                        )

                    if path.exists(video_copy_path):
                        print("Video already encoded. Skipping.")
                        continue

                    if path.exists(video_path):
                        self.convert_video_and_move_to_rendering(
                            video_path, video_copy_path
                        )
                        print(
                            "Converting Video... " + video[0]["title"].encode("utf-8")
                        )

    def convert_video_and_move_to_rendering(self, from_path, to_path):
        ffmpeg = ""
        if _platform == "linux" or _platform == "linux2":
            ffmpeg = "ffmpeg"
        elif _platform == "darwin":
            ffmpeg = path.join(os.getcwd(), "..", "ffmpeg")

        if self.transcode2webm:
            command = "".join(
                (
                    """{} -i "{}" -codec:v libvpx -quality best -cpu-used 0 -b:v 300k""",
                    """ -qmin 30 -qmax 42 -maxrate 300k -bufsize 1000k -threads 8 -vf scale=480:-1""",
                    """ -codec:a libvorbis -b:a 128k -f webm "{}" """,
                )
            ).format(ffmpeg, from_path, to_path)
        else:
            command = "".join(
                (
                    """{} -i "{}" -codec:v h264 -quality best -cpu-used 0 -b:v 300k""",
                    """ -qmin 30 -qmax 42 -maxrate 300k -bufsize 1000k -threads 8 -vf scale=480:-1""",
                    """ -codec:a mp3 -b:a 128k -movflags +faststart -f mp4 "{}" """,
                )
            ).format(ffmpeg, from_path, to_path)

        os.system(command)

    def download_video_data(self):
        """
        Download all the TED talk videos and the meta-data for it.
        Save the videos in the TED/build/{video id}/video.mp4.
        Save the thumbnail for the video in
        TED/build/{video id}/thumbnail.jpg.
        Save the image of the speaker in TED/build/{video id}/speaker.jpg.
        """

        self.load_metadata()
        for video in self.videos:
            video_id = str(video[0]["id"])
            video_title = video[0]["title"]
            video_link = video[0]["video_link"]
            video_speaker = video[0]["speaker_picture"]
            video_thumbnail = video[0]["thumbnail"]
            video_dir = path.join(self.scraper_dir, video_id)
            video_file_path = path.join(video_dir, "video.mp4")
            speaker_path = path.join(video_dir, "speaker.jpg")
            thumbnail_path = path.join(video_dir, "thumbnail.jpg")

            if not path.exists(video_dir):
                os.makedirs(video_dir)

            if not path.exists(video_file_path):
                print("Downloading video... " + video_title.encode("utf-8"))
                for i in range(5):
                    while True:
                        try:
                            r = utils.download_from_site(video_link)
                            with open(video_file_path, "wb") as code:
                                code.write(r.content)
                        except Exception as e:
                            raise e
                            sleep(5)
                            continue
                        break

            else:
                print(
                    "video.mp4 already exist. Skipping video "
                    + video_title.encode("utf-8")
                )

            # download an image of the speaker
            if not path.exists(speaker_path) and video_speaker != "":
                if video_speaker == "None":
                    print("Speaker has not image")
                else:
                    print("Downloading speaker image... " + video_title.encode("utf-8"))
                    print(video_speaker.encode("utf-8"))
                    r = utils.download_from_site(video_speaker)
                    with open(speaker_path, "wb") as code:
                        code.write(r.content)
            else:
                print(
                    "speaker.jpg already exist. Skipping video "
                    + video_title.encode("utf-8")
                )

            # download the thumbnail of the video
            if not path.exists(thumbnail_path):
                print("Downloading video thumbnail... " + video_title.encode("utf-8"))
                r = utils.download_from_site(video_thumbnail)
                with open(thumbnail_path, "wb") as code:
                    code.write(r.content)
            else:
                print(
                    "thumbnail.jpg already exist. Skipping video "
                    + video_title.encode("utf-8")
                )

    def download_subtitles(self):
        """
        Download the subtitle files, generate a WebVTT file
        and save the subtitles in
        TED/build/{video id}/subs_{language code}.vtt.
        """
        self.load_metadata()
        for video in self.videos:
            video_id = str(video[0]["id"])
            video_title = video[0]["title"]
            video_subtitles = video[0]["subtitles"]
            subs_dir = path.join(self.scraper_dir, video_id, "subs")

            if not path.exists(subs_dir):
                os.makedirs(subs_dir)
            else:
                print("Subtitles already exist. Skipping video.")
                continue

            # download subtitles
            print("Downloading subtitles... " + video_title.encode("utf-8"))
            for subtitle in video_subtitles:
                sleep(0.5)
                subtitle_file = WebVTTcreator(subtitle["link"], 11820).get_content()
                if subtitle_file == False:
                    video[0]["subtitles"].remove(subtitle)
                    pass
                subtitle_file = subtitle_file.encode("utf-8")
                subtitle_file_name = "subs_{}.vtt".format(subtitle["languageCode"])
                subtitle_file_name = path.join(subs_dir, subtitle_file_name)
                with open(subtitle_file_name, "w") as sub_file:
                    sub_file.write(subtitle_file)
        self.dump_data()  # To save info than some videos have, finaly not subtitle

    def load_metadata(self):
        """
        Load the dumped json meta-data file.
        """

        with open(self.meta_data_dir) as data_file:
            self.videos = json.load(data_file)

    def create_zims(self):
        print("Creating ZIM files")

        # Check, if the folder exists. Create it, if it doesn't.
        if not path.exists(self.zim_dir):
            os.makedirs(self.zim_dir)

        for i in self.topics:
            html_dir = path.join(self.html_dir, i)
            zim_path = path.join(
                self.zim_dir,
                "ted_en_{topic}_{date}.zim".format(
                    topic=i.replace(" ", "_"),
                    date=datetime.datetime.now().strftime("%Y-%m"),
                ),
            )
            title = "TED talks - " + i[0].upper() + i[1:]
            description = "Ideas worth spreading"
            name = "kiwix." + i.replace(" ", "_")
            create_zim(html_dir, zim_path, title, description, name)

    def run(self):
        self.extract_all_video_links()
        self.dump_data()
        # self.download_subtitles()
        # self.download_video_data()
        # self.render_welcome_page()
        # self.render_video_pages()
        # self.copy_files_to_rendering_directory()
        # self.generate_topic_data()
        # self.encode_videos()
        # self.resize_thumbnails()
        # self.create_zims()


def resize_image(image_path):
    from PIL import Image

    image = Image.open(image_path)
    w, h = image.size
    image = image.resize((248, 187), Image.ANTIALIAS)
    image.save(image_path)


def exec_cmd(cmd):
    return envoy.run(str(cmd.encode("utf-8")))


def create_zim(static_folder, zim_path, title, description, name):

    print("\tWritting ZIM for {}".format(title))

    context = {
        "languages": "eng",
        "title": title,
        "description": description,
        "creator": "TED",
        "publisher": "Kiwix",
        "home": "index.html",
        "favicon": "favicon.png",
        "static": static_folder,
        "zim": zim_path,
        "scraper": "Ted scraper : https://github.com/openzim/ted",
        "source": "https://new.ted.com",
        "tags": "_category:ted;ted",
        "name": name,
    }

    cmd = (
        'zimwriterfs --welcome="{home}" --favicon="{favicon}" '
        '--language="{languages}" --title="{title}" '
        '--description="{description}" '
        '--creator="{creator}" --publisher="{publisher}" --tags="{tags}" --source="{source}" --scraper="{scraper}" --name="{name}" "{static}" "{zim}"'.format(
            **context
        )
    )
    print(cmd)

    if exec_cmd(cmd):
        print("Successfuly created ZIM file at {}".format(zim_path))
    else:
        print("Unable to create ZIM file :(")


def bin_is_present(binary):
    try:
        subprocess.Popen(
            binary,
            universal_newlines=True,
            shell=False,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
    except OSError:
        return False
    else:
        return True


if __name__ == "__main__":
    pass
