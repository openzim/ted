#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import logging
import argparse

from .constants import NAME, SCRAPER, MATCHING, ALL, NONE, logger
from .scraper import Ted2Zim


def main():
    parser = argparse.ArgumentParser(
        prog=NAME, description="Scraper to create ZIM files from TED talks",
    )

    parser.add_argument(
        "--topics",
        help="Comma-seperated list of topics to scrape. Should be exactly same as given on ted.com/talks",
    )

    parser.add_argument(
        "--max-videos-per-topic",
        help="Max number of videos to scrape in each topic. Default behaviour is to scrape all",
        default=9999,
        type=int,
    )

    parser.add_argument(
        "--output",
        help="Output folder for ZIM file or build folder",
        default="/output",
        dest="output_dir",
    )

    parser.add_argument(
        "--name",
        help="ZIM name. Used as identifier and filename (date will be appended)",
        required=True,
    )

    parser.add_argument(
        "--format",
        help="Format to download/transcode video to. webm is smaller",
        choices=["mp4", "webm"],
        default="webm",
        dest="video_format",
    )

    parser.add_argument(
        "--low-quality",
        help="Re-encode video using stronger compression",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--no-zim",
        help="Don't produce a ZIM file, create build folder only.",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--zim-file",
        help="ZIM file name (based on --name if not provided)",
        dest="fname",
    )

    parser.add_argument(
        "--language", help="ISO-639-3 (3 chars) language code of content", default="eng"
    )

    parser.add_argument(
        "--title",
        help="Custom title for your project and ZIM. Default value - TED Collection",
    )

    parser.add_argument(
        "--description",
        help="Custom description for your project and ZIM. Default value - A selection of several topics' videos from TED",
    )

    parser.add_argument("--creator", help="Name of content creator", default="TED")

    parser.add_argument(
        "--publisher", help="Custom publisher name (ZIM metadata)", default="Kiwix"
    )

    parser.add_argument(
        "--tags",
        help="List of comma-separated Tags for the ZIM file. category:ted, ted, and _videos:yes added automatically",
    )

    parser.add_argument(
        "--keep",
        help="Don't erase build folder on start (for debug/devel)",
        default=False,
        action="store_true",
        dest="keep_build_dir",
    )

    parser.add_argument(
        "--debug", help="Enable verbose output", action="store_true", default=False
    )

    parser.add_argument(
        "--version",
        help="Display scraper version and exit",
        action="version",
        version=SCRAPER,
    )

    parser.add_argument(
        "--autoplay",
        help="Enable autoplay on video articles. Behavior differs on platforms/browsers.",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--optimization-cache",
        help="URL with credentials to S3/S3 based bucket for using as optimization cache",
        dest="s3_url_with_credentials",
    )

    parser.add_argument(
        "--use-any-optimized-version",
        help="Use the cached files if present, whatever the version",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--playlist", help="A playlist ID from ted.com/playlists to scrape videos from",
    )

    parser.add_argument(
        "--only-videos-in",
        help="Comma-seperated list of TED language codes",
        dest="source_language",
    )

    parser.add_argument(
        "--subtitles-enough",
        help="Consider subtitle availability while filtering videos by language",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--subtitles",
        help="Whether to provide subtitles in language requested, no subtitles, or all available subtitles",
        default=MATCHING,
        dest="subtitles_setting",
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    try:
        if args.topics and args.playlist:
            parser.error("--topics is incompatible with --playlist")
        elif args.topics:
            if args.max_videos_per_topic < 1:
                parser.error(
                    "Maximum number of videos to scrape per topic must be greater than or equal to 1"
                )
            if args.subtitles_enough and not args.source_language:
                parser.error(
                    "--subtitles-enough is only meant to be used if --only-videos-in is present"
                )
        elif args.playlist:
            if args.source_language:
                parser.error(
                    "--only-videos-in is not compatible with playlists. Use this option only in combination with --topics"
                )
            if args.subtitles_enough:
                parser.error("--subtitles-enough is not compatible with playlists")
        else:
            parser.error("Either --topics or --playlist is required")
        if not args.subtitles_setting:
            parser.error("--subtitles cannot take in empty string")
        scraper = Ted2Zim(**dict(args._get_kwargs()))
        scraper.run()
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
