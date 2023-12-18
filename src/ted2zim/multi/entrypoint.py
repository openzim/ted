#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

import logging
import argparse

from ..constants import NAME, SCRAPER, getLogger, setDebug
from ..utils import has_argument


def main():
    parser = argparse.ArgumentParser(
        prog=f"{NAME}-multi",
        description="Scraper to create ZIM file(s) from TED topic(s) or playlist(s)",
        epilog="All titles, descriptions and names can use the variables {identity} to get playlist ID or topic name (with dashes) in each case, or {slug} to get the slug (with dashes)",
        allow_abbrev=False,
    )

    parser.add_argument(
        "--topics",
        help="Comma seperated list of topics to scrape. Should be same as on ted.com/talks. Pass all to scrape all",
    )

    parser.add_argument(
        "--playlists",
        help="Comma seperated list of playlist IDs to scrape. Pass all to scrape all",
    )

    parser.add_argument(
        "--indiv-zims",
        help="Make individual ZIMs for topics. Multiple ZIMs are always created for multiple playlists",
        action="store_true",
        dest="indiv_zims",
    )

    parser.add_argument(
        "--name-format",
        help="Format for building individual --name argument. Required in individual ZIMs mode.",
    )

    parser.add_argument(
        "--zim-file-format",
        help="Format for building individual --zim-file argument. Uses --name-format otherwise",
    )

    parser.add_argument(
        "--title-format",
        help="Custom title format for individual ZIMs",
    )

    parser.add_argument(
        "--description-format",
        help="Custom description format for individual ZIMs",
    )

    parser.add_argument(
        "--metadata-from",
        help="File path or URL to a JSON file holding custom metadata for individual playlists/topics. Format in README",
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

    args, extra_args = parser.parse_known_args()

    # prevent launching without any topic(s)/playlist(s)
    if (
        not args.playlists
        and not args.topics
        and not has_argument("playlist", extra_args)
    ):
        parser.error("Please provide topic(s) and/or playlist(s) to scrape")

    # prevent setting --title and --description
    for arg in ("name", "title", "description", "zim-file"):
        if args.indiv_zims and has_argument(arg, extra_args):
            parser.error(
                f"Can't use --{arg} in individual ZIMs mode. Use --{arg}-format to set format."
            )

    # name-format mandatory if indiv-zims
    if args.indiv_zims and not args.name_format:
        parser.error("--name-format is mandatory in individual ZIMs mode")

    setDebug(args.debug)
    logger = getLogger()
    logger.setLevel(logging.DEBUG if args.debug else logging.INFO)

    from .scraper import TedHandler

    try:
        handler = TedHandler(dict(args._get_kwargs()), extra_args=extra_args)
        raise SystemExit(handler.run())
    except Exception as exc:
        logger.error(f"FAILED. An error occurred: {exc}")
        if args.debug:
            logger.exception(exc)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
