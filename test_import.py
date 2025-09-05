# test_import.py
try:
    from core.rag_system import ArgoRAGSystem
    print("✅ Successfully imported full RAG system")
    rag = ArgoRAGSystem()
except Exception as e:
    print(f"❌ Failed to import full RAG system: {e}")
    import traceback
    traceback.print_exc()