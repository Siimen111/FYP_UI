from typing import Dict, List

from .repo import load_commit
from .util import ensure_repo


def clauses_by_id(snapshot: dict) -> Dict[str, dict]:
    clauses = snapshot.get("clauses", [])
    return {c["cid"]: c for c in clauses}


def diff_snapshots(base: dict, updated: dict) -> List[dict]:
    base_by_id = clauses_by_id(base)
    updated_by_id = clauses_by_id(updated)

    all_ids = sorted(set(base_by_id.keys()) | set(updated_by_id.keys()), key=lambda x: (len(x), x))
    diffs: List[dict] = []
    for cid in all_ids:
        base_clause = base_by_id.get(cid)
        updated_clause = updated_by_id.get(cid)

        if base_clause is None and updated_clause is None:
            continue
        if base_clause is None:
            diffs.append(
                {
                    "op": "ADDED",
                    "cid": cid,
                    "before_text": "",
                    "after_text": updated_clause.get("text", ""),
                    "before_heading": "",
                    "after_heading": updated_clause.get("heading", ""),
                }
            )
            continue
        if updated_clause is None:
            diffs.append(
                {
                    "op": "REMOVED",
                    "cid": cid,
                    "before_text": base_clause.get("text", ""),
                    "after_text": "",
                    "before_heading": base_clause.get("heading", ""),
                    "after_heading": "",
                }
            )
            continue

        if base_clause.get("text") != updated_clause.get("text") or base_clause.get("heading") != updated_clause.get("heading"):
            diffs.append(
                {
                    "op": "CHANGED",
                    "cid": cid,
                    "before_text": base_clause.get("text", ""),
                    "after_text": updated_clause.get("text", ""),
                    "before_heading": base_clause.get("heading", ""),
                    "after_heading": updated_clause.get("heading", ""),
                }
            )

    return diffs


def diff_commits(a_id: str, b_id: str) -> None:
    ensure_repo()
    a = load_commit(a_id)["snapshot"]
    b = load_commit(b_id)["snapshot"]

    A = clauses_by_id(a)
    B = clauses_by_id(b)

    all_ids = sorted(set(A.keys()) | set(B.keys()), key=lambda x: (len(x), x))

    changed = 0
    for cid in all_ids:
        a_clause = A.get(cid)
        b_clause = B.get(cid)

        if a_clause is None:
            print(f"[ADDED]   cid={cid} heading={b_clause.get('heading','')}")
            changed += 1
            continue
        if b_clause is None:
            print(f"[REMOVED] cid={cid} heading={a_clause.get('heading','')}")
            changed += 1
            continue

        if a_clause.get("text") != b_clause.get("text") or a_clause.get("heading") != b_clause.get("heading"):
            changed += 1
            print(f"[CHANGED] cid={cid} heading={b_clause.get('heading','')}")
            print("  --- A:", a_clause.get("text", "").strip())
            print("  +++ B:", b_clause.get("text", "").strip())
            print()

    if changed == 0:
        print("(no differences)")
