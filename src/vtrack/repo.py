import json
import os

from .constants import COMMITS_DIR, HEAD_FILE
from .snapshot import enrich_snapshot
from .util import ensure_repo, read_json, sha1_str, utc_now_iso, write_json


def init_repo() -> None:
    os.makedirs(COMMITS_DIR, exist_ok=True)
    if not os.path.exists(HEAD_FILE):
        with open(HEAD_FILE, "w", encoding="utf-8") as f:
            f.write("")
    print("Initialized repo in .myvcs/")


def get_head() -> str:
    ensure_repo()
    with open(HEAD_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def set_head(commit_id: str) -> None:
    with open(HEAD_FILE, "w", encoding="utf-8") as f:
        f.write(commit_id)


def load_commit(commit_id: str) -> dict:
    path = os.path.join(COMMITS_DIR, f"{commit_id}.json")
    if not os.path.exists(path):
        raise SystemExit(f"Commit not found: {commit_id}")
    return read_json(path)


def commit_snapshot_data(
    snapshot: dict, author: str, message: str, ai_meta: dict | None = None, parent: str | None = None
) -> str:
    ensure_repo()
    parent_id = parent if parent is not None else get_head() or None
    snapshot = enrich_snapshot(snapshot)

    payload = {
        "parent": parent_id,
        "author": author,
        "timestamp_utc": utc_now_iso(),
        "message": message,
        "snapshot": snapshot,
    }
    if ai_meta:
        payload["ai_meta"] = ai_meta

    # Commit ID is derived from content + metadata; stable enough for PoC.
    commit_id = sha1_str(json.dumps(payload, sort_keys=True))
    payload["commit_id"] = commit_id

    write_json(os.path.join(COMMITS_DIR, f"{commit_id}.json"), payload)
    set_head(commit_id)
    print(f"Committed: {commit_id}")
    return commit_id


def commit_snapshot(contract_path: str, author: str, message: str) -> str:
    snapshot = read_json(contract_path)
    return commit_snapshot_data(snapshot, author, message)


def log_history(
    limit: int = 50,
    show_merge_id: bool = False,
    show_parents: bool = False,
    show_diffs: bool = False,
) -> None:
    ensure_repo()
    head = get_head()
    if not head:
        print("(no commits yet)")
        return

    cur = head
    count = 0
    while cur and count < limit:
        c = load_commit(cur)
        print(f"- {c['commit_id']}")
        print(f"  Author: {c['author']}")
        print(f"  Time:   {c['timestamp_utc']}")
        print(f"  Msg:    {c['message']}")
        if show_merge_id:
            merge_id = (c.get("snapshot") or {}).get("merge_meta", {}).get("merge_id")
            if not merge_id:
                merge_id = (c.get("ai_meta") or {}).get("merge_id")
            if merge_id:
                print(f"  Merge:  {merge_id}")
        if show_parents:
            ai_meta = c.get("ai_meta") or {}
            base_id = ai_meta.get("base_commit_id")
            left_id = ai_meta.get("left_commit_id")
            right_id = ai_meta.get("right_commit_id")
            if base_id or left_id or right_id:
                print(f"  Base:   {base_id or 'n/a'}")
                print(f"  Left:   {left_id or 'n/a'}")
                print(f"  Right:  {right_id or 'n/a'}")
        if show_diffs:
            diffs = (c.get("ai_meta") or {}).get("clause_diffs") or []
            if diffs:
                print("  Diffs:")
                for diff in diffs:
                    op = diff.get("op", "unknown")
                    cid = diff.get("cid", "n/a")
                    before_text = (diff.get("before_text") or "").strip()
                    after_text = (diff.get("after_text") or "").strip()
                    before_heading = diff.get("before_heading")
                    after_heading = diff.get("after_heading")
                    print(f"    - {op} cid={cid}")
                    if before_heading is not None:
                        print(f"      before_heading: {before_heading}")
                    if before_text:
                        print(f"      before_text: {before_text}")
                    if after_heading is not None:
                        print(f"      after_heading: {after_heading}")
                    if after_text:
                        print(f"      after_text: {after_text}")
        cur = c.get("parent")
        count += 1
