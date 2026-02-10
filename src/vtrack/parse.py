import json
import os
from typing import List

from .suggest import MAX_NEW_TOKENS_ENV_VAR, USE_CACHE_ENV_VAR, _get_model


def _build_clause_prompt(text: str) -> str:
    return (
        "You are extracting clauses from a contract.\n"
        "Return JSON only (no markdown, no code fences).\n"
        "JSON schema: [\n"
        "  {\"cid\": \"c_001\", \"heading\": \"<heading or empty>\", \"text\": \"<clause text>\"}\n"
        "]\n"
        "Rules:\n"
        "- Use sequential cids starting at c_001.\n"
        "- Use headings like '1. Term' or section titles if present.\n"
        "- Keep clause text concise and preserve meaning.\n\n"
        "TEXT:\n"
        f"{text}\n"
    )


def _strip_model_output(decoded: str, prompt_text: str) -> str:
    if "model\n" in decoded:
        return decoded.split("model\n")[-1].strip()
    tail = decoded[len(prompt_text) :].strip()
    return tail or decoded.strip()


def _parse_json_array(raw: str) -> list:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start != -1 and end != -1 and end > start:
            return json.loads(raw[start : end + 1])
    return []


def _normalize_clause_list(clauses: list) -> List[dict]:
    normalized: List[dict] = []
    for idx, clause in enumerate(clauses, start=1):
        cid = clause.get("cid") or f"c_{idx:03d}"
        heading = clause.get("heading", "")
        text = clause.get("text", "")
        normalized.append(
            {
                "cid": cid,
                "heading": heading,
                "text": text,
            }
        )
    return normalized


def parse_clauses_ai(text: str, model_dir: str | None = None, base_model: str | None = None) -> List[dict]:
    prompt = _build_clause_prompt(text)
    model, tokenizer, _base = _get_model(model_dir=model_dir, base_model=base_model)
    if hasattr(tokenizer, "apply_chat_template"):
        messages = [
            {"role": "system", "content": "You extract contract clauses."},
            {"role": "user", "content": prompt},
        ]
        encoded_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    else:
        encoded_prompt = prompt
    inputs = tokenizer(encoded_prompt, return_tensors="pt")
    inputs = {k: v.to(model.device) for k, v in inputs.items()}
    max_new_tokens = int(os.environ.get(MAX_NEW_TOKENS_ENV_VAR, "256"))
    use_cache = os.environ.get(USE_CACHE_ENV_VAR, "1") == "1"
    output = model.generate(
        **inputs,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        use_cache=use_cache,
    )
    decoded = tokenizer.decode(output[0], skip_special_tokens=True)
    rendered = _strip_model_output(decoded, encoded_prompt)
    parsed = _parse_json_array(rendered)
    if not isinstance(parsed, list) or not parsed:
        raise ValueError("AI clause parser returned no clauses.")
    return _normalize_clause_list(parsed)


def parse_clauses_simple(text: str) -> List[dict]:
    cleaned = text.replace("\r\n", "\n").strip()
    blocks = [b.strip() for b in cleaned.split("\n\n") if b.strip()]
    if not blocks:
        blocks = [cleaned] if cleaned else [""]
    clauses: List[dict] = []
    for idx, block in enumerate(blocks, start=1):
        clauses.append({"cid": f"c_{idx:03d}", "heading": "", "text": block})
    return clauses
