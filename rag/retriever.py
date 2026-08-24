import os
import glob
import re
import yaml
from typing import List, Dict, Any, Tuple

STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "because", "as", "until", "while", "of",
    "at", "by", "for", "with", "about", "against", "between", "through",
    "during", "before", "after", "above", "below", "to", "from", "up",
    "down", "in", "out", "on", "off", "over", "under", "again", "further",
    "then", "once", "here", "there", "when", "where", "why", "how",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "i", "me", "my", "myself", "we", "our", "ours", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them",
    "their", "also", "if", "into"
}

class SimpleRAG:
    """
    Offline RAG engine. Chunks documents into paragraphs, scores them
    using weighted term-frequency, and returns relevant results.
    Now supports YAML frontmatter metadata and hybrid search.
    """

    def __init__(self, knowledge_dir: str):
        self.knowledge_dir = knowledge_dir
        self.chunks: List[Dict[str, Any]] = []
        self._load_and_chunk()

    def _parse_frontmatter(self, text: str) -> Tuple[Dict[str, Any], str]:
        """Parses YAML frontmatter if present and returns metadata + clean text."""
        metadata = {}
        content = text
        if text.startswith("---"):
            # Try to match the frontmatter block
            match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', text, re.DOTALL)
            if match:
                yaml_text = match.group(1)
                content = match.group(2)
                try:
                    metadata = yaml.safe_load(yaml_text) or {}
                except yaml.YAMLError:
                    pass
        return metadata, content

    def _load_and_chunk(self):
        pattern = os.path.join(self.knowledge_dir, "**/*.md")
        files = glob.glob(pattern, recursive=True)
        print(f"[RAG] Loading {len(files)} knowledge files...")

        for fpath in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    raw_content = f.read()

                basename = os.path.basename(fpath)
                metadata, content = self._parse_frontmatter(raw_content)

                # Clean up scraped HTML artifacts
                content = re.sub(r'Jump to content.*?hide Navigation', '', content)
                content = re.sub(r'Main page Contents Current events.*?Wikipedia', '', content)
                content = re.sub(r'\[\d+\]', '', content)

                # Split by paragraphs
                paragraphs = re.split(r'\n\s*\n', content)

                current_chunk = ""
                for para in paragraphs:
                    text = para.strip()
                    if not text or text.startswith("Source:"):
                        continue
                    
                    if len(current_chunk) + len(text) < 500:
                        current_chunk += " " + text
                    else:
                        if current_chunk:
                            self.chunks.append({
                                "source": basename,
                                "text": current_chunk.strip(),
                                "metadata": metadata
                            })
                        current_chunk = text
                
                if len(current_chunk) > 50:
                    self.chunks.append({
                        "source": basename,
                        "text": current_chunk.strip(),
                        "metadata": metadata
                    })

            except Exception as e:
                print(f"[RAG] Error reading {fpath}: {e}")

        print(f"[RAG] Indexed {len(self.chunks)} chunks from {len(files)} files.")

    def _tokenize(self, text: str) -> list[str]:
        words = re.findall(r'[a-z]{3,}', text.lower())
        return [w for w in words if w not in STOP_WORDS]

    def retrieve(self, query: str, analysis: dict = None, top_k: int = 5) -> list[dict]:
        """
        Retrieve chunks using analysis keywords and metadata boosting.
        """
        query_terms = []
        if analysis and "keywords" in analysis and analysis["keywords"]:
            query_terms = analysis["keywords"]
        else:
            query_terms = self._tokenize(query)
            
        if not query_terms:
            return []

        scored = []
        for chunk in self.chunks:
            text = chunk["text"]
            source = chunk["source"]
            metadata = chunk["metadata"]
            
            text_lower = text.lower()
            metadata_str = str(metadata).lower()
            
            terms_found = 0
            total_hits = 0
            for term in query_terms:
                count = text_lower.count(term)
                # Boost if term found in metadata keywords or title
                if term in metadata_str:
                    count += 2
                
                if count > 0:
                    terms_found += 1
                    total_hits += min(count, 5)

            if terms_found == 0:
                continue
                
            coverage = terms_found / len(query_terms)
            length_penalty = len(text_lower) / 500.0
            if length_penalty < 1.0: length_penalty = 1.0
            
            score = (coverage * total_hits) / length_penalty

            # Phrase bonus (first two terms)
            if len(query_terms) >= 2:
                phrase = " ".join(query_terms[:2])
                if phrase in text_lower:
                    score += 2.0

            scored.append({"score": score, "source": source, "text": text, "metadata": metadata})

        scored.sort(key=lambda x: x["score"], reverse=True)

        results = []
        for res in scored[:top_k]:
            if res["score"] > 0.1:
                results.append(res)

        return results
