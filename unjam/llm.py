"""Small, optional AI layer.

Design rule: the LLM never computes anything. It only explains numbers that the code produced.
Two protections make this checkable:
  1. the prompt says 'use only these facts, copy numbers exactly'
  2. unverified_numbers() flags every number in the answer that is not in the facts
Without an API key everything still works: offline text is produced from the same facts by rules.
"""
from __future__ import annotations

import json
import math
import re
import urllib.error
import urllib.request

from .config import gemini_key, gemini_model

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMError(RuntimeError):
    pass


def is_configured() -> bool:
    return bool(gemini_key())


def _post(url: str, headers: dict, body: dict, timeout: int) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"Gemini API error {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMError(f"Could not reach the Gemini API: {exc}") from exc


def generate(prompt: str, system: str | None = None, timeout: int = 60) -> str:
    """One Gemini call. Raises LLMError (never returns made-up text on failure)."""
    key = gemini_key()
    if not key:
        raise LLMError("No GEMINI_API_KEY set. Copy .env.example to .env and add your key.")
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    data = _post(API_URL.format(model=gemini_model()),
                 {"Content-Type": "application/json", "x-goog-api-key": key}, body, timeout)
    try:
        parts = data["candidates"][0]["content"]["parts"]
        text = "".join(p.get("text", "") for p in parts).strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMError(f"Unexpected Gemini response: {str(data)[:300]}") from exc
    if not text:
        raise LLMError("Gemini returned an empty answer.")
    return text


# --------------------------------------------------------------------------- number guard

_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _norm(token: str) -> str:
    token = token.replace(",", "")
    if "." in token:
        int_part, frac = token.split(".", 1)
        int_part = int_part.lstrip("0") or "0"
        frac = frac.rstrip("0")
        return f"{int_part}.{frac}" if frac else int_part
    return token.lstrip("0") or "0"


def numbers_in(text: str) -> set[str]:
    return {_norm(t) for t in _NUM.findall(text)}


def unverified_numbers(answer: str, facts_text: str, free_up_to: int = 10) -> list[str]:
    """Numbers in `answer` that do not appear in `facts_text` (small counting numbers are allowed)."""
    allowed = numbers_in(facts_text)
    bad = []
    for tok in _NUM.findall(answer):
        n = _norm(tok)
        if n in allowed:
            continue
        if "." not in tok and n.isdigit() and int(n) <= free_up_to:
            continue
        if tok not in bad:
            bad.append(tok)
    return bad


# --------------------------------------------------------------------------- tiny retrieval (for "Ask the report")

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower().replace("_", " "))


def facts_to_chunks(facts: dict) -> list[str]:
    """Turn the facts dictionary into short, self-contained text snippets."""
    chunks: list[str] = []
    for section, value in facts.items():
        title = section.replace("_", " ")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    chunks.append(f"{title}: " + "; ".join(f"{k.replace('_', ' ')} = {v}" for k, v in item.items()))
                else:
                    chunks.append(f"{title}: {item}")
        elif isinstance(value, dict):
            parts = []
            for k, v in value.items():
                if isinstance(v, list):
                    for item in v:
                        chunks.append(f"{title} / {k.replace('_', ' ')}: " + (
                            "; ".join(f"{kk.replace('_', ' ')} = {vv}" for kk, vv in item.items())
                            if isinstance(item, dict) else str(item)))
                else:
                    parts.append(f"{k.replace('_', ' ')} = {v}")
            if parts:
                chunks.append(f"{title}: " + "; ".join(parts))
        else:
            chunks.append(f"{title}: {value}")
    return chunks


def retrieve(question: str, chunks: list[str], k: int = 4) -> list[tuple[float, str]]:
    """TF-IDF cosine similarity in ~20 lines (no ML library needed)."""
    docs = [_tokens(c) for c in chunks]
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}

    def vec(tokens: list[str]) -> dict[str, float]:
        v: dict[str, float] = {}
        for t in tokens:
            if t in idf:
                v[t] = v.get(t, 0.0) + idf[t]
        return v

    def cos(a: dict, b: dict) -> float:
        dot = sum(w * b.get(t, 0.0) for t, w in a.items())
        na = math.sqrt(sum(w * w for w in a.values()))
        nb = math.sqrt(sum(w * w for w in b.values()))
        return dot / (na * nb) if na and nb else 0.0

    q = vec(_tokens(question))
    scored = sorted(((cos(q, vec(d)), c) for d, c in zip(docs, chunks)), key=lambda x: x[0], reverse=True)
    return [(s, c) for s, c in scored[:k] if s > 0]
