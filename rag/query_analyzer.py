"""
Agricultural Query Analyzer for AgriMate Offline RAG.
Analyzes user queries to extract structured metadata (domain, crop, animal,
problem_type, symptoms, and expanded keywords) to guide offline retrieval.
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
    "loss", "appetite"
]

# Synonyms for Query Expansion
SYNONYMS: Dict[str, List[str]] = {
    "corn": ["maize"],
    "maize": ["corn"],
    "cow": ["cattle"],
    "cattle": ["cow"],
    "hen": ["chicken", "poultry"],
    "chicken": ["poultry", "hen"],
    "poultry": ["chicken", "hen"],
    "pig": ["swine"],
    "swine": ["pig"],
    "sweet potato": ["sweetpotato"],
    "sweetpotato": ["sweet potato"],
    "groundnut": ["peanut"],
    "groundnuts": ["peanuts", "peanut"],
    "peanut": ["groundnut"],
    "peanuts": ["groundnuts", "groundnut"],
    "yellowing": ["yellow"],
    "yellow": ["yellowing"],
    "rotting": ["rot"],
    "rot": ["rotting"],
    "wilting": ["wilt"],
    "wilt": ["wilting"],
    "spot": ["spots"],
    "spots": ["spot"],
    "scab": ["scabs"],
    "scabs": ["scab"],
    "lesion": ["lesions"],
    "lesions": ["lesion"],
    "blister": ["blisters"],
    "blisters": ["blister"],
    "swelling": ["swollen"],
    "swollen": ["swelling"],
    "diarrhea": ["diarrhoea"],
    "diarrhoea": ["diarrhea"],
    "lame": ["lameness"],
    "lameness": ["lame"],
    "lumps": ["lumpy"],
    "lumpy": ["lumps"],
}

# Stopwords to filter out during tokenization
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

# Follow-up Pronouns
FOLLOW_UP_PRONOUNS = {
    "it", "they", "them", "its", "their", "theirs", "this", "these", "that", "those"
}

# Problem Type Pattern Indicators
PROBLEM_TYPE_PATTERNS = {
    "pest": [
        "pest", "pests", "insect", "insects", "caterpillar", "caterpillars",
        "worm", "worms", "armyworm", "fall armyworm", "borer", "borers",
        "aphid", "aphids", "beetle", "beetles", "weevil", "weevils",
        "mite", "mites", "tick", "ticks", "flea", "fleas", "fly", "flies",
        "locust", "locusts", "grasshopper", "grasshoppers", "moth", "moths",
        "bug", "bugs", "larva", "larvae", "grub", "grubs", "infestation",
        "infested", "chewing", "chewed", "eating holes", "holes in leaves",
        "holes", "leafminer", "stemborer", "cutworm", "whitefly", "whiteflies",
        "termite", "termites", "slug", "slugs", "snail", "snails", "eating"
    ],
    "disease": [
        "disease", "diseases", "infection", "fungus", "fungal", "bacteria",
        "bacterial", "virus", "viral", "blight", "rot", "rotting", "wilt",
        "wilting", "mold", "mould", "rust", "smut", "spot", "spots",
        "lesion", "lesions", "scab", "scabs", "canker", "mosaic", "mildew",
        "fever", "cough", "diarrhea", "diarrhoea", "mastitis", "anthrax",
        "pox", "swelling", "swollen", "discharge", "bleeding", "blister",
        "blisters", "lump", "lumps", "lumpy", "scabby", "sick", "coccidiosis",
        "bloat", "footrot", "damping off", "anthracnose", "galls", "chlorosis",
        "necrosis", "necrotic", "dieback", "pustule", "pustules"
    ],
    "deficiency": [
        "deficiency", "deficient", "nutrient deficiency", "lack of nitrogen",
        "nitrogen deficiency", "phosphorus deficiency", "potassium deficiency",
        "nutrient", "nutrients", "fertilizer deficiency", "stunted growth",
        "yellowing of leaves", "malnutrition", "malnourished", "micronutrient",
        "nitrogen", "phosphorus", "potassium", "calcium", "magnesium", "zinc", "iron"
    ],
    "management": [
        "planting", "plant", "how to plant", "spacing", "pruning", "prune",
        "harvest", "harvesting", "when to harvest", "irrigation", "irrigate",
        "watering", "water requirement", "breed", "breeding", "housing",
        "shelter", "feed", "feeds", "feeding", "diet", "ration", "vaccination",
        "vaccine", "vaccines", "vaccinate", "storage", "storing", "store",
        "yield", "yields", "soil preparation", "compost", "mulch", "mulching",
        "weed control", "weeding", "gestation", "milking", "cultivation",
        "cultivate", "sowing", "sow", "seed rate", "fertilizer application",
        "fertilizer", "fertilizers", "manure"
    ]
}


class QueryAnalyzer:
    """
    Analyzes an agricultural query and optional conversation history to produce
    structured search filters and query expansions.
    """

    def __init__(self):
        self._build_alias_maps()

    def _build_alias_maps(self):
        # Crop aliases mapping to canonical name
        self.crop_aliases = {
            "sweet potato": "sweet potato",
            "sweet potatoes": "sweet potato",
            "sweetpotato": "sweet potato",
            "sweetpotatoes": "sweet potato",
            "sugar cane": "sugarcane",
            "sugarcane": "sugarcane",
            "ground nut": "groundnuts",
            "ground nuts": "groundnuts",
            "groundnut": "groundnuts",
            "groundnuts": "groundnuts",
            "peanut": "groundnuts",
            "peanuts": "groundnuts",
            "cow pea": "cowpeas",
            "cow peas": "cowpeas",
            "cowpea": "cowpeas",
            "cowpeas": "cowpeas",
            "bean": "beans",
            "beans": "beans",
            "maize": "maize",
            "corn": "corn",
            "wheat": "wheat",
            "sorghum": "sorghum",
            "millet": "millet",
            "rice": "rice",
            "cassava": "cassava",
            "cassavas": "cassava",
            "yam": "yam",
            "yams": "yam",
            "potato": "potato",
            "potatoes": "potato",
            "tomato": "tomato",
            "tomatoes": "tomato",
            "onion": "onion",
            "onions": "onion",
            "cabbage": "cabbage",
            "cabbages": "cabbage",
            "spinach": "spinach",
            "banana": "banana",
            "bananas": "banana",
            "plantain": "plantain",
            "plantains": "plantain",
            "coffee": "coffee",
            "cocoa": "cocoa",
            "tea": "tea",
            "cotton": "cotton",
            "tobacco": "tobacco",
        }

        # Animal aliases mapping to canonical name
        self.animal_aliases = {
            "goat": "goat",
            "goats": "goat",
            "sheep": "sheep",
            "cattle": "cattle",
            "cow": "cow",
            "cows": "cow",
            "bull": "bull",
            "bulls": "bull",
            "calf": "calf",
            "calves": "calf",
            "pig": "pig",
            "pigs": "pig",
            "swine": "swine",
            "chicken": "chicken",
            "chickens": "chicken",
            "poultry": "poultry",
            "hen": "hen",
            "hens": "hen",
            "duck": "duck",
            "ducks": "duck",
            "turkey": "turkey",
            "turkeys": "turkey",
            "donkey": "donkey",
            "donkeys": "donkey",
            "horse": "horse",
            "horses": "horse",
            "camel": "camel",
            "camels": "camel",
            "rabbit": "rabbit",
            "rabbits": "rabbit",
        }

    def _extract_crop(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        # Match longest alias first (e.g. 'sweet potato' before 'potato')
        for alias, canonical in sorted(self.crop_aliases.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return canonical
        return None

    def _extract_animal(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        for alias, canonical in sorted(self.animal_aliases.items(), key=lambda x: len(x[0]), reverse=True):
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_lower):
                return canonical
        return None

    def _extract_symptoms(self, query_lower: str) -> List[str]:
        matched = []
        for sym in SYMPTOM_KEYWORDS:
            pattern = r'\b' + re.escape(sym) + r'\b'
            match = re.search(pattern, query_lower)
            if match:
                matched.append((match.start(), sym))
        # Sort symptoms by appearance order in query
        matched.sort(key=lambda x: x[0])
        return [s for _, s in matched]

    def _determine_domain(
        self, query_lower: str, crop: Optional[str], animal: Optional[str]
    ) -> str:
        if crop and not animal:
            return "crop"
        if animal and not crop:
            return "livestock"
        if crop and animal:
            return "general"

        crop_indicators = {
            "plant", "plants", "crop", "crops", "leaf", "leaves", "stem", "stems",
            "root", "roots", "seed", "seeds", "seedling", "seedlings", "fruit",
            "fruits", "flower", "flowers", "harvest", "harvesting", "soil",
            "yield", "yields", "vegetable", "vegetables", "orchard", "field"
        }
        livestock_indicators = {
            "livestock", "animal", "animals", "herd", "herds", "flock", "flocks",
            "cattle", "udder", "udders", "milk", "milking", "meat", "egg", "eggs",
            "veterinary", "vet", "vaccine", "vaccination", "pasture", "grazing",
            "hoof", "hooves", "horn", "horns", "beak", "feather", "feathers", "tail"
        }

        crop_score = sum(
            1 for word in crop_indicators if re.search(r'\b' + re.escape(word) + r'\b', query_lower)
        )
        livestock_score = sum(
            1 for word in livestock_indicators if re.search(r'\b' + re.escape(word) + r'\b', query_lower)
        )

        if crop_score > livestock_score:
            return "crop"
        elif livestock_score > crop_score:
            return "livestock"
        return "general"

    def _determine_problem_type(self, query_lower: str, symptoms: List[str]) -> str:
        scores = {
            "pest": 0,
            "disease": 0,
            "deficiency": 0,
            "management": 0,
        }

        for pt, patterns in PROBLEM_TYPE_PATTERNS.items():
            for pat in patterns:
                if re.search(r'\b' + re.escape(pat) + r'\b', query_lower):
                    weight = 2 if (" " in pat or len(pat) > 5) else 1
                    scores[pt] += weight

        if symptoms:
            # Symptoms generally indicate disease unless specific pest/deficiency keywords dominate
            scores["disease"] += len(symptoms)

        max_score = max(scores.values())
        if max_score > 0:
            # Break ties by priority: pest, disease, deficiency, management
            priority_order = ["pest", "disease", "deficiency", "management"]
            for pt in priority_order:
                if scores[pt] == max_score:
                    return pt
        return "general"

    def _extract_keywords(
        self, query: str, crop: Optional[str], animal: Optional[str]
    ) -> List[str]:
        query_lower = query.lower()
        tokens = re.findall(r'[a-zA-Z0-9_-]+', query_lower)
        keywords: List[str] = []
        seen = set()

        def add_token(t: str):
            t_clean = t.strip().lower()
            if t_clean and t_clean not in STOP_WORDS and len(t_clean) >= 2 and t_clean not in seen:
                seen.add(t_clean)
                keywords.append(t_clean)

        # 1. Add non-stopword tokens from query
        for token in tokens:
            add_token(token)
            # Expand single-word synonyms
            if token in SYNONYMS:
                for syn in SYNONYMS[token]:
                    for sub in re.findall(r'[a-zA-Z0-9_-]+', syn.lower()):
                        add_token(sub)

        # 2. Expand multi-word phrase synonyms
        for phrase, syn_list in SYNONYMS.items():
            if " " in phrase and phrase in query_lower:
                for syn in syn_list:
                    for sub in re.findall(r'[a-zA-Z0-9_-]+', syn.lower()):
                        add_token(sub)

        # 3. If crop or animal was identified (including carried forward), ensure it's in keywords
        for entity in (crop, animal):
            if entity:
                for sub in re.findall(r'[a-zA-Z0-9_-]+', entity.lower()):
                    add_token(sub)
                    if sub in SYNONYMS:
                        for syn in SYNONYMS[sub]:
                            for s in re.findall(r'[a-zA-Z0-9_-]+', syn.lower()):
                                add_token(s)

        return keywords

    def analyze(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Analyze a user query and conversation history.

        Returns a dictionary with keys:
            - domain: 'crop', 'livestock', or 'general'
            - crop: detected crop name or None
            - animal: detected animal name or None
            - problem_type: 'disease', 'pest', 'deficiency', 'management', or 'general'
            - symptoms: list of detected symptom keywords
            - keywords: list of significant non-stopword tokens plus expanded synonyms
        """
        if not query:
            query = ""

        query_lower = query.lower()

        # Step 1: Detect crop and animal directly in current query
        crop = self._extract_crop(query_lower)
        animal = self._extract_animal(query_lower)

        # Step 2: Follow-up detection using conversation history
        # If no crop/animal was found and the query contains pronouns like 'it', 'they', etc.,
        # look back through history for the last detected crop or animal.
        has_pronoun = any(
            re.search(r'\b' + re.escape(p) + r'\b', query_lower) for p in FOLLOW_UP_PRONOUNS
        )

        if (crop is None and animal is None) and history and (has_pronoun or not (crop or animal)):
            for entry in reversed(history):
                if isinstance(entry, dict):
                    # Check direct structured keys
                    if entry.get("crop"):
                        crop = self.crop_aliases.get(entry["crop"].lower(), entry["crop"])
                        break
                    if entry.get("animal"):
                        animal = self.animal_aliases.get(entry["animal"].lower(), entry["animal"])
                        break

                    # Check text fields in history item
                    text = (
                        entry.get("content")
                        or entry.get("query")
                        or entry.get("prompt")
                        or entry.get("text")
                        or entry.get("message")
                        or ""
                    )
                    if isinstance(text, str) and text:
                        hist_crop = self._extract_crop(text)
                        if hist_crop:
                            crop = hist_crop
                            break
                        hist_animal = self._extract_animal(text)
                        if hist_animal:
                            animal = hist_animal
                            break
                elif isinstance(entry, str):
                    hist_crop = self._extract_crop(entry)
                    if hist_crop:
                        crop = hist_crop
                        break
                    hist_animal = self._extract_animal(entry)
                    if hist_animal:
                        animal = hist_animal
                        break

        # Step 3: Extract symptoms
        symptoms = self._extract_symptoms(query_lower)

        # Step 4: Determine domain
        domain = self._determine_domain(query_lower, crop, animal)

        # Step 5: Determine problem type
        problem_type = self._determine_problem_type(query_lower, symptoms)

        # Step 6: Extract keywords and expand synonyms
        keywords = self._extract_keywords(query, crop, animal)

        return {
            "domain": domain,
            "crop": crop,
            "animal": animal,
            "problem_type": problem_type,
            "symptoms": symptoms,
            "keywords": keywords,
        }


