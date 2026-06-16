"""Load/save helpers for a show's ``summaries_<show>.json`` file.

The network stores per-show episode records either in the wrapped form
``{"podcast": "<name>", "summaries": [ ... ]}`` (current standard) or as a
bare list (a few legacy files). These helpers read either shape, hand back
the records list for in-place edits, and write it back atomically in the
same shape — used by the multilingual stage to attach ``translations`` to
existing records without disturbing the rest of the file.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple


def load_summaries(path: Path) -> Tuple[Optional[dict], List[dict]]:
    """Return ``(wrapper, records)``.

    ``wrapper`` is the enclosing dict for the wrapped form (so ``save_summaries``
    can preserve sibling keys like ``"podcast"``), or ``None`` for a bare list.
    ``records`` is the list of episode dicts (a live reference into ``wrapper``
    when wrapped) — mutate it, then pass both back to ``save_summaries``.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("summaries"), list):
        return data, data["summaries"]
    if isinstance(data, list):
        return None, data
    raise ValueError(f"Unrecognized summaries shape in {path}")


def upsert_translation(path: Path, episode_num: int, lang: str, entry: dict) -> bool:
    """Concurrency-safe write of one translation track to the summaries file.

    Re-reads the file fresh, sets ``record.translations[lang] = entry`` on the
    matching episode, and saves — so a translation run never clobbers a record
    the live English cron appended between the run's initial load and its save
    (the failure mode of holding an in-memory snapshot and overwriting the
    whole file at the end of a long batch). Returns True if the episode was
    found and written, False otherwise.
    """
    wrapper, records = load_summaries(path)
    for rec in records:
        if rec.get("episode_num") == episode_num:
            rec.setdefault("translations", {})[lang] = entry
            save_summaries(path, wrapper, records)
            return True
    return False


def save_summaries(path: Path, wrapper: Optional[dict], records: List[dict]) -> None:
    """Atomically write ``records`` back, preserving the original shape."""
    path = Path(path)
    if wrapper is not None:
        wrapper["summaries"] = records
        payload = wrapper
    else:
        payload = records
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
