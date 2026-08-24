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

                # Improved Chunking by Markdown Headings
                sections = re.split(r'\n##\s+', content)
                
                # The first section might be the top-level intro
                for i, section in enumerate(sections):
                    section = section.strip()
                    if not section:
                        continue
                        
                    # Extract heading title if it's a ## section
                    title = ""
                    if i > 0:
                        lines = section.split('\n', 1)
                        title = lines[0].strip()
                    else:
                        # Extract top # heading
                        top_match = re.search(r'^#\s+(.*)', section)
                        if top_match:
                            title = top_match.group(1).strip()
                            
                    # Construct metadata dynamically if not provided by frontmatter
                    chunk_metadata = metadata.copy()
                    if not chunk_metadata:
                        basename_lower = basename.lower()
                        # Guess domain and crop/animal from filename
                        domain = "general"
                        crop = None
                        animal = None
                        
                        if "maize" in basename_lower or "cassava" in basename_lower or "tomato" in basename_lower or "drought" in basename_lower or "soil" in basename_lower:
                            domain = "crop"
                            if "maize" in basename_lower: crop = "maize"
                            elif "cassava" in basename_lower: crop = "cassava"
                            elif "tomato" in basename_lower: crop = "tomato"
                        elif "cattle" in basename_lower or "poultry" in basename_lower or "goat" in basename_lower or "sheep" in basename_lower or "lumpy" in basename_lower:
                            domain = "livestock"
                            if "cattle" in basename_lower or "lumpy" in basename_lower: animal = "cattle"
                            elif "poultry" in basename_lower: animal = "poultry"
                            elif "goat" in basename_lower or "sheep" in basename_lower: animal = "goat" # simplifies goat/sheep group
                            
                        chunk_metadata = {
                            "domain": domain,
                            "crop": crop,
                            "animal": animal,
                            "disease": title,
                            "topic": "disease" if "disease" in basename_lower else "general"
                        }
                    
                    self.chunks.append({
                        "source": basename,
                        "text": f"## {title}\n{section}" if i > 0 else section,
                        "metadata": chunk_metadata
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
