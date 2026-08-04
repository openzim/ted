"""ZIM file creation helper

zimscraperlib.zim.make_zim_file() is a convenient one-call helper to build a
zimwriterfs-like ZIM from a build folder, but its `language` parameter is typed
(and enforced at runtime via beartype) as a single `str` and passed as-is to
`zimscraperlib.zim.metadata.LanguageMetadata()`.

Unlike prior zimscraperlib versions (<5.0), `LanguageMetadata` no longer splits a
comma-separated string into individual ISO-639-3 codes: passing e.g. "eng,fra"
now fails validation because the whole string is checked as a single (invalid)
code instead of being split into ["eng", "fra"] first (see
`zimscraperlib.zim.metadata.TextListBasedMetadata.get_cleaned_value`).

TED talks routinely have several audio/subtitle languages above the configured
threshold (see `Ted2Zim.compute_zim_languages()`), so ted2zim needs to build its
`Language` ZIM metadata from an actual list of codes. This module re-implements
`make_zim_file()` using the same public building blocks it uses internally
(`Creator`, `add_to_zim`, `add_redirects_to_zim`), changing only how the
`Language` metadata is constructed so multiple codes are properly supported.

See https://github.com/openzim/python-scraperlib upstream implementation this is
adapted from (`zimscraperlib/zim/filesystem.py`)."""

from __future__ import annotations

import datetime
import pathlib
from collections.abc import Sequence

from zimscraperlib.zim import metadata
from zimscraperlib.zim.creator import Creator
from zimscraperlib.zim.filesystem import add_redirects_to_zim, add_to_zim


def make_zim_file(
    *,
    build_dir: pathlib.Path,
    fpath: pathlib.Path,
    name: str,
    main_page: str,
    illustration: str,
    title: str,
    description: str,
    languages: Sequence[str],
    date: datetime.date | None = None,
    creator: str = "-",
    publisher: str = "-",
    tags: Sequence[str] | None = None,
    source: str | None = None,
    flavour: str | None = None,
    scraper: str | None = None,
    long_description: str | None = None,
    redirects: Sequence[tuple[str, str, str]] | None = None,
    redirects_file: pathlib.Path | None = None,
    workaround_nocancel: bool = True,
    ignore_duplicates: bool = True,
    disable_metadata_checks: bool = False,
):
    """Creates a zimwriterfs-like ZIM file at {fpath} from {build_dir}

    Same as zimscraperlib.zim.make_zim_file() except `languages` accepts a
    sequence of ISO-639-3 codes instead of a single, comma-joined string (see
    module docstring for why zimscraperlib's own helper cannot be used as-is for
    a ZIM with more than one language).

    main_page: path of item to serve as main page
    illustration: relative path to illustration file in build_dir
    tags: list of str tags to add to meta
    redirects: list of (src, dst, title) tuple to create redirects from
    workaround_nocancel: disable workaround to prevent ZIM creation on error"""

    # sanity checks
    if not build_dir.exists() or not build_dir.is_dir():
        raise OSError(f"Incorrect build_dir: {build_dir}")

    illustration_path = build_dir / illustration
    if not illustration_path.exists() or not illustration_path.is_file():
        raise OSError(f"Incorrect illustration: {illustration} ({illustration_path})")

    with open(illustration_path, "rb") as fh:
        illustration_data = fh.read()

    # disable recommendations if requested
    metadata.APPLY_RECOMMENDATIONS = not disable_metadata_checks

    zim_file = Creator(
        filename=fpath,
        main_path=main_page,
        ignore_duplicates=ignore_duplicates,
    ).config_metadata(
        metadata.StandardMetadataList(
            # mandatory
            Name=metadata.NameMetadata(name),
            Title=metadata.TitleMetadata(title),
            Description=metadata.DescriptionMetadata(description),
            Date=metadata.DateMetadata(date or datetime.date.today()),  # noqa: DTZ011
            Language=metadata.LanguageMetadata(list(languages)),
            Creator=metadata.CreatorMetadata(creator),
            Publisher=metadata.PublisherMetadata(publisher),
            Illustration_48x48_at_1=metadata.DefaultIllustrationMetadata(
                illustration_data
            ),
            # optional
            Tags=metadata.TagsMetadata(list(tags)) if tags else None,
            Source=metadata.SourceMetadata(source) if source else None,
            Flavour=metadata.FlavourMetadata(flavour) if flavour else None,
            Scraper=metadata.ScraperMetadata(scraper) if scraper else None,
            LongDescription=(
                metadata.LongDescriptionMetadata(long_description)
                if long_description
                else None
            ),
        )
    )

    zim_file.start()
    try:
        add_to_zim(build_dir, zim_file, build_dir)

        if redirects or redirects_file:
            add_redirects_to_zim(
                zim_file, redirects=redirects, redirects_file=redirects_file
            )

    # prevents .finish() which would create an incomplete .zim file
    # this would leave a .zim.tmp folder behind.
    # UPSTREAM: wait until a proper cancel() is provided
    except Exception:
        if workaround_nocancel:
            zim_file.can_finish = False  # pragma: no cover
        raise
    finally:
        zim_file.finish()
