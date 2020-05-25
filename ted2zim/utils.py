#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import time
import json

import requests


def update_subtitles_list(video_id, language_list):
    """ adds `link` to each language dict containing the subtitle url """

    for language in language_list:
        language[
            "link"
        ] = f"https://www.ted.com/talks/subtitles/id/{video_id}/lang/{language['languageCode']}"

    return language_list


def download_link(url):
    for attempt in range(1, 6):
        time.sleep(1)  # delay requests
        req = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if req.status_code != 429:
            return req
        time.sleep(30 * attempt)  # wait upon failure
    raise ConnectionRefusedError(f"Failed to download {url} after {attempt} attempts")


class WebVTT:

    """ TED JSON subtitles to WebVTT """

    def __init__(self, url):
        self.url = url

    def convert(self):
        """ download and convert its URL to WebVTT text """
        req = download_link(self.url)

        if req.status_code == 404:
            return None
        try:
            source_subtitles = req.json()
        except json.JSONDecodeError:
            return None

        return self.json_to_vtt(source_subtitles)

    @staticmethod
    def miliseconds_to_human(miliseconds):
        """ Human/VTT formatted time code from miliseconds

            ex: 00:00:00.000 """

        hours, remainder = divmod(miliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        seconds, miliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{miliseconds:03}"

    @staticmethod
    def json_to_vtt(json_subtitles, offset=11820):
        """ WebVTT string from TED JSON subtitles list

            TED format: {"captions": [
                {'duration': 1726,
                 'content': 'And more concretely,',
                 'startOfParagraph': False,
                 'startTime': 382083
                },
            ]}

            https://en.wikipedia.org/wiki/WebVTT """

        document = "WEBVTT\n\n"
        if "captions" in json_subtitles:
            for subtitle in json_subtitles["captions"]:
                startTime = int(subtitle["startTime"]) + offset
                duration = int(subtitle["duration"])
                content = subtitle["content"].strip()

                document += (
                    WebVTT.miliseconds_to_human(startTime)
                    + " --> "
                    + WebVTT.miliseconds_to_human(startTime + duration)
                    + "\n"
                )
                document += content + "\n\n"
        return document
