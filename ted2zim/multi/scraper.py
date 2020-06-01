#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu


import re
import sys
import json
import shutil
import pathlib
import subprocess

import requests
from zimscraperlib.logging import nicer_args_join

from ..constants import NAME, getLogger
from ..utils import has_argument

logger = getLogger()


class TedHandler(object):
    def __init__(
        self, options, extra_args,
    ):
        # save options as properties
        for key, value in options.items():
            if key not in ["topics", "playlists"]:
                setattr(self, key, value)
            else:
                value_list = (
                    [] if not value else [val.strip() for val in value.split(",")]
                )
                setattr(self, key, value_list)

        self.extra_args = extra_args

        self.output_dir = pathlib.Path(self.output_dir).expanduser().resolve()
        self.build_dir = self.output_dir.joinpath("build")

        # metadata_from JSON file
        self.metadata_from = (
            pathlib.Path(self.metadata_from) if self.metadata_from else None
        )
        self.metadata = {}  # custom metadata holder

    @property
    def ted2zim_exe(self):
        """ ted2zim executable """

        # handle either `python ted2zim` or `ted2zim`
        executable = pathlib.Path(sys.executable)
        if re.match(r"python[0-9]*", executable.name):
            return [str(executable), "ted2zim"]
        return [str(executable)]

    @staticmethod
    def compute_format(item, fmt):
        return fmt.format(identity=item.replace(" ", "_"))

    def run(self):
        def log_run_result(success, process):
            if success:
                logger.info(".. OK")
            else:
                logger.error(".. ERROR. Printing scraper output and exiting.")
                logger.error(process.stdout)
                return process.returncode

        logger.info(f"starting {NAME}-multi scraper")

        self.fetch_metadata()

        if self.topics:
            if self.indiv_zims and len(self.topics) > 1:
                for topic in self.topics:
                    logger.info(f"Executing ted2zim for topic {topic}")
                    success, process = self.run_indiv_zim_mode(topic, mode="topic")
                    log_run_result(success, process)

            else:
                logger.info("Falling back to ted2zim for topic(s)")
                if not self.handle_single_zim(mode="topic"):
                    logger.error("ted2zim Failed")

        if self.playlists:
            if len(self.playlists) > 1:
                for playlist in self.playlists:
                    logger.info(f"Executing ted2zim for playlist {playlist}")
                    success, process = self.run_indiv_zim_mode(
                        playlist, mode="playlist"
                    )
                    log_run_result(success, process)
            else:
                logger.info("Falling back to ted2zim for playlist")
                if not self.handle_single_zim(mode="playlist"):
                    logger.error("ted2zim Failed")

    def run_indiv_zim_mode(self, item, mode):
        """ run ted2zim for an individual topic/playlist """

        args = self.ted2zim_exe

        if mode == "topic":
            args += [
                "--topics",
                item,
                "--output",
                str(self.output_dir.joinpath("topics", item.replace(" ", "_"))),
            ]
        elif mode == "playlist":
            args += [
                "--playlist",
                item,
                "--output",
                str(self.output_dir.joinpath("playlists", item)),
            ]
        else:
            raise ValueError(f"Unsupported mode {mode}")

        # set metadata args
        metadata = self.metadata.get(item.replace(" ", "_"), {})
        for key in (
            "name",
            "zim-file",
            "title",
            "description",
            "tags",
            "creator",
        ):
            # use value from metadata JSON if present else from command-line
            value = metadata.get(
                key, getattr(self, f"{key.replace('-', '_')}_format", None)
            )

            if value:  # only set arg if we have a value so it can be defaulted
                args += [f"--{key}", self.compute_format(item, str(value))]

        # ensure we supplied a name
        if not has_argument("name", args):
            args += ["--name", self.compute_format(item, self.name_format)]

        # append regular ted2zim args
        args += self.extra_args

        if self.debug:
            args += ["--debug"]

        logger.debug(nicer_args_join(args))
        process = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        return process.returncode == 0, process

    def handle_single_zim(self, mode):
        """ redirect request to standard ted2zim """

        args = self.ted2zim_exe
        if mode == "topic":
            args += [
                "--topics",
                ",".join(self.topics),
                "--output",
                str(self.output_dir.joinpath("topics")),
            ]
        elif mode == "playlist":
            args += [
                "--playlist",
                self.playlists[0],
                "--output",
                str(self.output_dir.joinpath("playlists")),
            ]
        else:
            raise ValueError(f"Unsupported mode {mode}")
        args += self.extra_args
        if "--name" not in self.extra_args and self.name_format:
            name_item = "_".join(self.topics) if mode == "topic" else self.playlists[0]
            args += ["--name", self.compute_format(name_item, self.name_format)]
        if self.debug:
            args += ["--debug"]
        return subprocess.run(args).returncode == 0

    def fetch_metadata(self):
        """ retrieves and loads metadata from --metadata-from """

        if not self.metadata_from:
            return

        logger.info(f"Retrieving custom metadata from {self.metadata_from}")
        # load JSON from source (URL or file)
        try:
            if str(self.metadata_from).startswith("http"):
                self.metadata = requests.get(str(self.metadata_from)).json()
            else:
                if not self.metadata_from.exists():
                    raise IOError(
                        f"--metadata-from file could not be found: {self.metadata_from}"
                    )
                with open(self.metadata_from, "r") as fh:
                    self.metadata = json.load(fh)
        except Exception as exc:
            logger.debug(exc)
            raise ValueError(
                f"--metadata-from could not be loaded as JSON: {self.metadata_from}"
            )

        # ensure the basic format is respected: dict of playlist id/ topic name to dict of meta
        if not isinstance(self.metadata, dict) or len(self.metadata) != sum(
            [
                1
                for k, v in self.metadata.items()
                if isinstance(k, str) and isinstance(v, dict)
            ]
        ):
            raise ValueError("--metadata-from JSON is of unexpected format")
