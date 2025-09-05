# debug_tool.py
import asyncio
from core.query_router import QueryRouter

async def debug_tool_execution():
    router = QueryRouter()
    
    # Test the regional stats tool directly
    print("Testing regional stats tool...")
    
    result = await router.mcp_client.tool_factory.execute_regional_stats(
        region_name="arabian_sea",
        parameter="oxygen"
    )
    
    print(f"Result: {result}")

asyncio.run(debug_tool_execution())