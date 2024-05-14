import contextlib
import json
import pathlib
import tempfile
import time
from http import HTTPStatus

import requests

from ted2zim.constants import BASE_URL, REQUESTS_TIMEOUT


def has_argument(arg_name, all_args):
    """whether --arg_name is specified in all_args"""
    return list(filter(lambda x: x.startswith(f"--{arg_name}"), all_args))


def update_subtitles_list(video_id, language_list):
    """adds `link` to each language dict containing the subtitle url"""

    for language in language_list:
        language["link"] = (
            f"https://www.ted.com/talks/subtitles/id/{video_id}/lang/{language['languageCode']}"
        )

    return language_list


def request_url(url, json_data=None):
    """performs an HTTP request and returns the response, either GET or POST

    - json_data is used as POST body when passed, otherwise a GET request is done
    - request is retried 5 times, with a 30*attemp_no secs pause between retries
    - a pause of 1 sec is done before every request (including first one)
    """

    if url == f"{BASE_URL}playlists/57":
        url = f"{BASE_URL}playlists/57/björk_6_talks_that_are_music"
    max_attempts, attempt = 5, 1
    while True:
        try:
            time.sleep(1)  # delay requests
            if json_data:
                req = requests.post(
                    url,
                    headers={"User-Agent": "Mozilla/5.0"},
                    json=json_data,
                    timeout=REQUESTS_TIMEOUT,
                )
            else:
                req = requests.get(
                    url, headers={"User-Agent": "Mozilla/5.0"}, timeout=REQUESTS_TIMEOUT
                )
            req.raise_for_status()
            return req
        except Exception as exc:
            if req.status_code == HTTPStatus.NOT_FOUND:
                raise exc
            time.sleep(30 * attempt)  # wait upon failure

        if attempt < max_attempts:
            attempt += 1
            continue

        if json_data:
            raise ConnectionRefusedError(
                f"Failed to query {url} after {attempt} attempts (HTTP "
                f"{req.status_code}); sent data was: {json.dumps(json_data)}"
            )
        else:
            raise ConnectionRefusedError(
                f"Failed to download {url} after {attempt} attempts "
                f"(HTTP {req.status_code})"
            )


class WebVTT:
    """TED JSON subtitles to WebVTT"""

    def __init__(self, url):
        self.url = url

    def convert(self, offset):
        """download and convert its URL to WebVTT text"""
        req = request_url(self.url)

        if req.status_code == HTTPStatus.NOT_FOUND:
            return None
        try:
            source_subtitles = req.json()
        except json.JSONDecodeError:
            return None

        return self.json_to_vtt(source_subtitles, offset)

    @staticmethod
    def miliseconds_to_human(miliseconds):
        """Human/VTT formatted time code from miliseconds

        ex: 00:00:00.000"""

        hours, remainder = divmod(miliseconds, 3600000)
        minutes, remainder = divmod(remainder, 60000)
        seconds, miliseconds = divmod(remainder, 1000)
        return f"{hours:02}:{minutes:02}:{seconds:02}.{miliseconds:03}"

    @staticmethod
    def json_to_vtt(json_subtitles, offset):
        """WebVTT string from TED JSON subtitles list

        TED format: {"captions": [
            {'duration': 1726,
             'content': 'And more concretely,',
             'startOfParagraph': False,
             'startTime': 382083
            },
        ]}

        https://en.wikipedia.org/wiki/WebVTT"""

        document = "WEBVTT\n\n"
        if "captions" in json_subtitles:
            for subtitle in json_subtitles["captions"]:
                start_time = int(subtitle["startTime"]) + offset
                duration = int(subtitle["duration"])
                content = subtitle["content"].strip()

                document += (
                    WebVTT.miliseconds_to_human(start_time)
                    + " --> "
                    + WebVTT.miliseconds_to_human(start_time + duration)
                    + "\n"
                )
                document += content + "\n\n"
        return document


@contextlib.contextmanager
def get_temp_fpath(**kwargs):
    fpath = None
    try:
        fh = tempfile.NamedTemporaryFile(delete=False, **kwargs)
        fpath = pathlib.Path(fh.name)
        fh.close()
        yield fpath
    finally:
        if fpath:
            fpath.unlink()


def get_main_title(titles, locale_ted_codes: list[str]):
    """main title from list of titles dict based on language pref with fallback"""
    missing = "n/a"
    if not titles:
        return missing

    def get_for(lang: str):
        filtered = [title["text"] for title in titles if title["lang"] == lang]
        if filtered:
            return filtered[0]

    for code in [*locale_ted_codes, "default", "en"]:
        title = get_for(code)
        if title:
            return title

    return missing
