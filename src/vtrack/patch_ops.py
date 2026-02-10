import hashlib
from typing import Dict, List, Tuple


"""
Patch ops format (v1):

REPLACE_CLAUSE_TEXT:
  {
    "op": "REPLACE_CLAUSE_TEXT",
    "cid": "c_123",
    "expected_fingerprint": "<sha256 of normalized text>",
    "new_text": "Updated clause text",
    "new_heading": "Optional new heading"
  }

INSERT_CLAUSE:
  {
    "op": "INSERT_CLAUSE",
    "after_cid": "c_122",  # null or "" means insert at start
    "clause": {
      "cid": "c_123",
      "heading": "Optional heading",
      "text": "Clause body text"
    }
  }

REMOVE_CLAUSE:
  {
    "op": "REMOVE_CLAUSE",
    "cid": "c_123",
    "expected_fingerprint": "<sha256 of normalized text>"
  }
"""


def normalize_text(text: str) -> str:
    return " ".join((text or "").split())


def clause_fingerprint(text: str) -> str:
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def apply_patch_ops(snapshot: dict, patch_ops: List[dict]) -> Tuple[dict, List[dict], List[dict]]:
    clauses = [dict(c) for c in snapshot.get("clauses", [])]
    applied_ops: List[dict] = []
    skipped_ops: List[dict] = []

    def reindex() -> Tuple[Dict[str, int], Dict[str, int]]:
        index_by_cid: Dict[str, int] = {}
        index_by_uid: Dict[str, int] = {}
        for idx, clause in enumerate(clauses):
            cid = clause.get("cid")
            if cid:
                index_by_cid[cid] = idx
            clause_uid = clause.get("clause_uid")
            if clause_uid:
                index_by_uid[clause_uid] = idx
        return index_by_cid, index_by_uid

    def resolve_index(op: dict, index_by_cid: Dict[str, int], index_by_uid: Dict[str, int]) -> int | None:
        candidates = []
        cid = op.get("cid")
        clause_uid = op.get("clause_uid")
        if cid:
            candidates.append(cid)
        if clause_uid and clause_uid != cid:
            candidates.append(clause_uid)
        for value in candidates:
            idx = index_by_cid.get(value)
            if idx is not None:
                return idx
            idx = index_by_uid.get(value)
            if idx is not None:
                return idx
        return None

    index_by_cid, index_by_uid = reindex()

    for op in patch_ops:
        op_type = op.get("op")
        if op_type == "REPLACE_CLAUSE_TEXT":
            idx = resolve_index(op, index_by_cid, index_by_uid)
            if idx is None:
                skipped_ops.append({"op": op, "reason": "cid_not_found", "status": "NEEDS_REVIEW"})
                continue
            expected = op.get("expected_fingerprint")
            current_text = clauses[idx].get("text", "")
            if expected and clause_fingerprint(current_text) != expected:
                skipped_ops.append({"op": op, "reason": "fingerprint_mismatch", "status": "NEEDS_REVIEW"})
                continue
            clauses[idx]["text"] = op.get("new_text", "")
            if "new_heading" in op:
                clauses[idx]["heading"] = op.get("new_heading", "")
            applied_ops.append(op)
            continue

        if op_type == "REMOVE_CLAUSE":
            idx = resolve_index(op, index_by_cid, index_by_uid)
            if idx is None:
                skipped_ops.append({"op": op, "reason": "cid_not_found", "status": "NEEDS_REVIEW"})
                continue
            expected = op.get("expected_fingerprint")
            current_text = clauses[idx].get("text", "")
            if expected and clause_fingerprint(current_text) != expected:
                skipped_ops.append({"op": op, "reason": "fingerprint_mismatch", "status": "NEEDS_REVIEW"})
                continue
            clauses.pop(idx)
            index_by_cid, index_by_uid = reindex()
            applied_ops.append(op)
            continue

        if op_type == "INSERT_CLAUSE":
            clause = op.get("clause") or {}
            new_cid = clause.get("cid")
            if not new_cid:
                skipped_ops.append({"op": op, "reason": "missing_clause_cid"})
                continue
            if new_cid in index_by_cid:
                skipped_ops.append({"op": op, "reason": "cid_exists"})
                continue
            after_cid = op.get("after_cid") or op.get("after_clause_uid")
            if not after_cid:
                clauses.insert(0, clause)
                index_by_cid, index_by_uid = reindex()
                applied_ops.append(op)
                continue
            after_idx = index_by_cid.get(after_cid) or index_by_uid.get(after_cid)
            if after_idx is None:
                skipped_ops.append({"op": op, "reason": "after_cid_not_found", "status": "NEEDS_REVIEW"})
                continue
            clauses.insert(after_idx + 1, clause)
            index_by_cid, index_by_uid = reindex()
            applied_ops.append(op)
            continue

        skipped_ops.append({"op": op, "reason": "unknown_op"})

    new_snapshot = dict(snapshot)
    new_snapshot["clauses"] = clauses
    return new_snapshot, applied_ops, skipped_ops
