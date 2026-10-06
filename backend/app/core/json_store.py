"""Reading the small JSON files that hold queues, drafts and progress."""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def read_json_store(path: Path, default: Any) -> Any:
    """Return the parsed file, or `default` when the file does not exist.

    A file that no longer parses is kept as `<name>.corrupt`: starting empty and
    saving over it would silently destroy whatever was in it. An unreadable file
    raises for the same reason.
    """
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        kept = path.with_name(path.name + ".corrupt")
        path.replace(kept)
        logger.error("%s is not valid JSON (%s); kept as %s and starting empty.", path, exc, kept)
        return default
