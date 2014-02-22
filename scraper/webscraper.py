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
    videos = []


    def __init__(self):
        self.pages = self.extract_page_number()
        self.extract_all_video_links()
        

    def extract_page_number(self):
        self.soup = BeautifulSoup(requests.get(self.BASE_URL).text)
        pages = self.soup.select('div.pagination a.pagination__item')[-1]
        return int(pages.text)
        

    def extract_all_video_links(self):
        for page in range(1, self.pages):
            url = utils.build_video_page(page)
            html = requests.get(url).text
            self.soup = BeautifulSoup(html)
            self.extract_videos()
            print self.videos


    def extract_videos(self):
        for video in self.soup.select('div.row div.media__image a'):
            url = utils.create_absolute_link(self.BASE_URL, video['href'])
            self.videos.append(url)




if __name__ == '__main__':
    Scraper()
