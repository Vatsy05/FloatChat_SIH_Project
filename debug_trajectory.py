# debug_trajectory.py
import asyncio
from core.query_router import QueryRouter

async def debug_trajectory():
    router = QueryRouter()
    
    # Test the tool directly
    print("Testing trajectory tool for float 2902238...")
    
    result = await router.mcp_client.tool_factory.execute_trajectory(
        wmo_id=2902238,
        days_back=90
    )
    
    print(f"Result: {result}")
    
    # Also test if the float exists
    test_query = """
        SELECT COUNT(*) as count, 
               MAX(profile_date) as latest_date,
               MIN(profile_date) as earliest_date
        FROM public.argo_profiles 
        WHERE wmo_id = 2902238
    """
    
    try:
        db_result = router.db_client.execute_query(test_query)
        print(f"Float exists in DB: {db_result}")
    except Exception as e:
        print(f"DB query error: {e}")

asyncio.run(debug_trajectory())