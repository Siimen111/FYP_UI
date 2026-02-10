import json
import os
from typing import Dict, List

from .constants import AI_REQUESTS_DIR, SUGGESTIONS_DIR
from .util import read_json, sha1_str, utc_now_iso, write_json

MODEL_ENV_VAR = "VTRACK_MODEL_DIR"
BASE_MODEL_ENV_VAR = "VTRACK_BASE_MODEL"
NO_ADAPTER_ENV_VAR = "VTRACK_NO_ADAPTER"
DEVICE_MAP_ENV_VAR = "VTRACK_DEVICE_MAP"
CPU_OFFLOAD_ENV_VAR = "VTRACK_CPU_OFFLOAD"
MAX_MEMORY_ENV_VAR = "VTRACK_MAX_MEMORY"
OFFLOAD_DIR_ENV_VAR = "VTRACK_OFFLOAD_DIR"
MAX_NEW_TOKENS_ENV_VAR = "VTRACK_MAX_NEW_TOKENS"
USE_CACHE_ENV_VAR = "VTRACK_USE_CACHE"


def _default_model_dir() -> str:
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", "model"))


def _read_adapter_config(model_dir: str) -> Dict[str, str]:
    config_path = os.path.join(model_dir, "adapter_config.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Missing adapter_config.json in {model_dir}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _infer_device_map(base_model: str, max_memory: dict | None) -> dict:
    try:
        from accelerate import infer_auto_device_map, init_empty_weights
        from transformers import AutoConfig, AutoModelForCausalLM
    except ImportError as exc:
        raise RuntimeError("Missing accelerate/transformers. Install them to infer a device map.") from exc

    config = AutoConfig.from_pretrained(base_model, trust_remote_code=True)
    with init_empty_weights():
        empty_model = AutoModelForCausalLM.from_config(config, trust_remote_code=True)
    no_split = getattr(empty_model, "_no_split_modules", None)
    return infer_auto_device_map(empty_model, max_memory=max_memory, no_split_module_classes=no_split)


def _load_local_model(
    model_dir: str | None,
    base_model_override: str | None,
    device_map: str | dict,
    cpu_offload: bool,
    max_memory: dict | None,
    offload_dir: str | None,
):
    try:
        from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
        from peft import PeftModel
    except ImportError as exc:
        raise RuntimeError("Missing transformers/peft. Install dependencies to use local inference.") from exc

    base_model = base_model_override
    use_adapter = False
    if model_dir and os.path.exists(os.path.join(model_dir, "adapter_config.json")):
        cfg = _read_adapter_config(model_dir)
        base_model = base_model or cfg.get("base_model_name_or_path")
        use_adapter = os.environ.get(NO_ADAPTER_ENV_VAR, "0") != "1"
    elif model_dir:
        base_model = base_model or model_dir
    if not base_model:
        raise RuntimeError("Base model not set. Use VTRACK_BASE_MODEL or provide adapter_config.json.")

    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True, trust_remote_code=True)
    config = AutoConfig.from_pretrained(base_model, trust_remote_code=True)
    if getattr(config, "quantization_config", None) is not None:
        if isinstance(config.quantization_config, dict):
            config.quantization_config["llm_int8_enable_fp32_cpu_offload"] = cpu_offload
        else:
            config.quantization_config.llm_int8_enable_fp32_cpu_offload = cpu_offload
    quant_config = BitsAndBytesConfig(load_in_4bit=True, llm_int8_enable_fp32_cpu_offload=cpu_offload)
    if cpu_offload and isinstance(device_map, str) and device_map in {"auto", "balanced", "sequential"}:
        device_map = _infer_device_map(base_model, max_memory)
    if offload_dir:
        os.makedirs(offload_dir, exist_ok=True)
    try:
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            config=config,
            device_map=device_map,
            quantization_config=quant_config,
            trust_remote_code=True,
            max_memory=max_memory,
            offload_folder=offload_dir,
        )
    except TypeError:
        # Fallback when model class does not accept 4-bit args.
        model = AutoModelForCausalLM.from_pretrained(
            base_model,
            device_map=device_map,
            trust_remote_code=True,
            max_memory=max_memory,
            offload_folder=offload_dir,
        )
    if use_adapter:
        model = PeftModel.from_pretrained(model, model_dir)
    model.eval()
    return model, tokenizer, base_model


