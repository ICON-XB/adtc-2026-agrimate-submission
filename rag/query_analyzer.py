"""
Agricultural Query Analyzer for AgriMate Offline RAG.
Analyzes user queries to extract structured metadata (domain, crop, animal,
problem_type, symptoms, negative_symptoms, and expanded keywords) to guide offline retrieval.
Maintains strict conversation state.
"""

import re
from typing import Any, Dict, List, Optional

# Known Crops List
CROPS = [
    "maize", "corn", "wheat", "sorghum", "millet", "rice", "beans",
    "cowpeas", "groundnuts", "cassava", "yam", "potato", "sweet potato",
    "tomato", "onion", "cabbage", "spinach", "banana", "plantain",
    "coffee", "cocoa", "tea", "cotton", "sugarcane", "tobacco"
]

# Known Animals List
ANIMALS = [
    "goat", "sheep", "cattle", "cow", "bull", "calf", "pig", "swine",
    "chicken", "poultry", "hen", "duck", "turkey", "donkey", "horse",
    "camel", "rabbit"
]

# Symptom Keywords
SYMPTOM_KEYWORDS = [
    "yellow", "yellowing", "brown", "black", "white", "spots", "spot",
    "wilt", "wilting", "rot", "rotting", "mold", "mould", "stunted",
    "curling", "drooping", "holes", "lumps", "lumpy", "hard", "scab",
    "scabs", "lesion", "lesions", "blister", "blisters", "swelling",
    "swollen", "diarrhea", "diarrhoea", "cough", "fever", "limp",
    "bleeding", "discharge", "lame", "lameness", "thin", "emaciated",
    "loss", "appetite", "pus", "fluid", "scratch", "scratching", "hair loss"
]

# Synonyms for Query Expansion
SYNONYMS: Dict[str, List[str]] = {
    "corn": ["maize"], "maize": ["corn"],
    "cow": ["cattle"], "cattle": ["cow"],
    "hen": ["chicken", "poultry"], "chicken": ["poultry", "hen"], "poultry": ["chicken", "hen"],
    "pig": ["swine"], "swine": ["pig"],
    "sweet potato": ["sweetpotato"], "sweetpotato": ["sweet potato"],
    "groundnut": ["peanut"], "groundnuts": ["peanuts", "peanut"], "peanut": ["groundnut"], "peanuts": ["groundnuts", "groundnut"],
    "yellowing": ["yellow"], "yellow": ["yellowing"],
    "rotting": ["rot"], "rot": ["rotting"],
    "wilting": ["wilt"], "wilt": ["wilting"],
    "spot": ["spots"], "spots": ["spot"],
    "scab": ["scabs"], "scabs": ["scab"],
    "lesion": ["lesions"], "lesions": ["lesion"],
    "blister": ["blisters"], "blisters": ["blister"],
    "swelling": ["swollen"], "swollen": ["swelling"],
    "diarrhea": ["diarrhoea"], "diarrhoea": ["diarrhea"],
    "lame": ["lameness"], "lameness": ["lame"],
    "lumps": ["lumpy"], "lumpy": ["lumps"],
}

STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "also", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "can", "could", "did", "do", "does", "doing",
    "down", "during", "each", "few", "for", "from", "further", "had", "has", "have",
    "having", "he", "her", "here", "hers", "herself", "him", "himself", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "itself", "just", "me", "might",
    "more", "most", "must", "my", "myself", "no", "nor", "not", "now", "of", "off",
    "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out",
    "over", "own", "same", "shall", "she", "should", "so", "some", "such", "than",
    "that", "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom",
    "why", "will", "with", "would", "you", "your", "yours", "yourself", "yourselves",
    "help", "please", "tell", "give", "want", "need", "like", "get"
}

