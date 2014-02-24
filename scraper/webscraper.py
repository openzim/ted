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
import json


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
            # break


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
            self.extract_video_info(url)
            break


    def extract_video_info(self, url):
        """
        Extract the meta-data of the video:
        Speaker, the profession of the speaker, a short biography of 
        the speaker, the link to a picture of the speaker, title, 
        publishing date, view count, description of the TED talk, 
        direct download link to the video, download link to the subtitle
        files and a link to a thumbnail of the video.
        """
        self.soup = BeautifulSoup(requests.get(url).text)

        json_data = self.soup.select('div.talks-main script')[-1].text
        json_data = ' '.join(json_data.split(',', 1)[1].split(')')[:-1])
        json_data = json.loads(json_data)

        # Extract the speaker of the TED talk
        speaker = json_data['talks'][0]['speaker']

        # Extract the profession of the speaker of the TED talk
        speaker_profession = self.soup.select('div.talk-speaker__description') \
            [0].text.strip()

        # Extract the short biography of the speaker of the TED talk
        speaker_bio = self.soup.select('div.talk-speaker__bio')[0].text.strip()

        # Extract the Url to the picture of the speaker of the TED talk
        speaker_picture = self.soup.select('img.thumb__image')[0]['src']

        # Extract the title of the TED talk
        title = json_data['talks'][0]['title']

        # Extract the description of the TED talk
        description = self.soup.select('p.talk-description')[0].text.strip()

        # Extract the upload date of the TED talk
        date = self.soup.find('div', class_="talk-hero__meta")
        date = date.find_all('span')[1]
        date.strong.replace_with('')
        date = date.text.strip()

        # Extract the view count of the TED talk
        views = self.soup.select('span.talk-sharing__value')[0].text.strip()
        
        # Extract the thumbnail of the of the TED talk video
        thumbnail = json_data['talks'][0]['thumb']

        # Extract the download link of the TED talk video
        video_download = json_data['talks'][0]['nativeDownloads']['medium']

        # Extract the video Id of the TED talk video. 
        # We need this to generate the subtitle page 
        video_id = json_data['talks'][0]['id']

        # Generate a list of all subtitle languages with the link to
        # its subtitles page. It will be in this format:
        # [
        #     {
        #         'languageCode': u'bg',
        #         'link': 'http://www.ted.com/talks/subtitles/id/1907/lang/bg',
        #         'languageName': u'Bulgarian'
        #     }
        # ]
        subtitles = [{'languageName':lang['languageName'], \
        'languageCode':lang['languageCode']} \
        for lang in json_data['talks'][0]['languages']]
        subtitles = utils.build_subtitle_pages(video_id, subtitles)

        print subtitles



if __name__ == '__main__':
    Scraper()
