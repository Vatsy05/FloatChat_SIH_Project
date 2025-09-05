# debug_import.py
print("Testing import chain...")

try:
    from core.rag_system import ArgoRAGSystem
    print("✅ rag_system imports successfully")
except Exception as e:
    print(f"❌ rag_system failed: {e}")

try:
    from core.query_router import QueryRouter
    print("✅ query_router imports successfully")
    router = QueryRouter()
except Exception as e:
    print(f"❌ query_router failed: {e}")
    import traceback
    traceback.print_exc()