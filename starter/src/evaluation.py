"""Retrieval-only evaluation and trace aggregation."""
import re
from typing import Any


def evaluate_query(question: dict[str, Any], hits: list[dict[str, Any]]) -> dict[str, Any]:
    gold_sources = set(question.get("gold_source_ids", [question.get("gold_source_id")]))
    gold_pages = {str(p) for p in question.get("gold_pages", [question.get("gold_page")])}
    evidence = re.sub(r"\s+", " ", question.get("evidence_quote", "")).strip().lower()
    def hit(item: dict[str, Any]) -> bool:
        same_source = item.get("metadata", {}).get("document_id", item.get("document_id")) in gold_sources or item.get("source") in gold_sources
        same_page = str(item.get("page")) in gold_pages
        text = re.sub(r"\s+", " ", item.get("text", "")).strip().lower()
        return same_source and same_page and (not evidence or evidence in text)
    flags = [hit(h) for h in hits]
    return {"question_id": question["id"], "split": question["split"], "hits": hits,
            "hit_at_1": bool(flags and flags[0]), "evidence_hit_at_3": any(flags[:3])}


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, dict[str, dict[str, int]]] = {}
    for trace in traces:
        strategy = trace["strategy"]
        split = trace["split"]
        cell = result.setdefault(strategy, {}).setdefault(split, {"n": 0, "hit_at_1": 0, "evidence_hit_at_3": 0})
        cell["n"] += 1
        cell["hit_at_1"] += int(trace["hit_at_1"])
        cell["evidence_hit_at_3"] += int(trace["evidence_hit_at_3"])
    return result
