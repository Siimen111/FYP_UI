import os
from typing import List

from .patch_ops import clause_fingerprint
from .constants import COMMITS_DIR
from .util import ensure_repo, read_json


def enrich_snapshot(snapshot: dict) -> dict:
    clauses = []
    for clause in snapshot.get("clauses", []):
        text = clause.get("text", "")
        updated = dict(clause)
        updated["clause_hash"] = clause.get("clause_hash") or clause_fingerprint(text)
        clauses.append(updated)
    new_snapshot = dict(snapshot)
    new_snapshot["clauses"] = clauses
    return new_snapshot


def get_snapshot(commit_id: str) -> List[dict]:
    ensure_repo()
    path = os.path.join(COMMITS_DIR, f"{commit_id}.json")
    snapshot = read_json(path)["snapshot"]
    enriched = enrich_snapshot(snapshot)
    ordered: List[dict] = []
    for clause in enriched.get("clauses", []):
        ordered.append(
            {
                "clause_uid": clause.get("cid"),
                "section_path": clause.get("section_path", ""),
                "text": clause.get("text", ""),
                "clause_hash": clause.get("clause_hash"),
            }
        )
    return ordered
