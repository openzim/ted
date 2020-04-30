#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

# Class for creating a WebVTT subtitles file from the
# JSON subtitles format from www.TED.com

import json
import requests
import time


class WebVTTcreator:

    WebVTTdocument = "WEBVTT\n\n"

    def __init__(self, url, offset=0):

        # Loads the json representation of the subtitles form the given
        # Url and decodes it.
        # Creates a WebVtt document off it and saves it in a .vtt file.
        dl_ok = False
        while not dl_ok:
            r = requests.get(url)
            if r.status_code == 429:
                time.sleep(30)
            elif r.status_code == 404:
                return False
            else:
                dl_ok = True
                subtitles_json = r.text
        if self.is_json(subtitles_json):
            self.create_WebVtt(json.loads(subtitles_json), offset)
        else:
            return False

    def create_WebVtt(self, json, offset):

        # Create the WebVTT file from the given decoded json.
        # Structure of a WebVTT file:

        # WebVTT

        # 00:00:00.000 --> 00:00:00.000
        # [start time --> end time]
        # 'content'
        if "captions" in json:
            for subtitle in json["captions"]:
                startTime = int(subtitle["startTime"]) + offset
                duration = int(subtitle["duration"])
                content = subtitle["content"]

                self.WebVTTdocument += (
                    self.time_string(startTime)
                    + " --> "
                    + self.time_string(startTime + duration)
                    + "\n"
                )
                self.WebVTTdocument += content + "\n\n"

    def time_string(self, ms):

        # Create the '00:00:00.000' string representation of the time.
        hours, remainder = divmod(ms, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        seconds, miliseconds = divmod(remainder, 1000)
        return "%.2d:%.2d:%.2d.%.3d" % (hours, minutes, seconds, miliseconds)

    def get_content(self):
        return self.WebVTTdocument

    def is_json(self, json_data):
        try:
            json.loads(json_data)
        except ValueError:
            return False
        return True


if __name__ == "__main__":
    WebVTTcreator("https://www.ted.com/talks/subtitles/id/1907/lang/en")
