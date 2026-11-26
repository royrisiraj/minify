import re
import string

SHORT_CODE_LENGTH = 7
SHORT_CODE_ALPHABET = string.ascii_letters + string.digits
SHORT_CODE_PATTERN = r"^[0-9A-Za-z]{7}$"
SHORT_CODE_RE = re.compile(SHORT_CODE_PATTERN, re.ASCII)
MAX_CREATION_ATTEMPTS = 5
MAX_URL_LENGTH = 4096
MAX_REQUEST_BYTES = 32 * 1024
RESERVED_PATHS = frozenset(
    {"", "health", "ready", "docs", "redoc", "openapi.json", "openapi", "swagger", "api"}
)


def usable_code(code: str) -> bool:
    return bool(SHORT_CODE_RE.fullmatch(code)) and code.casefold() not in RESERVED_PATHS
