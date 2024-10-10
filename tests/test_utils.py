import pytest

from ted2zim.utils import is_valid_uri


@pytest.mark.parametrize(
    ["url", "expected"],
    [
        ("http://-/", False),
        (
            "https://ted-conferences-speaker-photos-production.s3.amazonaws.com",
            True,
        ),
        ("http://-example.com", False),
        ("https://example-.com", False),
        ("https//example..com", False),
        ("http://www.asdf.com", True),
        ("http://A1-B2.C3D4.E5F6.COM", True),
    ],
)
def test_is_valid_uri(url, expected):
    assert is_valid_uri(url) == expected
