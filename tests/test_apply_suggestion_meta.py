import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.vtrack.apply import apply_suggestion
from src.vtrack.constants import SUGGESTIONS_DIR
from src.vtrack.patch_ops import clause_fingerprint
from src.vtrack.repo import commit_snapshot_data, init_repo, load_commit
from src.vtrack.util import write_json


class ApplySuggestionMetaTests(unittest.TestCase):
    def test_apply_suggestion_records_parents_and_clause_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                init_repo()
                base_snapshot = {
                    "doc_id": "doc_demo",
                    "title": "Demo Contract",
                    "clauses": [
                        {"cid": "c_1", "heading": "Payment", "text": "Pay within 10 days."},
                        {"cid": "c_2", "heading": "Term", "text": "Term is 12 months."},
                    ],
                }
                base_commit_id = commit_snapshot_data(base_snapshot, "tester", "base")

                os.makedirs(SUGGESTIONS_DIR, exist_ok=True)
                suggestion_id = "suggest_1"
                patch_ops = [
                    {
                        "op": "REPLACE_CLAUSE_TEXT",
                        "cid": "c_1",
                        "expected_fingerprint": clause_fingerprint("Pay within 10 days."),
                        "new_text": "Pay within 15 days.",
                    }
                ]
                suggestion_payload = {
                    "suggestion_id": suggestion_id,
                    "merge_id": "merge_123",
                    "base_commit_id": base_commit_id,
                    "left_commit_id": "left_1",
                    "right_commit_id": "right_1",
                    "patch_ops": patch_ops,
                    "model_version": "test-model",
                    "created_at_utc": "2026-01-01T00:00:00+00:00",
                }
                write_json(os.path.join(SUGGESTIONS_DIR, f"{suggestion_id}.json"), suggestion_payload)

                result = apply_suggestion(suggestion_id, "tester", "apply suggestion")
                applied_commit = load_commit(result["new_commit_id"])
                ai_meta = applied_commit.get("ai_meta") or {}

                self.assertEqual(ai_meta.get("merge_id"), "merge_123")
                self.assertEqual(ai_meta.get("base_commit_id"), base_commit_id)
                self.assertEqual(ai_meta.get("left_commit_id"), "left_1")
                self.assertEqual(ai_meta.get("right_commit_id"), "right_1")

                diffs = ai_meta.get("clause_diffs") or []
                self.assertEqual(len(diffs), 1)
                diff = diffs[0]
                self.assertEqual(diff.get("op"), "REPLACE_CLAUSE_TEXT")
                self.assertEqual(diff.get("cid"), "c_1")
                self.assertEqual(diff.get("before_text"), "Pay within 10 days.")
                self.assertEqual(diff.get("after_text"), "Pay within 15 days.")
            finally:
                os.chdir(cwd)
