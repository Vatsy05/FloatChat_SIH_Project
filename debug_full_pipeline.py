# debug_full_pipeline.py
import asyncio
from core.query_router import QueryRouter

async def debug_full():
    router = QueryRouter()
    
    query = "Compare oxygen levels between Arabian Sea and Bay of Bengal"
    
    # Run the full MCP pipeline
    result = await router.mcp_client.process_query_with_tools(query, "")
    
    print("Full Pipeline Result:")
    print(f"Success: {result.get('success')}")
    print(f"Error: {result.get('error')}")
    print(f"Tools Used: {result.get('tools_used')}")
    print(f"Tool Errors: {result.get('tool_errors')}")
    
    # Check raw tool results if available
    if 'raw_tool_results' in result:
        print("\nRaw Tool Results:")
        for r in result['raw_tool_results']:
            print(f"- {r.get('tool_name')}: success={r.get('success')}")

asyncio.run(debug_full())