"""
Relevance Gate for AgriMate RAG.

Post-retrieval filtering module that adjusts chunk scores based on query analysis
(crop, animal, symptom keywords) and filters out irrelevant or low-confidence chunks.
"""

from __future__ import annotations

import re
from typing import Any


class RelevanceGate:
    """
    Filters and reranks RAG retrieval results based on structured query analysis.
    
    Adjusts scores by boosting relevant entity/symptom matches and penalizing
    chunks that fail to match target crops or livestock.
    """

    def __init__(
        self,
        crop_boost: float = 1.3,
        crop_penalty: float = 0.5,
        animal_boost: float = 1.3,
        animal_penalty: float = 0.5,
        symptom_boost: float = 1.25,
        evidence_threshold: float = 0.5,
    ) -> None:
        """
        Initialize the RelevanceGate with configurable boost/penalty factors.

        Args:
            crop_boost: Multiplier for chunks matching the queried crop.
            crop_penalty: Multiplier (<= 1.0) for chunks missing the queried crop.
            animal_boost: Multiplier for chunks matching the queried animal.
            animal_penalty: Multiplier (<= 1.0) for chunks missing the queried animal.
            symptom_boost: Multiplier for chunks matching one or more symptoms.
            evidence_threshold: Score threshold for declaring sufficient evidence.
        """
        self.crop_boost = crop_boost
        self.crop_penalty = crop_penalty
        self.animal_boost = animal_boost
        self.animal_penalty = animal_penalty
        self.symptom_boost = symptom_boost
        self.evidence_threshold = evidence_threshold

    @staticmethod
    def _normalize_terms(value: Any) -> list[str]:
        """Normalize a string, list of strings, or None into a clean list of strings."""
        if not value:
            return []
        if isinstance(value, str):
            # Handle comma-separated strings or single term
            parts = [p.strip() for p in value.split(",") if p.strip()]
            return parts
        if isinstance(value, (list, tuple, set)):
            result = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    result.append(item.strip())
                elif item is not None:
                    s = str(item).strip()
                    if s:
                        result.append(s)
            return result
        return [str(value).strip()]

    @staticmethod
    def _contains_term(term: str, text: str) -> bool:
        """
        Check if a term or multi-word phrase appears in the text using word boundary matching.
        """
        if not term or not text:
            return False
        pattern = r"\b" + re.escape(term.strip().lower()) + r"\b"
        return bool(re.search(pattern, text.lower()))

    def _evaluate_result(
        self,
        result: dict,
        analysis: dict,
        min_score: float = 0.3,
    ) -> dict:
        """
        Evaluate a single retrieval result against the query analysis.

        Returns a dictionary containing the adjusted score, evaluation details,
        and whether it passes the min_score threshold.
        """
        raw_score = float(result.get("score", 0.0))
        text = str(result.get("text", ""))
        source = str(result.get("source", ""))
        combined_text = f"{source} {text}"

        adjusted_score = raw_score
        adjustments: list[str] = []

        # 1. Crop matching
        crops = self._normalize_terms(analysis.get("crop"))
        if crops:
            matched_crops = [c for c in crops if self._contains_term(c, combined_text)]
            if matched_crops:
                adjusted_score *= self.crop_boost
                adjustments.append(
                    f"Crop match ({', '.join(matched_crops)}): +{(self.crop_boost - 1.0) * 100:.0f}% (x{self.crop_boost})"
                )
            else:
                adjusted_score *= self.crop_penalty
                adjustments.append(
                    f"Crop mismatch (expected {', '.join(crops)}): -{(1.0 - self.crop_penalty) * 100:.0f}% (x{self.crop_penalty})"
                )

        # 2. Animal matching
        animals = self._normalize_terms(analysis.get("animal"))
        if animals:
            matched_animals = [a for a in animals if self._contains_term(a, combined_text)]
            if matched_animals:
                adjusted_score *= self.animal_boost
                adjustments.append(
                    f"Animal match ({', '.join(matched_animals)}): +{(self.animal_boost - 1.0) * 100:.0f}% (x{self.animal_boost})"
                )
            else:
                adjusted_score *= self.animal_penalty
                adjustments.append(
                    f"Animal mismatch (expected {', '.join(animals)}): -{(1.0 - self.animal_penalty) * 100:.0f}% (x{self.animal_penalty})"
                )

        # 3. Symptoms matching
        symptoms = self._normalize_terms(analysis.get("symptoms"))
        if symptoms:
            matched_symptoms = [
                s for s in symptoms if self._contains_term(s, combined_text)
            ]
            if matched_symptoms:
                adjusted_score *= self.symptom_boost
                adjustments.append(
                    f"Symptom match ({', '.join(matched_symptoms)}): +{(self.symptom_boost - 1.0) * 100:.0f}% (x{self.symptom_boost})"
                )
            else:
                adjustments.append("No symptoms matched (no boost)")

        passed = adjusted_score >= min_score

        # Prepare adjusted result item preserving original keys
        updated_item = result.copy()
        updated_item["score"] = round(adjusted_score, 4)
        updated_item["raw_score"] = round(raw_score, 4)

        return {
            "item": updated_item,
            "raw_score": raw_score,
            "adjusted_score": adjusted_score,
            "adjustments": adjustments,
            "passed": passed,
            "source": source,
            "text": text,
        }

    def filter(
        self,
        results: list[dict],
        analysis: dict,
        min_score: float = 0.3,
    ) -> tuple[list[dict], bool]:
        """
        Filter and rerank retrieval results based on query analysis.

        Args:
            results: List of retrieval result dicts with keys 'source', 'text', 'score'.
            analysis: Output dict from QueryAnalyzer.analyze() with keys:
                      'domain', 'crop', 'animal', 'symptoms', 'keywords'.
            min_score: Minimum adjusted score required to retain a result.

        Returns:
            tuple: (filtered_results, has_sufficient_evidence)
                - filtered_results: List of result dicts sorted by adjusted score descending.
                - has_sufficient_evidence: True if at least 1 result has adjusted score >= 0.5.
        """
        if not results:
            return [], False

        evaluations = [
            self._evaluate_result(r, analysis, min_score=min_score) for r in results
        ]

        # Retain only items passing min_score threshold
        filtered_results = [
            ev["item"] for ev in evaluations if ev["passed"]
        ]

        # Sort remaining items by adjusted score descending
        filtered_results.sort(key=lambda x: x["score"], reverse=True)

        # Check if at least 1 remaining result meets evidence threshold (>= 0.5)
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
        """
        Generate a human-readable diagnostic report explaining why each chunk
        was kept or rejected.

        Args:
            results: List of retrieval result dicts.
            analysis: Output dict from QueryAnalyzer.analyze().
            min_score: Minimum score threshold used for filtering.

        Returns:
            str: Multi-line formatted explanation string.
        """
        if not results:
            return "RelevanceGate Explanation: No retrieval results provided to evaluate."

        lines: list[str] = []
        lines.append("=" * 60)
        lines.append("RELEVANCE GATE EVALUATION REPORT")
        lines.append("=" * 60)

        # Analysis summary
        crop = analysis.get("crop")
        animal = analysis.get("animal")
        symptoms = analysis.get("symptoms")
        domain = analysis.get("domain")
        keywords = analysis.get("keywords")

        lines.append(f"Query Analysis Context:")
        lines.append(f"  - Domain:   {domain or 'None'}")
        lines.append(f"  - Crop:     {crop or 'None'}")
        lines.append(f"  - Animal:   {animal or 'None'}")
        lines.append(f"  - Symptoms: {symptoms or 'None'}")
        lines.append(f"  - Keywords: {keywords or 'None'}")
        lines.append(f"Thresholds: min_score={min_score:.2f}, evidence_threshold={self.evidence_threshold:.2f}")
        lines.append("-" * 60)

        evaluations = [
            self._evaluate_result(r, analysis, min_score=min_score) for r in results
        ]

        kept_count = 0
        rejected_count = 0

        for idx, ev in enumerate(evaluations, start=1):
            status = "KEPT" if ev["passed"] else "REJECTED"
            if ev["passed"]:
                kept_count += 1
            else:
                rejected_count += 1

            snippet = ev["text"].replace("\n", " ").strip()
            if len(snippet) > 90:
                snippet = snippet[:87] + "..."

            lines.append(f"Chunk #{idx}: [{ev['source']}] -> [{status}]")
            lines.append(f"  Snippet:        \"{snippet}\"")
            lines.append(f"  Initial Score:  {ev['raw_score']:.4f}")
            lines.append(f"  Adjusted Score: {ev['adjusted_score']:.4f}")

            if ev["adjustments"]:
                lines.append("  Score Factors:")
                for adj in ev["adjustments"]:
                    lines.append(f"    • {adj}")
            else:
                lines.append("  Score Factors: None (no entity/symptom rules triggered)")

            lines.append(f"  Decision Reason: {'Adjusted score >= min_score (' + str(min_score) + ')' if ev['passed'] else 'Adjusted score < min_score (' + str(min_score) + ')'}")
            lines.append("-" * 40)

        evidence_met = any(
            ev["adjusted_score"] >= self.evidence_threshold and ev["passed"]
            for ev in evaluations
        )

        lines.append(f"Summary: Evaluated={len(evaluations)} | Kept={kept_count} | Rejected={rejected_count}")
        lines.append(f"Sufficient Evidence (score >= {self.evidence_threshold:.2f}): {evidence_met}")
        lines.append("=" * 60)

        return "\n".join(lines)


