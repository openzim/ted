#!/usr/bin/env python

"""
Class for scraping www.TED.com.
"""
__title__ = 'webscraper'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'

import requests
from bs4 import BeautifulSoup
from urlparse import urljoin
import utils


class Scraper():

    BASE_URL = 'http://new.ted.com/talks/browse'
    soup = None
    pages = None


    def __init__(self):
        self.pages = self.extract_page_number()
        self.extract_videos()
        

    def extract_page_number(self):
        self.soup = BeautifulSoup(requests.get(self.BASE_URL).text)
        self.pages = self.soup.select('div.pagination a.pagination__item')[-1]


    def extract_videos(self):
        videos = []

        for video in self.soup.select('div.row div.media__image a'):
            print utils.create_absolute_link(self.BASE_URL, video['href'])
            print '\n\n'



if __name__ == '__main__':
    Scraper()
