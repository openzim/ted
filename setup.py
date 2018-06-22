#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

""" TED ZIM creator for Offline Use """

from codecs import open

from setuptools import setup, find_packages

with open('README.md', 'r', 'utf-8') as f:
    readme = f.read()

with open('requirements.txt', 'r') as f:
    requirements = [l.strip() for l in f.readlines() if len(l.strip())]

setup(
    name='ted2zim',
    version="1.0.1",
    description=__doc__,
    long_description=readme,
    author="Kiwix",
    author_email="contact@kiwix.org",
    url='http://github.com/openzim/ted',
    keywords="ted zim kiwix openzim offline",
    license="GPL-3.0",
    packages=find_packages('.'),
    zip_safe=False,
    platforms='any',
    include_package_data=True,
    data_files=['README.md', 'requirements.txt'],
    package_dir={'scraper': 'scraper'},
    install_requires=requirements,
    scripts=['ted2zim'],
    classifiers=[
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
    ],
)
