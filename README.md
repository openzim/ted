# TED Scraper

TED (Technology, Entertainment, Design) is a global set of conferences under the slogan "ideas worth spreading". They address a wide range of topics within the research and practice of science and culture, often through storytelling. The speakers are given a maximum of 18 minutes to present their ideas in the most innovative and engaging ways they can. Its web site is https://www.ted.com.

The purpose of this project is to create a sustainable solution to create ZIM files providing the TED and TEDx videos in a similar manner like online.

## Running the project

It requires python3 and one can run by following these steps after cloning the repository

1. Install the package

```
python3 setup.py install
```

2. Run the command 'ted2zim' as follows

```
ted2zim [-h] --categories CATEGORIES --max-videos MAX_VIDEOS --name
               NAME [--format {mp4,webm}] [--low-quality]
               [--output OUTPUT_DIR] [--no-zim] [--zim-file FNAME]
               [--language LANGUAGE] [--locale LOCALE_NAME] --title TITLE
               --description DESCRIPTION --creator CREATOR
               [--publisher PUBLISHER] [--tags TAGS] [--keep]
               [--skip-download] [--debug]

```

Example usage

```
ted2zim --categories="augmented reality, technology" --max-videos=55 --debug --name="ted_technology" --format=mp4 --low-quality --title="technology" --description="TED videos in technology category" --creator="satyamtg" --publisher="satyamtg" --output="output"
```
