# TED Scraper

TED (Technology, Entertainment, Design) is a global set of conferences under the slogan "ideas worth spreading". They address a wide range of topics within the research and practice of science and culture, often through storytelling. The speakers are given a maximum of 18 minutes to present their ideas in the most innovative and engaging ways they can. Its web site is https://www.ted.com.

The purpose of this project is to create a sustainable solution to create ZIM files providing the TED and TEDx videos in a similar manner like online.

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/ted/badge)](https://www.codefactor.io/repository/github/openzim/ted)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PyPI version shields.io](https://img.shields.io/pypi/v/ted2zim.svg)](https://pypi.org/project/ted2zim/)

## Building the project

It's advised, that you have `pip` installed. 
Chose one of the following methods to do that:

```bash
sudo apt-get install python-setuptools
sudo easy_install pip
```

It's advised, that you have `virtualenv` installed:

```bash
sudo pip install virtualenv
```

Up next you have to create a virtual enviroment in the kiwix-other/TED/ directory for the TED Scraper:

```bash
virtualenv --no-site-packages venv 
```

Activiate the virtual enviroment:

```bash
source venv/bin/activate
```

Install all the dependencies for the TED Scraper:

```bash
pip install -r requirements.txt
```

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
