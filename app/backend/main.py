from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
import time
import os
import jwt
from argon2 import PasswordHasher
from datetime import datetime, timedelta

# Application Initialization
app = FastAPI(title="AgriMate Secure API", description="Offline-first secure agricultural AI")

# --- Security Config ---
SECRET_KEY = os.environ.get("AGRIMATE_SECRET_KEY", "super-secret-offline-key-change-in-prod")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
ph = PasswordHasher()

# --- Middleware (OWASP Security Headers & CORS) ---
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], # Vite default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Basic Rate Limiting (In-Memory Mock) ---
# In a real app, use Redis or limits package
RATE_LIMIT = 50 # requests per minute
client_requests = {}

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    
    if client_ip not in client_requests:
        client_requests[client_ip] = []
        
    # Clean up old requests
    client_requests[client_ip] = [req_time for req_time in client_requests[client_ip] if current_time - req_time < 60]
    
    if len(client_requests[client_ip]) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Too many requests"})
        
    client_requests[client_ip].append(current_time)
    return await call_next(request)


# --- Authentication & RBAC ---
# In-memory user DB for demonstration
fake_users_db = {
    "admin": {
        "username": "admin",
        "password_hash": ph.hash("SecureAdminPass123!"),
        "role": "admin",
        "mfa_enabled": False
    },
    "farmer": {
        "username": "farmer",
        "password_hash": ph.hash("FarmerPass123!"),
        "role": "user",
        "mfa_enabled": False
    }
}

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    username: str
    password: str

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    token = token.split(" ")[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
    
    user = fake_users_db.get(username)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

def require_role(required_role: str):
    def role_checker(current_user: dict = Depends(get_current_user)):
        if current_user.get("role") != required_role and current_user.get("role") != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not enough privileges")
        return current_user
    return role_checker

# --- Endpoints ---
@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    user = fake_users_db.get(user_data.username)
    if not user:
        # Prevent timing attacks by generic error message
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    try:
        ph.verify(user["password_hash"], user_data.password)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

class QueryRequest(BaseModel):
    prompt: str
    region: str = "pan-african"
    history: list = []
    debug: bool = False

import sys
import os

# Add parent directory to path so we can import rag module
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
try:
    from rag.retriever import SimpleRAG
    from rag.query_analyzer import QueryAnalyzer
    from rag.relevance_gate import RelevanceGate
    from rag.online_collector import OnlineCollector
    
    knowledge_path = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge")
    local_rag = SimpleRAG(knowledge_path)
    query_analyzer = QueryAnalyzer()
    relevance_gate = RelevanceGate()
    online_collector = OnlineCollector(knowledge_path)
except Exception as e:
    local_rag = None
    query_analyzer = None
    relevance_gate = None
    online_collector = None
    print("Warning: Could not initialize local RAG components:", e)


def try_online_answer(prompt: str, region: str) -> str | None:
    """Try to get an answer from Gemini API if key is present, otherwise safely return None."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            import google.generativeai as genai
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            system_prompt = (
                f"You are AgriMate, an expert agricultural AI assistant. "
                f"The user is farming in the {region.replace('-', ' ')} region. "
                f"Answer their question with highly detailed, professional, and actionable advice."
            )
            response = model.generate_content(f"{system_prompt}\n\nQuestion: {prompt}")
            return response.text
        except Exception as e:
            print("Gemini API failed:", e)

    # Secondary online attempt using DuckDuckGo search API to synthesize a response
    try:
        from ddgs import DDGS
        results = DDGS().text(f"agriculture {region} {prompt}", max_results=2)
        if results:
            synthesized = "According to search records:\n"
            for r in results:
                synthesized += f"- {r.get('body', '')}\n"
            return synthesized
    except Exception:
        pass
        
    return None


def format_llm_context(results: list) -> str:
    """Formats the retrieved chunks into a compact evidence package for the LLM."""
    if not results:
        return ""
    
    context_blocks = []
    for i, r in enumerate(results, start=1):
        source = r["source"].replace(".md", "").replace("_", " ").title()
        text = r["text"].replace("\n", " ").strip()
        metadata = r.get("metadata", {})
        crop = metadata.get("crop", "N/A")
        animal = metadata.get("animal", "N/A")
        disease = metadata.get("disease", "Unknown")
        
        block = f"[RELEVANT SOURCE {i}]\nSource: {source}\n"
        if crop: block += f"Crop: {crop}\n"
        if animal: block += f"Animal: {animal}\n"
        block += f"Disease/Topic: {disease}\nEvidence:\n{text}\n"
        
        context_blocks.append(block)
        
    return "\n".join(context_blocks)


def generate_llm_like_response(prompt: str, results: list, analysis: dict = None) -> tuple:
    """
    Synthesizes an evidence-driven, cautious agricultural answer.
    - Does NOT force a diagnosis.
    - Recommends follow-up questions when evidence is ambiguous.
    - Never uses a generic action-plan template.
    - Does not invent drug dosages or chemical rates.
    """
    context_text = format_llm_context(results)

    if not results:
        return (
            "I don't have enough specific information in my local database to answer that reliably.\n\n"
            "Could you give me a few more details?\n"
            "- Which crop or animal is affected?\n"
            "- What symptoms are you seeing?\n"
            "- When did the problem start?",
            context_text
        )

    analysis = analysis or {}
    domain      = analysis.get("domain", "general")
    crop        = analysis.get("crop")
    animal      = analysis.get("animal")
    symptoms    = analysis.get("symptoms", [])
    problem_type= analysis.get("problem_type", "general")

    # Collect unique diseases/topics from the retrieved chunks
    diseases = []
    for r in results:
        meta = r.get("metadata", {})
        d = meta.get("disease", "")
        if d and d not in diseases:
            diseases.append(d)

    source_names = [r["source"].replace(".md", "").replace("_", " ").title() for r in results]
    unique_sources = list(dict.fromkeys(source_names))

    subject_label = animal or crop or "your crop/livestock"

    # --- Build the answer ---
    response_parts = []

    # 1. Opening: acknowledge what the user described
    if symptoms:
        symptom_str = ", ".join(symptoms)
        response_parts.append(
            f"The symptoms you describe ({symptom_str}) on {subject_label} can have several causes. "
            "Based on the information in my local agricultural database, here are the most likely possibilities."
        )
    else:
        response_parts.append(
            f"Based on your question about {subject_label}, here is what I found in my local agricultural database."
        )

    # 2. Evidence-based possibilities (from retrieved chunks only)
    if diseases:
        possibilities = []
        for r in results:
            meta = r.get("metadata", {})
            disease = meta.get("disease", "")
            if not disease:
                continue
            # Extract first 200 chars of the text as a snippet
            snippet = r["text"].strip().replace("\n", " ")
            # Find symptom description if present
            sym_match = None
            for line in r["text"].split("\n"):
                if "symptom" in line.lower() or "key" in line.lower():
                    sym_match = line.strip(" -*#").strip()[:180]
                    break
            if disease not in [p[0] for p in possibilities]:
                possibilities.append((disease, sym_match or snippet[:180]))

        if possibilities:
            response_parts.append("\n**Possible causes from my database:**")
            for disease_name, desc in possibilities[:3]:
                response_parts.append(f"- **{disease_name}**: {desc}")

    # 3. Diagnostic differentiation questions (if we have multiple possibilities)
    follow_up_questions = []
    
    # helper to check if we already know about a symptom concept
    known_symptoms_text = " ".join(symptoms) + " " + " ".join(analysis.get("negative_symptoms", []))
    
    def already_knows(*terms):
        return any(term in known_symptoms_text for term in terms)

    if domain == "livestock" and animal:
        if "lump" in " ".join(symptoms) or "hard" in " ".join(symptoms):
            if not already_knows("jaw", "neck"):
                follow_up_questions.append(f"Are the lumps all over the body, or mainly around the jaw/neck?")
            if not already_knows("pus", "fluid"):
                follow_up_questions.append(f"Do the lumps contain pus or fluid?")
            if not already_knows("scratch", "hair"):
                follow_up_questions.append(f"Is the {animal} scratching, or losing hair around the lumps?")
            if not already_knows("fever", "nasal", "discharge", "appetite"):
                follow_up_questions.append(f"Does the {animal} have fever, nasal discharge, or reduced appetite?")
        elif "scratch" in prompt.lower() or "hair" in prompt.lower() or "itch" in prompt.lower():
            if not already_knows("crust", "scale", "bare"):
                follow_up_questions.append("Are there visible crusts, scales, or bare patches of skin?")
            if not already_knows("start", "where"):
                follow_up_questions.append("Where on the body did the problem start?")
        elif problem_type == "disease" or "diarrhea" in prompt.lower() or "dying" in prompt.lower():
            if not already_knows("how many", "spread"):
                follow_up_questions.append(f"How many {animal}s are affected?")
            if not already_knows("eat", "drink", "appetite"):
                follow_up_questions.append("Are affected animals eating and drinking normally?")

    elif domain == "crop" and crop:
        if "yellow" in " ".join(symptoms) or "spot" in " ".join(symptoms):
            if not already_knows("circular", "rectangular", "cigar", "shape"):
                follow_up_questions.append(f"Are the spots small and circular, rectangular, or long/cigar-shaped?")
            if not already_knows("halo", "yellow"):
                follow_up_questions.append("Do the spots have yellow halos around them?")
            if not already_knows("vein", "restrict"):
                follow_up_questions.append("Are the lesions restricted by the leaf veins?")
            if not already_knows("lower", "upper", "first"):
                follow_up_questions.append("Did the problem start on the lower leaves or upper leaves first?")
        elif "wilt" in " ".join(symptoms):
            if not already_knows("heat", "night", "recover"):
                follow_up_questions.append("Are the plants wilting in the heat of the day and recovering at night?")
            if not already_knows("soil", "dry", "waterlogged"):
                follow_up_questions.append("Is the soil dry or waterlogged?")
            if not already_knows("root", "rot", "discolor"):
                follow_up_questions.append("Are the roots discolored or rotting?")
        elif "curl" in prompt.lower() or "insect" in prompt.lower() or "pest" in prompt.lower():
            if not already_knows("insect", "underside"):
                follow_up_questions.append("Are insects visible on the underside of the leaves?")
            if not already_knows("color"):
                follow_up_questions.append("What color are the insects?")
            if not already_knows("sticky", "sooty"):
                follow_up_questions.append("Are the leaves sticky or have a sooty coating?")

    if follow_up_questions:
        response_parts.append(
            "\n**To narrow down the cause, please tell me:**"
        )
        for q in follow_up_questions[:4]:
            response_parts.append(f"- {q}")

    # 4. Safe immediate actions (domain-specific, NOT generic isolation/sanitation)
    if domain == "livestock":
        response_parts.append(
            "\n**Safe immediate steps:** Separate any visibly sick animal from the herd. "
            "Monitor body temperature, appetite, and water intake. "
            "A veterinarian or livestock extension officer should examine the animal before giving any medications."
        )
    elif domain == "crop":
        response_parts.append(
            "\n**Safe immediate steps:** Avoid overhead watering if fungal disease is suspected. "
            "Remove and destroy heavily infected plant material. "
            "Do not apply fungicides or pesticides without confirming the cause — contact your local agricultural extension officer."
        )

    # 5. Source attribution
    if unique_sources:
        response_parts.append(f"\n*Sources: {', '.join(unique_sources)}*")

    return "\n".join(response_parts), context_text



def try_offline_answer(prompt: str, history: list, debug: bool = False) -> tuple[str | None, list[str], dict]:
    """Search the local knowledge base using the full RAG pipeline."""
    if not local_rag or not query_analyzer or not relevance_gate:
        return None, [], {}

    # 1. Analyze query
    analysis = query_analyzer.analyze(prompt, history)
    
    # 2. Retrieve wider candidate pool (10), hard filter + rank will narrow it down
    results = local_rag.retrieve(prompt, analysis, top_k=10)
    
    # 3. Two-stage relevance gate: hard filter then rank
    filtered_results, sufficient_evidence = relevance_gate.filter(results, analysis, min_score=0.3)
    
    debug_info = {}
    if debug:
        debug_info = {
            "analysis": analysis,
            "explanation": relevance_gate.explain(results, analysis, min_score=0.3),
            "sufficient_evidence": sufficient_evidence
        }

    if not sufficient_evidence:
        return None, [], debug_info

    sources = []
    for r in filtered_results:
        src = r["source"].replace(".md", "").replace("_", " ").title()
        if src not in sources:
            sources.append(src)

    formatted_response, context_text = generate_llm_like_response(prompt, filtered_results, analysis)
    if debug:
        debug_info["llm_context"] = context_text
    return formatted_response, sources, debug_info


@app.post("/api/query")
async def process_query(query: QueryRequest):
    """
    Dual-mode query handler:
    - Online fallback (if configured)
    - Offline RAG with full intelligence pipeline
    """
    sanitized = query.prompt.replace("<", "&lt;").replace(">", "&gt;")

    # We skip direct online fallback if we want to test our local RAG pipeline
    # The pipeline itself handles online knowledge expansion if needed.
    # To strictly test the RAG pipeline, we will only rely on try_offline_answer
    
    offline_answer, sources, debug_info = try_offline_answer(sanitized, query.history, query.debug)
    
    if offline_answer:
        response_data = {
            "response": offline_answer,
            "sources": [f"Local: {s}" for s in sources],
            "mode": "offline"
        }
        if query.debug:
            response_data["debug"] = debug_info
        return response_data

    # Nothing found anywhere
    fallback = {
        "response": f"I don't have enough verified information in my local database to answer this accurately.",
        "sources": [],
        "mode": "offline",
        "insufficient_evidence": True
    }
    if query.debug:
        fallback["debug"] = debug_info
    return fallback

class CollectRequest(BaseModel):
    prompt: str

@app.post("/api/collect")
async def manual_collect(req: CollectRequest):
    if not online_collector:
        return {"status": "error", "message": "Online collector not initialized."}
    
    try:
        collect_result = online_collector.search_and_collect(req.prompt, max_sources=3)
        if collect_result.get("status") == "success":
            # Clear and reload RAG to include new files
            if local_rag:
                local_rag.chunks = []
                local_rag._load_and_chunk()
        return collect_result
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/health")
async def health_check():
    doc_count = len(local_rag.chunks) if local_rag else 0
    return {"status": "ok", "documents_indexed": doc_count}


@app.get("/api/documents")
async def list_documents():
    """Lists all offline agricultural documents in the RAG database."""
    if not local_rag:
        return {"documents": []}
    
    # Extract unique filenames from indexed chunks
    unique_docs = sorted(list(set(chunk[0] for chunk in local_rag.chunks)))
    docs_info = []
    for doc in unique_docs:
        docs_info.append({
            "filename": doc,
            "title": doc.replace(".md", "").replace("_", " ").title()
        })
    return {"documents": docs_info}
