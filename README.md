# VTrack (AI Merge Prototype)

Local AI merge suggestion (no adapter) using Gemma 3 4B:

```sh
python src/fyp_vtrack.py suggest --merge-id <merge_id> --base-model "C:\\Users\\sherm\\FYP\\src\\gemma_3_4b_it" --no-adapter
```

## Next steps

- Alert when different lawyers edit the same clause (two-way or three-way conflicts).
- Add feature for outputting new file after merge.
- Re-integrate three-way merges (safe merge for non-conflicting clauses when three unresolved conflicts remain).
- Refine the lawyer UI with separate clickable tabs.
- Package the app as a simple executable for lawyers (open, upload, compare).
- Add stub login for different lawyers to save preferences and uploader names.
- Canned demo docs + unit tests for `apply_patch_ops` + integration test `/merge` → `/suggest` → `/apply`.
- UX polish + logging/audit (hash mismatch warnings, suggestion rationale, export).
- Demo script + buffer for top failure modes.
- Fine-tune a new Gemma-based adapter (LoRA) and wire it into `vtrack.suggest`.

## Completed

- Add FastAPI endpoints (`/merge`, `/suggest`, `/apply`, `/commits`, `/commit/{id}`, `/suggestion/{id}`).
- Minimal UI wired to API (commit picker, conflict list, suggestion panel, apply/skip).

# CLI Testing Quickstart

## 1) Initialize + commit base/left/right

```sh
python src/fyp_vtrack.py init
python src/fyp_vtrack.py commit --file contract.json --author "you" --msg "base"
python src/fyp_vtrack.py commit --file contract_diff.json --author "you" --msg "left"
python src/fyp_vtrack.py commit --file contract_diff_alt.json --author "you" --msg "right"
python src/fyp_vtrack.py log --limit 3
```

## 2) Merge + find the merge ID

```sh
python src/fyp_vtrack.py merge --base <base_id> --left <left_id> --right <right_id> --out merged_contract.json
Get-ChildItem .myvcs\ai_requests
```

The filename (without `.json`) is the `merge_id`.

## 3) Generate a suggestion (base model only)

```sh
python src/fyp_vtrack.py suggest --merge-id <merge_id> --base-model "C:\\Users\\sherm\\FYP\\src\\gemma_3_4b_it" --mode full
```

Other modes:

```sh
python src/fyp_vtrack.py suggest --merge-id <merge_id> --base-model "C:\\Users\\sherm\\FYP\\src\\gemma_3_4b_it" --mode partial
python src/fyp_vtrack.py suggest --merge-id <merge_id> --base-model "C:\\Users\\sherm\\FYP\\src\\gemma_3_4b_it" --mode alert
```

## 4) Apply a suggestion (explicit approval required)

```sh
python src/fyp_vtrack.py apply-suggest --suggestion-id <suggestion_id> --author "you" --msg "apply suggestion" --approve
```

## 5) View the timeline (merge IDs, parents, clause diffs)

```sh
python src/fyp_vtrack.py log --show-merge-id --show-parents --show-diffs
```

# Desktop UI (Electron)

## Setup

```sh
cd desktop
npm install
```

## Run

```sh
npm start
```

## Notes

- Ensure the FastAPI server is running (default: `http://127.0.0.1:8000`).
- Update the API Base URL in the app if your server is bound to a different host/port.

### Start the FastAPI server

```sh
VTRACK_DEVICE_MAP=auto VTRACK_MAX_NEW_TOKENS=128 python -m uvicorn vtrack.api:app
```

```sh
VTRACK_BASE_MODEL="C:\Users\sherm\FYP\src\gemma_3_4b_it"
```
