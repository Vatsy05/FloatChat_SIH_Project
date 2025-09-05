"""Test script for MCP integration"""
import asyncio
from core.query_router import QueryRouter

async def test_mcp():
    """Test MCP functionality"""
    
    router = QueryRouter()
    
    # Test queries
    test_queries = [
        "Show me temperature profiles in Arabian Sea",  # Simple - Direct SQL
        "Find the nearest 5 floats to latitude 15.5 longitude 72.8",  # Complex - MCP
        "Compare oxygen levels between Arabian Sea and Bay of Bengal",  # Complex - MCP
        "Show trajectory of float 2902238 for last 60 days"  # Complex - MCP
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        
        result = await router.route_query(query)
        
        print(f"Success: {result.get('success')}")
        print(f"Execution Path: {result.get('execution_path')}")
        
        if result.get('tools_used'):
            print(f"Tools Used: {result.get('tools_used')}")
        
        if result.get('error'):
            print(f"Error: {result.get('error')}")

if __name__ == "__main__":
    asyncio.run(test_mcp())