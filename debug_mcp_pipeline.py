# debug_mcp_pipeline.py
import asyncio
import json
from core.query_router import QueryRouter

async def debug_mcp():
    router = QueryRouter()
    
    query = "Compare oxygen levels between Arabian Sea and Bay of Bengal"
    
    # Step 1: Test tool analysis
    context_chunks = router.rag_system.retrieve_context(query, top_k=5)
    
    analysis = await router.mcp_client._analyze_query_for_tools(
        query, context_chunks, ""
    )
    
    print("LLM Analysis Response:")
    print(json.dumps(analysis, indent=2))
    
    # Step 2: If we have tool calls, try executing them
    if analysis.get("tool_calls"):
        print("\nExecuting tools:")
        for tool_call in analysis["tool_calls"]:
            print(f"\nTool: {tool_call['name']}")
            print(f"Parameters: {tool_call.get('parameters', {})}")
            
            result = await router.mcp_client._execute_tool(tool_call)
            print(f"Result: {result}")

asyncio.run(debug_mcp())