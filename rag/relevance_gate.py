"""
Relevance Gate for AgriMate RAG — Two-Stage Pipeline.

Stage 1: HARD FILTER — rejects chunks with mismatched crop/animal/domain.
Stage 2: SEMANTIC RANK — scores survivors by symptom, keyword, and region match.

All scores normalized 0.0-1.0. Decisions: RELEVANT / PARTIALLY_RELEVANT / IRRELEVANT.
"""

from __future__ import annotations
import re
from typing import Any

# Animals that belong exclusively to cattle domain — should not be primary result for goats
CATTLE_ONLY_DISEASE_SOURCES = {"lumpy_skin_disease"}
GOAT_SHEEP_GROUP = {"goat", "sheep", "caprine", "ovine"}
CATTLE_GROUP = {"cattle", "cow", "bull", "calf", "bovine"}
POULTRY_GROUP = {"poultry", "chicken", "hen", "duck", "turkey"}


class RelevanceGate:
    def __init__(self, evidence_threshold: float = 0.5) -> None:
        self.evidence_threshold = evidence_threshold

    @staticmethod
    def _normalize_terms(value: Any) -> list[str]:
        if not value:
            return []
        if isinstance(value, str):
            parts = [p.strip().lower() for p in value.split(",") if p.strip()]
            return parts
        if isinstance(value, (list, tuple, set)):
            result = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    result.append(item.strip().lower())
                elif item is not None:
                    s = str(item).strip().lower()
                    if s:
                        result.append(s)
            return result
        return [str(value).strip().lower()]

    @staticmethod
    def _contains_term(term: str, text: str) -> bool:
        if not term or not text:
            return False
        pattern = r"\b" + re.escape(term.strip().lower()) + r"\b"
        return bool(re.search(pattern, text.lower()))


    def _norm(self, value) -> list:
        return self._normalize_terms(value)

    def _has(self, term: str, text: str) -> bool:
        return self._contains_term(term, text)

    def _hard_filter(self, result: dict, analysis: dict) -> tuple:
        """Stage 1: Reject chunks that definitively cannot answer the query."""
        meta = result.get("metadata", {})
        source = str(result.get("source", "")).lower().replace(".md", "")
        combined = f"{source} {str(result.get('text', '')).lower()}"

        # HARD REJECT WIKIPEDIA
        if "wikipedia" in combined or "wikipedia" in source:
            return False, "SOURCE MISMATCH: Wikipedia is not a trusted primary diagnostic source"

        query_crops   = self._norm(analysis.get("crop"))
        query_animals = self._norm(analysis.get("animal"))
        query_domain  = str(analysis.get("domain", "general")).lower()

        chunk_crop   = str(meta.get("crop") or "").lower().strip()
        chunk_animal = str(meta.get("animal") or "").lower().strip()
        chunk_domain = str(meta.get("domain") or "general").lower().strip()

        # HARD CROP MISMATCH
        if query_crops:
            req = query_crops[0]
            if chunk_crop and chunk_crop != req:
                return False, f"HARD CROP MISMATCH: chunk='{chunk_crop}', query='{req}'"
            if not chunk_crop and not self._has(req, combined):
                return False, f"HARD CROP MISMATCH: '{req}' not mentioned in chunk"

        # HARD ANIMAL MISMATCH
        if query_animals:
            req_animal = query_animals[0]
            if chunk_animal and chunk_animal != req_animal:
                goat_ok   = req_animal in GOAT_SHEEP_GROUP and chunk_animal in GOAT_SHEEP_GROUP
                cattle_ok = req_animal in CATTLE_GROUP and chunk_animal in CATTLE_GROUP
                if not goat_ok and not cattle_ok:
                    return False, f"HARD ANIMAL MISMATCH: chunk='{chunk_animal}', query='{req_animal}'"
            # Cattle-only disease sources rejected for goat queries
            if req_animal in GOAT_SHEEP_GROUP:
                src_base = source.split(".")[0]
                if src_base in CATTLE_ONLY_DISEASE_SOURCES:
                    return False, f"SPECIES MISMATCH: source '{source}' is cattle-only, not for '{req_animal}'"

        # CROSS-DOMAIN REJECTION
        if query_domain == "crop" and chunk_domain == "livestock":
            return False, "DOMAIN MISMATCH: livestock chunk rejected for crop query"
        if query_domain == "livestock" and chunk_domain == "crop":
            return False, "DOMAIN MISMATCH: crop chunk rejected for livestock query"

        return True, "Passed hard filter"

    def _rank_score(self, result: dict, analysis: dict) -> tuple:
        """Stage 2: Score chunks that passed the hard filter. Include Diagnostic Matcher logic."""
        raw_score = float(result.get("score", 0.0))
        combined  = f"{result.get('source', '')} {result.get('text', '')}".lower()

        score   = 0.0
        factors = []

        query_crops  = self._norm(analysis.get("crop"))
        query_animals= self._norm(analysis.get("animal"))
        symptoms     = self._norm(analysis.get("symptoms"))
        negative_symptoms = self._norm(analysis.get("negative_symptoms"))
        keywords     = self._norm(analysis.get("keywords"))

        if query_crops and self._has(query_crops[0], combined):
            score += 0.35
            factors.append(f"Crop match ({query_crops[0]}): +0.35")
        if query_animals and self._has(query_animals[0], combined):
            score += 0.35
            factors.append(f"Animal match ({query_animals[0]}): +0.35")

        # Positive Symptom Matching
        if symptoms:
            matched = [s for s in symptoms if self._has(s, combined)]
            if matched:
                bonus = min(0.40, 0.15 * len(matched))
                score += bonus
                factors.append(f"Positive symptom match ({', '.join(matched)}): +{bonus:.2f}")
            else:
                factors.append("No positive symptom match")

        # Negative Symptom Conflicts (Diagnostic Matcher)
        if negative_symptoms:
            conflict = [ns for ns in negative_symptoms if self._has(ns, combined)]
            if conflict:
                penalty = 0.20 * len(conflict)
                score -= penalty
                factors.append(f"Negative symptom conflict ({', '.join(conflict)}): -{penalty:.2f}")

        if keywords:
            hits  = [k for k in keywords if self._has(k, combined)]
            bonus = min(0.15, 0.03 * len(hits))
            score += bonus
            factors.append(f"Keyword coverage ({len(hits)}/{len(keywords)}): +{bonus:.2f}")

        raw_bonus = min(0.10, (raw_score / 15.0) * 0.10)
        score += raw_bonus
        factors.append(f"BM25 signal: +{raw_bonus:.2f}")

        return max(0.0, min(1.0, score)), factors

    def _evaluate_result(self, result: dict, analysis: dict, min_score: float = 0.3) -> dict:
        """Legacy wrapper kept for compatibility — delegates to two-stage pipeline."""
        keep, reason = self._hard_filter(result, analysis)
        if not keep:
            return {"item": result, "raw_score": 0.0, "adjusted_score": 0.0,
                    "decision": "IRRELEVANT", "adjustments": [reason], "passed": False,
                    "source": result.get("source",""), "text": result.get("text","")}
        score, factors = self._rank_score(result, analysis)
        decision = "RELEVANT" if score >= 0.7 else ("PARTIALLY_RELEVANT" if score >= min_score else "IRRELEVANT")
        passed   = decision != "IRRELEVANT"
        updated  = result.copy()
        updated["score"] = round(score, 4)
        return {"item": updated, "raw_score": float(result.get("score", 0.0)),
                "adjusted_score": score, "decision": decision, "adjustments": factors,
                "passed": passed, "source": result.get("source",""), "text": result.get("text","")}


    def filter(
        self,
        results: list[dict],
        analysis: dict,
        min_score: float = 0.3,
    ) -> tuple[list[dict], bool]:
        if not results:
            return [], False

        evaluations = [
            self._evaluate_result(r, analysis, min_score=min_score) for r in results
        ]

        # Filter by passing decision
        passing_evals = [ev for ev in evaluations if ev["passed"]]
        
        # Sort descending by normalized score
        passing_evals.sort(key=lambda x: x["adjusted_score"], reverse=True)

        # Deduplicate sources (keep max 1-2 chunks per source unless extremely relevant)
        source_counts = {}
        filtered_results = []
        for ev in passing_evals:
            src = ev["source"]
            source_counts[src] = source_counts.get(src, 0) + 1
            
            # Prefer max 1 chunk per source unless it's a RELEVANT chunk and we have room
            if source_counts[src] > 1 and ev["decision"] != "RELEVANT":
                continue
            if source_counts[src] > 2:
                continue
                
            filtered_results.append(ev["item"])
            
            # Hard limit to 3 chunks total (Requirement 6)
            if len(filtered_results) >= 3:
                break

        has_sufficient_evidence = any(
            r["score"] >= self.evidence_threshold for r in filtered_results
        )

        return filtered_results, has_sufficient_evidence

    def explain(
        self,
        results: list[dict],
        analysis: dict,
        min_score: float = 0.3,
    ) -> str:
        if not results:
            return "RelevanceGate Explanation: No retrieval results provided to evaluate."

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("RELEVANCE GATE EVALUATION REPORT")
        lines.append("=" * 60)

        domain = analysis.get("domain")
        crop = analysis.get("crop")
        animal = analysis.get("animal")
        symptoms = analysis.get("symptoms")

        lines.append("Query Analysis Context:")
        lines.append(f"  - Domain:   {domain or 'None'}")
        lines.append(f"  - Entities: Crop={crop or 'None'}, Animal={animal or 'None'}")
        lines.append(f"  - Symptoms: {symptoms or 'None'}")
        lines.append("-" * 60)

        evaluations = [
            self._evaluate_result(r, analysis, min_score=min_score) for r in results
        ]
        # Sort for display
        evaluations.sort(key=lambda x: x["adjusted_score"], reverse=True)

        for idx, ev in enumerate(evaluations, start=1):
            snippet = ev["text"].replace("\n", " ").strip()
            if len(snippet) > 80:
                snippet = snippet[:77] + "..."

            lines.append(f"Chunk #{idx}: [{ev['source']}] -> {ev['decision']}")
            lines.append(f"  Snippet:    \"{snippet}\"")
            lines.append(f"  Scores:     Raw={ev['raw_score']:.4f} -> Normalized={ev['adjusted_score']:.4f}")

            if ev["adjustments"]:
                for adj in ev["adjustments"]:
                    lines.append(f"    - {adj}")
            lines.append("-" * 40)

        lines.append(f"Summary: Evaluated={len(evaluations)} | Passed Threshold={sum(1 for ev in evaluations if ev['passed'])}")
        lines.append("=" * 60)

        return "\n".join(lines)


if __name__ == "__main__":
    gate = RelevanceGate()
    # Test would go here
    pass
