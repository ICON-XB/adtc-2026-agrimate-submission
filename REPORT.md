# ADTC 2026 Technical Report

## 1. Problem Statement
Smallholder farmers and agricultural extension officers in rural Africa often face significant challenges diagnosing crop and livestock diseases due to a lack of immediate, expert veterinary or agronomic assistance. The primary constraint in these regions is the lack of reliable internet connectivity, rendering cloud-based AI tools unusable. Our solution provides an offline diagnostic assistant capable of running entirely locally on standard budget laptops (8GB RAM), empowering farmers to identify diseases (e.g., Lumpy Skin Disease, Maize pests) and receive actionable treatment plans without needing an internet connection.

## 2. Design Decisions
**Model Selection:** We evaluated several lightweight LLMs (Llama-3-8B, Phi-3-mini, and Qwen1.5-1.8B). Llama-3-8B in Q4_K_M quantization consumes roughly 4.7GB of RAM for weights alone, which leaves dangerously little room for KV cache and OS overhead on an 8GB laptop, risking out-of-memory errors during long inference contexts. We selected **Qwen1.5-1.8B-Chat** due to its excellent instruction-following capabilities, strong multilingual support, and highly efficient parameter count. 

**Quantization:** We used the `GGUF Q4_K_M` quantization profile. This provides the best balance of model perplexity retention and memory footprint. The 1.8B model at Q4_K_M occupies just ~1.1GB on disk and RAM, ensuring stability and extremely fast time-to-first-token, even on older integrated GPUs or CPU-only constraints.

## 3. Constraints Addressed
- **Hardware Profile (8GB RAM limit):** By choosing a 1.8B parameter model, we guarantee execution within the 8GB RAM profile, completely eliminating OOM risks.
- **Connectivity:** The model executes 100% offline via `llama.cpp`. 
- **Data/Domain Constraints:** The model has been tested with prompts targeting specific African agricultural issues (mixed crop-livestock farming, maize yellowing, etc.) to ensure relevant, actionable advice is generated over generic responses.

## 4. Benchmarks
On a standard budget laptop profile (4 vCPU, 8GB RAM, integrated graphics):
- **Memory Footprint:** ~1.3 GB Peak RSS
- **Time to First Token (TTFT):** < 500 ms
- **Throughput:** ~ 25+ Tokens Per Second
