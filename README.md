# TED Scraper

TED (Technology, Entertainment, Design) is a global set of conferences under the slogan "ideas worth spreading". They address a wide range of topics within the research and practice of science and culture, often through storytelling. The speakers are given a maximum of 18 minutes to present their ideas in the most innovative and engaging ways they can. Its web site is https://www.ted.com.

The purpose of this project is to create a sustainable solution to create ZIM files providing the TED and TEDx videos in a similar manner like online.

[![CodeFactor](https://www.codefactor.io/repository/github/openzim/ted/badge)](https://www.codefactor.io/repository/github/openzim/ted)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![PyPI version shields.io](https://img.shields.io/pypi/v/ted2zim.svg)](https://pypi.org/project/ted2zim/)


## Running the project

It requires python3 and one can run by following these steps after cloning the repository

1. Install the package

```
python3 setup.py install
```

2. Run the command 'ted2zim' as follows

```
usage: ted2zim [-h] --topics TOPICS --max-videos-per-topic
               MAX_VIDEOS_PER_TOPIC [--output OUTPUT_DIR] --name NAME
               [--format {mp4,webm}] [--low-quality] [--no-zim]
               [--zim-file FNAME] [--language LANGUAGE] --title TITLE
               --description DESCRIPTION --creator CREATOR
               [--publisher PUBLISHER] [--tags TAGS] [--keep] [--debug]

Scraper to create ZIM files from TED videos

optional arguments:
  -h, --help            show this help message and exit
  --topics TOPICS       Comma-seperated list of topics to scrape. Should be
                        exactly same as given on ted.com/talks
  --max-videos-per-topic MAX_VIDEOS_PER_TOPIC
                        Max number of videos to scrape in each topic. Default
                        behaviour is to scrape all
  --output OUTPUT_DIR   Output folder for ZIM file or build folder
  --name NAME           ZIM name. Used as identifier and filename (date will
                        be appended)
  --format {mp4,webm}   Format to download/transcode video to. webm is smaller
  --low-quality         Re-encode video using stronger compression
  --no-zim              Don't produce a ZIM file, create HTML folder only.
  --zim-file FNAME      ZIM file name (based on --name if not provided)
  --language LANGUAGE   ISO-639-3 (3 chars) language code of content
  --title TITLE         Custom title for your project and ZIM. Default to
                        Channel name (of first video if playlists)
  --description DESCRIPTION
                        Custom description for your project and ZIM. Default
                        to Channel name (of first video if playlists)
  --creator CREATOR     Name of content creator
  --publisher PUBLISHER
                        Custom publisher name (ZIM metadata)
  --tags TAGS           List of comma-separated Tags for the ZIM file.
                        category:ted, ted, and _videos:yes added automatically
  --keep                Don't erase build folder on start (for debug/devel)
  --debug               Enable verbose output
```

Example usage

```
ted2zim --topics="augmented reality" --max-videos-per-topic=10 --debug --name="augumented_reality" --format=mp4 --title="Augmented Reality" --description="TED videos in AR category" --creator="TED" --publisher="openzim" --output="output" --keep --low-quality
```

## License

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
