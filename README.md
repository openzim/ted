# TED Scraper

TED (Technology, Entertainment, Design) is a global set of conferences under the slogan "ideas worth spreading". They address a wide range of topics within the research and practice of science and culture, often through storytelling. The speakers are given a maximum of 18 minutes to present their ideas in the most innovative and engaging ways they can. Its web site is www.ted.com.

The purpose of this project is to create a sustainable solution to create ZIM files providing the TED and TEDx videos in a similar manner like www.ted.com.
Everything about this project can be found [here](www.kiwix.org/wiki/TED). 

## Building the project

It's advised, that you have `pip` installed. 
Chose one of the following methods to do that:

    sudo apt-get install python-setuptools

    sudo easy_install pip

It's advised, that you have `virtualenv` installed:

    sudo pip install virtualenv

Up next you have to create a virtual enviroment in the kiwix-other/TED/ directory for the TED Scraper:

    virtualenv --no-site-packages venv 

Activiate the virtual enviroment:

    source venv/bin/activate

Install all the dependencies for the TED Scraper:

    pip install -r requirements.txt