class QueryAnalyzer:
    def __init__(self):
        self._build_alias_maps()

    def _build_alias_maps(self):
        self.crop_aliases = {
            "sweet potato": "sweet potato", "sweet potatoes": "sweet potato",
            "sugarcane": "sugarcane", "sugar cane": "sugarcane",
            "groundnut": "groundnuts", "groundnuts": "groundnuts", "peanut": "groundnuts", "peanuts": "groundnuts",
            "cowpea": "cowpeas", "cowpeas": "cowpeas",
            "bean": "beans", "beans": "beans",
            "maize": "maize", "corn": "corn",
            "wheat": "wheat", "sorghum": "sorghum", "millet": "millet", "rice": "rice",
            "cassava": "cassava", "yam": "yam", "potato": "potato", "tomato": "tomato",
            "onion": "onion", "cabbage": "cabbage", "spinach": "spinach", "banana": "banana",
            "plantain": "plantain", "coffee": "coffee", "cocoa": "cocoa", "tea": "tea",
            "cotton": "cotton", "tobacco": "tobacco",
        }
        self.animal_aliases = {
            "goat": "goat", "goats": "goat",
            "sheep": "sheep", "cattle": "cattle", "cow": "cow", "cows": "cow",
            "bull": "bull", "calf": "calf", "pig": "pig", "swine": "swine",
            "chicken": "chicken", "poultry": "poultry", "hen": "hen", "duck": "duck",
            "turkey": "turkey", "donkey": "donkey", "horse": "horse", "camel": "camel",
            "rabbit": "rabbit",
        }

    def _extract_crop(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for alias, canonical in sorted(self.crop_aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                return canonical
        return None

    def _extract_animal(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for alias, canonical in sorted(self.animal_aliases.items(), key=lambda x: len(x[0]), reverse=True):
            if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                return canonical
        return None

    def _extract_symptoms(self, query_lower: str) -> tuple[List[str], List[str]]:
        """Extract positive and negative symptoms separately."""
        positive = []
        negative = []

        # Replace variations of negative statements with a standard marker
        # "don't have fluids", "no fever", "without pus" -> "NOT_ fluid", "NOT_ fever", "NOT_ pus"
        
        # Simplified negative detection: split by common negative phrases
        neg_phrases = ["no ", "not ", "don't have ", "dont have ", "doesn't have ", "doesnt have ", "without "]
        
        # We'll tag symptom matches as negative if they immediately follow a negative phrase in the same clause
        clauses = re.split(r'[,;.!&]| and | but ', query_lower)
        
        for clause in clauses:
            clause = " " + clause.strip() + " "
            is_negative_clause = False
            for np in neg_phrases:
                if " " + np in clause:
                    is_negative_clause = True
                    break
            
            for sym in SYMPTOM_KEYWORDS:
                pattern = r'\b' + re.escape(sym) + r'\b'
                if re.search(pattern, clause):
                    if is_negative_clause:
                        # Ensure the negative phrase comes *before* the symptom in this clause
                        sym_idx = clause.find(sym)
                        neg_idx = -1
                        for np in neg_phrases:
                            idx = clause.find(" " + np)
                            if idx != -1 and idx < sym_idx:
                                neg_idx = idx
                                break
                        if neg_idx != -1:
                            negative.append(sym)
                        else:
                            positive.append(sym)
                    else:
                        positive.append(sym)
                        
        return list(set(positive)), list(set(negative))

    def _determine_domain(self, query_lower: str, crop: Optional[str], animal: Optional[str]) -> str:
        if crop and not animal: return "crop"
        if animal and not crop: return "livestock"
        if crop and animal: return "general"
        return "general"

    def _extract_keywords(self, query: str) -> List[str]:
        tokens = re.findall(r'[a-zA-Z0-9_-]+', query.lower())
        return list(set([t for t in tokens if len(t) > 2 and t not in STOP_WORDS]))

    def merge_state(self, new_query: str, existing_state: Optional[Dict] = None) -> Dict[str, Any]:
        """
        CRITICAL RULE #2: Merge new information into explicit conversation state.
        CRITICAL RULE #1: Never change animal/crop unless explicitly overridden.
        """
        if not existing_state:
            existing_state = {
                "domain": "general",
                "animal": None,
                "crop": None,
                "problem_type": "general",
                "problem": "",
                "symptoms": [],
                "negative_symptoms": [],
                "keywords": [],
                "conversation_turn": 0
            }

        query_lower = new_query.lower()

        new_crop = self._extract_crop(query_lower)
        new_animal = self._extract_animal(query_lower)
        pos, neg = self._extract_symptoms(query_lower)
        
        # Merge Crop and Animal - existing state WINS unless explicitly overriden 
        final_crop = existing_state.get("crop")
        if new_crop: final_crop = new_crop
        
        final_animal = existing_state.get("animal")
        if new_animal: final_animal = new_animal
        
        final_domain = self._determine_domain(query_lower, final_crop, final_animal)
        
        # Merge Symptoms
        final_pos = set(existing_state.get("symptoms", []))
        final_neg = set(existing_state.get("negative_symptoms", []))
        
        for p in pos: final_pos.add(p)
        for n in neg: final_neg.add(n)
        
        # Ensure no symptom is in both (new overrides old if conflicting)
        for n in neg:
            if n in final_pos: final_pos.remove(n)
        for p in pos:
            if p in final_neg: final_neg.remove(p)

        new_keywords = self._extract_keywords(new_query)
        final_keywords = list(set(existing_state.get("keywords", []) + new_keywords))

        new_state = {
            "domain": final_domain,
            "animal": final_animal,
            "crop": final_crop,
            "problem_type": "disease" if (final_pos or final_neg) else "general",
            "problem": "",
            "symptoms": list(final_pos),
            "negative_symptoms": list(final_neg),
            "keywords": final_keywords,
            "conversation_turn": existing_state.get("conversation_turn", 0) + 1
        }
        return new_state

    def analyze(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Legacy wrapper. Reconstructs state from history if provided, then merges.
        """
        state = None
        if history:
            # We recreate the state by playing back user queries
            for h in history:
                role = h.get("role")
                if role == "user":
                    content = h.get("content", "")
                    state = self.merge_state(content, state)
                    
        return self.merge_state(query, state)

