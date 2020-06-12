#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu


import re
import sys
import json
import pathlib
import tempfile
import datetime
import subprocess

import requests
from zimscraperlib.logging import nicer_args_join
from kiwixstorage import KiwixStorage

from ..constants import NAME, getLogger
from ..utils import download_link

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

    @staticmethod
    def download_playlists_list_from_site(topics_list):
        records = []
        for topic in topics_list:
            logger.debug(f"Getting playlists related to {topic}")
            playlist_sub_list = json.loads(
                download_link(
                    f"https://www.ted.com/playlists/browse.json?topics={topic['value'].replace(' ', '+')}"
                ).text
            )
            for record in playlist_sub_list["records"]:
                if record not in records:
                    records.append(record)
            logger.debug("..OK")
        return records

    def download_playlists_list_from_cache(self, key, s3_storage):
        fpath = pathlib.Path(tempfile.NamedTemporaryFile(delete=False).name)
        if not s3_storage.has_object(key):
            return False
        try:
            meta = s3_storage.get_object_stat(key).meta
            if datetime.datetime.fromisoformat(
                meta.get("retrieved_on")
            ) > datetime.datetime.now() - datetime.timedelta(days=7):
                s3_storage.download_file(key, fpath)
            else:
                logger.debug(
                    "playlists_list.json in optimization cache is too old to be used"
                )
                return False
        except Exception as exc:
            logger.error(f"{key} failed to download from cache: {exc}")
            return False
        logger.info(f"downloaded playlist list from cache at {key}")
        with open(fpath, "r") as fp:
            json_data = json.load(fp)
        fpath.unlink()
        return json_data

    def upload_playlists_list_to_cache(self, playlists_list, key, s3_storage):
        fpath = pathlib.Path(tempfile.NamedTemporaryFile(delete=False).name)
        with open(fpath, "w") as fp:
            json.dump(playlists_list, fp)
        try:
            s3_storage.upload_file(
                fpath, key, meta={"retrieved_on": datetime.datetime.now().isoformat()},
            )
        except Exception as exc:
            logger.error(f"{key} failed to upload to cache: {exc}")
        else:
            logger.info(f"successfully uploaded playlist list to cache at {key}")
        finally:
            fpath.unlink()

    def get_list_of_all(self, mode):
        """ returns a list of topics or playlists"""
        # get all topics
        topics_list = json.loads(
            download_link("https://www.ted.com/topics/combo?models=Talks").text
        )
        if mode == "topic":
            return topics_list

        # mode is playlist
        s3_url_with_credentials = None
        s3_arg = "--optimization-cache"
        for index, arg in enumerate(self.extra_args):
            if arg.startswith(s3_arg):
                s3_url_with_credentials = (
                    arg[len(s3_arg) + 1 :] if "=" in arg else self.extra_args[index + 1]
                )
                break

        if s3_url_with_credentials:
            s3_storage = KiwixStorage(s3_url_with_credentials)
            if not s3_storage.check_credentials(
                list_buckets=True, bucket=True, write=True, read=True, failsafe=True
            ):
                logger.error("S3 credential check failed. Continuing without S3")
                return self.download_playlists_list_from_site(topics_list)
            key = "playlists_list.json"
            self.output_dir.mkdir(parents=True, exist_ok=True)
            playlists_list = self.download_playlists_list_from_cache(key, s3_storage)
            if not playlists_list:
                logger.debug("Attempting to retrieve playlists list from TED")
                playlists_list = self.download_playlists_list_from_site(topics_list)
                self.upload_playlists_list_to_cache(playlists_list, key, s3_storage)
            return playlists_list
        return self.download_playlists_list_from_site(topics_list)

    def log_run_result(self, success, process):
        if success:
            logger.info(".. OK")
        else:
            logger.error(".. ERROR. Printing scraper output and exiting.")
            logger.error(process.stdout)
            return process.returncode

    def run(self):
        logger.info(f"starting {NAME}-multi scraper")

        self.fetch_metadata()

        if self.topics:
            if self.topics == ["all"]:
                self.topics = [
                    topic["value"] for topic in self.get_list_of_all(mode="topic")
                ]
            if self.indiv_zims:
                for topic in self.topics:
                    logger.info(f"Executing ted2zim for topic {topic}")
                    success, process = self.run_indiv_zim_mode(topic, mode="topic")
                    self.log_run_result(success, process)

            else:
                if not self.handle_single_zim(mode="topic"):
                    logger.error("ted2zim Failed")

        if self.playlists:
            if self.playlists == ["all"]:
                self.playlists = [
                    str(playlist["id"])
                    for playlist in self.get_list_of_all(mode="playlist")
                ]
            # automatically set self.indiv_zims if not already set and multiple playlists
            if len(self.playlists) > 1 and not self.indiv_zims:
                self.indiv_zims = True
            if self.indiv_zims:
                for playlist in self.playlists:
                    logger.info(f"Executing ted2zim for playlist {playlist}")
                    success, process = self.run_indiv_zim_mode(
                        playlist, mode="playlist"
                    )
                    self.log_run_result(success, process)
            else:
                if not self.handle_single_zim(mode="playlist"):
                    logger.error("ted2zim Failed")

    def run_indiv_zim_mode(self, item, mode):
        """ run ted2zim for an individual topic/playlist """

        args = self.ted2zim_exe

        if mode == "topic":
            args += [
                "--topics",
                item,
            ]
        elif mode == "playlist":
            args += [
                "--playlist",
                item,
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
            ]
        elif mode == "playlist":
            args += [
                "--playlist",
                self.playlists[0],
            ]
        else:
            raise ValueError(f"Unsupported mode {mode}")
        args += self.extra_args
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
