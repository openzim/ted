from ted2zim.__about__ import __version__
import json
from bs4 import BeautifulSoup
import requests
from pathlib import Path
from ted2zim.constants import REQUESTS_TIMEOUT, SEARCH_URL, get_logger
from ted2zim.utils import request_url
from typing import Any, NamedTuple
import math

log = get_logger()

PER_PAGE = 24
DATA_PATH = Path("output/data")


class Video:
    slug: str
    duration: float
    topics: list["Topic"]

    def __init__(self, slug: str, duration: str | float):
        self.slug = slug
        if isinstance(duration, str):
            self.duration = float(duration)
        else:
            self.duration = duration
        self.topics = []

    def add_topic(self, topic: "Topic"):
        self.topics.append(topic)
        topic.videos.append(self)


class Topic:
    name: str
    videos: list[Video]

    def __init__(self, name: str):
        self.name = name
        self.videos = []

    def add_video(self, video: Video):
        self.videos.append(video)
        video.topics.append(self)


def get_all_videos_of_topic(topic):
    """generates a search results and returns the total number of videos scraped"""

    all_videos = []
    page = 0
    while True:
        result = query_search_engine(topic, page)
        slugs = [
            {"slug": hit["slug"], "duration": hit["duration"]}
            for hit in result.json()["results"][0]["hits"]
        ]
        all_videos.extend(slugs)
        if len(slugs) < PER_PAGE:
            break
        page += 1
    return all_videos


def query_search_engine(topic, page):
    log.info(f"Fetching page {page} of topic {topic}")
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
                "hitsPerPage": PER_PAGE,
                "maxValuesPerFacet": 500,
                "page": page,
                "query": "",
                "tagFilters": "",
            },
        },
    ]
    return request_url(SEARCH_URL, data)


