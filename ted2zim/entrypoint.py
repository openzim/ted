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
        "--categories", help="List of topics to scrape", required=True, nargs="+",
    )

    parser.add_argument(
        "--max-pages",
        help="Number of pages to scrape in each topic. Pass 'max' if you want to scrape all",
        required=True,
        dest="max_pages",
    )

    parser.add_argument(
        "--debug", help="Enable verbose output", action="store_true", default=False
    )

    args = parser.parse_args()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    try:
        scraper = Ted2Zim(**dict(args._get_kwargs()))
        scraper.extract_all_video_links()
        scraper.dump_data()
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
