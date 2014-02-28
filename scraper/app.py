#!/usr/bin/env python

"""
Class to run the Scraper for www.TED.com.
"""
__title__ = 'app'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'

import argparse
from webscraper import Scraper

class App():


	def __init__(self):
		self.parse_commandline_arguments()
		self.run()


	def parse_commandline_arguments(self):
		
		parser = argparse.ArgumentParser(description='Scrape www.TED.com')

		parser.add_argument('--metadata', '-m', action='store_true',
			help="""Download the meta data for all TED talks 
			and dump it in a json file""")
		parser.add_argument('--render', '-r', action='store_true', 
			help="""Render HTML pages for the videos""")
		parser.add_argument('--video', '-v', action='store_true', 
			help="Download the TED videos in mp4")
		parser.add_argument('--subs', '-s', action='store_true', 
			help="Download Subtitles") 

		self.args = vars(parser.parse_args())


	def run(self):
		scraper = Scraper()

		if not self.args['metadata'] and not self.args['render'] \
			and not self.args['video'] and not self.args['subs']:
			scraper.extract_all_video_links()
			scraper.dump_data()
			scraper.download_subtitles()
			scraper.download_video_data()
			scraper.render_welcome_page()
			scraper.render_video_pages()
			scraper.copy_files_to_rendering_directory()

		if self.args['metadata']:
			scraper.extract_all_video_links()
			scraper.dump_data()

		if self.args['render']:
			scraper.render_welcome_page()
			scraper.render_video_pages()
			scraper.copy_files_to_rendering_directory()

		if self.args['video']:
			scraper.download_video_data()

		if self.args['subs']:
			scraper.download_subtitles()


if __name__ == '__main__':
	App()