if __name__ == "__main__":
    analyzer = QueryAnalyzer()

    test_cases = [
        {
            "query": "My maize leaves have yellow spots and are wilting",
            "history": None,
            "description": "Crop Disease Query"
        },
        {
            "query": "What pest is eating holes in my cabbage?",
            "history": None,
            "description": "Crop Pest Query"
        },
        {
            "query": "My cow has a high fever and swollen udders",
            "history": None,
            "description": "Livestock Disease Query"
        },
        {
            "query": "How do I treat it?",
            "history": [{"role": "user", "content": "My tomato has yellowing leaves"}],
            "description": "Follow-up Query with Pronoun ('it') referencing Tomato"
        },
        {
            "query": "What should I feed them?",
            "history": [{"role": "user", "content": "I recently acquired four dairy goats"}],
            "description": "Follow-up Query with Pronoun ('them') referencing Goats"
        },
        {
            "query": "My tomato plants have stunted growth due to nitrogen deficiency",
            "history": None,
            "description": "Deficiency Query"
        },
        {
            "query": "What is the best spacing for planting sweet potato?",
            "history": None,
            "description": "Management Query"
        },
        {
            "query": "How does crop rotation improve soil fertility?",
            "history": None,
            "description": "General Crop Query"
        },
        {
            "query": "My corn and hen have rotting and wilting issues",
            "history": None,
            "description": "Synonym Expansion Test (corn->maize, hen->chicken/poultry, rotting->rot, wilting->wilt)"
        },
    ]

    print("=" * 70)
    print("AGRIMATE QUERY ANALYZER - TEST SUITE")
    print("=" * 70)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n[Test Case {i}] {tc['description']}")
        print(f"Query:   \"{tc['query']}\"")
        if tc["history"]:
            print(f"History: {tc['history']}")
        result = analyzer.analyze(tc["query"], tc["history"])
        print("Analysis Result:")
        for k, v in result.items():
            print(f"  {k:14}: {v}")

    print("\n" + "=" * 70)
    print("All tests completed successfully.")
    print("=" * 70)
