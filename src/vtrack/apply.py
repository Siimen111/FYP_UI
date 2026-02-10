import os

from .constants import SUGGESTIONS_DIR
from .patch_ops import apply_patch_ops
from .repo import commit_snapshot_data, load_commit
from .util import read_json, utc_now_iso


def apply_suggestion(suggestion_id: str, author: str, message: str) -> dict:
    suggestion_path = os.path.join(SUGGESTIONS_DIR, f"{suggestion_id}.json")
    suggestion = read_json(suggestion_path)

    base_commit_id = suggestion.get("base_commit_id")
    if not base_commit_id:
        raise SystemExit("Suggestion missing base_commit_id")

    base_snapshot = load_commit(base_commit_id)["snapshot"]
    patch_ops = suggestion.get("patch_ops", [])
    new_snapshot, applied_ops, skipped_ops = apply_patch_ops(base_snapshot, patch_ops)

    def _find_clause(snapshot: dict, clause_id: str) -> dict | None:
        for clause in snapshot.get("clauses", []):
            if clause.get("cid") == clause_id or clause.get("clause_uid") == clause_id:
                return clause
        return None

    clause_diffs = []
    for op in applied_ops:
        op_type = op.get("op")
        cid = op.get("cid") or op.get("clause_uid")
        before_clause = _find_clause(base_snapshot, cid) if cid else None
        if op_type == "REPLACE_CLAUSE_TEXT":
            clause_diffs.append(
                {
                    "op": op_type,
                    "cid": cid,
                    "before_text": (before_clause or {}).get("text", ""),
                    "after_text": op.get("new_text", ""),
                    "after_heading": op.get("new_heading"),
                }
            )
        elif op_type == "REMOVE_CLAUSE":
            clause_diffs.append(
                {
                    "op": op_type,
                    "cid": cid,
                    "before_text": (before_clause or {}).get("text", ""),
                    "before_heading": (before_clause or {}).get("heading", ""),
                }
            )
        elif op_type == "INSERT_CLAUSE":
            clause = op.get("clause") or {}
            clause_diffs.append(
                {
                    "op": op_type,
                    "cid": clause.get("cid"),
                    "after_text": clause.get("text", ""),
                    "after_heading": clause.get("heading", ""),
                }
            )

    ai_meta = {
        "applied_suggestion_id": suggestion_id,
        "merge_id": suggestion.get("merge_id"),
        "base_commit_id": suggestion.get("base_commit_id"),
        "left_commit_id": suggestion.get("left_commit_id"),
        "right_commit_id": suggestion.get("right_commit_id"),
        "model": suggestion.get("model_version"),
        "generated_at_utc": suggestion.get("created_at_utc"),
        "applied_at_utc": utc_now_iso(),
        "conflict_cids": [op.get("cid") for op in patch_ops if op.get("cid")],
        "skipped_ops": skipped_ops,
        "clause_diffs": clause_diffs,
    }

    new_commit_id = commit_snapshot_data(
        new_snapshot,
        author,
        message,
        ai_meta=ai_meta,
        parent=base_commit_id,
    )

    return {
        "new_commit_id": new_commit_id,
        "applied_ops": applied_ops,
        "skipped_ops": skipped_ops,
    }
