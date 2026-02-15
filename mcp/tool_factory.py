"""Factory for creating MCP tools with dependency injection"""
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from database.supabase_client import SupabaseClient
from core.data_processor import ArgoDataProcessor
from config.settings import Config
from .tool_registry import ToolRegistry, ToolDefinition

class MCPToolFactory:
    """Factory to create MCP tools with shared dependencies"""
    
    def __init__(self, supabase_client: SupabaseClient, data_processor: ArgoDataProcessor):
        self.db_client = supabase_client
        self.data_processor = data_processor
        self.config = Config()
        self.registry = ToolRegistry()
        self._initialize_tools()
    
    def _initialize_tools(self):
        """Initialize all tools with shared dependencies"""
        
        # 1. Spatial Search Tool
        self.registry.register_tool(ToolDefinition(
            name="find_nearest_floats",
            description="Find nearest ARGO floats to a geographic location using spatial search",
            parameters={
                "type": "object",
                "properties": {
                    "latitude": {"type": "number", "description": "Query latitude"},
                    "longitude": {"type": "number", "description": "Query longitude"},
                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 10},
                    "max_distance_km": {"type": "number", "description": "Maximum search radius in km", "default": 500}
                },
                "required": ["latitude", "longitude"]
            },
            execute=self.execute_nearest_floats,
            category="spatial"
        ))
        
        # 2. Regional Statistics Tools
        self.registry.register_tool(ToolDefinition(
            name="get_regional_stats",
            description="Get statistical summary for a geographic region",
            parameters={
                "type": "object",
                "properties": {
                    "region_name": {
                        "type": "string",
                        "description": "Predefined region name",
                        "enum": list(self.config.REGIONS.keys())
                    },
                    "parameter": {
                        "type": "string",
                        "description": "Parameter to analyze",
                        "enum": ["temperature", "salinity", "oxygen", "chlorophyll", "nitrate"]
                    },
                    "start_date": {"type": "string", "description": "Start date (ISO format)"},
                    "end_date": {"type": "string", "description": "End date (ISO format)"}
                },
                "required": ["region_name", "parameter"]
            },
            execute=self.execute_regional_stats,
            category="statistical"
        ))
        
        # 3. Comparison Tools
        self.registry.register_tool(ToolDefinition(
            name="compare_profiles",
            description="Compare parameters across multiple floats",
            parameters={
                "type": "object",
                "properties": {
                    "wmo_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of float WMO IDs to compare"
                    },
                    "parameter": {
                        "type": "string",
                        "description": "Parameter to compare",
                        "enum": ["temperature", "salinity", "oxygen", "chlorophyll"]
                    }
                },
                "required": ["wmo_ids", "parameter"]
            },
            execute=self.execute_comparison,
            category="comparison"
        ))
        
        # 4. Float Trajectory Tools
        self.registry.register_tool(ToolDefinition(
            name="get_float_trajectory",
            description="Get trajectory path of a specific float",
            parameters={
                "type": "object",
                "properties": {
                    "wmo_id": {"type": "integer", "description": "Float WMO ID"},
                    "days_back": {"type": "integer", "description": "Number of days to look back", "default": 90}
                },
                "required": ["wmo_id"]
            },
            execute=self.execute_trajectory,
            category="trajectory"
        ))
        
        # 5. Execute Safe SQL Tools
        self.registry.register_tool(ToolDefinition(
            name="execute_validated_query",
            description="Execute validated SQL query with safety checks",
            parameters={
                "type": "object",
                "properties": {
                    "sql_query": {"type": "string", "description": "SQL query to execute"},
                    "query_type": {
                        "type": "string",
                        "description": "Type of query",
                        "enum": ["geographic", "temporal", "statistical", "profile", "comparative"]
                    },
                    "max_results": {"type": "integer", "description": "Maximum results", "default": 100}
                },
                "required": ["sql_query", "query_type"]
            },
            execute=self.execute_validated_query,
            category="query"
        ))
    
    async def execute_nearest_floats(self, latitude: float, longitude: float, 
                                    limit: int = 10, max_distance_km: float = 500) -> Dict:
        """Execute nearest floats RPC function"""
        try:
            result = self.db_client.client.rpc('find_nearest_floats', {
                'query_lat': latitude,
                'query_lon': longitude,
                'limit_count': limit,
                'max_distance_km': max_distance_km
            }).execute()
            
            data = result.data if result.data else []
            
            return {
                'success': True,
                'tool_name': 'find_nearest_floats',
                'floats': data,
                'count': len(data),
                'query_location': {'lat': latitude, 'lon': longitude},
                'search_radius_km': max_distance_km
            }
        except Exception as e:
            return {
                'success': False,
                'tool_name': 'find_nearest_floats',
                'error': str(e)
            }
    
    async def execute_regional_stats(self, region_name: str, parameter: str = 'temperature',
                                     start_date: str = None, end_date: str = None) -> Dict:
        """Execute regional statistics RPC"""
        if region_name not in self.config.REGIONS:
            return {
                'success': False,
                'tool_name': 'get_regional_stats',
                'error': f'Unknown region: {region_name}'
            }
        
        bounds = self.config.REGIONS[region_name]
        
        try:
            # Format dates if provided
            if not start_date:
                start_date = (datetime.now() - timedelta(days=90)).isoformat()
            
            # Debug print
            print(f"Calling RPC with: region={region_name}, param={parameter}, dates={start_date} to {end_date}")
            
            result = self.db_client.client.rpc('get_regional_statistics', {
                'lat_min': bounds['lat_min'],
                'lat_max': bounds['lat_max'],
                'lon_min': bounds['lon_min'],
                'lon_max': bounds['lon_max'],
                'start_date': start_date,
                'end_date': end_date,
                'param_name': parameter  # Make sure this matches RPC function parameter name
            }).execute()
            
            print(f"RPC result: {result.data}")
            
            return {
                'success': True,
                'tool_name': 'get_regional_stats',
                'region': region_name,
                'statistics': result.data if result.data else {},
                'parameter': parameter,
                'date_range': {'start': start_date, 'end': end_date}
            }
        except Exception as e:
            print(f"RPC Error: {str(e)}")  # Add this for debugging
            return {
                'success': False,
                'tool_name': 'get_regional_stats',
                'error': str(e)
            }
    
    async def execute_comparison(self, wmo_ids: list, parameter: str = 'temperature') -> Dict:
        """Execute profile comparison"""
        try:
            result = self.db_client.client.rpc('compare_profile_parameters', {
                'wmo_ids': wmo_ids,
                'param_name': parameter
            }).execute()
            
            data = result.data if result.data else []
            
            # Process comparison data
            comparison_result = self.data_processor._create_comparison_data(data)
            
            return {
                'success': True,
                'tool_name': 'compare_profiles',
                'profiles': data,
                'comparison': comparison_result,
                'parameter': parameter,
                'float_count': len(wmo_ids)
            }
        except Exception as e:
            return {
                'success': False,
                'tool_name': 'compare_profiles',
                'error': str(e)
            }
    
    async def execute_trajectory(self, wmo_id: int, days_back: int = 90) -> Dict:
        """Get float trajectory"""
        try:
            result = self.db_client.client.rpc('get_float_trajectory', {
                'float_wmo': wmo_id,
                'days_back': days_back
            }).execute()
            
            trajectory_data = result.data if result.data else []
            
            # Debug print
            print(f"Trajectory RPC returned: {len(trajectory_data) if isinstance(trajectory_data, list) else 'non-list'} points")
            if trajectory_data and len(trajectory_data) > 0:
                print(f"First point: {trajectory_data[0]}")
            
            return {
                'success': True,
                'tool_name': 'get_float_trajectory',
                'wmo_id': wmo_id,
                'trajectory': trajectory_data,
                'point_count': len(trajectory_data) if isinstance(trajectory_data, list) else 0,
                'days_back': days_back
            }
        except Exception as e:
            return {
                'success': False,
                'tool_name': 'get_float_trajectory',
                'error': str(e)
            }
    
    async def execute_validated_query(self, sql_query: str, query_type: str, 
                                     max_results: int = 100) -> Dict:
        """Execute validated SQL query"""
        try:
            # Use the safe SQL RPC function
            result = self.db_client.client.rpc('execute_safe_sql', {
                'query_text': sql_query + f' LIMIT {max_results}'
            }).execute()
            
            if result.data and isinstance(result.data, dict) and 'error' in result.data:
                return {
                    'success': False,
                    'tool_name': 'execute_validated_query',
                    'error': result.data['error']
                }
            
            data = result.data if result.data else []
            
            return {
                'success': True,
                'tool_name': 'execute_validated_query',
                'results': data,
                'count': len(data),
                'query_type': query_type,
                'sql_query': sql_query
            }
        except Exception as e:
            return {
                'success': False,
                'tool_name': 'execute_validated_query',
                'error': str(e)
            }
    
    def get_tool_registry(self) -> ToolRegistry:
        """Get the tool registry"""
        return self.registry