<h1 align="center">ted2zim</h1>

<div align="center">
  <strong>Get the best :bulb: TED videos offline :arrow_down:</strong>
</div>
<div align="center">
  An offliner to create ZIM :package: files from TED talks
</div>

<br />

<div align="center">
  <!-- PyPI version -->
  <a href="https://pypi.org/project/ted2zim/">
    <img alt="PyPI" src="https://img.shields.io/pypi/v/ted2zim?style=for-the-badge">
  </a>
  <!-- Docker version -->
  <a href="https://hub.docker.com/r/openzim/ted">
    <img alt="Docker" src="https://img.shields.io/docker/build/openzim/ted?style=for-the-badge">
  </a>
  <!-- Codefactor grade -->
  <a href="https://www.codefactor.io/repository/github/openzim/ted">
    <img alt="CodeFactor Grade"
     src="https://img.shields.io/codefactor/grade/github/openzim/ted/master?label=codefactor&style=for-the-badge">
  </a>
  <!-- License -->
  <a href="https://www.gnu.org/licenses/gpl-3.0">
    <img alt="GitHub" src="https://img.shields.io/github/license/openzim/ted?color=blueviolet&style=for-the-badge">
  </a>
</div>


TED (Technology, Entertainment, Design) is a global set of conferences under the slogan "ideas worth spreading". They address a wide range of topics within the research and practice of science and culture, often through storytelling. The speakers are given a maximum of 18 minutes to present their ideas in the most innovative and engaging ways they can. One can eaisly find all the TED videos [here](https://ted.com/talks).

This project is aimed at creating a sustainable solution to make TED accessible offline by creating ZIM files providing these videos in a similar manner like online.


## Getting started :rocket:

#### Install the dependencies
Make sure that you have `python3`, `unzip`, `ffmpeg`, `wget` and `curl` installed on your system before running the scraper (otherwise you'll get a warning to install them).

#### Setup the package
One can eaisly install the PyPI version but let's setup the source version. Firstly, clone this repository and install the package as given below.

```bash
pip3 install -r requirements.txt
```

```bash
python3 setup.py install
```

That's it. You can now run `ted2zim` from your terminal

```bash
ted2zim --topics [TOPICS] --name [NAME]
```

For the full list of arguments, see [this](ted2zim/entrypoint.py) file or run the following
```bash
ted2zim --help
```

Example usage
```bash
ted2zim --topics="augmented reality" --max-videos-per-topic=10 --debug --name="augumented_reality" --format=mp4 --title="Augmented Reality" --description="TED videos in AR category" --creator="TED" --publisher="openzim" --output="output" --keep --low-quality
```

This project can also be run with docker. Use the provided [Dockerfile](Dockerfile) to run it with docker. See steps [here](https://docs.docker.com/get-started/part2/).

## Features :robot:
You can create ZIMs for multiple topics (should be same as given [here](https://ted.com/talks)), choose between different video formats (webm/mp4), different compression rates, and even use an S3 based cache.

#### Want more flexibility? There's a multitool
`ted2zim-multi` is an extra command available that allows you to do much more with the scraper. It falls back to `ted2zim` if normal commands are passed. It supports creation of multiple ZIMs with single command for both playlists and topics and even getting metadata from a specified JSON file. It supports the following extra arguments -
- --indiv-zims - Allows you to create one zim/topic or one zim/playlist
- --{name|description|zim-file|title}-format - Allows you to add custom format for the equivalent `ted2zim` arguments. You can add {identity} as a placeholder in these values to get the playlist ID / topic name in it's place
- --metadata-from - Path to a JSON file containing the metadata. Should be of the following format -
```bash
{
    "<playlist-id/topic-name-with-underscores>": {
        "name": "sample_name_{identity}",
        "description": "Sample description",
        "title": "Custom title",
        "zim-file": "sample.zim",
        "tags": "tag",
        "creator": "Yourself",
        "build-dir": "/custom_build_dir"
    }
}
```
See ted2zim-multi --help for details.

## License :book:

[GPLv3](https://www.gnu.org/licenses/gpl-3.0) or later, see
[LICENSE](LICENSE) for more details.
