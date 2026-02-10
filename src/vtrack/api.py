import os
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .apply import apply_suggestion
from .constants import AI_REQUESTS_DIR, COMMITS_DIR, HEAD_FILE, SUGGESTIONS_DIR
from .diff import clauses_by_id, diff_snapshots
from .export import write_docx
from .parse import parse_clauses_ai, parse_clauses_simple
from .merge import three_way_merge, two_way_merge
from .repo import commit_snapshot_data, get_head, init_repo, load_commit
from .suggest import _get_model, ai_merge, get_model_info, load_ai_requests, write_suggestion
from .util import ensure_repo, read_json, write_json


app = FastAPI(title="VTrack API")


def _http_bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=400, detail=str(exc))


def _http_not_found(message: str) -> HTTPException:
    return HTTPException(status_code=404, detail=message)


def _ensure_repo_or_init() -> None:
    try:
        ensure_repo()
    except SystemExit:
        init_repo()


@app.on_event("startup")
def warm_model_on_startup() -> None:
    if os.environ.get("VTRACK_WARM_MODEL", "1") != "1":
        return
    try:
        _get_model()
    except Exception as exc:
        raise RuntimeError(f"Failed to warm model on startup: {exc}") from exc


def _snapshot_from_text(
    text: str,
    title: str,
    doc_id: str,
    parse_mode: str = "ai",
    model_dir: str | None = None,
    base_model: str | None = None,
) -> Dict[str, Any]:
    if parse_mode == "ai":
        clauses = parse_clauses_ai(text, model_dir=model_dir, base_model=base_model)
    else:
        clauses = parse_clauses_simple(text)
    return {"doc_id": doc_id, "title": title, "clauses": clauses}


def _snapshot_from_upload_content(
    file: UploadFile,
    content: bytes,
    title: str,
    doc_id: str,
    parse_mode: str = "ai",
    model_dir: str | None = None,
    base_model: str | None = None,
) -> Dict[str, Any]:
    filename = (file.filename or "").lower()
    if filename.endswith(".txt"):
        text = content.decode("utf-8", errors="replace")
        return _snapshot_from_text(
            text,
            title,
            doc_id,
            parse_mode=parse_mode,
            model_dir=model_dir,
            base_model=base_model,
        )
    if filename.endswith(".docx"):
        placeholder = f"[DOCX upload stub] {file.filename or 'document.docx'}"
        return _snapshot_from_text(
            placeholder,
            title,
            doc_id,
            parse_mode="simple",
            model_dir=model_dir,
            base_model=base_model,
        )
    raise ValueError("Unsupported file type. Upload .txt or .docx.")


class MergeRequest(BaseModel):
    base_id: str
    left_id: str
    right_id: Optional[str] = None
    out_path: Optional[str] = None


class SuggestRequest(BaseModel):
    merge_id: str
    model_dir: Optional[str] = None
    base_model: Optional[str] = None
    no_adapter: bool = False
    mode: str = "full"


class ApplyRequest(BaseModel):
    suggestion_id: str
    author: str
    msg: str
    mode: Optional[str] = None


@app.post("/merge")
def merge(request: MergeRequest) -> Dict[str, Any]:
    try:
        if request.right_id:
            merged, conflicts, ai_requests, merge_id = three_way_merge(
                request.base_id, request.left_id, request.right_id
            )
        else:
            merged, conflicts, ai_requests, merge_id = two_way_merge(
                request.base_id, request.left_id
            )
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    merged_path = None
    if request.out_path:
        ext = os.path.splitext(request.out_path)[1].lower()
        if ext == ".docx":
            write_docx(merged, request.out_path)
        else:
            write_json(request.out_path, merged)
        merged_path = request.out_path

    ai_request_path = os.path.join(AI_REQUESTS_DIR, f"{merge_id}.json")
    write_json(
        ai_request_path,
        {
            "merge_id": merge_id,
            "base_commit_id": request.base_id,
            "left_commit_id": request.left_id,
            "right_commit_id": request.right_id,
            "created_at_utc": merged["merge_meta"]["timestamp_utc"],
            "ai_requests": ai_requests,
        },
    )

    return {
        "merge_id": merge_id,
        "conflicts": conflicts,
        "merged": merged,
        "merged_path": merged_path,
        "ai_request_path": ai_request_path,
    }


