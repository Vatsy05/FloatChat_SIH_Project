"""
FastAPI server for ARGO FloatChat AI
Provides REST API endpoints for Next.js frontend integration
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import asyncio
import time
from typing import Dict, List, Any, Optional

# Import your core modules
from config.settings import Config
from core.query_router import QueryRouter
from core.session_manager import SessionManager

# Initialize FastAPI app
app = FastAPI(
    title="ARGO FloatChat AI API",
    description="REST API for oceanographic data analysis using natural language",
    version="1.0.0"
)

# Add CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "*"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize system components using QueryRouter
try:
    config = Config()
    config.validate_config()
    
    # Use QueryRouter which handles all component initialization properly
    query_router = QueryRouter()
    
    # Extract components from router for direct access
    rag_system = query_router.rag_system
    sql_generator = query_router.sql_generator
    data_processor = query_router.data_processor
    database_client = query_router.db_client
    mcp_client = query_router.mcp_client
    
    # Session manager is separate
    session_manager = SessionManager()
    
    print("✅ API server components initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize components: {e}")

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    use_mcp: Optional[bool] = None  # Allow client to force MCP usage
    options: Optional[Dict[str, Any]] = {}

class QueryResponse(BaseModel):
    success: bool
    session_id: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float
    sql_query: Optional[str] = None
    execution_path: Optional[str] = None  # "direct_sql" or "mcp"
    tools_used: Optional[List[str]] = None  # For MCP queries

class SessionResponse(BaseModel):
    session_id: str
    created: bool

# API Endpoints

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "ARGO FloatChat AI API",
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time()
    }

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test database connection
        db_stats = database_client.get_database_stats()
        
        # Test RAG system
        rag_stats = rag_system.get_collection_stats()
        
        # Test LLM system
        llm_stats = sql_generator.llm_manager.get_usage_stats()
        
        return {
            "status": "healthy",
            "components": {
                "database": {"status": "connected", "stats": db_stats},
                "rag_system": {"status": "ready", "stats": rag_stats},
                "llm_manager": {"status": "ready", "stats": llm_stats},
                "mcp_tools": {"status": "ready", "tool_count": len(mcp_client.tool_registry.get_all_tools())}
            },
            "timestamp": time.time()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }

@app.post("/api/sessions", response_model=SessionResponse)
async def create_session():
    """Create a new chat session"""
    try:
        session_id = session_manager.create_session()
        return SessionResponse(session_id=session_id, created=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get session information"""
    try:
        session_stats = session_manager.get_session_stats(session_id)
        if "error" in session_stats:
            raise HTTPException(status_code=404, detail="Session not found")
        return session_stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/query", response_model=QueryResponse)
async def process_query(request: QueryRequest):
    """Main query processing endpoint with automatic routing"""
    start_time = time.time()
    
    try:
        # Create session if needed
        if not request.session_id:
            session_id = session_manager.create_session()
        else:
            session_id = request.session_id
        
        # Get session context
        session_context = session_manager.get_context_for_query(session_id, request.query)
        
        # Route query through QueryRouter (handles both simple and complex queries)
        result = await query_router.route_query(request.query, session_context)
        
        execution_time = time.time() - start_time
        
        # Add to session history
        if result.get("success"):
            results_summary = f"Query processed via {result.get('execution_path', 'unknown')}"
            if result.get("tools_used"):
                results_summary += f" using tools: {', '.join(result['tools_used'])}"
            
            session_manager.add_query_to_history(
                session_id, 
                request.query, 
                result.get("sql_query", ""), 
                {"execution_path": result.get("execution_path")},
                results_summary
            )
        
        return QueryResponse(
            success=result.get("success", False),
            session_id=session_id,
            data=result.get("data"),
            error=result.get("error"),
            execution_time_ms=execution_time * 1000,
            sql_query=result.get("sql_query"),
            execution_path=result.get("execution_path"),
            tools_used=result.get("tools_used")
        )
        
    except Exception as e:
        return QueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=str(e),
            execution_time_ms=(time.time() - start_time) * 1000,
            execution_path=None
        )

@app.post("/api/query/mcp")
async def process_mcp_query(request: QueryRequest):
    """Force query processing through MCP pipeline"""
    start_time = time.time()
    
    try:
        # Create session if needed
        if not request.session_id:
            session_id = session_manager.create_session()
        else:
            session_id = request.session_id
        
        # Get session context
        session_context = session_manager.get_context_for_query(session_id, request.query)
        
        # Force MCP processing
        result = await mcp_client.process_query_with_tools(request.query, session_context)
        
        execution_time = time.time() - start_time
        
        return QueryResponse(
            success=result.get("success", False),
            session_id=session_id,
            data=result.get("data"),
            error=result.get("error"),
            execution_time_ms=execution_time * 1000,
            sql_query=result.get("sql_query"),
            execution_path="mcp",
            tools_used=result.get("tools_used")
        )
        
    except Exception as e:
        return QueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=str(e),
            execution_time_ms=(time.time() - start_time) * 1000,
            execution_path="mcp"
        )

@app.post("/api/query/direct")
async def process_direct_query(request: QueryRequest):
    """Force query processing through direct SQL pipeline"""
    start_time = time.time()
    
    try:
        # Create session if needed
        if not request.session_id:
            session_id = session_manager.create_session()
        else:
            session_id = request.session_id
        
        # Get session context
        session_context = session_manager.get_context_for_query(session_id, request.query)
        
        # Force direct SQL processing
        result = query_router._process_direct_sql(request.query, session_context)
        
        execution_time = time.time() - start_time
        
        return QueryResponse(
            success=result.get("success", False),
            session_id=session_id,
            data=result.get("data"),
            error=result.get("error"),
            execution_time_ms=execution_time * 1000,
            sql_query=result.get("sql_query"),
            execution_path="direct_sql"
        )
        
    except Exception as e:
        return QueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=str(e),
            execution_time_ms=(time.time() - start_time) * 1000,
            execution_path="direct_sql"
        )

@app.get("/api/database/stats")
async def get_database_stats():
    """Get database statistics"""
    try:
        stats = database_client.get_database_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/database/sample/{table}")
async def get_sample_data(table: str, limit: int = 5):
    """Get sample data from database table"""
    try:
        if table not in ["argo_floats", "argo_profiles"]:
            raise HTTPException(status_code=400, detail="Invalid table name")
        
        sample_data = database_client.get_sample_data(table, limit)
        return {"success": True, "data": sample_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/regions")
async def get_regions():
    """Get available geographic regions"""
    return {
        "success": True,
        "data": {
            "regions": config.REGIONS,
            "description": "Predefined geographic regions for ARGO data queries"
        }
    }

@app.get("/api/mcp/tools")
async def get_available_tools():
    """Get list of available MCP tools"""
    tools = mcp_client.tool_registry.get_tool_definitions_for_llm()
    return {
        "success": True,
        "data": {
            "tools": tools,
            "count": len(tools)
        }
    }

@app.post("/api/sql/validate")
async def validate_sql(sql_query: str):
    """Validate SQL query"""
    try:
        # Use the validation logic from sql_generator
        validation_result = sql_generator._validate_sql(sql_query)
        return {"success": True, "validation": validation_result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    # Fix for reload warning - use string format for module:app
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=True)