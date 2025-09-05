# debug_profile_query.py
import asyncio
from core.query_router import QueryRouter
import json

async def debug_profile_processing():
    router = QueryRouter()
    
    # Run the query
    query = "Show temperature profiles in Arabian Sea"
    
    # Get raw SQL results
    sql_response = router.sql_generator.generate_query(query, "")
    print(f"SQL Query: {sql_response['sql_query']}")
    
    # Execute query
    raw_results = router.db_client.execute_query(sql_response['sql_query'])
    print(f"\nRaw results count: {len(raw_results)}")
    
    if raw_results:
        # Check first row structure
        first_row = raw_results[0]
        print(f"\nFirst row keys: {first_row.keys()}")
        
        # Check temperature data format
        temp_data = first_row.get('temperature_celsius')
        print(f"\nTemperature data type: {type(temp_data)}")
        print(f"Temperature data sample: {str(temp_data)[:200]}")
        
        # Check if it's being extracted properly
        if temp_data:
            # Try manual extraction
            if isinstance(temp_data, str):
                print("\nData is string, needs parsing")
            elif isinstance(temp_data, list):
                print(f"\nData is list with {len(temp_data)} values")
                print(f"First few values: {temp_data[:5]}")
    
    # Now process through data processor
    sql_response["query_text"] = query
    processed = router.data_processor.process_query_results(raw_results, sql_response)
    
    print(f"\nProcessed profiles count: {len(processed['data']['profiles']['data'])}")

asyncio.run(debug_profile_processing())