import os
import sys
import tempfile
import unittest
from unittest import mock

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from src.vtrack.api import app
from src.vtrack.constants import AI_REQUESTS_DIR, SUGGESTIONS_DIR
from src.vtrack.patch_ops import clause_fingerprint
from src.vtrack.repo import commit_snapshot_data, init_repo, load_commit
from src.vtrack.util import read_json, write_json


class ApiEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        init_repo()
        self.client = TestClient(app)

    def tearDown(self) -> None:
        os.chdir(self.cwd)
        self.temp_dir.cleanup()

    def _seed_commits(self) -> tuple[str, str, str]:
        base_snapshot = {
            "doc_id": "doc_demo",
            "title": "Demo Contract",
            "clauses": [
                {"cid": "c_1", "heading": "Payment", "text": "Pay within 10 days."},
                {"cid": "c_2", "heading": "Term", "text": "Term is 12 months."},
            ],
        }
        left_snapshot = {
            **base_snapshot,
            "clauses": [
                {"cid": "c_1", "heading": "Payment", "text": "Pay within 15 days."},
                {"cid": "c_2", "heading": "Term", "text": "Term is 12 months."},
            ],
        }
        right_snapshot = {
            **base_snapshot,
            "clauses": [
                {"cid": "c_1", "heading": "Payment", "text": "Pay within 5 days."},
                {"cid": "c_2", "heading": "Term", "text": "Term is 12 months."},
            ],
        }
        base_id = commit_snapshot_data(base_snapshot, "tester", "base")
        left_id = commit_snapshot_data(left_snapshot, "tester", "left")
        right_id = commit_snapshot_data(right_snapshot, "tester", "right")
        return base_id, left_id, right_id

    def test_merge_and_commit_endpoints(self) -> None:
        base_id, left_id, right_id = self._seed_commits()

        response = self.client.post(
            "/merge",
            json={
                "base_id": base_id,
                "left_id": left_id,
                "right_id": right_id,
                "out_path": "merged.json",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("merge_id", payload)
        self.assertTrue(payload["conflicts"])
        self.assertTrue(os.path.exists(payload["ai_request_path"]))

        commit_response = self.client.get(f"/commit/{base_id}")
        self.assertEqual(commit_response.status_code, 200)
        self.assertEqual(commit_response.json().get("commit_id"), base_id)

        commits_response = self.client.get("/commits")
        self.assertEqual(commits_response.status_code, 200)
        self.assertGreaterEqual(commits_response.json().get("count", 0), 3)

    def test_suggest_and_apply_endpoints(self) -> None:
        base_id, left_id, right_id = self._seed_commits()
        merge_id = "merge_test_1"
        ai_request_payload = {
            "merge_id": merge_id,
            "base_commit_id": base_id,
            "left_commit_id": left_id,
            "right_commit_id": right_id,
            "created_at_utc": "2026-01-01T00:00:00+00:00",
            "ai_requests": [
                {
                    "cid": "c_1",
                    "base": {"text": "Pay within 10 days."},
                    "left": {"text": "Pay within 15 days."},
                    "right": {"text": "Pay within 5 days."},
                    "base_commit_id": base_id,
                    "left_commit_id": left_id,
                    "right_commit_id": right_id,
                    "expected_fingerprint": clause_fingerprint("Pay within 10 days."),
                }
            ],
        }
        os.makedirs(AI_REQUESTS_DIR, exist_ok=True)
        write_json(os.path.join(AI_REQUESTS_DIR, f"{merge_id}.json"), ai_request_payload)

        patch_ops = [
            {
                "op": "REPLACE_CLAUSE_TEXT",
                "cid": "c_1",
                "expected_fingerprint": clause_fingerprint("Pay within 10 days."),
                "new_text": "Pay within 12 days.",
            }
        ]
        with mock.patch("vtrack.api.ai_merge", return_value={"patch_ops": patch_ops}) as _mock_merge:
            with mock.patch("vtrack.api.get_model_info", return_value="test-model"):
                suggest_response = self.client.post(
                    "/suggest",
                    json={"merge_id": merge_id, "base_model": "dummy", "mode": "full", "no_adapter": True},
                )

        self.assertEqual(suggest_response.status_code, 200)
        suggestion = suggest_response.json().get("suggestion") or {}
        suggestion_id = suggestion.get("suggestion_id")
        self.assertTrue(suggestion_id)
        suggestion_path = os.path.join(SUGGESTIONS_DIR, f"{suggestion_id}.json")
        self.assertTrue(os.path.exists(suggestion_path))

        apply_response = self.client.post(
            "/apply",
            json={"suggestion_id": suggestion_id, "author": "tester", "msg": "apply suggestion"},
        )
        self.assertEqual(apply_response.status_code, 200)
        new_commit_id = apply_response.json().get("new_commit_id")
        self.assertTrue(new_commit_id)

        applied_commit = load_commit(new_commit_id)
        clauses = applied_commit.get("snapshot", {}).get("clauses", [])
        clause_texts = {clause.get("cid"): clause.get("text") for clause in clauses}
        self.assertEqual(clause_texts.get("c_1"), "Pay within 12 days.")

        suggestion_response = self.client.get(f"/suggestion/{suggestion_id}")
        self.assertEqual(suggestion_response.status_code, 200)
        stored = suggestion_response.json()
        self.assertEqual(stored.get("suggestion_id"), suggestion_id)
        self.assertEqual(read_json(suggestion_path).get("suggestion_id"), suggestion_id)
