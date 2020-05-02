#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import logging
import argparse

from .constants import NAME, SCRAPER, logger
from .scraper import Ted2Zim


def main():
    parser = argparse.ArgumentParser(
        prog=NAME, description="Scraper to create ZIM files from TED videos",
    )

    parser.add_argument(
        "--categories",
        help="Comma-seperated list of topics to scrape. Should be exactly same as given on ted.com/talks",
        required=True,
    )

    parser.add_argument(
        "--max-videos",
        help="Max number of videos to scrape in each topic. Pass 'max' if you want to scrape all",
        required=True,
    )

    parser.add_argument(
        "--transcode2webm",
        help="Whether to transcode videos to webm format",
        action="store_true",
    )

    parser.add_argument(
        "--output",
        help="Output folder for ZIM file or build folder",
        default="/output",
        dest="output_dir",
    )

    parser.add_argument(
        "--debug", help="Enable verbose output", action="store_true", default=False
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    try:
        scraper = Ted2Zim(**dict(args._get_kwargs()))
        scraper.run()
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
