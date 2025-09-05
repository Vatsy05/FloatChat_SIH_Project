"""MCP Client for orchestrating tool execution"""
import json
import asyncio
from typing import Dict, List, Any, Optional
from core.llm_manager import GroqLLMManager
from core.rag_system import ArgoRAGSystem
from database.supabase_client import SupabaseClient
from core.data_processor import ArgoDataProcessor
from .tool_factory import MCPToolFactory

class ArgoMCPClient:
    """MCP Client for ARGO oceanographic data analysis"""
    
    def __init__(self, llm_manager: GroqLLMManager, rag_system: ArgoRAGSystem,
                 supabase_client: SupabaseClient, data_processor: ArgoDataProcessor):
        """Initialize with injected dependencies"""
        self.llm_manager = llm_manager
        self.rag_system = rag_system
        self.db_client = supabase_client
        self.data_processor = data_processor
        
        # Initialize tool factory
        self.tool_factory = MCPToolFactory(supabase_client, data_processor)
        self.tool_registry = self.tool_factory.get_tool_registry()
        
        print(f"🔧 Initialized MCP Client with {len(self.tool_registry.get_all_tools())} tools")
    
    async def process_query_with_tools(self, user_query: str, session_context: str = "") -> Dict[str, Any]:
        """Process query using MCP tools"""
        try:
            # Step 1: Get context from RAG
            context_chunks = self.rag_system.retrieve_context(user_query, top_k=5)
            
            # Step 2: Analyze query and determine tools
            analysis = await self._analyze_query_for_tools(user_query, context_chunks, session_context)
            
            if not analysis.get("success"):
                return analysis
            
            # Step 3: Execute suggested tools
            tool_results = []
            for tool_call in analysis.get("tool_calls", []):
                result = await self._execute_tool(tool_call)
                tool_results.append(result)
            
            # Step 4: Generate final response
            final_response = await self._synthesize_response(
                user_query, analysis, tool_results, context_chunks
            )
            
            return final_response
            
        except Exception as e:
            return {
                "success": False,
                "error": f"MCP processing error: {str(e)}",
                "execution_path": "mcp"
            }
    
    async def _analyze_query_for_tools(self, user_query: str, context_chunks: List[Dict], 
                                      session_context: str) -> Dict[str, Any]:
        """Analyze query to determine which tools to use"""
        
        # Format tool definitions for LLM
        tool_definitions = self.tool_registry.get_tool_definitions_for_llm()
        context_text = "\n\n".join([chunk['content'] for chunk in context_chunks])
        
        # Create analysis prompt
        analysis_prompt = self._build_tool_analysis_prompt(
            user_query, tool_definitions, context_text, session_context
        )
        
        # Get LLM response
        response = self.llm_manager.generate_tool_analysis(analysis_prompt)
        
        return response
    
    async def _execute_tool(self, tool_call: Dict) -> Dict[str, Any]:
        """Execute a specific tool"""
        tool_name = tool_call.get("name")
        tool_params = tool_call.get("parameters", {})
        
        tool_def = self.tool_registry.get_tool(tool_name)
        if not tool_def:
            return {
                "success": False,
                "tool_name": tool_name,
                "error": f"Unknown tool: {tool_name}"
            }
        
        try:
            # Execute tool function
            result = await tool_def.execute(**tool_params)
            return result
        except Exception as e:
            return {
                "success": False,
                "tool_name": tool_name,
                "error": str(e)
            }
    
    async def _synthesize_response(self, user_query: str, analysis: Dict, 
                                  tool_results: List[Dict], context_chunks: List[Dict]) -> Dict:
        """Synthesize final response from tool results"""
        
        # Extract successful results
        successful_results = [r for r in tool_results if r.get("success")]
        
        if not successful_results:
            return {
                "success": False,
                "error": "All tool executions failed",
                "tool_errors": [r.get("error") for r in tool_results],
                "execution_path": "mcp"
            }
        
        # Process combined data for visualization
        processed_data = self._process_tool_results_for_visualization(
            successful_results, analysis.get("query_type", "general")
        )
        
        # Generate summary text based on results
        summary_text = self._generate_summary_text(successful_results, analysis.get("query_type"))
        
        return {
            "success": True,
            "execution_path": "mcp",
            "data": processed_data,  # Keep the data wrapped
            "summary": summary_text,  # Add summary text
            "tools_used": [r.get("tool_name") for r in successful_results],
            "raw_tool_results": successful_results,
            "sql_query": None,  # Remove misleading SQL
            "explanation": analysis.get("explanation"),
            "confidence": analysis.get("confidence", 0.85)
        }

    def _generate_summary_text(self, tool_results: List[Dict], query_type: str) -> str:
        """Generate human-readable summary of results"""
        
        summary_parts = []
        
        for result in tool_results:
            tool_name = result.get("tool_name")
            
            if tool_name == "get_float_trajectory":
                wmo_id = result.get("wmo_id")
                point_count = result.get("point_count", 0)
                trajectory = result.get("trajectory", [])
                
                if trajectory and len(trajectory) > 0:
                    first_date = trajectory[0].get("date", "")[:10] if trajectory[0].get("date") else "unknown"
                    last_date = trajectory[-1].get("date", "")[:10] if trajectory[-1].get("date") else "unknown"
                    
                    summary_parts.append(
                        f"Retrieved trajectory for float {wmo_id} with {point_count} position points "
                        f"spanning from {first_date} to {last_date}."
                    )
                else:
                    summary_parts.append(
                        f"No trajectory data found for float {wmo_id} in the specified time period."
                    )
                
            elif tool_name == "get_regional_stats":
                stats = result.get("statistics", {})
                region = result.get("region", "").replace("_", " ").title()
                param = stats.get("parameter", "").title()
                
                if "surface_values" in stats:
                    values = stats["surface_values"]
                    mean_val = values.get("mean", 0)
                    min_val = values.get("min", 0) 
                    max_val = values.get("max", 0)
                    
                    summary_parts.append(
                        f"The average surface {param.lower()} in {region} over the last 12 months is "
                        f"{mean_val:.2f} PSU, ranging from {min_val:.2f} to {max_val:.2f} PSU. "
                        f"This analysis is based on {stats.get('profile_count', 0)} profiles from "
                        f"{stats.get('float_count', 0)} ARGO floats."
                    )
                
            elif tool_name == "find_nearest_floats":
                floats = result.get("floats", [])
                if floats:
                    summary_parts.append(
                        f"Found {len(floats)} ARGO floats. The nearest float (WMO {floats[0]['wmo_id']}) "
                        f"is {floats[0]['distance_km']:.1f} km away."
                    )
        
        return " ".join(summary_parts) if summary_parts else "Data retrieved successfully."

    def _build_tool_analysis_prompt(self, query: str, tools: List[Dict], 
                                   context: str, session: str) -> Dict:
        """Build prompt for tool analysis"""
        return {
            "query": query,
            "available_tools": tools,
            "domain_context": context,
            "session_context": session,
            "instructions": """Analyze the query and determine:
            1. Which tools are needed to answer this query
            2. In what order they should be executed
            3. What parameters to pass to each tool
            4. Generate a SQL query as backup
            
            Return a JSON with:
            - success: boolean
            - query_type: string
            - tool_calls: array of {name, parameters}
            - sql_query: backup SQL query
            - explanation: string
            - confidence: float
            """
        }
    
    def _process_tool_results_for_visualization(self, tool_results: List[Dict],
                                               query_type: str) -> Dict:
        """Process tool results into visualization format"""
        
        display_components = []
        statistics_data = None
        geospatial_data = None
        trajectory_data = None
        table_data = None
        
        for result in tool_results:
            tool_name = result.get("tool_name")
            
            if tool_name == "get_float_trajectory":
                display_components.append("trajectory")
                display_components.append("map")
                display_components.append("table")
                
                # Extract trajectory data
                trajectory_points = result.get("trajectory", [])
                
                if trajectory_points:
                    trajectory_data = {
                        "wmo_id": result.get("wmo_id"),
                        "path": trajectory_points,
                        "point_count": result.get("point_count", len(trajectory_points)),
                        "days_back": result.get("days_back", 90)
                    }
                    
                    # Also create geospatial data for map
                    geospatial_data = {
                        "type": "trajectory",
                        "trajectories": [{
                            "wmo_id": result.get("wmo_id"),
                            "path": trajectory_points
                        }]
                    }
                    
                    # Create table data
                    table_data = {
                        "columns": ["Date", "Latitude", "Longitude", "Cycle", "Temperature", "Salinity"],
                        "rows": [
                            [
                                point.get("date", "")[:10] if point.get("date") else "",
                                f"{point.get('lat', 0):.3f}",
                                f"{point.get('lon', 0):.3f}",
                                str(point.get("cycle", "")),
                                f"{point.get('temperature', 0):.2f}" if point.get('temperature') else "N/A",
                                f"{point.get('salinity', 0):.2f}" if point.get('salinity') else "N/A"
                            ]
                            for point in trajectory_points[:50]  # Limit for display
                        ]
                    }
                
            elif tool_name == "get_regional_stats":
                display_components.append("statistics")
                display_components.append("table")  # Add table for statistics
                
                region = result.get("region")
                stats = result.get("statistics", {})
                
                if not statistics_data:
                    statistics_data = {"regions": {}}
                
                statistics_data["regions"][region] = stats
                
                # Create table data from statistics
                if stats.get("surface_values"):
                    values = stats["surface_values"]
                    table_data = {
                        "columns": ["Metric", "Value", "Unit"],
                        "rows": [
                            ["Parameter", stats.get("parameter", "").title(), ""],
                            ["Mean", f"{values.get('mean', 0):.2f}", "PSU"],
                            ["Minimum", f"{values.get('min', 0):.2f}", "PSU"],
                            ["Maximum", f"{values.get('max', 0):.2f}", "PSU"],
                            ["Std Deviation", f"{values.get('std_dev', 0):.3f}", "PSU"],
                            ["Profile Count", str(stats.get("profile_count", 0)), "profiles"],
                            ["Float Count", str(stats.get("float_count", 0)), "floats"]
                        ]
                    }
                
            elif tool_name == "find_nearest_floats":
                display_components.append("map")
                display_components.append("table")
                
                floats = result.get("floats", [])
                geospatial_data = {
                    "type": "points",
                    "features": floats,
                    "center": result.get("query_location"),
                    "search_radius": result.get("search_radius_km")
                }
                
                # Create table for nearest floats
                if floats:
                    table_data = {
                        "columns": ["WMO ID", "Distance (km)", "Latitude", "Longitude", "Type"],
                        "rows": [
                            [
                                str(f["wmo_id"]),
                                f"{f['distance_km']:.1f}",
                                f"{f['latitude']:.3f}",
                                f"{f['longitude']:.3f}",
                                f.get("float_category", "Unknown")
                            ]
                            for f in floats[:10]
                        ]
                    }
        
        # Build final response
        response = {
            "query_type": query_type,
            "display_components": list(set(display_components))
        }
        
        # Add non-null data
        if trajectory_data:
            response["trajectory"] = trajectory_data
        if geospatial_data:
            response["geospatial"] = geospatial_data
        if statistics_data:
            response["statistics"] = statistics_data
        if table_data:
            response["table"] = table_data
        
        response["execution_stats"] = {
            "tools_executed": len(tool_results),
            "execution_path": "mcp"
        }
        
        return response