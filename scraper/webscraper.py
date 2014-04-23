#!/usr/bin/env python

"""
Class for scraping www.TED.com.
"""
__title__ = 'webscraper'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'

import sys
import os.path
import shutil
import distutils.dir_util
import os
from datetime import datetime
from sys import platform as _platform
import requests
from bs4 import BeautifulSoup
from urlparse import urljoin
import utils
import json
from jinja2 import Environment, FileSystemLoader
import urllib
from WebVTTcreator import WebVTTcreator
from collections import defaultdict


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
        if '-d' in sys.argv:
            self.startTime = datetime.now()
        # self.extract_all_video_links()
        # self.dump_data()
        # self.render_video_pages()

        # Print the execution time of the script
        if '-d' in sys.argv:
            print('The script took {} to run'
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
        json_data = self.soup.select('div.talks-main script')
        if len(json_data)==0: return
        json_data = json_data[-1].text
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

        # Extract the length of the TED talk in minutes
        length = int(json_data['talks'][0]['duration'])
        length = divmod(length, 60)[0]

        # Extract the thumbnail of the of the TED talk video
        thumbnail = json_data['talks'][0]['thumb']

        # Extract the download link of the TED talk video
        if not json_data['talks'][0]['nativeDownloads']:
            return
        video_link = json_data['talks'][0]['nativeDownloads']['medium']
        if not video_link:
            return

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
        keywords = self.soup.find(
            'meta', attrs={
                'name': 'keywords'})['content']
        keywords = [key.strip() for key in keywords.split(',')]

        # Extract the ratings list for the TED talk
        ratings = json_data['ratings']

        # Append the meta-data to a list
        self.videos.append([{
            'id': video_id,
            'title': title.encode('ascii', 'ignore'),
            'description': description.encode('ascii', 'ignore'),
            'speaker': speaker.encode('ascii', 'ignore'),
            'speaker_profession': speaker_profession.encode('ascii', 'ignore'),
            'speaker_bio': speaker_bio.encode('ascii', 'ignore'),
            'speaker_picture': speaker_picture.encode('ascii', 'ignore'),
            'date': date.encode('ascii', 'ignore'),
            'thumbnail': thumbnail.encode('ascii', 'ignore'),
            'video_link': video_link.encode('ascii', 'ignore'),
            'length': length,
            'subtitles': subtitles,
            'keywords': keywords,
            'ratings': ratings}])


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
        scraper_dir = build_dir + '/TED/scraper'

        # Check, if the folder exists. Create it, if it doesn't.
        if not os.path.exists(scraper_dir):
            os.makedirs(scraper_dir)

        # Create or override the 'TED.json' file in the build
        # directory with the video data gathered from the scraper.
        with open(scraper_dir + '/TED.json', 'w') as ted_file:
            ted_file.write(data)


    def render_video_pages(self):
        """
        Render static html pages from the scraped video data and
        save the pages in TED/build/{video id}/index.html.
        """
        print 'Rendering template...'

        meta_data_path = os.path.dirname(os.path.abspath(__file__)) \
            + '/../build/TED/scraper/TED.json'

        if not os.path.exists(meta_data_path):
            sys.exit(
                "TED.json file not found. Run the script with the '-m' flag")

        self.load_metadata()

        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('video.html')

        for video in self.videos:
            for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues']:
                if i in video[0]['keywords']:
                    path = build_dir + '/TED/html/' + i + '/' + str(video[0]['id'])
                    if not os.path.exists(path):
                        os.makedirs(path)

                    html = template.render(
                        title=video[0]['title'],
                        speaker=video[0]['speaker'],
                        description=video[0]['description'],
                        languages=video[0]['subtitles'],
                        speaker_bio=video[0]['speaker_bio'].replace('Full bio', ''),
                        date=video[0]['date'],
                        profession=video[0]['speaker_profession'])

                    html = html.encode('utf-8')

                    with open(path + '/' + 'index.html', 'w') as html_page:
                        html_page.write(html)


    def render_welcome_page(self):
        """
        Create the data for the index.html page (the summary page).
        """

        meta_data_path = os.path.dirname(os.path.abspath(__file__)) \
            + '/../build/TED/scraper/TED.json'

        if not os.path.exists(meta_data_path):
            sys.exit(
                "TED.json file not found. Run the script with the '-m' flag")

        self.load_metadata()

        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        env = Environment(loader=FileSystemLoader('templates'))
        template = env.get_template('welcome.html')

        for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues']:
            path = build_dir + '/TED/html/' + i + '/'
            if not os.path.exists(path):
                os.makedirs(path)

            with open(path + 'index.html', 'w') as html_page:
                html_page.write(self.create_welcome_page_data(i, template))


    def create_welcome_page_data(self, keyword, template):
        """
        Create the data for the index.html page (the summary page).
        """
        teds = []
        languages = []
        languagelist = []

        for video in self.videos:
            if keyword in video[0]['keywords']:
                teds.append(video)
            else:
                continue

            for language in video[0]['subtitles']:
                languages.append({'languageCode': language['languageCode'],
                                  'languageName': language['languageName']})

                language_code = language['languageCode']

                languages_already_in = []
                for i in languagelist:
                    languages_already_in.append(i.keys()[0])

                if not language_code in languages_already_in:
                    lang_dict = {language_code: []}
                    lang_dict[language_code].append(video)
                    languagelist.append(lang_dict)
                else:
                    lst = languagelist[
                        languages_already_in.index(language_code)]
                    lst[language_code].append(video)

        sorted_languages = []
        for x in languages:
            if x not in sorted_languages:
                sorted_languages.append(x)

        languages = sorted(sorted_languages, key=lambda x: x['languageName'])

        html = template.render(
            languages=languages,
            teds=teds,
            languagelist=languagelist)

        html = html.encode('utf-8')

        return html


    def copy_files_to_rendering_directory(self):
        """
        Copy files from the /scraper directory to the /html/{zimfile} directory.
        """
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        templates_dir = os.path.dirname(
            os.path.abspath(__file__)) + '/../scraper/templates'

        for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues' ]:
            copy_path = build_dir + '/TED/html/' + i 
            if os.path.exists(templates_dir + '/CSS'):
                distutils.dir_util.copy_tree(templates_dir + '/CSS', copy_path+'/CSS')
            if os.path.exists(templates_dir + '/JS'):
                distutils.dir_util.copy_tree(templates_dir + '/JS', copy_path+'/JS')


        for video in self.videos:
            for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues']:
                if i in video[0]['keywords']:
                    path = build_dir + '/TED/scraper/' + str(video[0]['id'])
                    copy_path = build_dir + '/TED/html/' + i + '/' + str(video[0]['id'])
                    thumbnail = path + '/thumbnail.jpg'
                    subs = path + '/subs/'
                    speaker = path + '/speaker.jpg'
                    video_ = path + '/video.mp4'

                    if os.path.exists(thumbnail):
                        shutil.copy(thumbnail, copy_path)

                    if os.path.exists(subs):
                        distutils.dir_util.copy_tree(subs, copy_path + '/subs')

                    if os.path.exists(speaker):
                        shutil.copy(speaker, copy_path)


    def generate_category_data(self):
        """
        Generate the json page data for every category.
        """

        self.load_metadata()
        video_list = defaultdict(list)
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'

        for video in self.videos:
            for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues']:
                if i in video[0]['keywords']:
                    json_data = \
                        {'languages': [lang['languageCode'] for lang in video[0]['subtitles']],
                         'id': video[0]['id'],
                         'description': video[0]['description'],
                         'title': video[0]['title'],
                         'speaker': video[0]['speaker'],
                         }
                    video_list[i].append(json_data)

        for k, v in video_list.items():
            path = build_dir + '/TED/html/' + k + '/JS'
            
            if not os.path.exists(path):
                os.makedirs(path)
            
            with open(path + '/data.js', 'w') as page_file:
                json_data = json.dumps(v, indent=4, separators=(',', ': '))
                json_data = 'json_data = ' + json_data 
                page_file.write(json_data)


    def resize_thumbnails(self):
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build/TED/html/'
        thumbnails = [os.path.join(root, name)
                for root, dirs, files in os.walk(build_dir)
                for name in files
                if name == 'thumbnail.jpg']

        for thumbnail in thumbnails:
            resize_image(thumbnail)
            print 'Resizing ' + thumbnail


    def encode_videos(self):
        """
        Encode the videos from mp4 to webm. We will use ffmpeg over the 
        command line for this. There is a static binary version
        in the kiwix-other/TED/ directory, that we will use on macs. 
        """

        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'

        self.load_metadata()
        for video in self.videos:
            for i in ['technology', 'entertainment', 'design', 'business', 'science', 'global issues']:
                if i in video[0]['keywords']:
                    path = build_dir + '/TED/scraper/' + str(video[0]['id'])
                    copy_path = build_dir + '/TED/html/' + \
                        i + '/' + str(video[0]['id'])

                    video_ = path + '/video.mp4'

                    if  os.path.exists(copy_path +'/video.webm'):
                        print 'Video already encoded. Skipping.'
                        continue

                    if os.path.exists(video_):
                        self.convert_video_and_move_to_rendering(
                            video_, copy_path +'/video.webm')
                        print 'Converting Video... ' + video[0]['title']



    def convert_video_and_move_to_rendering(self, from_path, to_path):
        ffmpeg = ''
        if _platform == "linux" or _platform == "linux2":
            ffmpeg = 'ffmpeg'
        elif _platform == "darwin":
            ffmpeg = os.path.dirname(os.path.abspath(__file__)) + '/../ffmpeg'


        command = ''.join(("""{} -i "{}" -codec:v libvpx -quality best -cpu-used 0 -b:v 300k""",
            """ -qmin 30 -qmax 42 -maxrate 300k -bufsize 1000k -threads 8 -vf scale=480:-1""",
            """ -codec:a libvorbis -b:a 128k -f webm "{}" """)).format(
                ffmpeg, from_path, to_path)

        os.system(command)

    def download_video_data(self):
        """
        Download all the TED talk videos and the meta-data for it.
        Save the videos in the TED/build/{video id}/video.mp4.
        Save the thumbnail for the video in
        TED/build/{video id}/thumbnail.jpg.
        Save the image of the speaker in TED/build/{video id}/speaker.jpg.
        """

        self.load_metadata()
        for video in self.videos:

            build_dir = os.path.dirname(
                os.path.abspath(__file__)) + '/../build'
            path = build_dir + '/TED/scraper/' + str(video[0]['id'])
            if not os.path.exists(path):
                os.makedirs(path)

            if not os.path.exists(path+ '/video.mp4'):
                print 'Downloading video... ' + video[0]['title']
                urllib.urlretrieve(
                    video[0]['video_link'],
                    path +
                    '/' +
                    "video.mp4")
            else: print 'video.mp4 already exist. Skipping video ' + video[0]['title'] 

            # download an image of the speaker
            if not os.path.exists(path+ '/speaker.jpg'):
                print 'Downloading speaker image... ' + video[0]['title']
                urllib.urlretrieve(
                    video[0]['speaker_picture'],
                    path +
                    '/' +
                    "speaker.jpg")
            else: print 'speaker.jpg already exist. Skipping video ' + video[0]['title'] 

            # download the thumbnail of the video
            if not os.path.exists(path+ '/thumbnail.jpg'):
                print 'Downloading video thumbnail... ' + video[0]['title']
                urllib.urlretrieve(
                    video[0]['thumbnail'],
                    path +
                    '/' +
                    'thumbnail.jpg')
            else: print 'thumbnail.jpg already exist. Skipping video ' + video[0]['title'] 


    def download_subtitles(self):
        """
        Download the subtitle files, generate a WebVTT file
        and save the subtitles in
        TED/build/{video id}/subs_{language code}.vtt.
        """
        self.load_metadata()
        for video in self.videos:
            build_dir = os.path.dirname(
                os.path.abspath(__file__)) + '/../build'
            path = build_dir + '/TED/scraper/' + str(video[0]['id']) + '/subs'
            if not os.path.exists(path):
                os.makedirs(path)
            else:
                print 'Subtitles already exist. Skipping video ' + video[0]['title'] 
                continue
            # download subtitles
            print 'Downloading subtitles... ' + video[0]['title']
            for subtitle in video[0]['subtitles']:
                subtitle_file = WebVTTcreator(
                    
                    subtitle['link'],
                    11820).get_content()
                subtitle_file = subtitle_file.encode('utf-8')
                with open(path + '/' + 'subs_{}.vtt'.format(subtitle['languageCode']), 'w') as sub_file:
                    sub_file.write(subtitle_file)


    def load_metadata(self):
        """
        Load the dumped json meta-data file.
        """
        build_dir = os.path.dirname(os.path.abspath(__file__)) + '/../build'
        meta_data_path = os.path.dirname(os.path.abspath(__file__)) \
            + '/../build/TED/scraper/TED.json'
        with open(meta_data_path) as data_file:
            self.videos = json.load(data_file)


def resize_image(image_path):
    from PIL import Image
    image = Image.open(image_path)
    w, h = image.size
    image = image.resize((248, 187))
    image.save(image_path)


if __name__ == '__main__':
    Scraper().generate_category_data()