_MODEL_CACHE = {"model": None, "tokenizer": None, "base": None}


def _get_model(
    model_dir: str | None = None,
    base_model: str | None = None,
    device_map: str | None = None,
    cpu_offload: bool | None = None,
    max_memory: dict | None = None,
    offload_dir: str | None = None,
):
    if _MODEL_CACHE["model"] is not None:
        return _MODEL_CACHE["model"], _MODEL_CACHE["tokenizer"], _MODEL_CACHE["base"]

    model_dir = model_dir or os.environ.get(MODEL_ENV_VAR, None)
    base_model = base_model or os.environ.get(BASE_MODEL_ENV_VAR, None)
    device_map_raw = device_map or os.environ.get(DEVICE_MAP_ENV_VAR, "auto")
    if isinstance(device_map_raw, str) and device_map_raw.strip().startswith("{"):
        device_map = json.loads(device_map_raw)
    else:
        device_map = device_map_raw
    if cpu_offload is None:
        cpu_offload = os.environ.get(CPU_OFFLOAD_ENV_VAR, "0") == "1"
    if max_memory is None:
        max_memory_raw = os.environ.get(MAX_MEMORY_ENV_VAR, "")
        if max_memory_raw.strip().startswith("{"):
            raw = json.loads(max_memory_raw)
            max_memory = {}
            for key, value in raw.items():
                if isinstance(key, str) and key.isdigit():
                    max_memory[int(key)] = value
                else:
                    max_memory[key] = value
    if offload_dir is None:
        offload_dir = os.environ.get(OFFLOAD_DIR_ENV_VAR, None)
    model, tokenizer, base = _load_local_model(model_dir, base_model, device_map, cpu_offload, max_memory, offload_dir)
    _MODEL_CACHE["model"] = model
    _MODEL_CACHE["tokenizer"] = tokenizer
    _MODEL_CACHE["base"] = base
    return model, tokenizer, base


def _build_prompt(request: dict, mode: str) -> str:
    base = request.get("base", {})
    left = request.get("left", {})
    right = request.get("right", {})
    if mode == "full":
        instruction = (
            "You are resolving a clause conflict.\n"
            "Return reasoning and merged clause text.\n"
            "Format exactly:\n"
            "REASONING:\n"
            "<short reasoning>\n\n"
            "TEXT:\n"
            "<merged clause text>\n\n"
        )
    elif mode == "partial":
        instruction = (
            "You are reviewing a clause conflict.\n"
            "Return recommendations only. Do not rewrite the clause.\n"
            "Format exactly:\n"
            "RECOMMENDATIONS:\n"
            "<bulleted or numbered guidance>\n\n"
        )
    else:
        instruction = (
            "You are reviewing a clause conflict for significant deviation.\n"
            "Return an alert decision and reason.\n"
            "Format exactly:\n"
            "ALERT:\n"
            "<yes/no>\n"
            "REASON:\n"
            "<short reason>\n\n"
        )
    return (
        f"{instruction}"
        f"[BASE]\n{base.get('text','')}\n\n"
        f"[LEFT]\n{left.get('text','')}\n\n"
        f"[RIGHT]\n{right.get('text','')}\n"
    )


