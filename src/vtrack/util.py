import hashlib
import json
import os
from datetime import datetime, timezone

from .constants import COMMITS_DIR, HEAD_FILE, VCS_DIR


def utc_now_iso() -> str:
    # Store a timezone-aware timestamp; you can show it in local time later if needed.
    return datetime.now(timezone.utc).isoformat()


def read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: str, obj: dict) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def sha1_str(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()


def ensure_repo() -> None:
    if not os.path.isdir(VCS_DIR) or not os.path.isdir(COMMITS_DIR) or not os.path.isfile(HEAD_FILE):
        raise SystemExit("Not a repo. Run: python fyp_vtrack.py init")
