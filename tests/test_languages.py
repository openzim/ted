import pytest

from ted2zim import languages as tedlang


@pytest.mark.parametrize(
    "input_languages,expected_languages",
    [
        pytest.param(["English", "fr", "hin"], ["en", "fr", "hi"], id="simple"),
        pytest.param(["chi"], ["zh", "zh-cn", "zh-tw"], id="chinese"),
        pytest.param(["Portuguese"], ["pt", "pt-br"], id="portuguese"),
        pytest.param(["de_AT"], ["de"], id="austria"),
        pytest.param(["pt-br"], ["pt-br"], id="brazilian"),
        pytest.param(["alg"], [], id="missing_iso_639_3"),
        pytest.param(["fake"], [], id="not_existing"),
        pytest.param(
            ["English", "fr", "hin", "chi", "fake"],
            ["en", "fr", "hi", "zh", "zh-cn", "zh-tw"],
            id="full",
        ),
    ],
)
def test_to_ted_languages(input_languages, expected_languages):
    # we compare sets since order is not relevant
    assert set(tedlang.to_ted_langcodes(input_languages)) == set(expected_languages)


@pytest.mark.parametrize(
    "input_languages,expected_mapping",
    [
        pytest.param(
            ["en", "fr", "hi"], {"en": "eng", "fr": "fra", "hi": "hin"}, id="simple"
        ),
        pytest.param(
            ["zh", "zh-cn", "zh-tw"],
            {"zh": "zho", "zh-cn": "zho", "zh-tw": "zho"},
            id="chinese",
        ),
        pytest.param(["pt", "pt-br"], {"pt": "por", "pt-br": "por"}, id="portuguese"),
        pytest.param(["de_AT"], {"de_AT": "deu"}, id="austria"),
        pytest.param(["alg"], {"alg": None}, id="missing_iso_639_3"),
        pytest.param(["fake"], {"fake": None}, id="not_existing"),
        pytest.param(
            [
                "en",
                "fr",
                "hi",
                "zh",
                "zh-cn",
                "zh-tw",
                "pt",
                "pt-br",
                "de_AT",
                "alg",
                "fake",
            ],
            {
                "en": "eng",
                "fr": "fra",
                "hi": "hin",
                "zh": "zho",
                "zh-cn": "zho",
                "zh-tw": "zho",
                "de_AT": "deu",
                "pt": "por",
                "pt-br": "por",
                "alg": None,
                "fake": None,
            },
            id="full",
        ),
    ],
)
def test_ted_to_iso639_3_langcodes(input_languages, expected_mapping):
    assert tedlang.ted_to_iso639_3_langcodes(input_languages) == expected_mapping
