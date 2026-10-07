"""A failed step must not be recorded or shown as a success."""

import asyncio

from backend.app.core.json_store import read_json_store


def test_corrupt_store_is_kept_instead_of_being_overwritten(tmp_path):
    path = tmp_path / "queue.json"
    path.write_text("{broken", encoding="utf-8")

    assert read_json_store(path, {"applications": {}}) == {"applications": {}}
    assert (tmp_path / "queue.json.corrupt").read_text(encoding="utf-8") == "{broken"
    assert not path.exists()


def test_missing_store_starts_from_the_default(tmp_path):
    assert read_json_store(tmp_path / "none.json", []) == []
