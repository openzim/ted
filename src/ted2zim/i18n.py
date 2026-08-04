"""Translation helpers for the scraper's own UI strings (ZIM homepage/article pages).

zimscraperlib >=5.0 redesigned its `i18n` module around a single `Language` class
and dropped its `setlocale()`/`_()` gettext helpers (translation features were
removed entirely, see https://github.com/openzim/python-scraperlib changelog).

ted2zim used those two helpers only as a thin wrapper around the stdlib `gettext`
module to translate the small set of strings used in its own templates (see the
`locale/` folder). This module reimplements that same thin wrapper locally so the
rest of the codebase (and the `locale/` catalogs) does not have to change."""

from __future__ import annotations

import gettext
import locale as locale_module
import pathlib

DOMAIN = "messages"


class Locale:
    """holds current process-wide gettext translation state"""

    translation: gettext.NullTranslations = gettext.translation(DOMAIN, fallback=True)

    @classmethod
    def setup(cls, locale_dir: pathlib.Path, locale_name: str) -> str:
        if "." in locale_name:
            lang, encoding = locale_name.split(".")
        else:
            lang, encoding = locale_name, "UTF-8"

        computed = locale_module.setlocale(locale_module.LC_ALL, (lang, encoding))

        gettext.bindtextdomain(DOMAIN, str(locale_dir))
        gettext.textdomain(DOMAIN)

        cls.translation = gettext.translation(
            DOMAIN, str(locale_dir), languages=[lang], fallback=True
        )
        return computed


def _(text: str) -> str:
    """translates text according to setup'd locale"""
    return Locale.translation.gettext(text)


def setlocale(root_dir: pathlib.Path, locale_name: str) -> str:
    """set the desired locale for gettext.

    call this early"""
    return Locale.setup(root_dir / "locale", locale_name)
