from zimscraperlib.i18n import get_language_details

from ted2zim.constants import (
    TEDLANGS,
    get_logger,
)

logger = get_logger()


def get_display_name(lang_code, lang_name):
    """Display name for language"""

    lang_info = get_language_details(lang_code, failsafe=True)
    if lang_code != "en" and lang_info:
        return lang_info["native"] + " - " + lang_name
    return lang_name


def append_part1_or_part3(lang_code_list, lang_info):
    """Fills missing ISO languages codes for all in list

    lang_code_list: list og lang codes
    lang_info: see zimscraperlib.i18n"""

    # ignore extra language mappings if supplied query was an iso-639-1 code
    if "part1" in lang_info["iso_types"]:
        lang_code_list.append(lang_info["iso-639-1"])

    # supplied query was not iso-639-1
    elif lang_info["iso-639-1"]:
        lang_code_list.append(lang_info["iso-639-1"])
        # check for extra language codes to include
        if lang_info["iso-639-1"] in TEDLANGS["mappings"]:
            for code in TEDLANGS["mappings"][lang_info["iso-639-1"]]:
                lang_code_list.append(code)
    elif lang_info["iso-639-3"]:
        lang_code_list.append(lang_info["iso-639-3"])
    else:
        supplied_lang = lang_info["query"]
        logger.error(f"Language {supplied_lang} is not supported by TED")


def to_ted_langcodes(languages):
    """Converts languages queries into TED language codes

    Examples:
        ["English", "fr", "hin"] => ["en", "fr", "hi"]
        ["chi", "fake"] => ["zh", "zh-cn", "zh-tw"]
    """

    lang_code_list = []
    for lang in languages:
        lang_info = get_language_details(lang, failsafe=True)
        if lang_info:
            logger.warning(lang_info)
            if lang_info["querytype"] == "purecode":
                append_part1_or_part3(lang_code_list, lang_info)
            elif lang_info["querytype"] == "locale":
                query = lang_info["query"].replace("_", "-")
                if query in TEDLANGS["locales"]:
                    lang_code_list.append(query)
                else:
                    append_part1_or_part3(lang_code_list, lang_info)
            else:
                append_part1_or_part3(lang_code_list, lang_info)
    return list(set(lang_code_list))


def ted_to_iso639_3_langcodes(ted_langcodes):
    """Create a mapping of TED language codes to ISO639-3

    Returns a mapping dictionary of TED codes to converted ISO639-3 codes, when ISO code
    does not exist, dictionary value is "None".


    Examples:
        ["zh", "zh-cn", "zh-tw"] => {"zh": "chi", "zh-cn": "chi", "zh-tw": "chi"}
    """

    mapping = {}
    for lang in set(ted_langcodes):
        lang_info = get_language_details(lang, failsafe=True)
        if lang_info and lang_info["iso-639-3"]:
            mapping[lang] = lang_info["iso-639-3"]
        else:
            mapping[lang] = None

    return mapping