def ai_merge(
    ai_requests: List[dict],
    mode: str = "full",
    model_dir: str | None = None,
    base_model: str | None = None,
    device_map: str | None = None,
    cpu_offload: bool | None = None,
    max_memory: dict | None = None,
    offload_dir: str | None = None,
) -> dict:
    model, tokenizer, _base = _get_model(
        model_dir=model_dir,
        base_model=base_model,
        device_map=device_map,
        cpu_offload=cpu_offload,
        max_memory=max_memory,
        offload_dir=offload_dir,
    )
    patch_ops: List[dict] = []
    clause_recommendations: List[dict] = []
    clause_alerts: List[dict] = []

    def strip_model_output(decoded: str, prompt_text: str) -> str:
        if "model\n" in decoded:
            return decoded.split("model\n")[-1].strip()
        tail = decoded[len(prompt_text) :].strip()
        return tail or decoded.strip()

    def parse_full_output(output: str) -> tuple[str, str]:
        if "REASONING:" in output and "TEXT:" in output:
            after_reason = output.split("REASONING:", 1)[1]
            reasoning_part, text_part = after_reason.split("TEXT:", 1)
            return reasoning_part.strip(), text_part.strip()
        return "", output.strip()

    def parse_section(output: str, label: str) -> str:
        if label in output:
            return output.split(label, 1)[1].strip()
        return output.strip()

    def parse_alert_output(output: str) -> tuple[str | None, str]:
        if "ALERT:" not in output:
            return None, output.strip()
        after_alert = output.split("ALERT:", 1)[1]
        if "REASON:" in after_alert:
            alert_part, reason_part = after_alert.split("REASON:", 1)
            return alert_part.strip().lower(), reason_part.strip()
        return after_alert.strip().lower(), ""

    for req in ai_requests:
        prompt = _build_prompt(req, mode)
        if hasattr(tokenizer, "apply_chat_template"):
            messages = [
                {"role": "system", "content": "You merge contract clauses."},
                {"role": "user", "content": prompt},
            ]
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            text = prompt
        inputs = tokenizer(text, return_tensors="pt")
        inputs = {k: v.to(model.device) for k, v in inputs.items()}
        max_new_tokens = int(os.environ.get(MAX_NEW_TOKENS_ENV_VAR, "128"))
        use_cache = os.environ.get(USE_CACHE_ENV_VAR, "1") == "1"
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            use_cache=use_cache,
        )
        decoded = tokenizer.decode(output[0], skip_special_tokens=True)
        rendered = strip_model_output(decoded, text)

        if mode == "full":
            reasoning, new_text = parse_full_output(rendered)
            patch_ops.append(
                {
                    "op": "REPLACE_CLAUSE_TEXT",
                    "cid": req.get("cid"),
                    "expected_fingerprint": req.get("expected_fingerprint"),
                    "new_text": new_text,
                    "reasoning": reasoning,
                }
            )
            continue

        if mode == "partial":
            recommendations = parse_section(rendered, "RECOMMENDATIONS:")
            clause_recommendations.append(
                {
                    "cid": req.get("cid"),
                    "recommendations": recommendations,
                }
            )
            continue

        alert_flag, reason = parse_alert_output(rendered)
        needs_review = True
        if alert_flag is not None:
            needs_review = alert_flag.startswith("y")
        if needs_review:
            clause_alerts.append(
                {
                    "cid": req.get("cid"),
                    "status": "NEEDS_REVIEW",
                    "reason": reason,
                }
            )

    return {
        "patch_ops": patch_ops,
        "clause_recommendations": clause_recommendations,
        "clause_alerts": clause_alerts,
    }


def get_model_info(model_dir: str | None = None, base_model: str | None = None) -> str:
    model_dir = model_dir or os.environ.get(MODEL_ENV_VAR, None)
    base_model = base_model or os.environ.get(BASE_MODEL_ENV_VAR, None)
    if model_dir and os.path.exists(os.path.join(model_dir, "adapter_config.json")):
        cfg = _read_adapter_config(model_dir)
        base = base_model or cfg.get("base_model_name_or_path", "unknown-base")
        if os.environ.get(NO_ADAPTER_ENV_VAR, "0") == "1":
            return f"{base} (no adapter)"
        return f"{base} + adapter"
    if base_model:
        return f"{base_model} (no adapter)"
    return "unknown-model"


def load_ai_requests(merge_id: str) -> dict:
    path = os.path.join(AI_REQUESTS_DIR, f"{merge_id}.json")
    return read_json(path)


def write_suggestion(
    merge_id: str,
    ai_request_payload: dict,
    patch_ops: List[dict],
    model_version: str,
    mode: str = "full",
    clause_recommendations: List[dict] | None = None,
    clause_alerts: List[dict] | None = None,
) -> dict:
    payload = {
        "suggestion_id": "",
        "merge_id": merge_id,
        "base_commit_id": ai_request_payload.get("base_commit_id"),
        "left_commit_id": ai_request_payload.get("left_commit_id"),
        "right_commit_id": ai_request_payload.get("right_commit_id"),
        "patch_ops": patch_ops,
        "mode": mode,
        "auto_apply": False,
        "clause_recommendations": clause_recommendations or [],
        "clause_alerts": clause_alerts or [],
        "model_version": model_version,
        "created_at_utc": utc_now_iso(),
    }
    suggestion_id = sha1_str(json.dumps(payload, sort_keys=True))
    payload["suggestion_id"] = suggestion_id
    write_json(os.path.join(SUGGESTIONS_DIR, f"{suggestion_id}.json"), payload)
    return payload
