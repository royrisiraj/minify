import logging
import sys
import traceback


def configure_logging(level: str) -> None:
    logger = logging.getLogger("minify")
    logger.setLevel(level)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)


def log_failure(event: str, error: Exception) -> None:
    # Exception strings, source lines, locals, and SQL parameters can contain credentials.
    frames = traceback.extract_tb(error.__traceback__)
    location = " > ".join(f"{frame.name}:{frame.lineno}" for frame in frames)
    logging.getLogger("minify.errors").error(
        "%s type=%s frames=%s", event, type(error).__name__, location
    )
