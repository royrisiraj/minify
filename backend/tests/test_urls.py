import socket
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.constants import MAX_URL_LENGTH
from app.core.exceptions import AppError
from app.services.urls import validate_destination


@pytest.mark.parametrize(
    "value, expected",
    [
        ("https://example.com", "https://example.com"),
        (
            " HTTP://EXAMPLE.COM:8080/Path%2f?a=1&a=2#Case ",
            "http://example.com:8080/Path%2f?a=1&a=2#Case",
        ),
        ("https://example.com/?#", "https://example.com/?#"),
        ("https://example.com./", "https://example.com/"),
        ("https://bücher.de/straße?q=é", "https://xn--bcher-kva.de/stra%C3%9Fe?q=%C3%A9"),
        ("https://faß.de", "https://xn--fa-hia.de"),
        ("http://8.8.8.8/p%20q", "http://8.8.8.8/p%20q"),
        ("https://[2606:4700:4700::1111]/", "https://[2606:4700:4700::1111]/"),
        ("https://example.com/path?next=https%3A%2F%2Felsewhere.com#section", None),
    ],
)
def test_valid_destinations(value, expected, settings):
    with patch.object(socket, "getaddrinfo", side_effect=AssertionError("No DNS allowed")):
        assert validate_destination(value, settings) == (expected or value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        " ",
        "example.com",
        "//example.com",
        "ftp://example.com",
        "javascript:alert(1)",
        "data:text/html,x",
        "file:///tmp/file",
        "http:///example.com",
        "https://",
        "https://?a=b",
        "https://user:secret@example.com",
        "https://user@example.com",
        "https://@example.com",
        "https://example.com:",
        "https://example.com:0",
        "https://example.com:65536",
        "https://example.com:abc",
        "https://example.com:80:90",
        "https://[::1",
        "https://[::1]evil",
        "https://[::1]:443",
        "https://[fe80::1%25eth0]",
        "http://localhost",
        "http://foo.localhost",
        "http://localhost.",
        "http://database",
        "http://foo.internal",
        "http://app.local",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://172.16.0.1",
        "http://192.168.0.1",
        "http://169.254.169.254",
        "http://0.0.0.0",
        "http://224.0.0.1",
        "http://192.0.2.1",
        "http://[::]",
        "http://[fc00::1]",
        "http://[ff02::1]",
        "http://[::ffff:127.0.0.1]",
        "http://2130706433",
        "http://127.1",
        "http://0177.0.0.1",
        "http://0x7f000001",
        "http://0x7f.0.0.1",
        "http://example.123",
        "http://127%2e0%2e0%2e1",
        "http://example..com",
        "http://-example.com",
        "http://example.com..",
        "http://example.com/a b",
        "http://example.com\\@other.com",
        "http://example.com/%",
        "http://example.com/%zz",
        "http://example.com/%0d%0aLocation:evil",
        "http://example.com/%00",
        "http://example.com/%7f",
        "http://example.com/\n",
        "\thttp://example.com/",
        "http://example.com/\x00",
        "http://example.com/\u200b",
        "http://example.com/%E2%80%8B",
        "http://exa mple.com",
    ],
)
def test_unsafe_destinations(value, settings):
    with pytest.raises(AppError) as error:
        validate_destination(value, settings)
    assert error.value.status == 422
    assert value not in error.value.message or len(value) < 2


def test_length_boundaries(settings):
    prefix = "https://example.com/"
    assert (
        len(validate_destination(prefix + "x" * (MAX_URL_LENGTH - len(prefix)), settings))
        == MAX_URL_LENGTH
    )
    with pytest.raises(AppError):
        validate_destination(prefix + "x" * MAX_URL_LENGTH, settings)
    with pytest.raises(AppError):
        validate_destination(prefix + "é" * 1000, settings)


@pytest.mark.parametrize(
    "value",
    ["https://sho.rt/a", "https://SHO.RT:443/a", "https://sho.rt./a", "https://app.example.com/x"],
)
def test_self_origins(value):
    settings = Settings(
        _env_file=None, base_url="https://sho.rt", frontend_url="https://app.example.com"
    )
    with pytest.raises(AppError, match="SELF_REFERENTIAL_URL"):
        validate_destination(value, settings)
