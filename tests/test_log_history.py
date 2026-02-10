import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.vtrack.repo import commit_snapshot_data, init_repo, log_history


class LogHistoryTests(unittest.TestCase):
    def test_log_history_shows_parents_and_diffs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = os.getcwd()
            os.chdir(temp_dir)
            try:
                init_repo()
                snapshot = {
                    "doc_id": "doc_demo",
                    "title": "Demo Contract",
                    "clauses": [{"cid": "c_1", "heading": "Payment", "text": "Pay within 10 days."}],
                }
                ai_meta = {
                    "merge_id": "merge_456",
                    "base_commit_id": "base_1",
                    "left_commit_id": "left_1",
                    "right_commit_id": "right_1",
                    "clause_diffs": [
                        {
                            "op": "REPLACE_CLAUSE_TEXT",
                            "cid": "c_1",
                            "before_text": "Pay within 10 days.",
                            "after_text": "Pay within 15 days.",
                        }
                    ],
                }
                commit_snapshot_data(snapshot, "tester", "test commit", ai_meta=ai_meta)

                buffer = io.StringIO()
                with redirect_stdout(buffer):
                    log_history(limit=10, show_merge_id=True, show_parents=True, show_diffs=True)
                output = buffer.getvalue()

                self.assertIn("Merge:  merge_456", output)
                self.assertIn("Base:   base_1", output)
                self.assertIn("Left:   left_1", output)
                self.assertIn("Right:  right_1", output)
                self.assertIn("Diffs:", output)
                self.assertIn("before_text: Pay within 10 days.", output)
                self.assertIn("after_text: Pay within 15 days.", output)
            finally:
                os.chdir(cwd)
