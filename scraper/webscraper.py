#!/usr/bin/env python

"""
Class for scraping www.TED.com.
"""
__title__ = 'webscraper'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'

import sys
import os.path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from urlparse import urljoin
import utils
import json
from jinja2 import Environment, FileSystemLoader
import urllib 
from WebVTTcreator import WebVTTcreator


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
        # Time the script, if the script has been called with a '-d' flag
        if '-d' in sys.argv: self.startTime = datetime.now()
        
        # self.extract_all_video_links()
        # self.dump_data()
        # self.render_html_pages()

        # Print the execution time of the script
        if '-d' in sys.argv: print('The script took {} to run' \
            .format(datetime.now() - self.startTime))
        

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
        for page in range(1, self.extract_page_number()):
            url = utils.build_video_page(page)
            html = requests.get(url).text
            self.soup = BeautifulSoup(html)
            self.extract_videos()
            print 'Finished scraping page {}'.format(page)
            break


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
            self.extract_video_info(url)


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

        # Every TED video page has a <script>-tag with a Javascript
        # object with JSON in it. We will just stip away the object
        # signature and load the json to extract meta-data out of it.
        json_data = self.soup.select('div.talks-main script')[-1].text
        json_data = ' '.join(json_data.split(',', 1)[1].split(')')[:-1])
        json_data = json.loads(json_data)

        # Extract the speaker of the TED talk
        speaker = json_data['talks'][0]['speaker']

        # Extract the profession of the speaker of the TED talk
        speaker_profession = \
            self.soup.select('div.talk-speaker__description')[0].text.strip()

        # Extract the short biography of the speaker of the TED talk
        speaker_bio = self.soup.select('div.talk-speaker__bio')[0].text.strip()

        # Extract the Url to the picture of the speaker of the TED talk
        speaker_img = self.soup.select('img.thumb__image')[0]['src']

        # Extract the title of the TED talk
        title = json_data['talks'][0]['title']

        # Extract the description of the TED talk
        description = self.soup.select('p.talk-description')[0].text.strip()

        # Extract the upload date of the TED talk
        date = self.soup.find('div', class_="talk-hero__meta")
        date = date.find_all('span')[1]
        date.strong.replace_with('')
        date = date.text.strip()

        # Extract the length of the TED talk in minutes
        length = int(json_data['talks'][0]['duration'])
        length = divmod(length, 60)[0]

        # Extract the view count of the TED talk
        views = self.soup.select('span.talk-sharing__value')[0].text.strip()

        # Extract the thumbnail of the of the TED talk video
        thumbnail = json_data['talks'][0]['thumb']

        # Extract the download link of the TED talk video
        video_link = json_data['talks'][0]['nativeDownloads']['medium']

        # Extract the video Id of the TED talk video.
        # We need this to generate the subtitle page.
        video_id = json_data['talks'][0]['id']

        # Generate a list of all subtitle languages with the link to
        # its subtitles page. It will be in this format:
        # [
        #     {
        #         'languageCode': u'en',
        #         'link': 'http://www.ted.com/talks/subtitles/id/1907/lang/en',
        #         'languageName': u'English'
        #     }
        # ]
        subtitles = [{'languageName': lang['languageName'],
                      'languageCode':lang['languageCode']}
                     for lang in json_data['talks'][0]['languages']]
        subtitles = utils.build_subtitle_pages(video_id, subtitles)

        # Extract the keywords for the TED talk
        keywords = self.soup.find('meta', attrs={'name':'keywords'})['content']
        keywords = [key.strip() for key in keywords.split(',')]
        keywords.remove('TED')

        # Extract the ratings list for the TED talk
        ratings = json_data['ratings']

        # Append the meta-data to a list
        self.videos.append([{
            'id':video_id,
            'title':title.encode('ascii', 'ignore'), 
            'description':description.encode('ascii', 'ignore'),
            'speaker':speaker.encode('ascii', 'ignore'), 
            'speaker_profession':speaker_profession.encode('ascii', 'ignore'), 
            'speaker_bio':speaker_bio.encode('ascii', 'ignore'), 
            'speaker_img':speaker_img.encode('ascii', 'ignore'),  
            'date':date.encode('ascii', 'ignore'),
            'views':views.encode('ascii', 'ignore'), 
            'thumbnail':thumbnail.encode('ascii', 'ignore'), 
            'video_link':video_link.encode('ascii', 'ignore'), 
            'length':length,
            'subtitles':subtitles,
            'keywords':keywords,
            'ratings':ratings}])

        
    def dump_data(self):
        """
        Dump all the data about every TED talk in a json file 
        inside the 'build' folder.
        """
        # Prettified json dump 
        data = json.dumps(self.videos, indent=4, separators=(',', ': '))       

        # Get the direction of the 'build' folder. 
        # This folder my or may not exist yet.
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'

        # Check, if the folder exists. Create it, if it doesn't.
        if not os.path.exists(build_dir):
            os.makedirs(build_dir)
        
        # Create or override the 'TED.json' file in the build 
        # directory with the video data gathered from the scraper.
        with open(build_dir + '/TED.json', 'w') as ted_file:
             ted_file.write(data)


    def render_html_pages(self):
        """
        Render static html pages from the scraped video data and
        save the pages in TED/build/{video id}/index.html. 
        """
        print 'Rendering template...'

        meta_data_path = build_dir = os.path.dirname(os.path.abspath(__file__)) \
            + '/../build/TED.json'

        if not os.path.isfile(meta_data_path): 
            sys.exit("TED.json file not found. Run the script with the '-m' flag")

        self.load_json()
            
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('video.html')

        for video in self.videos:
            path = build_dir + '/TED/' + str(video[0]['id'])
            if not os.path.exists(path):
                os.makedirs(path)

            html = template.render(
                title=video[0]['title'],
                speaker=video[0]['speaker'],
                description=video[0]['description'],
                languages=video[0]['subtitles'], 
                views=video[0]['views'],
                speaker_bio=video[0]['speaker_bio'],
                date=video[0]['date'],
                profession=video[0]['speaker_profession'])

            html =  html.encode('utf-8')

            with open(path + '/' + 'index.html', 'w') as html_page:
                 html_page.write(html)

        
    def download_video_data(self):
        """
        Download all the TED talk videos and the meta-data for it.
        Save the videos in the TED/build/{video id}/video.mp4.
        Save the thumbnail for the video in 
        TED/build/{video id}/thumbnail.jpg.
        Save the image of the speaker in TED/build/{video id}/speaker.jpg.
        """

        self.load_json()
        for video in self.videos:

            build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
            path = build_dir + '/TED/' + str(video[0]['id'])

            print 'Downloading video...'
            urllib.urlretrieve(video[0]['video_link'], path + '/' + "video.mp4")

            # download an image of the speaker 
            print 'Downloading speaker image...'
            urllib.urlretrieve(video[0]['speaker_img'], path + '/' + "speaker.jpg")

            # download the thumbnail of the video 
            print 'Downloading video thumbnail...'
            urllib.urlretrieve(video[0]['thumbnail'], path + '/' + "thumbnail.jpg")            


    def download_subtitles(self):
        """
        Download the subtitle files, generate a WebVTT file
        and save the subtitles in 
        TED/build/{video id}/subs_{language code}.vtt.
        """
        self.load_json()
        for video in self.videos:
            build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
            path = build_dir + '/TED/' + str(video[0]['id'])
            # download subtitles
            print 'Downloading subtitles...'
            for subtitle in video[0]['subtitles']:
                subtitle_file = WebVTTcreator(subtitle['link'], 11820).get_content()
                subtitle_file = subtitle_file.encode('utf-8')
                with open(path + '/' + 'subs_{}.vtt'.format(subtitle['languageCode']), 'w') as sub_file:
                        sub_file.write(subtitle_file)
                    

    def load_json(self):
        """
        Load the dumped json meta-data file.
        """
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        meta_data_path = build_dir = os.path.dirname(os.path.abspath(__file__)) \
            + '/../build/TED.json'
        with open(meta_data_path) as data_file:    
            self.videos = json.load(data_file)

        

if __name__ == '__main__':
    Scraper()
