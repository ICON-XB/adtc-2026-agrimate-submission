"""
Online Knowledge Collector for AgriMate.

Handles optional online web search, content scraping, sanitization,
deduplication, and structured Markdown/YAML knowledge base persistence.
"""

import os
import re
import json
import time
import html
import hashlib
import urllib.request
import urllib.error
from datetime import datetime
from typing import List, Dict, Any, Optional

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
    "their", "also", "if", "into", "agriculture", "agricultural"
}


class OnlineCollector:
    """
    Collects, cleans, deduplicates, and stores agricultural knowledge
    from online web searches into the AgriMate knowledge base.
    """

    def __init__(self, knowledge_dir: str):
        """
        Initialize the collector with a path to the knowledge base directory.
        """
        self.knowledge_dir = os.path.abspath(knowledge_dir)
        os.makedirs(self.knowledge_dir, exist_ok=True)

    def _search_web(self, query: str, max_results: int) -> List[Dict[str, Any]]:
        """
        Search DuckDuckGo for relevant agricultural content.
        Uses ddgs/duckduckgo_search safely wrapped in try/except.
        """
        try:
            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            ddgs = DDGS()
            raw_results = ddgs.text(f"agriculture {query}", max_results=max_results)

            results = []
            if raw_results:
                for r in raw_results:
                    title = r.get("title", "").strip()
                    url = r.get("href") or r.get("url") or r.get("link", "")
                    snippet = r.get("body") or r.get("snippet", "")
                    if url:
                        results.append({
                            "title": title,
                            "url": url,
                            "snippet": snippet
                        })
            return results
        except Exception as e:
            print(f"[OnlineCollector] Search error: {e}")
            return []

    def _clean_content(self, raw_text: str) -> str:
        """
        Strips HTML tags, scripts, boilerplate, navigation, and cookie notices.
        Keeps only substantial paragraphs (>= 50 chars) and caps total length to 3000 chars.
        """
        if not raw_text:
            return ""

        # Remove scripts, styles, headers, footers, navs, aside, form, noscript
        text = re.sub(
            r'<(script|style|nav|header|footer|aside|form|noscript|svg)[^>]*>.*?</\1>',
            ' ',
            raw_text,
            flags=re.DOTALL | re.IGNORECASE
        )
        # Remove HTML comments
        text = re.sub(r'<!--.*?-->', ' ', text, flags=re.DOTALL)

        # Replace block tags with newline breaks
        text = re.sub(r'<(?:p|div|h[1-6]|li|tr|br|section|article|blockquote)[^>]*>', '\n', text, flags=re.IGNORECASE)

        # Strip remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Unescape HTML entities (&amp;, &nbsp;, etc.)
        text = html.unescape(text)

        # Common boilerplate filters
        boilerplate_patterns = [
            r'cookie\s+policy',
            r'privacy\s+policy',
            r'terms\s+of\s+(?:use|service)',
            r'all\s+rights\s+reserved',
            r'copyright\s+(?:©|\(c\)|\d{4})',
            r'subscribe\s+to',
            r'sign\s+in',
            r'create\s+(?:an\s+)?account',
            r'log\s+in',
            r'jump\s+to\s+content',
            r'navigation\s+menu',
            r'share\s+on\s+(?:facebook|twitter|linkedin)',
            r'follow\s+us\s+on',
            r'we\s+use\s+cookies'
        ]
        boilerplate_re = re.compile('|'.join(boilerplate_patterns), re.IGNORECASE)

        paragraphs = []
        raw_paragraphs = re.split(r'\n+', text)

        for p in raw_paragraphs:
            cleaned_p = re.sub(r'\s+', ' ', p).strip()
            # Keep paragraphs with 50+ characters that do not match boilerplate
            if len(cleaned_p) >= 50 and not boilerplate_re.search(cleaned_p):
                paragraphs.append(cleaned_p)

        combined = "\n\n".join(paragraphs)

        # Limit total content to 3000 characters
        if len(combined) > 3000:
            truncated = combined[:3000]
            last_period = truncated.rfind('.')
            if last_period > 2500:
                combined = truncated[:last_period + 1]
            else:
                combined = truncated.rsplit(' ', 1)[0] + "..."

        return combined

    def _compute_hash(self, content: str) -> str:
        """
        Compute a SHA-256 hash of the first 500 characters of cleaned content.
        """
        prefix = re.sub(r'\s+', ' ', content).strip().lower()[:500]
        return hashlib.sha256(prefix.encode('utf-8', errors='ignore')).hexdigest()

    def _check_duplicate(self, content: str) -> bool:
        """
        Checks if substantially similar content already exists in knowledge dir
        using a 500-char content hash and substring matching.
        """
        if not os.path.exists(self.knowledge_dir):
            return False

        target_hash = self._compute_hash(content)

        # 1. Check update_log.json if available
        log_path = os.path.join(self.knowledge_dir, "update_log.json")
        if os.path.exists(log_path):
            try:
                with open(log_path, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                    if isinstance(entries, list):
                        for entry in entries:
                            if entry.get("content_hash") == target_hash:
                                return True
            except Exception:
                pass

        # 2. Check existing markdown files
        import glob
        md_files = glob.glob(os.path.join(self.knowledge_dir, "**/*.md"), recursive=True)
        target_prefix = re.sub(r'\s+', ' ', content).strip().lower()[:200]

        for fpath in md_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    file_text = f.read()

                # Strip frontmatter if present
                body = file_text
                if file_text.startswith("---"):
                    parts = file_text.split("---", 2)
                    if len(parts) >= 3:
                        body = parts[2]

                # Compare hash
                if self._compute_hash(body) == target_hash:
                    return True

                # Substring check if long enough
                if len(target_prefix) >= 100:
                    norm_body = re.sub(r'\s+', ' ', body).lower()
                    if target_prefix in norm_body:
                        return True
            except Exception:
                continue

        return False

    def _categorize(self, query: str, title: str, content: str) -> str:
        """
        Categorize into: crop_disease | livestock_disease | pest | general
        """
        text = f"{query} {title} {content}".lower()

        pest_terms = [
            "pest", "armyworm", "caterpillar", "locust", "stem borer", "weevil",
            "aphid", "whitefly", "leafminer", "beetle", "mite", "moth", "worm",
            "insect", "striga", "witchweed", "weed", "infestation", "larva", "larvae"
        ]
        livestock_terms = [
            "livestock", "cattle", "cow", "goat", "sheep", "swine", "pig", "poultry",
            "chicken", "bird flu", "newcastle", "lumpy skin", "east coast fever",
            "foot and mouth", "anthrax", "rinderpest", "mastitis", "veterinary", "animal"
        ]
        crop_disease_terms = [
            "disease", "blight", "rust", "mosaic", "rot", "wilt", "mildew", "smut",
            "fungus", "fungal", "bacterial", "viral", "leaf spot", "canker", "scab",
            "dieback", "damping off", "maize", "cassava", "sorghum", "millet", "crop"
        ]

        pest_score = sum(1 for term in pest_terms if term in text)
        livestock_score = sum(1 for term in livestock_terms if term in text)
        crop_score = sum(1 for term in crop_disease_terms if term in text)

        if pest_score > livestock_score and pest_score >= crop_score and pest_score > 0:
            return "pest"
        if livestock_score > pest_score and livestock_score >= crop_score and livestock_score > 0:
            return "livestock_disease"
        if crop_score > 0:
            return "crop_disease"
        return "general"

    def _extract_keywords(self, query: str, title: str, content: str) -> List[str]:
        """
        Extract meaningful keywords from query, title, and content.
        """
        combined = f"{query} {title}".lower()
        words = re.findall(r'[a-z]{3,}', combined)
        keywords = []
        for w in words:
            if w not in STOP_WORDS and w not in keywords:
                keywords.append(w)
            if len(keywords) >= 5:
                break

        if len(keywords) < 3:
            content_words = re.findall(r'[a-z]{4,}', content.lower())
            for cw in content_words:
                if cw not in STOP_WORDS and cw not in keywords:
                    keywords.append(cw)
                if len(keywords) >= 5:
                    break

        return keywords if keywords else ["agriculture", "management"]

    def _save_document(self, title: str, content: str, url: str, category: str, keywords: Optional[List[str]] = None) -> str:
        """
        Saves document as markdown with YAML frontmatter in knowledge dir.
        Returns the saved file path.
        """
        save_dir = os.path.join(self.knowledge_dir, category)
        os.makedirs(save_dir, exist_ok=True)

        safe_title = re.sub(r'[^a-zA-Z0-9_-]', '_', title.lower()).strip('_')
        safe_title = re.sub(r'_+', '_', safe_title)[:50]
        if not safe_title:
            safe_title = f"doc_{int(time.time())}"

        filename = f"{safe_title}.md"
        filepath = os.path.join(save_dir, filename)

        counter = 1
        while os.path.exists(filepath):
            filename = f"{safe_title}_{counter}.md"
            filepath = os.path.join(save_dir, filename)
            counter += 1

        date_str = datetime.now().strftime("%Y-%m-%d")

        if not keywords:
            keywords = self._extract_keywords(category, title, content)

        clean_title = title.replace('"', '\\"').replace('\n', ' ')
        keywords_yaml = "\n".join([f"  - {kw}" for kw in keywords])

        doc_content = (
            f"---\n"
            f"title: \"{clean_title}\"\n"
            f"source: {url}\n"
            f"date_collected: {date_str}\n"
            f"category: {category}\n"
            f"keywords:\n"
            f"{keywords_yaml}\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"**Source**: {url}\n\n"
            f"{content}\n"
        )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(doc_content)

        return filepath

    def _log_update(self, entry: Dict[str, Any]):
        """
        Appends metadata entry to knowledge/update_log.json.
        """
        try:
            os.makedirs(self.knowledge_dir, exist_ok=True)
            log_path = os.path.join(self.knowledge_dir, "update_log.json")
            entries = []
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            entries = data
                except Exception:
                    entries = []

            entries.append(entry)

            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(entries, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[OnlineCollector] Error logging update: {e}")

    def search_and_collect(self, query: str, max_sources: int = 3) -> Dict[str, Any]:
        """
        Searches web for query, fetches content, cleans it, checks duplicates,
        saves to knowledge directory, and logs updates.
        Returns:
            {'sources_found': N, 'sources_saved': M, 'files': [...], 'status': 'success'|'no_results'|'error'}
        """
        summary: Dict[str, Any] = {
            "sources_found": 0,
            "sources_saved": 0,
            "files": [],
            "status": "error"
        }

        try:
            search_results = self._search_web(query, max_results=max_sources)
            summary["sources_found"] = len(search_results)

            if not search_results:
                summary["status"] = "no_results"
                return summary

            saved_files = []

            for item in search_results:
                title = item.get("title", "Untitled Agricultural Note")
                url = item.get("url", "")
                snippet = item.get("snippet", "")

                if not url:
                    continue

                raw_html = ""
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    with urllib.request.urlopen(req, timeout=10) as response:
                        raw_html = response.read().decode("utf-8", errors="ignore")
                except Exception as e:
                    print(f"[OnlineCollector] Could not fetch URL {url}: {e}")
                    if snippet and len(snippet) >= 50:
                        raw_html = f"<p>{snippet}</p>"
                    else:
                        continue

                cleaned_content = self._clean_content(raw_html)
                if not cleaned_content or len(cleaned_content) < 50:
                    if snippet and len(snippet) >= 50:
                        cleaned_content = self._clean_content(f"<p>{snippet}</p>")
                    if not cleaned_content or len(cleaned_content) < 50:
                        continue

                if self._check_duplicate(cleaned_content):
                    print(f"[OnlineCollector] Duplicate detected for: {title}")
                    continue

                category = self._categorize(query, title, cleaned_content)
                keywords = self._extract_keywords(query, title, cleaned_content)

                saved_path = self._save_document(title, cleaned_content, url, category, keywords)
                saved_filename = os.path.basename(saved_path)
                saved_files.append(saved_filename)

                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "query": query,
                    "title": title,
                    "url": url,
                    "category": category,
                    "filename": saved_filename,
                    "content_hash": self._compute_hash(cleaned_content),
                    "chars_saved": len(cleaned_content)
                }
                self._log_update(log_entry)

            summary["sources_saved"] = len(saved_files)
            summary["files"] = saved_files
            summary["status"] = "success"
            return summary

        except Exception as e:
            print(f"[OnlineCollector] search_and_collect failure: {e}")
            summary["status"] = "error"
            return summary


if __name__ == "__main__":
    import sys
    base_dir = os.path.join(os.path.dirname(__file__), "..", "knowledge")
    collector = OnlineCollector(knowledge_dir=base_dir)

    test_query = "fall armyworm maize control"
    print(f"Testing OnlineCollector with query: '{test_query}'...")
    result = collector.search_and_collect(test_query, max_sources=3)

    print("\nCollection Result:")
    print(json.dumps(result, indent=2))
