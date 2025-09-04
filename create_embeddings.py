import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import Config
from core.rag_system import ArgoRAGSystem

def main():
    config = Config()
    rag = ArgoRAGSystem()
    num_chunks = rag.create_embeddings_from_file("./data/improved_knowledge_base.md")
    print(f"✅ Created {num_chunks} embeddings successfully!")

if __name__ == "__main__":
    main()
