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
import yt_dlp
from bs4 import BeautifulSoup
from kiwixstorage import KiwixStorage
from pif import get_public_ip
from slugify import slugify
from zimscraperlib.download import BestMp4, BestWebm, YoutubeDownloader, save_large_file
from zimscraperlib.i18n import _, get_language_details, setlocale
from zimscraperlib.image.optimization import optimize_image
from zimscraperlib.image.presets import WebpMedium
from zimscraperlib.image.transformation import resize_image
from zimscraperlib.inputs import compute_descriptions
from zimscraperlib.video.presets import VideoMp4Low, VideoWebmLow
from zimscraperlib.zim import make_zim_file
from zimscraperlib.zim.metadata import (
    validate_description,
    validate_language,
    validate_longdescription,
    validate_tags,
    validate_title,
)

from ted2zim.constants import (
    ALL,
    BASE_URL,
    MATCHING,
    NONE,
    ROOT_DIR,
    SCRAPER,
    SEARCH_URL,
    TEDLANGS,
    get_logger,
)
from ted2zim.processing import post_process_video
from ted2zim.utils import WebVTT, get_main_title, request_url, update_subtitles_list

logger = get_logger()


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
        long_description,
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
        disable_metadata_checks,
    ):
        # video-encoding info
        self.video_format = video_format
        self.low_quality = low_quality

        # zim params
        self.fname = fname
        self.languages = (
            [] if languages is None else [lang.strip() for lang in languages.split(",")]
        )

        def get_iso_639_3_language(lang: str) -> str | None:
            """Helper function to safely get ISO-639-3 code from input language"""
            lang_info = get_language_details(lang, failsafe=True)
            if lang_info:
                return lang_info["iso-639-3"]
            else:
                logger.warning(
                    f"Failed to get iso-639-3 language info for {lang}. "
                    "This value will be missing in ZIM Language metadata."
                )
                return None

        def sort_languages_hack(languages: set[str]) -> list[str]:
            """This is a temporary hack to sort languages by importance in the ZIM

            For now, if eng is among the list, we assume it is the most important
            language. Otherwise list is kept as-is
            """
            return sorted(languages, key=lambda x: -1 if x == "eng" else 0)

        self.zim_languages = ",".join(
            sort_languages_hack(
                {
                    lang
                    for lang in [
                        get_iso_639_3_language(lang) for lang in self.languages
                    ]
                    if lang
                }
            )
        )

        if not self.zim_languages:
            self.zim_languages = "eng"

        self.tags = [] if tags is None else [tag.strip() for tag in tags.split(",")]
        self.tags = [*self.tags, "_category:ted", "ted", "_videos:yes"]
        self.title = title
        self.description = description
        self.long_description = long_description
        self.creator = creator
        self.publisher = publisher
        self.name = name
        self.disable_metadata_checks = disable_metadata_checks

        if not self.disable_metadata_checks:
            # Validate ZIM metadata early so that we do not waste time doing operations
            # for a scraper which will fail anyway in the end
            validate_language("Language", self.zim_languages)
            validate_tags("Tags", self.tags)
            if self.title:
                validate_title("Title", self.title)
            if self.description:
                validate_description("Description", self.description)
            if self.long_description:
                validate_longdescription("LongDescription", self.long_description)

        # directory setup
        self.output_dir = pathlib.Path(output_dir).expanduser().resolve()
        if tmp_dir:
            pathlib.Path(tmp_dir).mkdir(parents=True, exist_ok=True)
        self.build_dir = pathlib.Path(tempfile.mkdtemp(dir=tmp_dir))

        # scraper options
        self.topics = [] if not topics else topics.split(",")
        self.autoplay = autoplay
        self.playlist = playlist
        self.subtitles_enough = subtitles_enough
        self.subtitles_setting = (
            subtitles_setting
            if subtitles_setting in (ALL, MATCHING, NONE)
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
        self.already_visited = set()

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
        return BASE_URL + "talks/"

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
        elif lang_info["iso-639-1"]:
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
        soup = BeautifulSoup(request_url(playlist_url).text, features="html.parser")
        video_elements = soup.find_all("a", attrs={"class": "group"})
        self.playlist_title = soup.find("h1").string  # pyright: ignore
        self.playlist_description = soup.find(
            "p", attrs={"class": "text-base"}
        ).string  # pyright: ignore

        for element in video_elements:
            relative_path = element.get("href")
            url = urllib.parse.urljoin(self.talks_base_url, relative_path)
            json_data = self.extract_info_from_video_page(url)

            if json_data is not None:
                player_data = json_data["playerData"]
                lang_code = json_data["language"]
                if self.source_languages:
                    # If the first video which was fetched is in source_languages,
                    # save it.
                    if lang_code in self.source_languages:
                        self.update_videos_list_from_info(json_data)
                    # Determine the next languages to fetch from source_languages
                    other_languages = [
                        code for code in self.source_languages if code != lang_code
                    ]
                else:
                    # No languages were specified. We use the the languages returned
                    # from the json_data of this video to generate other language urls.
                    other_languages = [
                        language["languageCode"]
                        for language in player_data["languages"]
                        if language["languageCode"] != lang_code
                    ]

                if not other_languages:
                    # No need to generate urls for other languages as the list
                    # is empty
                    self.already_visited.add(urllib.parse.urlparse(url).path)
                    continue

                other_lang_urls = self.generate_urls_for_other_languages(
                    url, other_languages
                )

                logger.debug(
                    f"Searching info for the video in other {len(other_lang_urls)} "
                    "other language(s)"
                )
                for lang_url in other_lang_urls:
                    data = self.extract_info_from_video_page(lang_url)
                    if data is not None:
                        self.update_videos_list_from_info(data)

                self.already_visited.add(urllib.parse.urlparse(url).path)
            logger.debug(f"Seen {relative_path}")
        logger.debug(f"Total videos found on playlist: {len(video_elements)}")
        if not video_elements:
            raise ValueError("Wrong playlist ID supplied. No videos found")

    def generate_search_results(self, topic):
        """generates a search results and returns the total number of videos scraped"""

        total_videos_scraped = 0
        page = 0
        while True:
            result = self.query_search_engine(topic, page)
            result_json = result.json()
            (
                nb_videos_extracted,
                nb_videos_on_page,
            ) = self.extract_videos_in_search_results(result_json)
            if nb_videos_on_page == 0:
                break
            total_videos_scraped += nb_videos_extracted
            page += 1
        return total_videos_scraped

    def query_search_engine(self, topic, page):
        logger.debug(f"Fetching page {page} of topic {topic}")
        data = [
            {
                "indexName": "relevance",
                "params": {
                    "attributeForDistinct": "objectID",
                    "distinct": 1,
                    "facetFilters": [[f"tags:{topic}"]],
                    "facets": ["subtitle_languages", "tags"],
                    "highlightPostTag": "__/ais-highlight__",
                    "highlightPreTag": "__ais-highlight__",
                    "hitsPerPage": 24,
                    "maxValuesPerFacet": 500,
                    "page": page,
                    "query": "",
                    "tagFilters": "",
                },
            },
        ]
        return request_url(SEARCH_URL, data)

    def extract_videos_from_topics(self, topic):
        """extracts metadata for required number of videos on different topics"""

        logger.debug(f"Fetching video links for topic: {topic}")
        total_videos_scraped = self.generate_search_results(topic)
        logger.info(f"Total video links found in {topic}: {total_videos_scraped}")
        if total_videos_scraped == 0:
            return False
        return True

    def update_zim_metadata(self):
        if self.playlist:
            if not self.title:
                self.title = self.playlist_title.strip()  # pyright: ignore
            default_description = self.playlist_description.strip()  # pyright: ignore
        elif len(self.topics) > 1:
            if not self.title:
                self.title = "TED Collection"
            default_description = "A selection of TED videos from several topics"
        else:
            topic_str = self.topics[0].replace("+", " ")
            if not self.title:
                self.title = f"{topic_str.capitalize()} from TED"
            default_description = f"A selection of {topic_str} videos from TED"

        # update description and long_description if not already set by user input,
        # based on default_description potentially retrieved from playlist / topics
        # compute_descriptions always returns valid description and long description
        # when based on default_description
        self.description, self.long_description = compute_descriptions(
            default_description=default_description,
            user_description=self.description,
            user_long_description=self.long_description,
        )

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

    def generate_urls_for_other_languages(self, url, languages):
        """Possible URLs for other requested languages based on a video url"""

        urls = []
        page_lang, query = self.get_lang_code_from_url(
            url, with_full_query=True
        )  # pyright: ignore[reportGeneralTypeIssues]
        url_parts = list(urllib.parse.urlparse(url))

        # update the language query field value with other languages and form URLs
        for language in languages:
            if language != page_lang:
                query.update({"language": language})
                url_parts[4] = urllib.parse.urlencode(query)
                urls.append(urllib.parse.urlunparse(url_parts))
        return urls

    def extract_videos_in_search_results(self, result_json):
        hits = result_json["results"][0]["hits"]
        nb_extracted = 0
        nb_listed = len(hits)
        logger.debug(f"{nb_listed} video(s) found on current page")
        for hit in hits:
            url = urllib.parse.urljoin(self.talks_base_url, hit["slug"])
            json_data = self.extract_info_from_video_page(url)

            if json_data is None:
                continue

            lang_code = json_data["language"]
            player_data = json_data["playerData"]
            # we need to filter videos since this has not been done
            # before for topics with the "new" search page (2023)
            if self.source_languages:
                # If the first video which was fetched is in self.source_languages
                # save it and increment the counter.
                if (
                    lang_code in self.source_languages
                    and self.update_videos_list_from_info(json_data)
                ):
                    nb_extracted += 1

                # Determine the next languages to fetch from source_languages
                other_languages = [
                    code for code in self.source_languages if code != lang_code
                ]

                # If there are any valid language codes which can be fetched, fetch them
                # and save accordingly
                if other_languages:
                    other_lang_urls = self.generate_urls_for_other_languages(
                        url, other_languages
                    )
                    logger.debug(
                        f"Searching info for the video in {len(other_lang_urls)} "
                        "other language(s)"
                    )
                    for lang_url in other_lang_urls:
                        data = self.extract_info_from_video_page(lang_url)
                        if data is not None and self.update_videos_list_from_info(data):
                            # It is possible that this is the first time we
                            # are saving this video as the first video might
                            # not necessarily be in the source_languages.
                            # We increment the counter relying on the fact that
                            # update_videos_list returns True only if this
                            # is the first time we are saving the video.
                            nb_extracted += 1

                if lang_code not in self.source_languages:
                    # Video language fetched is not among the selected ones, we have to
                    # check subtitles if they are enough
                    if not self.subtitles_enough:
                        logger.debug(
                            f"Ignoring video in non-selected language {lang_code}"
                        )
                    else:
                        matching_languages = [
                            lang
                            for lang in player_data["languages"]
                            if lang["languageCode"] in self.source_languages
                        ]
                        if len(matching_languages) == 0:
                            logger.debug(
                                "Ignoring video without a selected language"
                                "in audio or subtitles"
                            )
            else:
                # Since we are searching for all languages, first update the
                # videos list with the data we just scraped.
                if self.update_videos_list_from_info(json_data):
                    nb_extracted += 1

                # We use the the languages returned from the json_data of
                # this video to generate other language urls
                other_languages = []
                for language in player_data["languages"]:
                    #  Do not include the language of the video that was just scraped
                    if language["languageCode"] == lang_code:
                        continue
                    other_languages.append(language["languageCode"])

                if other_languages:
                    other_lang_urls = self.generate_urls_for_other_languages(
                        url, other_languages
                    )
                    logger.debug(
                        f"Searching info for the video in {len(other_lang_urls)} "
                        "other language(s)"
                    )
                    for lang_url in other_lang_urls:
                        data = self.extract_info_from_video_page(lang_url)
                        if data is not None:
                            self.update_videos_list_from_info(data)

            logger.debug(f"Seen {hit['slug']}")
            self.already_visited.add(urllib.parse.urlparse(url).path)
        return nb_extracted, nb_listed

    def get_lang_code_from_url(self, url, *, with_full_query=False):
        """gets the queried language code from a ted talk url"""

        # sample - https://www.ted.com/talks/alex_rosenthal_the_gauntlet_think_like_a_coder_ep_8?language=ja
        url_parts = list(urllib.parse.urlparse(url))

        # explode url to extract `language` query field value
        query = dict(urllib.parse.parse_qsl(url_parts[4]))
        current_lang = query.get("language")
        if with_full_query:
            return current_lang, query
        return current_lang

    def extract_download_link(self, talk_data):
        """Returns download link / youtube video ID for a TED video"""
        if (
            isinstance(talk_data.get("resources", {}).get("h264"), list)
            and len(talk_data["resources"]["h264"])
            and talk_data["resources"]["h264"][0].get("file")
        ):
            logger.debug(
                "Using h264 resource link for bitrate="
                f"{talk_data['resources']['h264'][0].get('bitrate')}"
            )
            download_link = talk_data["resources"]["h264"][0]["file"]
        else:
            download_link = None

        if (
            talk_data.get("external", {}).get("service")
            and talk_data["external"]["service"] == "YouTube"
            and talk_data["external"].get("code")
        ):
            logger.debug(f"Found Youtube ID {talk_data['external']['code']}")
            youtube_id = talk_data["external"]["code"]
        else:
            youtube_id = None

        return download_link, youtube_id

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
        youtube_id,
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
                    "youtube_id": youtube_id,
                    "length": length,
                    "subtitles": subtitles,
                    "subtitles_set": {
                        subtitle["languageCode"] for subtitle in subtitles
                    },
                }
            )
            logger.debug(f"Successfully inserted video {video_id} into video list")
            return True

        # update localized meta for video if already in self.videos
        # based on --subtitles=matching
        logger.debug(f"Video {video_id} already present in video list")
        for index, video in enumerate(self.videos):
            if video.get("failed", False):
                continue
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
                if self.subtitles_setting in (MATCHING, NONE):
                    # Only add subtitles which have not been added to avoid
                    # duplicates
                    new_subtitles = [
                        subtitle
                        for subtitle in subtitles
                        if subtitle["languageCode"]
                        not in self.videos[index]["subtitles_set"]
                    ]
                    self.videos[index]["subtitles"] += new_subtitles
                    for subtitle in new_subtitles:
                        self.videos[index]["subtitles_set"].add(
                            subtitle["languageCode"]
                        )
        return False

    def get_lang_code_and_name(self, json_data):
        player_data = json_data["playerData"]
        lang_code = json_data["language"]
        try:
            lang_name = [
                lang["languageName"]
                for lang in player_data["languages"]
                if lang["languageCode"] == lang_code
            ][-1]
        except Exception as exc:
            logger.warning(f"player data has no entry for {lang_code}: {exc}")
            lang_name = lang_code

        return lang_code, lang_name

    def update_videos_list_from_info(self, json_data):
        player_data = json_data["playerData"]
        lang_code, lang_name = self.get_lang_code_and_name(json_data)

        native_talk_language = player_data["nativeLanguage"]
        # Extract the speaker of the TED talk
        if len(json_data["speakers"]):
            if isinstance(json_data["speakers"], dict):
                speaker_info = (
                    json_data["speakers"]["nodes"][0]
                    if json_data["speakers"].get("nodes", [])
                    else {}
                )
            elif isinstance(json_data["speakers"], list):
                speaker_info = json_data["speakers"][0]
            else:
                raise OSError(f"Unexpected speaker JSON format: {json_data}")
            speaker = " ".join(
                [
                    speaker_info.get("firstame", ""),
                    speaker_info.get("middlename", ""),
                    speaker_info.get("lastname", ""),
                ]
            )
        else:
            speaker_info = {
                "description": "None",
                "whotheyare": "None",
                "photo_url": "",
            }
            if "presenterDisplayName" in json_data:
                speaker = json_data["presenterDisplayName"]
            else:
                speaker = "None"

        # Extract the ted talk details from json
        video_id = json_data["id"]
        speaker_profession = speaker_info.get("description")
        speaker_bio = speaker_info.get("whoTheyAre", "-")
        speaker_picture = speaker_info.get("photoUrl", "-")
        title = json_data.get("title", "n/a")
        description = json_data.get("description", "n/a")
        date = (
            dateutil.parser.parse(json_data["recordedOn"]).strftime("%d %B %Y")
            if json_data.get("recordedOn")
            else "Unknown"
        )
        length = int(json_data["duration"]) // 60
        thumbnail = player_data["thumb"]
        video_link, youtube_id = self.extract_download_link(player_data)
        if not video_link and not youtube_id:
            logger.error(
                "No suitable download link or Youtube ID found. Skipping video"
            )
            return False

        langs = player_data["languages"]
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
            youtube_id=youtube_id,
            length=length,
            subtitles=subtitles,
        )

    def extract_info_from_video_page(
        self, url: str, retry_count: int = 0
    ) -> dict | None:
        """extract all info from a TED video page url.
        Returns a dict containign the video information if search was
        successful, else None.
        """

        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        # returns True if successfully scraped new video

        # don't scrape if URL already visited
        if urllib.parse.urlparse(url).path in self.already_visited:
            return None

        # don't scrape if maximum retry count is reached
        if retry_count > 5:  # noqa: PLR2004
            logger.error("Max retries exceeded. Skipping video")
            return None

        logger.debug(f"extract_info_from_video_page: {url}")
        html_content = request_url(url).text
        try:
            soup = BeautifulSoup(html_content, features="html.parser")

            json_data = json.loads(
                soup.find(
                    "script", attrs={"id": "__NEXT_DATA__"}
                ).string  # pyright: ignore
            )["props"]["pageProps"]["videoData"]

            requested_lang_code = self.get_lang_code_from_url(url)
            if requested_lang_code and json_data["language"] != requested_lang_code:
                logger.error(
                    f"Video has not yet been translated into {requested_lang_code}"
                )
                return None
            # Desrialize the data at json_data["playerData"] into a dict
            # and overwrite it accordingly
            json_data["playerData"] = json.loads(json_data["playerData"])
            return json_data
        except Exception:
            logger.error(
                f"Problem occured while parsing {url}. HTML content was:\n"
                f"{html_content}"
            )
            raise

    def add_default_language(self):
        """add metatada in default language (english or first avail) on all videos"""

        for video in self.videos:
            if video.get("failed", False):
                continue
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
            if video.get("failed", False):
                continue
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
                html_page.write(html)  # pyright: ignore[reportGeneralTypeIssues]

    def render_home_page(self):
        # Render the homepage
        env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(self.templates_dir)), autoescape=True
        )
        all_langs = {
            language["languageCode"]: language["languageName"]
            for video in self.videos
            if not video.get("failed", False)
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
            html_page.write(html)  # pyright: ignore[reportGeneralTypeIssues]

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
            if video.get("failed", False):
                continue
            lang_codes = [lang["languageCode"] for lang in video["subtitles"]] + [
                lang["languageCode"] for lang in video["languages"]
            ]
            json_data = {
                "languages": list(set(lang_codes)),
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

    def download_jpeg_image_and_convert(self, url, fpath, preset_options, resize=None):
        """downloads a JPEG image and convert to proper format

        Image is automatically converted and optimized into desired format detected from
        fpath
        """

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
        s3_key = f"speaker_image/{video_id}" if self.s3_storage else None
        if self.s3_storage:
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
                if s3_key and video_speaker:
                    self.upload_to_cache(s3_key, speaker_path, preset.VERSION)

    def download_thumbnail(
        self, video_id, video_title, video_thumbnail, thumbnail_path
    ):
        """download the thumbnail"""

        downloaded_from_cache = False
        preset = WebpMedium()
        s3_key = f"thumbnail/{video_id}" if self.s3_storage else None
        if self.s3_storage:
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

        if not self.yt_downloader:
            raise Exception("yt_downloader is not setup")

        # set up variables
        video_id = str(video["id"])
        # Take the english version of title or else whatever language it's available in
        video_title = video["title"][0]["text"]
        video_link = video["video_link"]
        youtube_id = video["youtube_id"]
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
        s3_key = (
            f"{self.video_format}/{self.video_quality}/{video_id}"
            if self.s3_storage
            else None
        )
        if self.s3_storage:
            downloaded_from_cache = self.download_from_cache(
                s3_key, req_video_file_path, preset.VERSION
            )
        if not downloaded_from_cache:
            downloaded = False
            # First try to download from video link
            if video_link:
                try:
                    save_large_file(video_link, org_video_file_path)
                    downloaded = True
                except Exception as exc:
                    logger.error(
                        f"Could not download from {video_link} for "
                        f"{org_video_file_path}",
                    )
                    logger.debug("", exc_info=exc)
                    org_video_file_path.unlink(missing_ok=True)
            # Second try to download from youtube ID (used both when no video link AND
            # when video link download failed - we experience sometimes 403 errors on
            # video link, see #167)
            if youtube_id:
                try:
                    options = (
                        BestWebm if self.video_format == "webm" else BestMp4
                    ).get_options(
                        target_dir=video_dir, filepath=pathlib.Path("video.%(ext)s")
                    )
                    with yt_dlp.YoutubeDL(options) as ydl:
                        ydl.download([youtube_id])
                    downloaded = True
                except Exception as exc:
                    logger.error(
                        f"Could not download from {youtube_id} for "
                        f"{org_video_file_path}",
                    )
                    logger.debug("", exc_info=exc)
            if not downloaded:
                video["failed"] = True
                return

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
            logger.debug("", exc_info=e)
            video["failed"] = True
            return
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
                if not video.get("failed", False)
            ]
            concurrent.futures.wait(fs, return_when=concurrent.futures.ALL_COMPLETED)
        self.yt_downloader.shutdown()

    def download_subtitles(self, index, video):
        """download, converts and writes VTT subtitles

        Subtitles a written for a given video at a specific index in self.videos
        """

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
            logger.debug("Subs dir exists already")

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
                if not video.get("failed", False)
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

        if not self.s3_storage:
            raise Exception("s3_storage is not set")

        if self.use_any_optimized_version:
            if not self.s3_storage.has_object(key, self.s3_storage.bucket_name):
                return False
        elif not self.s3_storage.has_object_matching_meta(
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
            self.s3_storage.upload_file(  # pyright: ignore[reportOptionalMemberAccess]
                object_path, key, meta={"encoder_version": f"v{encoder_version}"}
            )
        except Exception as exc:
            logger.error(f"{key} failed to upload to cache: {exc}")
            return False
        logger.info(f"uploaded {object_path} to cache at {key}")
        return True

    def remove_failed_topics_and_check_extraction(self, failed_topics):
        """removes failed topics from topics list and check scraper can continue"""

        for topic in failed_topics:
            self.topics.remove(topic)
        if not self.topics:
            if self.source_languages:
                raise ValueError(
                    "No videos found for any topic in the language(s) requested. Check "
                    "topic(s) and/or language code supplied to --languages"
                )
            raise ValueError("Wrong topic(s) were supplied. No videos found")

    def run(self):
        logger.info(
            f"Starting scraper with:\n"
            f"  langs: {', '.join(self.source_languages)}\n"
            f"  subtitles : {', '.join(self.subtitles_setting) if isinstance(self.subtitles_setting, list) else self.subtitles_setting}\n"  # noqa: E501
            f"  video format : {self.video_format}"
        )

        if self.s3_url_with_credentials and not self.s3_credentials_ok():
            raise ValueError("Unable to connect to Optimization Cache. Check its URL.")
        if self.s3_storage:
            logger.info(
                f"Using cache: {self.s3_storage.url.netloc} with bucket: "
                f"{self.s3_storage.bucket_name}"
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

        # display final stats and abort processing if no videos are left
        nb_success = sum(
            0 if video.get("failed", False) else 1 for video in self.videos
        )
        nb_failed = sum(1 if video.get("failed", False) else 0 for video in self.videos)
        logger.debug(f"Stats: {nb_success} videos ok, {nb_failed} videos failed")
        if nb_success == 0:
            raise Exception("No successfull video, aborting ZIM creation")

        # zim creation and cleanup
        if not self.no_zim:
            self.fname = (
                self.fname or f"{self.name.replace(' ', '-')}_{{period}}.zim"
            ).format(
                period=datetime.datetime.now().strftime("%Y-%m")  # noqa: DTZ005
            )
            logger.info("building ZIM file")
            if not self.output_dir.exists():
                self.output_dir.mkdir(parents=True)
            make_zim_file(
                build_dir=self.build_dir,
                fpath=self.output_dir.joinpath(self.fname),
                name=self.name,
                main_page="index",
                illustration="favicon.png",
                title=self.title,
                description=self.description,
                language=self.zim_languages,  # pyright: ignore[reportArgumentType]
                long_description=self.long_description,  # pyright: ignore[reportArgumentType]
                creator=self.creator,
                publisher=self.publisher,
                tags=self.tags,
                scraper=SCRAPER,
                disable_metadata_checks=self.disable_metadata_checks,
            )
            if not self.keep_build_dir:
                logger.info("removing temp folder")
                shutil.rmtree(self.build_dir, ignore_errors=True)

        logger.info("Done Everything")
