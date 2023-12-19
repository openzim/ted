import logging
import pathlib

from zimscraperlib.logging import getLogger as lib_getLogger

ROOT_DIR = pathlib.Path(__file__).parent
NAME = ROOT_DIR.name

with open(ROOT_DIR.joinpath("VERSION")) as fh:
    VERSION = fh.read().strip()

SCRAPER = f"{NAME} {VERSION}"

BASE_URL = "https://ted.com/"

SEARCH_URL = "https://zenith-prod-alt.ted.com/api/search"

MATCHING = "matching"
ALL = "all"
NONE = "none"

TEDLANGS = {
    "locales": ["zh-cn", "zh-tw", "pt-br", "fr-ca"],
    "mappings": {"zh": ["zh-cn", "zh-tw"], "pt": ["pt-br"], "fr": ["fr-ca"]},
}

REQUESTS_TIMEOUT = 30


class Global:
    debug = False


def set_debug(debug):
    """toggle constants global DEBUG flag (used by getLogger)"""
    Global.debug = bool(debug)


def get_logger():
    """configured logger respecting DEBUG flag"""
    return lib_getLogger(NAME, level=logging.DEBUG if Global.debug else logging.INFO)
