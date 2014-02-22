#!/usr/bin/env python

from urlparse import urljoin

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
    return 'http://new.ted.com/talks/browse?page=' + str(page)