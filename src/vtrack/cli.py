import argparse
import os

from .constants import AI_REQUESTS_DIR, SUGGESTIONS_DIR
from .diff import diff_commits
from .export import write_docx
from .merge import three_way_merge
from .repo import commit_snapshot, init_repo, log_history
from .suggest import ai_merge, get_model_info, load_ai_requests, write_suggestion
from .util import read_json, write_json
from .apply import apply_suggestion


def cmd_merge(base_id: str, left_id: str, right_id: str, out_path: str) -> None:
    merged, conflicts, ai_requests, merge_id = three_way_merge(base_id, left_id, right_id)
    ext = os.path.splitext(out_path)[1].lower()
    if ext == ".docx":
        write_docx(merged, out_path)
    else:
        write_json(out_path, merged)
    if ai_requests:
        ai_request_path = os.path.join(AI_REQUESTS_DIR, f"{merge_id}.json")
        write_json(
            ai_request_path,
            {
                "merge_id": merge_id,
                "base_commit_id": base_id,
                "left_commit_id": left_id,
                "right_commit_id": right_id,
                "created_at_utc": merged["merge_meta"]["timestamp_utc"],
                "ai_requests": ai_requests,
            },
        )
        print(f"AI requests written to: {ai_request_path}")
    if conflicts:
        print(f"Merged with conflicts in clauses: {conflicts}")
        print(f"Output written to: {out_path}")
    else:
        print("Merged cleanly (no conflicts).")
        print(f"Output written to: {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="FYP PoC: clause-aware version tracking + 3-way merge")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init")

    c = sub.add_parser("commit")
    c.add_argument("--file", required=True, help="Path to contract JSON")
    c.add_argument("--author", required=True)
    c.add_argument("--msg", required=True)

    l = sub.add_parser("log")
    l.add_argument("--limit", type=int, default=50)
    l.add_argument("--show-merge-id", action="store_true")
    l.add_argument("--show-parents", action="store_true")
    l.add_argument("--show-diffs", action="store_true")

    d = sub.add_parser("diff")
    d.add_argument("a")
    d.add_argument("b")

    m = sub.add_parser("merge")
    m.add_argument("--base", required=True)
    m.add_argument("--left", required=True)
    m.add_argument("--right", required=True)
    m.add_argument("--out", default="merged_contract.json")

    s = sub.add_parser("suggest")
    s.add_argument("--merge-id", required=True)
    s.add_argument("--model-dir", default=None, help="Override adapter model directory")
    s.add_argument("--base-model", default=None, help="Use a base model directly (no adapter)")
    s.add_argument("--no-adapter", action="store_true", help="Force running without adapter")
    s.add_argument("--mode", choices=["full", "partial", "alert"], default="full")

    a = sub.add_parser("apply-suggest")
    a.add_argument("--suggestion-id", required=True)
    a.add_argument("--author", required=True)
    a.add_argument("--msg", required=True)
    a.add_argument("--mode", choices=["full", "partial", "alert"], default=None)
    a.add_argument("--approve", action="store_true", help="Apply patch ops after confirming review")

    args = p.parse_args()

    if args.cmd == "init":
        init_repo()
    elif args.cmd == "commit":
        commit_snapshot(args.file, args.author, args.msg)
    elif args.cmd == "log":
        log_history(
            args.limit,
            show_merge_id=args.show_merge_id,
            show_parents=args.show_parents,
            show_diffs=args.show_diffs,
        )
    elif args.cmd == "diff":
        diff_commits(args.a, args.b)
    elif args.cmd == "merge":
        cmd_merge(args.base, args.left, args.right, args.out)
    elif args.cmd == "suggest":
        if args.no_adapter:
            os.environ["VTRACK_NO_ADAPTER"] = "1"
        requests = load_ai_requests(args.merge_id)
        suggestion_payload = ai_merge(
            requests["ai_requests"],
            mode=args.mode,
            model_dir=args.model_dir,
            base_model=args.base_model,
        )
        suggestion = write_suggestion(
            args.merge_id,
            requests,
            suggestion_payload["patch_ops"],
            model_version=get_model_info(model_dir=args.model_dir, base_model=args.base_model),
            mode=args.mode,
            clause_recommendations=suggestion_payload.get("clause_recommendations"),
            clause_alerts=suggestion_payload.get("clause_alerts"),
        )
        print(f"Suggestion written: {os.path.join(SUGGESTIONS_DIR, suggestion['suggestion_id'] + '.json')}")
    elif args.cmd == "apply-suggest":
        suggestion_path = os.path.join(SUGGESTIONS_DIR, f"{args.suggestion_id}.json")
        suggestion = read_json(suggestion_path)
        suggestion_mode = suggestion.get("mode", "full")
        if args.mode and args.mode != suggestion_mode:
            raise SystemExit(f"Suggestion mode is '{suggestion_mode}', but '{args.mode}' was requested.")
        if suggestion_mode != "full":
            raise SystemExit(f"Suggestion mode '{suggestion_mode}' does not include patch ops to apply.")
        if not args.approve:
            raise SystemExit("Refusing to apply patch ops without --approve.")
        result = apply_suggestion(args.suggestion_id, args.author, args.msg)
        print(f"New commit: {result['new_commit_id']}")
        if result["skipped_ops"]:
            print(f"Skipped ops: {len(result['skipped_ops'])}")
