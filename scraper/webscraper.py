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

    # The base Url. The link gives you a grid of all TED talks. 
    BASE_URL = 'http://new.ted.com/talks/browse'
    # BeautifulSoup instance
    soup = None
    # Page count
    pages = None
    # List of links to all TED talks
    videos = []


    def __init__(self):
        """
        Extract number of video pages. Generate the specific
        video page from it and srape it.
        """
        self.pages = self.extract_page_number()
        self.extract_all_video_links()
        

    def extract_page_number(self):
        """
        Extract the number of video pages by looking at the 
        pagination div at the bottom. Select all <a>-tags in it and 
        return the last element in the list. That's our total count
        """
        self.soup = BeautifulSoup(requests.get(self.BASE_URL).text)
        pages = self.soup.select('div.pagination a.pagination__item')[-1]
        return int(pages.text)
        

    def extract_all_video_links(self):
        """
        This method will build the specifiv video site by appending 
        the page number to the 'page' parameter to the url.
        We will iterate through every page and extract every 
        video link. The video link is extracted in `extract_videos()`.
        """
        for page in range(1, self.pages):
            url = utils.build_video_page(page)
            html = requests.get(url).text
            self.soup = BeautifulSoup(html)
            self.extract_videos()
            print self.videos


    def extract_videos(self):
        """
        All videos are embedded in a <div> with the class name 'row'. 
        We are searching for the div inside this div, that has an <a>-tag
        with the class name 'media__image', because this is the relative
        link to the representative TED talk. We have to turn this relative
        link to an absolute link. This is done through the `utils` class.
        """
        for video in self.soup.select('div.row div.media__image a'):
            url = utils.create_absolute_link(self.BASE_URL, video['href'])
            self.videos.append(url)


if __name__ == '__main__':
    Scraper()
