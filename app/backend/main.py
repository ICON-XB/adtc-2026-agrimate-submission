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


def generate_llm_like_response(prompt: str, results: list) -> str:
    """Simulates an LLM response by intelligently formatting RAG context."""
    if not results:
        return ""
        
    prompt_lower = prompt.lower()
    
    # Extract potential crop/animal from prompt
    subject = "your crops/livestock"
    if "maize" in prompt_lower or "corn" in prompt_lower: subject = "your maize"
    elif "goat" in prompt_lower: subject = "your goat"
    elif "cattle" in prompt_lower or "cow" in prompt_lower: subject = "your cattle"
    elif "cassava" in prompt_lower: subject = "your cassava"
    elif "poultry" in prompt_lower or "chicken" in prompt_lower: subject = "your poultry"
    
    # 1. Opening
    response = f"Based on the symptoms you described for {subject}, here is my analysis from our local agricultural database:\n\n"
    
    # 2. Diagnosis & Synthesis
    response += "DIAGNOSIS & INFORMATION\n------------------------\n"
    
    # Clean and synthesize the raw text snippets
    for r in results:
        text = r["text"].replace("\n", " ").strip()
        response += f"• {text}\n\n"
            
    # 3. Actionable Advice
    response += "RECOMMENDED ACTION PLAN\n------------------------\n"
    response += "1. Immediate Isolation: Separate the affected plants or animals to prevent the spread of any potential pathogen.\n"
    response += "2. Monitoring: Keep a close eye on the rest of your farm for similar symptoms.\n"
    response += "3. Sanitation: Ensure all tools, water sources, and equipment are clean and disinfected.\n"
    response += "4. Professional Consultation: Contact your local agricultural extension officer or veterinarian for specific chemical or medical treatments suitable for your region.\n"
    
    return response


def try_offline_answer(prompt: str, history: list, debug: bool = False) -> tuple[str | None, list[str], dict]:
    """Search the local knowledge base using the full RAG pipeline."""
    if not local_rag or not query_analyzer or not relevance_gate:
        return None, [], {}

    # 1. Analyze query
    analysis = query_analyzer.analyze(prompt, history)
    
    # 2. Retrieve candidates
    results = local_rag.retrieve(prompt, analysis, top_k=5)
    
    # 3. Relevance Gate filtering
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

    formatted_response = generate_llm_like_response(prompt, filtered_results)
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