def main(force: bool = False):
    log.info(f"Starting cluster {__version__}")
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    talks_file = DATA_PATH / "talks.json"
    if force or not talks_file.exists():
        data = [
            {
                "indexName": "coyote_models_acme_videos_alias_21e1372f285984be956cd03b7ad3406e",
                "params": {
                    "attributeForDistinct": "objectID",
                    "distinct": 1,
                    "facets": ["subtitle_languages", "tags"],
                    "highlightPostTag": "__/ais-highlight__",
                    "highlightPreTag": "__ais-highlight__",
                    "hitsPerPage": 1,
                    "maxValuesPerFacet": 500,
                    "page": 0,
                    "query": "",
                    "tagFilters": "",
                },
            }
        ]
        talks = request_url(SEARCH_URL, data).content
        talks_file.write_bytes(talks)

    topics_list = json.loads(talks_file.read_text())["results"][0]["facets"][
        "tags"
    ].keys()
    log.info(f"{len(topics_list)} topics found")
    for topic_name in topics_list:
        # for topic in ["tv"]:
        topic_file = DATA_PATH / f"{topic_name}.json"
        if not force and topic_file.exists():
            continue
        videos = get_all_videos_of_topic(topic_name)
        log.info(f"{len(videos)} videos found in topic {topic_name}")
        topic_file.write_text(json.dumps({"slugs": videos}, indent=2))

    # Loading all topics and videos in appropriate data structure
    excluded_topics = [
        "ted conference",
        "ted-ed",
        "tedmed",
        "tedx",
        "ted fellows",
        "ted en español",
        "ted prize",
        "ted membership",
        "ted residency",
        "ted books",
        "ted connects",
    ]
    # included_topics = [
    #     "design",
    #     "business",
    #     "global issues",
    #     "entertainment",
    #     "science",
    #     "technology",
    # ]
    topics: list[Topic] = []
    videos: dict[str, Video] = {}
    for topic_name in topics_list:
        if topic_name in excluded_topics:
            continue
        # if topic_name not in included_topics:
        #     continue

        topic_file = DATA_PATH / f"{topic_name}.json"
        topic_data = json.loads(topic_file.read_text())
        # if len(topic_data["slugs"]) > 500 or len(topic_data["slugs"]) < 10:
        #     continue
        topic = Topic(name=topic_name)
        topics.append(topic)
        print(f'{topic_name},{len( topic_data["slugs"])}')
        for video_data in topic_data["slugs"]:
            if not video_data["slug"] in videos:
                videos[video_data["slug"]] = Video(
                    slug=video_data["slug"], duration=video_data["duration"]
                )
            video = videos[video_data["slug"]]
            if (
                not video in topic.videos
            ):  # there are some duplicates in a single topic!
                topic.add_video(video)

    total = round(sum(video.duration for video in videos.values()))
    log.info(f"{len(videos)} videos found (total duration: {get_time_str(total)})")

    # avg_topics_per_video = sum(len(video.topics) for video in videos.values()) / len(
    #     videos
    # )
    # max_topics_per_video = max(len(video.topics) for video in videos.values())
    # log.info(f"avg_topics_per_video: {avg_topics_per_video}")
    # log.info(f"max_topics_per_video: {max_topics_per_video}")
    # for video in videos.values():
    #     if len(video.topics) == 28:
    #         log.info(f"max topics: {video.slug}")
    # exit()

    # Compute the best set of topics to consider to cover all videos
    videos_to_process: list[Video] = []
    videos_to_process.extend(videos.values())
    topics_left: list[Topic] = []
    topics_left.extend(topics)

    topics_left = sorted(topics_left, key=lambda topic: len(topic.videos), reverse=True)

    count = 0
    while len(videos_to_process) > 0:
        best_topic = topics_left[0]
        topics_left.remove(best_topic)
        cnt_original_videos = 0
        for video in best_topic.videos:
            if video in videos_to_process:
                cnt_original_videos += 1
                videos_to_process.remove(video)

        if cnt_original_videos == 0:
            continue
        count += 1
        log.info(
            f"{count} - {best_topic.name}: {len(best_topic.videos)} ({cnt_original_videos} original, {len(videos_to_process)} left)"
        )

    # count = 0
    # while len(videos_to_process) > 0:
    # while len(topics_left) > 0:
    #     best_topic = sorted(
    #         topics_left,
    #         key=lambda topic: sum(
    #             1 if video in videos_to_process else 0 for video in topic.videos
    #         ),
    #         reverse=True,
    #     )[0]
    #     best_topic = sorted(
    #         topics_left,
    #         key=lambda topic: len(topic.videos),
    #         reverse=True,
    #     )[0]
    #     count += 1
    #     log.info(
    #         f"{count} - {best_topic.name} with {len(best_topic.videos)} videos, "
    #         f"{sum(1 if video in videos_to_process else 0 for video in best_topic.videos)}"
    #         " original videos (not yet in another best topic)"
    #     )
    #     for video in best_topic.videos:
    #         if video in videos_to_process:
    #             videos_to_process.remove(video)
    #     topics_left.remove(best_topic)
    #     nb_videos = len(best_topic.videos)
    #     nb_orig = nb_videos
    #     test_next = True
    #     while test_next and nb_videos < 500:
    #         test_next = False
    #         matching_topics = sorted(
    #             topics_left,
    #             key=lambda topic: sum(
    #                 0 if video in best_topic.videos else 1 for video in topic.videos
    #             ),
    #         )
    #         for match_topic in matching_topics:
    #             nb_new = sum(
    #                 0 if video in best_topic.videos else 1
    #                 for video in match_topic.videos
    #             )
    #             if nb_new > len(match_topic.videos) / 2:
    #                 continue
    #             nb_videos = nb_videos + nb_new
    #             if nb_videos > 500 or nb_new > nb_orig / 2:
    #                 break
    #             log.info(
    #                 f"  + {match_topic.name} with {len(match_topic.videos)} videos, {nb_new} original ones"
    #             )
    #             for video in match_topic.videos:
    #                 if video in videos_to_process:
    #                     videos_to_process.remove(video)
    #             topics_left.remove(match_topic)
    #             test_next = True
    #     log.info(f"  Total: {nb_videos}")

    log.info("DONE")


def get_time_str(total_seconds: int) -> str:
    time_str = ""
    if total_seconds > 3600 * 24:
        days = math.floor(total_seconds / (3600 * 24))
        total_seconds -= days * 3600 * 24
        time_str += f"{days} days "
    if total_seconds > 3600:
        hours = math.floor(total_seconds / 3600)
        total_seconds -= hours * 3600
        time_str += f"{hours} hours "
    if total_seconds > 60:
        mins = math.floor(total_seconds / 60)
        total_seconds -= mins * 60
        time_str += f"{mins} mins "
    if total_seconds > 0:
        time_str += f"{total_seconds} secs"

    return time_str


if __name__ == "__main__":
    main()  # True)