@app.post("/upload")
async def upload_contract(
    author: str = Form(...),
    message: Optional[str] = Form(None),
    parse_mode: str = Form("ai"),
    base_model: Optional[str] = Form(None),
    file: UploadFile = File(...),
) -> Dict[str, Any]:
    try:
        _ensure_repo_or_init()
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    head_id = get_head() or None
    base_snapshot = None
    base_author = None
    doc_id = file.filename or "document"
    title = file.filename or "Uploaded Document"
    if head_id:
        base_commit = load_commit(head_id)
        base_snapshot = base_commit["snapshot"]
        base_author = base_commit.get("author")
        doc_id = base_snapshot.get("doc_id", doc_id)
        title = base_snapshot.get("title", title)

    content = await file.read()
    try:
        snapshot = _snapshot_from_upload_content(
            file,
            content,
            title,
            doc_id,
            parse_mode=parse_mode,
            base_model=base_model,
        )
    except (ValueError, RuntimeError) as exc:
        if parse_mode == "ai":
            text = content.decode("utf-8", errors="replace")
            snapshot = _snapshot_from_text(text, title, doc_id, parse_mode="simple")
        else:
            raise _http_bad_request(exc) from exc

    base_snapshot = base_snapshot or {"clauses": []}
    clause_diffs = diff_snapshots(base_snapshot, snapshot)
    base_by_id = clauses_by_id(base_snapshot)
    conflict_cids = []
    if base_author and base_author != author:
        conflict_cids = [
            diff["cid"]
            for diff in clause_diffs
            if diff.get("cid") in base_by_id
        ]
    ai_meta = {
        "base_commit_id": head_id,
        "clause_diffs": clause_diffs,
        "changed_clause_count": len(clause_diffs),
        "conflict_cids": conflict_cids,
    }

    commit_message = message or f"{author} upload"
    commit_id = commit_snapshot_data(snapshot, author, commit_message, ai_meta=ai_meta, parent=head_id)
    return {"commit_id": commit_id, "changed_clause_count": len(clause_diffs)}


@app.post("/suggest")
def suggest(request: SuggestRequest) -> Dict[str, Any]:
    try:
        payload = load_ai_requests(request.merge_id)
    except FileNotFoundError as exc:
        raise _http_not_found(f"AI request not found for merge_id: {request.merge_id}") from exc
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    os.environ["VTRACK_NO_ADAPTER"] = "1" if request.no_adapter else "0"

    suggestion_payload = ai_merge(
        payload["ai_requests"],
        mode=request.mode,
        model_dir=request.model_dir,
        base_model=request.base_model,
    )
    suggestion = write_suggestion(
        request.merge_id,
        payload,
        suggestion_payload["patch_ops"],
        model_version=get_model_info(model_dir=request.model_dir, base_model=request.base_model),
        mode=request.mode,
        clause_recommendations=suggestion_payload.get("clause_recommendations"),
        clause_alerts=suggestion_payload.get("clause_alerts"),
    )
    return {"suggestion": suggestion, "suggestion_path": os.path.join(SUGGESTIONS_DIR, f"{suggestion['suggestion_id']}.json")}


@app.post("/apply")
def apply(request: ApplyRequest) -> Dict[str, Any]:
    suggestion_path = os.path.join(SUGGESTIONS_DIR, f"{request.suggestion_id}.json")
    try:
        suggestion = read_json(suggestion_path)
    except FileNotFoundError as exc:
        raise _http_not_found(f"Suggestion not found: {request.suggestion_id}") from exc

    suggestion_mode = suggestion.get("mode", "full")
    if request.mode and request.mode != suggestion_mode:
        raise _http_bad_request(
            ValueError(f"Suggestion mode is '{suggestion_mode}', but '{request.mode}' was requested.")
        )
    if suggestion_mode != "full":
        raise _http_bad_request(ValueError(f"Suggestion mode '{suggestion_mode}' does not include patch ops to apply."))

    try:
        result = apply_suggestion(request.suggestion_id, request.author, request.msg)
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    return result


@app.get("/commits")
def commits(limit: int = 50) -> Dict[str, Any]:
    try:
        _ensure_repo_or_init()
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    entries: List[Dict[str, Any]] = []
    for name in os.listdir(COMMITS_DIR):
        if not name.endswith(".json"):
            continue
        payload = read_json(os.path.join(COMMITS_DIR, name))
        entries.append(
            {
                "commit_id": payload.get("commit_id"),
                "parent": payload.get("parent"),
                "author": payload.get("author"),
                "timestamp_utc": payload.get("timestamp_utc"),
                "message": payload.get("message"),
                "ai_meta": payload.get("ai_meta"),
            }
        )

    entries.sort(key=lambda item: item.get("timestamp_utc", ""), reverse=True)
    return {"count": min(limit, len(entries)), "commits": entries[:limit]}


@app.delete("/commits")
def delete_commits() -> Dict[str, Any]:
    try:
        _ensure_repo_or_init()
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc

    for name in os.listdir(COMMITS_DIR):
        if name.endswith(".json"):
            os.remove(os.path.join(COMMITS_DIR, name))

    with open(HEAD_FILE, "w", encoding="utf-8") as f:
        f.write("")

    return {"status": "ok", "deleted": True}


@app.get("/commit/{commit_id}")
def commit(commit_id: str) -> Dict[str, Any]:
    try:
        payload = load_commit(commit_id)
    except FileNotFoundError as exc:
        raise _http_not_found(f"Commit not found: {commit_id}") from exc
    except SystemExit as exc:
        raise _http_bad_request(exc) from exc
    return payload


@app.get("/suggestion/{suggestion_id}")
def suggestion(suggestion_id: str) -> Dict[str, Any]:
    path = os.path.join(SUGGESTIONS_DIR, f"{suggestion_id}.json")
    try:
        return read_json(path)
    except FileNotFoundError as exc:
        raise _http_not_found(f"Suggestion not found: {suggestion_id}") from exc
