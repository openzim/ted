#!/usr/bin/env python

import json


"""
Class for creating a WebVTT subtitles file from the JSON subtitles format 
from www.TED.com
"""
__title__ = 'WebVTTcreator'
__author__ = 'Rashiq Ahmad'
__license__ = 'GPLv3'


class WebVTTcreator():


	def __init__(self, json):
		self.decoded_json = json.loads(json)


	def create_fil(self):
		pass


