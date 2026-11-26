import ipaddress
import re
import unicodedata
from urllib.parse import quote, unquote, urlsplit

import idna

from app.core.config import Settings
from app.core.constants import MAX_URL_LENGTH
from app.core.exceptions import AppError


def invalid_url() -> AppError:
    return AppError(
        422, "INVALID_URL", "Enter a valid public HTTP or HTTPS URL without credentials."
    )


def unsafe_character(value: str) -> bool:
    return any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in value)


def public_host(host: str) -> str:
    if "%" in host:
        raise invalid_url()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            host = idna.encode(host, uts46=True, std3_rules=True).decode("ascii").lower()
        except idna.IDNAError:
            raise invalid_url() from None
        # A single trailing DNS root dot has the same origin as the unqualified spelling.
        host = host.removesuffix(".")
        labels = host.split(".")
        if (
            len(labels) < 2
            or len(host) > 253
            or labels[-1]
            in {
                "localhost",
                "local",
                "internal",
                "lan",
                "home",
                "localdomain",
                "test",
                "invalid",
                "onion",
            }
            or re.fullmatch(r"(?:[0-9]+|0x[0-9a-f]+)", labels[-1], re.IGNORECASE)
        ):
            raise invalid_url() from None
        return host
    if not address.is_global or address.is_multicast:
        raise invalid_url()
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped and (
            not address.ipv4_mapped.is_global or address.ipv4_mapped.is_multicast
        ):
            raise invalid_url()
        return f"[{address.compressed}]"
    return str(address)


def validate_destination(value: str, settings: Settings) -> str:
    # Check before parsing: urlsplit silently removes some controls.
    if not value or len(value) > MAX_URL_LENGTH or unsafe_character(value) or "\\" in value:
        raise invalid_url()
    value = value.strip(" ")
    if not value or any(c.isspace() for c in value):
        raise invalid_url()
    if not re.match(r"https?://", value, re.IGNORECASE):
        raise AppError(
            422, "INVALID_URL_SCHEME", "Use a complete URL starting with http:// or https://."
        )
    if re.search(r"%(?![0-9a-fA-F]{2})", value) or unsafe_character(unquote(value)):
        raise invalid_url()
    try:
        parts = urlsplit(value)
        if not parts.netloc or "@" in parts.netloc or not parts.hostname:
            raise invalid_url()
        # A colon must introduce a real port; a bracket must close the entire IPv6 host.
        authority = parts.netloc
        if authority.startswith("["):
            if not re.fullmatch(r"\[[^\]]+\](?::[0-9]+)?", authority):
                raise invalid_url()
        elif not re.fullmatch(r"[^:]+(?::[0-9]+)?", authority):
            raise invalid_url()
        port = parts.port
        if port is not None and not 1 <= port <= 65535:
            raise invalid_url()
        host = public_host(parts.hostname)
    except ValueError:
        raise invalid_url() from None
    scheme = parts.scheme.lower()
    for configured in (settings.base_url, settings.frontend_url):
        origin = urlsplit(str(configured))
        origin_host = origin.hostname.lower().removesuffix(".")
        if (scheme, host.strip("[]"), port or (443 if scheme == "https" else 80)) == (
            origin.scheme,
            origin_host,
            origin.port or (443 if origin.scheme == "https" else 80),
        ):
            raise AppError(
                422, "SELF_REFERENTIAL_URL", "Use a destination outside this Minify service."
            )
    result = f"{scheme}://{host}" + (f":{port}" if port is not None else "")
    result += quote(parts.path, safe="/%:@!$&'()*+,;=-._~")
    # Preserve empty query/fragment delimiters and existing percent encoding.
    before_fragment = value.split("#", 1)[0]
    if "?" in before_fragment:
        result += "?" + quote(parts.query, safe="/%?:@!$&'()*+,;=-._~")
    if "#" in value:
        result += "#" + quote(parts.fragment, safe="/%?:@!$&'()*+,;=-._~")
    if len(result) > MAX_URL_LENGTH:
        raise invalid_url()
    return result
