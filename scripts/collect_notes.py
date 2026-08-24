import os
import wikipedia
import time

# List of African agricultural topics to collect notes on
TOPICS = [
    "Agriculture in Africa",
    "Agriculture in South Africa",
    "Agriculture in Nigeria",
    "Agriculture in Kenya",
    "Agriculture in Egypt",
    "Lumpy skin disease",
    "Maize production in Africa",
    "Cassava production",
    "Desertification in Africa",
    "East African drought",
    "Cocoa production in Ivory Coast",
    "Farming systems in Africa"
]

KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge", "african_context")

def collect_notes():
    print(f"Starting data collection into {KNOWLEDGE_DIR}...")
    os.makedirs(KNOWLEDGE_DIR, exist_ok=True)
    
    for topic in TOPICS:
        try:
            print(f"Fetching data for: {topic}...")
            # Fetch summary and full page content
            page = wikipedia.page(topic, auto_suggest=False)
            
            # Format as Markdown
            markdown_content = f"# {page.title}\n\n"
            markdown_content += f"**Source**: {page.url}\n\n"
            markdown_content += page.content
            
            # Save to knowledge base
            filename = topic.lower().replace(" ", "_") + ".md"
            filepath = os.path.join(KNOWLEDGE_DIR, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)
                
            print(f"✅ Saved {filename}")
            time.sleep(1) # Be nice to Wikipedia API
            
        except wikipedia.exceptions.DisambiguationError as e:
            print(f"⚠️ Disambiguation for {topic}: {e.options}")
        except wikipedia.exceptions.PageError:
            print(f"❌ Page not found for {topic}")
        except Exception as e:
            print(f"❌ Error fetching {topic}: {e}")

if __name__ == "__main__":
    collect_notes()
    print("\nData collection complete. Your RAG database is now populated!")