if __name__ == "__main__":
    gate = RelevanceGate()

    print("\n" + "#" * 60)
    print("TEST SUITE: RelevanceGate")
    print("#" * 60)

    # -------------------------------------------------------------
    # Test Case 1: Maize crop query with specific symptoms
    # -------------------------------------------------------------
    print("\n--- Test Case 1: Maize with yellow leaves & spots ---")
    analysis_1 = {
        "domain": "crops",
        "crop": "maize",
        "animal": None,
        "symptoms": ["yellow leaves", "spots"],
        "keywords": ["maize", "yellow", "leaves", "spots"],
    }
    mock_results_1 = [
        {
            "source": "fall_armyworm.md",
            "text": "Fall armyworm attacks maize crops rapidly causing yellow leaves and dark spots on foliage.",
            "score": 0.55,
        },
        {
            "source": "soil_fertility.md",
            "text": "Nitrogen deficiency leads to yellow leaves in general plants, reducing overall yield.",
            "score": 0.45,
        },
        {
            "source": "cassava_mosaic.md",
            "text": "Cassava mosaic disease causes severe leaf curling and mosaic patterns on cassava plants.",
            "score": 0.35,
        },
    ]

    filtered_1, sufficient_1 = gate.filter(mock_results_1, analysis_1, min_score=0.3)
    explanation_1 = gate.explain(mock_results_1, analysis_1, min_score=0.3)

    print(explanation_1)
    print(f"Filtered Results Count: {len(filtered_1)}")
    print(f"Sufficient Evidence: {sufficient_1}")
    for r in filtered_1:
        print(f"  -> [{r['source']}] Score: {r['score']} (raw: {r['raw_score']})")

    assert len(filtered_1) >= 1
    assert filtered_1[0]["source"] == "fall_armyworm.md"
    assert sufficient_1 is True

    # -------------------------------------------------------------
    # Test Case 2: Livestock animal query with symptoms
    # -------------------------------------------------------------
    print("\n--- Test Case 2: Cattle with fever and ticks ---")
    analysis_2 = {
        "domain": "livestock",
        "crop": None,
        "animal": "cattle",
        "symptoms": ["fever", "ticks"],
        "keywords": ["cattle", "fever", "ticks", "lumps"],
    }
    mock_results_2 = [
        {
            "source": "east_coast_fever.md",
            "text": "East Coast fever is a disease of cattle transmitted by brown ear ticks causing high fever.",
            "score": 0.60,
        },
        {
            "source": "newcastle_disease.md",
            "text": "Newcastle disease in poultry causes high mortality, fever, and respiratory distress.",
            "score": 0.40,
        },
    ]

    filtered_2, sufficient_2 = gate.filter(mock_results_2, analysis_2, min_score=0.3)
    explanation_2 = gate.explain(mock_results_2, analysis_2, min_score=0.3)

    print(explanation_2)
    print(f"Filtered Results Count: {len(filtered_2)}")
    print(f"Sufficient Evidence: {sufficient_2}")
    for r in filtered_2:
        print(f"  -> [{r['source']}] Score: {r['score']} (raw: {r['raw_score']})")

    assert len(filtered_2) == 1
    assert filtered_2[0]["source"] == "east_coast_fever.md"
    assert sufficient_2 is True

    # -------------------------------------------------------------
    # Test Case 3: Low confidence / Irrelevant results (No sufficient evidence)
    # -------------------------------------------------------------
    print("\n--- Test Case 3: Irrelevant results test ---")
    analysis_3 = {
        "domain": "crops",
        "crop": "banana",
        "animal": None,
        "symptoms": ["wilt"],
        "keywords": ["banana", "wilt"],
    }
    mock_results_3 = [
        {
            "source": "tractor_maintenance.md",
            "text": "Routine maintenance for diesel engines and tractor transmissions.",
            "score": 0.25,
        },
        {
            "source": "goat_feeding.md",
            "text": "Optimal feed ratios for dairy goats in stall systems.",
            "score": 0.30,
        },
    ]

    filtered_3, sufficient_3 = gate.filter(mock_results_3, analysis_3, min_score=0.3)
    explanation_3 = gate.explain(mock_results_3, analysis_3, min_score=0.3)

    print(explanation_3)
    print(f"Filtered Results Count: {len(filtered_3)}")
    print(f"Sufficient Evidence: {sufficient_3}")

    assert len(filtered_3) == 0
    assert sufficient_3 is False

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
