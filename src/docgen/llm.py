import os, json, time, sys
from typing import Optional
from httpx import Client, Timeout, HTTPError

from .config import LLM_FALLBACK_CHAIN, OPENROUTER_BASE_URL, SYSTEM_PROMPT


class LLMError(Exception):
    pass


SUPPRESS_STDERR = False


def _api_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise LLMError("OPENROUTER_API_KEY не задан")
    return key


def _call_model(model: str, messages: list, max_tokens: int = 8192) -> Optional[str]:
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    with Client(timeout=Timeout(180.0)) as client:
        try:
            resp = client.post(
                f"{OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            if not SUPPRESS_STDERR:
                sys.stderr.write(f"  [LLM] {model}: HTTP {code}\n")
        except (KeyError, json.JSONDecodeError) as e:
            if not SUPPRESS_STDERR:
                sys.stderr.write(f"  [LLM] {model}: ответ не распознан ({e})\n")
        except Exception as e:
            if not SUPPRESS_STDERR:
                sys.stderr.write(f"  [LLM] {model}: {e}\n")
    return None


def generate(task_prompt: str, user_prompt: str, max_tokens: int = 8192,
             label: str = "") -> str:
    """Call OpenRouter with fallback through LLM_FALLBACK_CHAIN.

    SYSTEM_PROMPT (global anti-AI-isms rules) is always prepended.
    task_prompt is appended to it as task-specific instructions.
    """
    system = f"{SYSTEM_PROMPT}\n\n{task_prompt}"
    for model in LLM_FALLBACK_CHAIN:
        if not SUPPRESS_STDERR:
            sys.stderr.write(f"  [{label or 'LLM'}] {model}... ")
            sys.stderr.flush()
        t0 = time.time()
        content = _call_model(model, [
            {"role": "system", "content": system},
            {"role": "user", "content": user_prompt},
        ], max_tokens=max_tokens)
        elapsed = time.time() - t0
        if content:
            if not SUPPRESS_STDERR:
                sys.stderr.write(f"OK ({elapsed:.1f}s)\n")
                sys.stderr.flush()
            return content
        if not SUPPRESS_STDERR:
            sys.stderr.write(f"FAIL ({elapsed:.1f}s)\n")
            sys.stderr.flush()

    raise LLMError("Все модели в цепочке отказали")


def generate_json(task_prompt: str, user_prompt: str, max_tokens: int = 8192,
                  label: str = "") -> dict:
    raw = generate(task_prompt, user_prompt, max_tokens=max_tokens, label=label)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
    return json.loads(raw, strict=False)
