"""
Supabase client for ARGO float database operations
"""
import asyncio
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
from config.settings import Config

class SupabaseClient:
    def __init__(self):
        self.config = Config()
        self.client: Client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Supabase client"""
        try:
            self.client = create_client(
                self.config.SUPABASE_URL,
                self.config.SUPABASE_KEY
            )
            print("✅ Supabase client initialized successfully")
            
            # Test connection
            self._test_connection()
            
        except Exception as e:
            print(f"❌ Failed to initialize Supabase client: {str(e)}")
            raise
    
    def _test_connection(self):
        """Test database connection"""
        try:
            # Simple query to test connection
            result = self.client.table('argo_floats').select('count').execute()
            print(f"✅ Database connection test successful")
        except Exception as e:
            print(f"⚠️ Database connection test failed: {str(e)}")
    
    def execute_query(self, sql_query: str) -> List[Dict[str, Any]]:
        """Execute raw SQL query and return results"""
        try:
            print(f"🔍 Executing SQL query...")
            print(f"Query: {sql_query[:200]}...")
            
            # Execute raw SQL query using RPC or direct query
            result = self.client.rpc('execute_safe_sql', {'query_text': sql_query}).execute()
            
            if result.data:
                print(f"✅ Query executed successfully, returned {len(result.data)} rows")
                return result.data
            else:
                print("ℹ️ Query executed successfully, no rows returned")
                return []
                
        except Exception as e:
            print(f"❌ Error executing query: {str(e)}")
            # Try alternative execution method
            return self._execute_query_alternative(sql_query)
    
    def _execute_query_alternative(self, sql_query: str) -> List[Dict[str, Any]]:
        """Alternative query execution method using table operations"""
        try:
            # Parse query types and table
            sql_upper = sql_query.upper()
            
            if 'FROM PUBLIC.ARGO_PROFILES' in sql_upper or 'FROM ARGO_PROFILES' in sql_upper:
                return self._query_profiles_table(sql_query)
            elif 'FROM PUBLIC.ARGO_FLOATS' in sql_upper or 'FROM ARGO_FLOATS' in sql_upper:
                return self._query_floats_table(sql_query)
            elif 'JOIN' in sql_upper:
                return self._query_joined_tables(sql_query)
            else:
                print(f"⚠️ Could not parse query for alternative execution")
                return []
                
        except Exception as e:
            print(f"❌ Alternative query execution failed: {str(e)}")
            return []
    
    def _query_profiles_table(self, sql_query: str) -> List[Dict[str, Any]]:
        """Query argo_profiles table using Supabase filters"""
        try:
            # Start with base queries
            query = self.client.table('argo_profiles').select('*')
            
            # Parse common WHERE conditions
            if 'latitude BETWEEN' in sql_query:
                # Extract latitude bounds
                lat_match = self._extract_between_values(sql_query, 'latitude')
                if lat_match:
                    query = query.gte('latitude', lat_match[0]).lte('latitude', lat_match[1])
            
            if 'longitude BETWEEN' in sql_query:
                # Extract longitude bounds
                lon_match = self._extract_between_values(sql_query, 'longitude')
                if lon_match:
                    query = query.gte('longitude', lon_match[0]).lte('longitude', lon_match[1])
            
            if 'float_category' in sql_query:
                if "'BGC'" in sql_query:
                    query = query.eq('float_category', 'BGC')
                elif "'Core'" in sql_query:
                    query = query.eq('float_category', 'Core')
            
            if 'profile_date >=' in sql_query:
                # Extract date
                date_match = self._extract_date_condition(sql_query, 'profile_date >=')
                if date_match:
                    query = query.gte('profile_date', date_match)
            
            # Apply limit
            limit = self._extract_limit(sql_query)
            if limit:
                query = query.limit(limit)
            else:
                query = query.limit(100)  # Default limit
            
            result = query.execute()
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error querying profiles table: {str(e)}")
            return []
    
    def _query_floats_table(self, sql_query: str) -> List[Dict[str, Any]]:
        """Query argo_floats table using Supabase filters"""
        try:
            query = self.client.table('argo_floats').select('*')
            
            # Parse common conditions
            if 'institution' in sql_query and '=' in sql_query:
                institution = self._extract_string_condition(sql_query, 'institution')
                if institution:
                    query = query.eq('institution', institution)
            
            if 'float_type' in sql_query:
                float_type = self._extract_string_condition(sql_query, 'float_type')
                if float_type:
                    query = query.eq('float_type', float_type)
            
            # Apply limit
            limit = self._extract_limit(sql_query)
            query = query.limit(limit if limit else 100)
            
            result = query.execute()
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error querying floats table: {str(e)}")
            return []
    
    def _query_joined_tables(self, sql_query: str) -> List[Dict[str, Any]]:
        """Handle queries with JOINs using multiple queries"""
        try:
            # This is a simplified approach - in production you'd want more sophisticated JOIN handling
            
            # Get profile datas
            profiles_query = self.client.table('argo_profiles').select('*').limit(50)
            profiles_result = profiles_query.execute()
            
            if not profiles_result.data:
                return []
            
            # Get corresponding float data
            wmo_ids = [p['wmo_id'] for p in profiles_result.data]
            floats_query = self.client.table('argo_floats').select('*').in_('wmo_id', wmo_ids)
            floats_result = floats_query.execute()
            
            # Combine results (simple merge)
            float_dict = {f['wmo_id']: f for f in floats_result.data} if floats_result.data else {}
            
            combined_results = []
            for profile in profiles_result.data:
                combined_row = {**profile}
                if profile['wmo_id'] in float_dict:
                    float_data = float_dict[profile['wmo_id']]
                    # Add float data with 'f_' prefix to avoid conflicts
                    for key, value in float_data.items():
                        if key != 'wmo_id':  # Don't duplicate wmo_id
                            combined_row[f'f_{key}'] = value
                combined_results.append(combined_row)
            
            return combined_results
            
        except Exception as e:
            print(f"❌ Error handling joined query: {str(e)}")
            return []
    
    def _extract_between_values(self, sql_query: str, column: str) -> Optional[tuple]:
        """Extract BETWEEN values from SQL query"""
        try:
            import re
            pattern = f'{column}\\s+BETWEEN\\s+(\\d+(?:\\.\\d+)?)\\s+AND\\s+(\\d+(?:\\.\\d+)?)'
            match = re.search(pattern, sql_query, re.IGNORECASE)
            if match:
                return (float(match.group(1)), float(match.group(2)))
            return None
        except Exception:
            return None
    
    def _extract_date_condition(self, sql_query: str, condition: str) -> Optional[str]:
        """Extract date condition from SQL query"""
        try:
            import re
            pattern = f"{condition}\\s+'([^']+)'"
            match = re.search(pattern, sql_query, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    def _extract_string_condition(self, sql_query: str, column: str) -> Optional[str]:
        """Extract string condition from SQL query"""
        try:
            import re
            pattern = f"{column}\\s*=\\s*'([^']+)'"
            match = re.search(pattern, sql_query, re.IGNORECASE)
            if match:
                return match.group(1)
            return None
        except Exception:
            return None
    
    def _extract_limit(self, sql_query: str) -> Optional[int]:
        """Extract LIMIT value from SQL query"""
        try:
            import re
            pattern = r'LIMIT\s+(\d+)'
            match = re.search(pattern, sql_query, re.IGNORECASE)
            if match:
                return int(match.group(1))
            return None
        except Exception:
            return None
    
    def get_float_count(self) -> int:
        """Get total number of floats"""
        try:
            result = self.client.table('argo_floats').select('wmo_id', count='exact').execute()
            return result.count if hasattr(result, 'count') else len(result.data)
        except Exception as e:
            print(f"❌ Error getting float count: {str(e)}")
            return 0
    
    def get_profile_count(self) -> int:
        """Get total number of profiles"""
        try:
            result = self.client.table('argo_profiles').select('profile_id', count='exact').execute()
            return result.count if hasattr(result, 'count') else len(result.data)
        except Exception as e:
            print(f"❌ Error getting profile count: {str(e)}")
            return 0
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            float_count = self.get_float_count()
            profile_count = self.get_profile_count()
            
            # Get BGC float count
            bgc_result = self.client.table('argo_floats').select('wmo_id', count='exact').eq('float_category', 'BGC').execute()
            bgc_count = bgc_result.count if hasattr(bgc_result, 'count') else len(bgc_result.data)
            
            # Get Core float count
            core_count = float_count - bgc_count
            
            return {
                "total_floats": float_count,
                "core_floats": core_count,
                "bgc_floats": bgc_count,
                "total_profiles": profile_count,
                "avg_profiles_per_float": profile_count / float_count if float_count > 0 else 0
            }
        except Exception as e:
            print(f"❌ Error getting database stats: {str(e)}")
            return {
                "error": str(e),
                "total_floats": 0,
                "total_profiles": 0
            }
    
    def test_query_performance(self, sql_query: str) -> Dict[str, Any]:
        """Test query performance"""
        import time
        
        start_time = time.time()
        try:
            results = self.execute_query(sql_query)
            execution_time = time.time() - start_time
            
            return {
                "success": True,
                "execution_time_seconds": execution_time,
                "rows_returned": len(results),
                "query": sql_query[:100] + "..." if len(sql_query) > 100 else sql_query
            }
        except Exception as e:
            execution_time = time.time() - start_time
            return {
                "success": False,
                "execution_time_seconds": execution_time,
                "error": str(e),
                "query": sql_query[:100] + "..." if len(sql_query) > 100 else sql_query
            }
    
    def get_sample_data(self, table: str = 'argo_profiles', limit: int = 5) -> List[Dict[str, Any]]:
        """Get sample data from a table"""
        try:
            if table == 'argo_profiles':
                result = self.client.table('argo_profiles').select('*').limit(limit).execute()
            elif table == 'argo_floats':
                result = self.client.table('argo_floats').select('*').limit(limit).execute()
            else:
                return []
            
            return result.data if result.data else []
            
        except Exception as e:
            print(f"❌ Error getting sample data: {str(e)}")
            return []