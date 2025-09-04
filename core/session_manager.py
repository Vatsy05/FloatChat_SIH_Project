"""
Session Manager for handling conversation context and memory
"""
import uuid
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from config.settings import Config

class SessionManager:
    def __init__(self):
        self.config = Config()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def create_session(self, user_id: Optional[str] = None) -> str:
        """Create a new session and return session ID"""
        session_id = str(uuid.uuid4())
        
        self.sessions[session_id] = {
            "user_id": user_id,
            "created_at": datetime.now(),
            "last_activity": datetime.now(),
            "query_history": [],
            "context_summary": "",
            "current_focus": {
                "region": None,
                "timeframe": None,
                "float_type": None,
                "parameters": []
            },
            "preferences": {
                "visualization_types": [],
                "export_formats": [],
                "data_quality_level": "high"  # high, medium, low
            },
            "cache": {}  # For caching frequently used data
        }
        
        print(f"✅ Created new session: {session_id}")
        self._cleanup_old_sessions()
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        if session_id in self.sessions:
            self.sessions[session_id]["last_activity"] = datetime.now()
            return self.sessions[session_id]
        return None
    
    def add_query_to_history(self, session_id: str, user_query: str, sql_query: str, 
                           query_metadata: Dict[str, Any], results_summary: str) -> bool:
        """Add a query to session history"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        query_entry = {
            "timestamp": datetime.now(),
            "user_query": user_query,
            "sql_query": sql_query,
            "query_metadata": query_metadata,
            "results_summary": results_summary,
            "parameters_detected": query_metadata.get("parameters_detected", {}),
            "query_type": query_metadata.get("query_type", "unknown")
        }
        
        session["query_history"].append(query_entry)
        
        # Update current focus based on the latest query
        self._update_current_focus(session, query_metadata)
        
        # Limit history size
        if len(session["query_history"]) > self.config.MAX_CONTEXT_LENGTH:
            # Keep most recent queries and compress older ones
            session["query_history"] = self._compress_old_history(session["query_history"])
        
        # Update context summary
        self._update_context_summary(session)
        
        return True
    
    def get_context_for_query(self, session_id: str, current_query: str) -> str:
        """Generate context string for current query based on session history"""
        session = self.get_session(session_id)
        if not session or not session["query_history"]:
            return ""
        
        context_parts = []
        
        # Add session summary
        if session["context_summary"]:
            context_parts.append(f"Session Summary: {session['context_summary']}")
        
        # Add current focus
        focus = session["current_focus"]
        focus_parts = []
        if focus["region"]:
            focus_parts.append(f"region: {focus['region']}")
        if focus["timeframe"]:
            focus_parts.append(f"timeframe: {focus['timeframe']}")
        if focus["float_type"]:
            focus_parts.append(f"float type: {focus['float_type']}")
        if focus["parameters"]:
            focus_parts.append(f"parameters: {', '.join(focus['parameters'])}")
        
        if focus_parts:
            context_parts.append(f"Current Focus: {', '.join(focus_parts)}")
        
        # Add recent queries (last 3)
        recent_queries = session["query_history"][-3:]
        if recent_queries:
            context_parts.append("Recent Queries:")
            for i, query in enumerate(recent_queries, 1):
                context_parts.append(
                    f"{i}. User: '{query['user_query']}' -> "
                    f"Type: {query['query_type']}, "
                    f"Results: {query['results_summary']}"
                )
        
        # Detect query continuation patterns
        continuation_context = self._detect_continuation_patterns(session, current_query)
        if continuation_context:
            context_parts.append(f"Query Continuation: {continuation_context}")
        
        return "\n".join(context_parts)
    
    def update_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        """Update user preferences"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session["preferences"].update(preferences)
        return True
    
    def cache_data(self, session_id: str, cache_key: str, data: Any) -> bool:
        """Cache data for session"""
        session = self.get_session(session_id)
        if not session:
            return False
        
        session["cache"][cache_key] = {
            "data": data,
            "timestamp": datetime.now()
        }
        
        # Limit cache size
        if len(session["cache"]) > 10:
            # Remove oldest cached items
            oldest_key = min(session["cache"].keys(), 
                           key=lambda k: session["cache"][k]["timestamp"])
            del session["cache"][oldest_key]
        
        return True
    
    def get_cached_data(self, session_id: str, cache_key: str, max_age_minutes: int = 30) -> Optional[Any]:
        """Get cached data if it's still valid"""
        session = self.get_session(session_id)
        if not session or cache_key not in session["cache"]:
            return None
        
        cached_item = session["cache"][cache_key]
        age = datetime.now() - cached_item["timestamp"]
        
        if age.total_seconds() / 60 > max_age_minutes:
            # Cache expired
            del session["cache"][cache_key]
            return None
        
        return cached_item["data"]
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """Get session statistics"""
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}
        
        query_types = {}
        for query in session["query_history"]:
            query_type = query.get("query_type", "unknown")
            query_types[query_type] = query_types.get(query_type, 0) + 1
        
        return {
            "session_id": session_id,
            "created_at": session["created_at"].isoformat(),
            "last_activity": session["last_activity"].isoformat(),
            "total_queries": len(session["query_history"]),
            "query_types": query_types,
            "current_focus": session["current_focus"],
            "cached_items": len(session["cache"]),
            "session_age_minutes": (datetime.now() - session["created_at"]).total_seconds() / 60
        }
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            print(f"🗑️ Deleted session: {session_id}")
            return True
        return False
    
    def _update_current_focus(self, session: Dict[str, Any], query_metadata: Dict[str, Any]):
        """Update current session focus based on query metadata"""
        params_detected = query_metadata.get("parameters_detected", {})
        
        # Update region if specified
        if params_detected.get("region"):
            session["current_focus"]["region"] = params_detected["region"]
        
        # Update timeframe if specified
        if params_detected.get("timeframe"):
            session["current_focus"]["timeframe"] = params_detected["timeframe"]
        
        # Update float type if specified
        if params_detected.get("data_type"):
            session["current_focus"]["float_type"] = params_detected["data_type"]
        
        # Update parameters (merge with existing)
        if params_detected.get("parameters"):
            current_params = set(session["current_focus"]["parameters"])
            new_params = set(params_detected["parameters"])
            session["current_focus"]["parameters"] = list(current_params.union(new_params))
    
    def _update_context_summary(self, session: Dict[str, Any]):
        """Update context summary based on recent queries"""
        if len(session["query_history"]) < 2:
            return
        
        recent_queries = session["query_history"][-5:]  # Last 5 queries
        
        # Extract common themes
        query_types = [q["query_type"] for q in recent_queries]
        regions = [q["parameters_detected"].get("region") for q in recent_queries if q["parameters_detected"].get("region")]
        timeframes = [q["parameters_detected"].get("timeframe") for q in recent_queries if q["parameters_detected"].get("timeframe")]
        
        summary_parts = []
        
        # Most common query type
        if query_types:
            most_common_type = max(set(query_types), key=query_types.count)
            summary_parts.append(f"Primarily doing {most_common_type} analysis")
        
        # Most common region
        if regions:
            most_common_region = max(set(regions), key=regions.count)
            summary_parts.append(f"Focused on {most_common_region}")
        
        # Most common timeframe
        if timeframes:
            most_common_timeframe = max(set(timeframes), key=timeframes.count)
            summary_parts.append(f"Looking at {most_common_timeframe}")
        
        session["context_summary"] = "; ".join(summary_parts)
    
    def _detect_continuation_patterns(self, session: Dict[str, Any], current_query: str) -> Optional[str]:
        """Detect if current query is a continuation of previous queries"""
        if not session["query_history"]:
            return None
        
        current_query_lower = current_query.lower()
        last_query = session["query_history"][-1]
        
        # Check for continuation keywords
        continuation_keywords = [
            "now show", "also show", "what about", "compare with", "and also",
            "show me more", "continue with", "next", "also", "additionally"
        ]
        
        if any(keyword in current_query_lower for keyword in continuation_keywords):
            return f"Continuing from previous query about {last_query['query_type']} analysis"
        
        # Check for implicit continuation (same parameters without explicit mention)
        last_params = last_query.get("parameters_detected", {})
        if (not any(region in current_query_lower for region in ["arabian sea", "bay of bengal", "equator"]) and
            last_params.get("region")):
            return f"Assuming same region as previous query: {last_params['region']}"
        
        return None
    
    def _compress_old_history(self, query_history: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Compress old query history to save memory"""
        if len(query_history) <= self.config.MAX_CONTEXT_LENGTH:
            return query_history
        
        # Keep most recent queries as-is
        recent_queries = query_history[-self.config.MAX_CONTEXT_LENGTH//2:]
        
        # Compress older queries into summaries
        older_queries = query_history[:-self.config.MAX_CONTEXT_LENGTH//2]
        
        # Create summary of older queries
        if older_queries:
            compressed_summary = {
                "timestamp": older_queries[0]["timestamp"],
                "user_query": f"[COMPRESSED: {len(older_queries)} earlier queries]",
                "sql_query": "[COMPRESSED]",
                "query_metadata": {"query_type": "compressed"},
                "results_summary": f"Summary of {len(older_queries)} earlier queries",
                "parameters_detected": {},
                "query_type": "compressed"
            }
            return [compressed_summary] + recent_queries
        
        return recent_queries
    
    def _cleanup_old_sessions(self):
        """Clean up expired sessions"""
        current_time = time.time()
        
        # Only run cleanup periodically
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        self.last_cleanup = current_time
        
        expired_sessions = []
        timeout_threshold = datetime.now() - timedelta(minutes=self.config.SESSION_TIMEOUT_MINUTES)
        
        for session_id, session_data in self.sessions.items():
            if session_data["last_activity"] < timeout_threshold:
                expired_sessions.append(session_id)
        
        # Remove expired sessions
        for session_id in expired_sessions:
            del self.sessions[session_id]
            print(f"🧹 Cleaned up expired session: {session_id}")
        
        if expired_sessions:
            print(f"✅ Cleaned up {len(expired_sessions)} expired sessions")
    
    def get_all_sessions_stats(self) -> Dict[str, Any]:
        """Get statistics for all sessions"""
        active_sessions = len(self.sessions)
        total_queries = sum(len(session["query_history"]) for session in self.sessions.values())
        
        return {
            "active_sessions": active_sessions,
            "total_queries": total_queries,
            "avg_queries_per_session": total_queries / active_sessions if active_sessions > 0 else 0,
            "sessions": {sid: self.get_session_stats(sid) for sid in self.sessions.keys()}
        }