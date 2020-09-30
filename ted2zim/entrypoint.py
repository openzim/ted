#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import argparse

from .constants import NAME, SCRAPER, MATCHING, ALL, NONE, getLogger, setDebug


def main():
    parser = argparse.ArgumentParser(
        prog=NAME,
        description="Scraper to create ZIM files from TED talks topics or playlists",
    )

    parser.add_argument(
        "--topics",
        help="Comma-seperated list of topics to scrape; as given on ted.com/talks",
    )

    parser.add_argument(
        "--playlist",
        help="A playlist ID from ted.com/playlists to scrape videos from",
    )

    parser.add_argument(
        "--languages", help="Comma-seperated list of languages to filter videos"
    )

    parser.add_argument(
        "--locale",
        help="The locale to use in the UI (can be iso language code / locale)",
        dest="locale_name",
        default="eng",
    )

    parser.add_argument(
        "--subtitles-enough",
        help="Whether to include videos that have a subtitle in requested --languages if audio is in another language",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--subtitles",
        help=f"Language setting for subtitles. {ALL}: include all available subtitles, {MATCHING} (default): only subtitles matching --languages, {NONE}: include no subtitle. Also accepts comma-seperated list of language codes",
        default=MATCHING,
        dest="subtitles_setting",
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
        "--autoplay",
        help="Enable autoplay on video articles. Behavior differs on platforms/browsers.",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--name",
        help="ZIM name. Used as identifier and filename (date will be appended)",
        required=True,
    )

    parser.add_argument(
        "--title",
        help="Custom title for your ZIM. Based on selection otherwise.",
    )

    parser.add_argument(
        "--description",
        help="Custom description for your ZIM. Based on selection otherwise.",
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
        "--optimization-cache",
        help="URL with credentials and bucket name to S3 Optimization Cache",
        dest="s3_url_with_credentials",
    )

    parser.add_argument(
        "--use-any-optimized-version",
        help="Use files on S3 cache if present, whatever the version",
        default=False,
        action="store_true",
    )

    parser.add_argument(
        "--output",
        help="Output folder for ZIM file",
        default="/output",
        dest="output_dir",
    )

    parser.add_argument(
        "--tmp-dir",
        help="Path to create temp folder in. Used for building ZIM file. Receives all data (storage space)",
    )

    parser.add_argument(
        "--zim-file",
        help="ZIM file name (based on --name if not provided)",
        dest="fname",
    )

    parser.add_argument(
        "--no-zim",
        help="Don't produce a ZIM file, create build folder only.",
        action="store_true",
        default=False,
    )

    parser.add_argument(
        "--keep",
        help="Don't remove build folder on start (for debug/devel)",
        default=False,
        action="store_true",
        dest="keep_build_dir",
    )

    parser.add_argument(
        "--debug", help="Enable verbose output", action="store_true", default=False
    )

    parser.add_argument(
        "--threads",
        help="Maximum number of parallel threads to use",
        default=1,
        type=int,
    )

    parser.add_argument(
        "--version",
        help="Display scraper version and exit",
        action="version",
        version=SCRAPER,
    )

    args = parser.parse_args()
    setDebug(args.debug)
    logger = getLogger()

    from .scraper import Ted2Zim

    try:
        if args.topics and args.playlist:
            parser.error("--topics is incompatible with --playlist")
        elif args.topics:
            if args.subtitles_enough and not args.languages:
                parser.error(
                    "--subtitles-enough is only meant to be used if --languages is present"
                )
        elif args.playlist:
            if args.subtitles_enough:
                parser.error("--subtitles-enough is not compatible with playlists")
        else:
            parser.error("Either --topics or --playlist is required")
        if not args.subtitles_setting:
            parser.error("--subtitles cannot take an empty string")

        if not args.threads >= 1:
            parser.error("--threads must be provided a positive integer")

        scraper = Ted2Zim(**dict(args._get_kwargs()))
        scraper.run()
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
