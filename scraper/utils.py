#!/usr/bin/env python

from urlparse import urljoin

"""
Utils class for the scraper.
"""
__title__ = 'utils'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'


def create_absolute_link(base, rel_url):
    return urljoin(base, rel_url)

def build_video_page(page):
    return 'http://new.ted.com/talks/browse?page=' + str(page)