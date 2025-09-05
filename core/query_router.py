"""Query Router - Determines whether to use MCP or direct SQL pipeline"""
from typing import Dict, Any
from core.rag_system import ArgoRAGSystem
from core.llm_manager import GroqLLMManager
from mcp.mcp_client import ArgoMCPClient
from core.sql_generator import ArgoSQLGenerator
from database.supabase_client import SupabaseClient
from core.data_processor import ArgoDataProcessor

class QueryRouter:
    """Routes queries to appropriate processing pipeline"""
    
    def __init__(self):
        # Initialize components
        self.rag_system = ArgoRAGSystem()
        self.llm_manager = GroqLLMManager()
        self.db_client = SupabaseClient()
        self.data_processor = ArgoDataProcessor()
        self.sql_generator = ArgoSQLGenerator(self.rag_system, self.llm_manager)
        
        # Initialize MCP client with dependencies
        self.mcp_client = ArgoMCPClient(
            self.llm_manager,
            self.rag_system,
            self.db_client,
            self.data_processor
        )
    
    async def route_query(self, user_query: str, session_context: str = "") -> Dict[str, Any]:
        """Route query to appropriate pipeline"""
        
        # Determine query complexity
        complexity = self._analyze_query_complexity(user_query)
        
        if complexity == "complex":
            print("🔄 Routing to MCP pipeline for complex query")
            return await self.mcp_client.process_query_with_tools(user_query, session_context)
        else:
            print("⚡ Using direct SQL pipeline for simple query")
            return self._process_direct_sql(user_query, session_context)
    
    def _analyze_query_complexity(self, query: str) -> str:
        """Analyze query to determine complexity"""
        query_lower = query.lower()
        
        # Indicators for MCP routing
        mcp_indicators = [
            # Spatial operations
            'nearest', 'closest', 'nearby', 'around', 'within',
            # Comparisons
            'compare', 'versus', 'vs', 'difference', 'between',
            # Statistical analysis
            'average', 'mean', 'statistics', 'summary', 'trend', 'analyze',
            # Multi-region
            'arabian sea and bay of bengal',
            'multiple regions',
            # Complex BGC
            'bgc comparison', 'oxygen levels across',
            # Trajectory
            'trajectory', 'path', 'route'
        ]
        
        # Check for MCP indicators
        for indicator in mcp_indicators:
            if indicator in query_lower:
                return "complex"
        
        # Check for multiple regions
        regions_mentioned = sum([
            'arabian' in query_lower,
            'bengal' in query_lower,
            'equator' in query_lower
        ])
        if regions_mentioned > 1:
            return "complex"
        
        return "simple"
    
    def _process_direct_sql(self, user_query: str, session_context: str) -> Dict[str, Any]:
        """Process query using direct SQL pipeline"""
        try:
            # Generate SQL
            sql_response = self.sql_generator.generate_query(user_query, session_context)
            
            if not sql_response.get("success"):
                return sql_response
            
            # Execute query
            sql_query = sql_response["sql_query"]
            raw_results = self.db_client.execute_query(sql_query)
            
            # Pass ALL metadata to data processor, including original query
            sql_response["query_text"] = user_query  # Add this!
            
            # Process results
            processed_results = self.data_processor.process_query_results(
                raw_results, sql_response
            )
            
            return {
                "success": True,
                "execution_path": "direct_sql",
                "data": processed_results.get("data"),
                "sql_query": sql_query,
                "explanation": sql_response.get("explanation"),
                "confidence": sql_response.get("confidence")
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_path": "direct_sql"
            }
    
    def get_components(self) -> Dict[str, Any]:
        """Get all router components for external use"""
        return {
            "rag_system": self.rag_system,
            "llm_manager": self.llm_manager,
            "mcp_client": self.mcp_client,
            "sql_generator": self.sql_generator,
            "db_client": self.db_client,
            "data_processor": self.data_processor
        }