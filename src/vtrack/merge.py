from typing import List, Tuple

from .diff import clauses_by_id
from .patch_ops import clause_fingerprint
from .repo import load_commit
from .util import ensure_repo, sha1_str, utc_now_iso


def _clause_payload(clause: dict | None) -> dict:
    if clause is None:
        return {"text": "", "hash": None, "heading": ""}
    text = clause.get("text", "")
    return {"text": text, "hash": clause_fingerprint(text), "heading": clause.get("heading", "")}


def _build_ai_request(
    cid: str, base_id: str, left_id: str, right_id: str, base: dict | None, left: dict | None, right: dict | None
) -> dict:
    base_payload = _clause_payload(base)
    return {
        "cid": cid,
        "base": base_payload,
        "left": _clause_payload(left),
        "right": _clause_payload(right),
        "base_commit_id": base_id,
        "left_commit_id": left_id,
        "right_commit_id": right_id,
        "expected_fingerprint": base_payload.get("hash"),
    }


def three_way_merge(base_id: str, left_id: str, right_id: str) -> Tuple[dict, List[str], List[dict], str]:
    """
    Clause-level 3-way merge:
    - If only one side changed from base => take that change
    - If both changed and identical => take it
    - If both changed and different => conflict
    """
    ensure_repo()
    base = load_commit(base_id)["snapshot"]
    left = load_commit(left_id)["snapshot"]
    right = load_commit(right_id)["snapshot"]

    base_by_id = clauses_by_id(base)
    left_by_id = clauses_by_id(left)
    right_by_id = clauses_by_id(right)

    all_ids = sorted(
        set(base_by_id.keys()) | set(left_by_id.keys()) | set(right_by_id.keys()),
        key=lambda x: (len(x), x),
    )
    conflicts: List[str] = []
    ai_requests: List[dict] = []

    merged_clauses: List[dict] = []
    for cid in all_ids:
        b = base_by_id.get(cid)
        l = left_by_id.get(cid)
        r = right_by_id.get(cid)

        # Helper to compare clause equality (heading + text)
        def eq(x, y) -> bool:
            if x is None and y is None:
                return True
            if x is None or y is None:
                return False
            return x.get("heading") == y.get("heading") and x.get("text") == y.get("text")

        # Cases
        if eq(l, r):
            # Both same (including both None) => take that
            if l is not None:
                merged_clauses.append(l)
            continue

        # If left unchanged from base => take right
        if eq(l, b) and r is not None:
            merged_clauses.append(r)
            continue

        # If right unchanged from base => take left
        if eq(r, b) and l is not None:
            merged_clauses.append(l)
            continue

        # Otherwise conflict (both changed differently, or add/remove mismatch)
        conflicts.append(cid)
        ai_requests.append(_build_ai_request(cid, base_id, left_id, right_id, b, l, r))
        heading = (l or r or b or {}).get("heading", "")
        merged_clauses.append(
            {
                "cid": cid,
                "heading": heading,
                "text": (
                    "<<<CONFLICT>>>\n"
                    f"--- LEFT ({left_id}) ---\n{(l or {}).get('text','')}\n\n"
                    f"--- RIGHT ({right_id}) ---\n{(r or {}).get('text','')}\n"
                    "<<<END CONFLICT>>>"
                ),
            }
        )

    merge_id = sha1_str(f"{base_id}:{left_id}:{right_id}:{utc_now_iso()}")
    merged = {
        "doc_id": base.get("doc_id", "unknown"),
        "title": base.get("title", "Merged Document"),
        "clauses": merged_clauses,
        "merge_meta": {
            "merge_id": merge_id,
            "base": base_id,
            "left": left_id,
            "right": right_id,
            "timestamp_utc": utc_now_iso(),
            "conflict_cids": conflicts,
        },
    }
    return merged, conflicts, ai_requests, merge_id


def two_way_merge(base_id: str, other_id: str) -> Tuple[dict, List[str], List[dict], str]:
    """
    Clause-level 2-way merge:
    - Take changes from other compared to base.
    - Treat any changed clause as a conflict for suggestion.
    """
    ensure_repo()
    base = load_commit(base_id)["snapshot"]
    other = load_commit(other_id)["snapshot"]

    base_by_id = clauses_by_id(base)
    other_by_id = clauses_by_id(other)

    all_ids = sorted(
        set(base_by_id.keys()) | set(other_by_id.keys()),
        key=lambda x: (len(x), x),
    )

    conflicts: List[str] = []
    ai_requests: List[dict] = []
    merged_clauses: List[dict] = []
    for cid in all_ids:
        b = base_by_id.get(cid)
        o = other_by_id.get(cid)

        if o is not None:
            merged_clauses.append(o)

        if b is None and o is None:
            continue

        def eq(x, y) -> bool:
            if x is None and y is None:
                return True
            if x is None or y is None:
                return False
            return x.get("heading") == y.get("heading") and x.get("text") == y.get("text")

        if not eq(b, o):
            conflicts.append(cid)
            ai_requests.append(_build_ai_request(cid, base_id, other_id, base_id, b, o, b))

    merge_id = sha1_str(f"{base_id}:{other_id}:{utc_now_iso()}")
    merged = {
        "doc_id": base.get("doc_id", "unknown"),
        "title": base.get("title", "Merged Document"),
        "clauses": merged_clauses,
        "merge_meta": {
            "merge_id": merge_id,
            "base": base_id,
            "left": other_id,
            "right": None,
            "timestamp_utc": utc_now_iso(),
            "conflict_cids": conflicts,
        },
    }
    return merged, conflicts, ai_requests, merge_id
