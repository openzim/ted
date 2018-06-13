#!/usr/bin/env python

from urlparse import urljoin
from time import sleep
import requests

"""
Utils class for the scraper.
"""
__title__ = 'utils'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'


def create_absolute_link(base, rel_url):
    """
    Creates a absolute Url out of a relative link.
    Will return the given second parameter, if it's already
    an absolute link.
    """
    return urljoin(base, rel_url)


def build_video_page(page):
    """
    Url builder for TED talk video pages.
    Appending the page number to the 'page' parameter.
    """
    return 'http://new.ted.com/talks/browse?page={}'.format(page)


def build_subtitle_pages(video_id, language_list):
    """
    Url builder for the json subtitles page for TED talks.
    Building it from the video specific Id and the language
    we want the subtitles in.
    """

    for language in language_list:
        page = 'http://www.ted.com/talks/subtitles/id/{}/lang/{}' \
            .format(video_id, language['languageCode'])
        language['link'] = page

    return language_list

def download_from_site(url):
    headers = {
        'User-Agent': 'Mozilla/5.0',
    }
    for i in range(5):
        sleep(1) #delay requests
        r = requests.get(url, headers = headers)
        if r.status_code != 429:
            return r
        sleep(30*(i+1)) #if fail we wait
    raise ConnectionRefusedError("Too many retry fail")
