"""
FastAPI server for ARGO FloatChat AI
Provides REST API endpoints for Next.js frontend integration
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import time
from typing import Dict, List, Any, Optional

# Import your core modules
from config.settings import Config
try:
    from core.rag_system import ArgoRAGSystem
except ImportError:
    from core.rag_system_simple import ArgoRAGSystemSimple as ArgoRAGSystem
from core.sql_generator import ArgoSQLGenerator
from core.data_processor import ArgoDataProcessor
from core.session_manager import SessionManager
from database.supabase_client import SupabaseClient

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

# Initialize system components
try:
    config = Config()
    config.validate_config()
    
    rag_system = ArgoRAGSystem()
    sql_generator = ArgoSQLGenerator()
    data_processor = ArgoDataProcessor()
    session_manager = SessionManager()
    database_client = SupabaseClient()
    
    print("✅ API server components initialized successfully")
except Exception as e:
    print(f"❌ Failed to initialize components: {e}")

# Pydantic models for request/response
class QueryRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = {}

class QueryResponse(BaseModel):
    success: bool
    session_id: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float
    sql_query: Optional[str] = None

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
                "llm_manager": {"status": "ready", "stats": llm_stats}
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
    """Main query processing endpoint"""
    start_time = time.time()
    
    try:
        # Create session if needed
        if not request.session_id:
            session_id = session_manager.create_session()
        else:
            session_id = request.session_id
        
        # Get session context
        session_context = session_manager.get_context_for_query(session_id, request.query)
        
        # Generate SQL query
        sql_response = sql_generator.generate_query(request.query, session_context)
        
        if not sql_response.get("success"):
            return QueryResponse(
                success=False,
                session_id=session_id,
                error=sql_response.get("error", "SQL generation failed"),
                execution_time_ms=(time.time() - start_time) * 1000,
                sql_query=sql_response.get("sql_query")
            )
        
        sql_query = sql_response["sql_query"]
        
        # Execute query
        raw_results = database_client.execute_query(sql_query)
        
        # Process results
        processed_results = data_processor.process_query_results(raw_results, sql_response)
        
        execution_time = time.time() - start_time
        processed_results["data"]["execution_stats"]["execution_time_ms"] = execution_time * 1000
        
        # Add to session history
        results_summary = f"Found {len(raw_results)} records"
        session_manager.add_query_to_history(
            session_id, request.query, sql_query, sql_response, results_summary
        )
        
        return QueryResponse(
            success=True,
            session_id=session_id,
            data=processed_results.get("data"),
            execution_time_ms=execution_time * 1000,
            sql_query=sql_query
        )
        
    except Exception as e:
        return QueryResponse(
            success=False,
            session_id=request.session_id or "unknown",
            error=str(e),
            execution_time_ms=(time.time() - start_time) * 1000
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

@app.post("/api/sql/validate")
async def validate_sql(sql_query: str):
    """Validate SQL query"""
    try:
        # Use the validation logic from sql_generator
        validation_result = sql_generator._validate_sql(sql_query)
        return {"success": True, "validation": validation_result}
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)