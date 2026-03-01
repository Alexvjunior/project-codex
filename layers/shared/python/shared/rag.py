import json
import os
import re
from functools import lru_cache
from typing import Dict, List, Tuple


def _tokenize(text: str) -> List[str]:
    return [t for t in re.split(r"[^a-zA-Z0-9]+", (text or "").lower()) if t]


def _score(query_tokens: List[str], content: str) -> int:
    content_tokens = set(_tokenize(content))
    if not content_tokens:
        return 0
    return sum(1 for t in query_tokens if t in content_tokens)


def _load_json_file(path: str) -> List[Dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    if isinstance(payload, list):
        return payload
    return []


@lru_cache(maxsize=1)
def load_rag_corpus(base_dir: str) -> List[Dict]:
    corpus: List[Dict] = []
    files = [
        os.path.join(base_dir, "examples.json"),
        os.path.join(base_dir, "playbook.json"),
        os.path.join(base_dir, "faq.json"),
    ]
    for path in files:
        for row in _load_json_file(path):
            text = " ".join(
                [
                    str(row.get("context", "")),
                    str(row.get("dialogue", "")),
                    str(row.get("question", "")),
                    str(row.get("answer", "")),
                    str(row.get("guideline", "")),
                ]
            ).strip()
            if text:
                corpus.append({"source": os.path.basename(path), "text": text, "row": row})
    return corpus


def rag_retrieve(query: str, base_dir: str, top_k: int = 3) -> List[Dict]:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []
    scored: List[Tuple[int, Dict]] = []
    for doc in load_rag_corpus(base_dir):
        score = _score(query_tokens, doc["text"])
        if score > 0:
            scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]
