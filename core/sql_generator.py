"""
SQL Generator with validation and template fallbacks
"""
import re
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from core.rag_system_simple import ArgoRAGSystemSimple as ArgoRAGSystem
from core.llm_manager import GroqLLMManager
from config.settings import Config

class ArgoSQLGenerator:
    def __init__(self, rag_system=None, llm_manager=None):
        self.config = Config()
        self.rag_system = rag_system or ArgoRAGSystem()
        self.llm_manager = llm_manager or GroqLLMManager()
        
        # Updated SQL templates with proper fields for visualization
        self.sql_templates = {
            "basic_floats": """
                SELECT wmo_id, latitude, longitude, profile_date, float_category, cycle_number 
                FROM public.argo_profiles 
                WHERE {conditions} 
                LIMIT {limit}
            """,
            "temperature_profiles": """
                SELECT 
                    wmo_id, 
                    cycle_number, 
                    profile_date,
                    latitude,
                    longitude,
                    pressure_dbar, 
                    temperature_celsius,
                    salinity_psu,
                    float_category
                FROM public.argo_profiles 
                WHERE array_length(temperature_celsius, 1) > 0 
                    AND array_length(pressure_dbar, 1) > 0
                    AND {conditions} 
                ORDER BY profile_date DESC
                LIMIT {limit}
            """,
            "salinity_profiles": """
                SELECT 
                    wmo_id, 
                    cycle_number, 
                    profile_date,
                    latitude,
                    longitude,
                    pressure_dbar, 
                    temperature_celsius,
                    salinity_psu,
                    float_category
                FROM public.argo_profiles 
                WHERE array_length(salinity_psu, 1) > 0 
                    AND array_length(pressure_dbar, 1) > 0
                    AND {conditions} 
                ORDER BY profile_date DESC
                LIMIT {limit}
            """,
            "bgc_profiles": """
                SELECT 
                    wmo_id, 
                    cycle_number, 
                    profile_date,
                    latitude,
                    longitude,
                    pressure_dbar,
                    temperature_celsius,
                    salinity_psu,
                    doxy_micromol_per_kg,
                    chla_microgram_per_l,
                    nitrate_micromol_per_kg,
                    float_category
                FROM public.argo_profiles 
                WHERE float_category = 'BGC'
                    AND array_length(pressure_dbar, 1) > 0
                    AND (
                        array_length(chla_microgram_per_l, 1) > 0 
                        OR array_length(nitrate_micromol_per_kg, 1) > 0
                        OR array_length(doxy_micromol_per_kg, 1) > 0
                    )
                    AND {conditions}
                ORDER BY profile_date DESC
                LIMIT {limit}
            """,
            "float_metadata": """
                SELECT f.*, COUNT(p.profile_id) as profile_count 
                FROM public.argo_floats f 
                LEFT JOIN public.argo_profiles p ON f.wmo_id = p.wmo_id 
                WHERE {conditions} 
                GROUP BY f.wmo_id 
                LIMIT {limit}
            """,
            "trajectory": """
                SELECT 
                    wmo_id,
                    cycle_number,
                    profile_date,
                    latitude,
                    longitude,
                    float_category
                FROM public.argo_profiles
                WHERE {conditions}
                ORDER BY wmo_id, profile_date
                LIMIT {limit}
            """
        }
    
    def generate_query(self, user_query: str, session_context: str = "") -> Dict[str, Any]:
        """Generate SQL query from natural language and return in a unified format."""
        intent = self._analyze_query_intent(user_query)
        result_data = {}
        
        try:
            # Step 1: Retrieve relevant context from RAG system
            context_chunks = self._get_relevant_context(user_query, intent)
            
            # Step 2: Check for profile queries and handle specially
            if intent["query_type"] == "profile" or any(word in user_query.lower() for word in ['profile', 'temperature', 'vertical', 'depth']):
                result_data = self._generate_profile_query(intent, user_query)
            else:
                # Step 3: Generate SQL using LLM for non-profile queries
                llm_response = self.llm_manager.generate_sql_query(
                    user_query=user_query,
                    context_chunks=context_chunks,
                    session_context=session_context
                )
                
                if llm_response.get("success"):
                    # Validate generated SQL
                    validation_result = self._validate_sql(llm_response["sql_query"])
                    
                    if validation_result["valid"]:
                        # Enhance SQL for profile queries if needed
                        enhanced_sql = self._enhance_sql_for_profiles(llm_response["sql_query"], intent)
                        llm_response["sql_query"] = enhanced_sql
                        result_data = self._enhance_response_with_viz(llm_response, intent)
                    else:
                        print(f"⚠️ SQL validation failed: {validation_result['error']}")
                        result_data = self._generate_template_fallback(intent, user_query)
                else:
                    print(f"⚠️ LLM generation failed: {llm_response.get('error')}")
                    result_data = self._generate_template_fallback(intent, user_query)
                
        except Exception as e:
            print(f"❌ Error in SQL generation: {str(e)}")
            result_data = {
                "success": False,
                "error": f"SQL generation failed: {str(e)}",
                "sql_query": None,
                "explanation": "An error occurred during query generation.",
                "query_type": intent.get('query_type', 'error'),
                "suggested_visualizations": []
            }

        # Ensure the final output conforms to the required structure
        return {
            "success": result_data.get("success", False),
            "sql_query": result_data.get("sql_query"),
            "query_type": result_data.get("query_type", intent.get("query_type", "basic")),
            "query_text": user_query,
            "suggested_visualizations": result_data.get("suggested_visualizations", []),
            "explanation": result_data.get("explanation", "No explanation available."),
            "confidence": result_data.get("confidence", 0.8)
        }
    
    def _generate_profile_query(self, intent: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Generate specialized query for profile data"""
        conditions = ["1=1"]
        
        # Add region filter
        if intent["region"]:
            region_config = self.config.REGIONS[intent["region"]]
            conditions.append(
                f"latitude BETWEEN {region_config['lat_min']} AND {region_config['lat_max']} "
                f"AND longitude BETWEEN {region_config['lon_min']} AND {region_config['lon_max']}"
            )
        
        # Add timeframe filter
        if intent["timeframe"]:
            time_condition = self._build_time_condition(intent["timeframe"])
            if time_condition:
                conditions.append(time_condition)
        
        # Determine template based on parameters
        if 'salinity' in intent["parameters"] and 'profile' in user_query.lower():
            template_key = "salinity_profiles"
        elif 'chlorophyll' in intent["parameters"] or 'nitrate' in intent["parameters"]:
            template_key = "bgc_profiles"
        elif intent["float_type"] == "BGC":
            template_key = "bgc_profiles"
        else:
            template_key = "temperature_profiles"
        
        # Build final query
        conditions_str = " AND ".join(conditions)
        sql_query = self.sql_templates[template_key].format(
            conditions=conditions_str,
            limit=100
        )
        
        return {
            "success": True,
            "sql_query": sql_query.strip(),
            "explanation": f"Retrieving {', '.join(intent['parameters'])} profile data",
            "confidence": 0.9,
            "query_type": "profile",
            "parameters_detected": intent,
            "suggested_visualizations": ["profiles", "map", "table"]
        }
    
    def _enhance_sql_for_profiles(self, sql_query: str, intent: Dict[str, Any]) -> str:
        """Enhance SQL query to ensure it includes necessary fields for profile visualization"""
        sql_upper = sql_query.upper()
        
        # Check if this is a profile-related query
        if intent["query_type"] == "profile" or "TEMPERATURE" in sql_upper or "SALINITY" in sql_upper:
            # Check if pressure_dbar is missing
            if "PRESSURE_DBAR" not in sql_upper:
                # Try to add pressure_dbar to SELECT clause
                select_pattern = r'SELECT\s+(.*?)\s+FROM'
                match = re.search(select_pattern, sql_query, re.IGNORECASE | re.DOTALL)
                if match:
                    current_fields = match.group(1)
                    # Add pressure_dbar if not present
                    new_fields = current_fields
                    if "pressure_dbar" not in current_fields.lower():
                        new_fields = current_fields + ", pressure_dbar"
                    if "salinity_psu" not in current_fields.lower() and "salinity" in intent["parameters"]:
                        new_fields = new_fields + ", salinity_psu"
                    
                    sql_query = sql_query[:match.start(1)] + new_fields + sql_query[match.end(1):]
        
        return sql_query
    
    def _analyze_query_intent(self, user_query: str) -> Dict[str, Any]:
        """Analyze user query to extract intent and parameters"""
        query_lower = user_query.lower()
        
        intent = {
            "query_type": "basic",
            "parameters": [],
            "region": None,
            "timeframe": None,
            "float_type": None,
            "statistics": False,
            "comparison": False
        }
        
        # Detect query type - check profile first
        if any(word in query_lower for word in ['profile', 'depth', 'vertical', 'pressure']):
            intent["query_type"] = "profile"
        elif any(word in query_lower for word in ['compare', 'comparison', 'vs', 'versus']):
            intent["query_type"] = "comparative"
            intent["comparison"] = True
        elif any(word in query_lower for word in ['average', 'mean', 'max', 'min', 'count', 'sum']):
            intent["query_type"] = "statistical"
            intent["statistics"] = True
        elif any(word in query_lower for word in ['trajectory', 'path', 'track', 'movement']):
            intent["query_type"] = "trajectory"
        elif any(word in query_lower for word in ['time', 'temporal', 'evolution', 'trend']):
            intent["query_type"] = "time_series"
        elif any(word in query_lower for word in ['map', 'location', 'position', 'geographic', 'nearest']):
            intent["query_type"] = "geographic"
        
        # Detect parameters
        parameter_mapping = {
            'temperature': ['temperature', 'temp', 'sst', 'sea surface temperature'],
            'salinity': ['salinity', 'sal', 'sss', 'sea surface salinity'],
            'pressure': ['pressure', 'depth', 'vertical'],
            'oxygen': ['oxygen', 'doxy', 'dissolved oxygen'],
            'chlorophyll': ['chlorophyll', 'chla', 'phytoplankton'],
            'nitrate': ['nitrate', 'no3']
        }
        
        for param, keywords in parameter_mapping.items():
            if any(keyword in query_lower for keyword in keywords):
                intent["parameters"].append(param)
        
        # If temperature is mentioned, assume profile query needs pressure too
        if 'temperature' in intent["parameters"] and 'pressure' not in intent["parameters"]:
            intent["parameters"].append('pressure')
        
        # Detect regions
        if 'arabian sea' in query_lower or 'arabian' in query_lower:
            intent["region"] = "arabian_sea"
        elif 'bay of bengal' in query_lower or 'bengal' in query_lower:
            intent["region"] = "bay_of_bengal"
        elif 'equator' in query_lower:
            intent["region"] = "equator"
        
        # Detect float type
        if 'bgc' in query_lower or 'bio-geo' in query_lower or 'biogeochemical' in query_lower:
            intent["float_type"] = "BGC"
        elif 'core' in query_lower or 'standard' in query_lower:
            intent["float_type"] = "Core"
        
        # Detect timeframe
        if any(word in query_lower for word in ['last month', 'past month']):
            intent["timeframe"] = "last_month"
        elif any(word in query_lower for word in ['last 6 months', 'past 6 months']):
            intent["timeframe"] = "last_6_months"
        elif any(word in query_lower for word in ['last year', 'past year']):
            intent["timeframe"] = "last_year"
        elif 'recent' in query_lower:
            intent["timeframe"] = "last_month"
        
        return intent
    
    def _get_relevant_context(self, user_query: str, intent: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get relevant context chunks from RAG system"""
        context_chunks = []
        
        # Get general context
        general_context = self.rag_system.retrieve_context(user_query, top_k=3)
        context_chunks.extend(general_context)
        
        # Get schema-specific context
        schema_context = self.rag_system.search_by_category(user_query, "schema", top_k=2)
        context_chunks.extend(schema_context)
        
        # Get region-specific context if region detected
        if intent["region"]:
            geo_context = self.rag_system.search_by_category(f"{intent['region']} region", "geography", top_k=1)
            context_chunks.extend(geo_context)
        
        # Get BGC-specific context if BGC parameters detected
        if intent["float_type"] == "BGC" or any(p in intent["parameters"] for p in ['oxygen', 'chlorophyll', 'nitrate']):
            bgc_context = self.rag_system.search_by_category("BGC parameters", "bgc", top_k=2)
            context_chunks.extend(bgc_context)
        
        # Get example queries for similar query types
        example_context = self.rag_system.search_by_category(intent["query_type"], "examples", top_k=1)
        context_chunks.extend(example_context)
        
        # Remove duplicates
        seen = set()
        unique_chunks = []
        for chunk in context_chunks:
            chunk_id = chunk.get('content', '')[:100]
            if chunk_id not in seen:
                seen.add(chunk_id)
                unique_chunks.append(chunk)
        
        return unique_chunks[:8]
    
    def _validate_sql(self, sql_query: str) -> Dict[str, Any]:
        """Validate generated SQL query"""
        try:
            if not sql_query or not isinstance(sql_query, str):
                return {"valid": False, "error": "Empty or invalid SQL query"}
            
            sql_upper = sql_query.upper()
            
            # Check for required elements
            if "SELECT" not in sql_upper:
                return {"valid": False, "error": "Missing SELECT statement"}
            
            if "FROM" not in sql_upper:
                return {"valid": False, "error": "Missing FROM clause"}
            
            # Check for dangerous operations
            dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "ALTER", "CREATE", "INSERT", "UPDATE"]
            if any(keyword in sql_upper for keyword in dangerous_keywords):
                return {"valid": False, "error": "Query contains dangerous operations"}
            
            # Check for proper table references
            valid_tables = ["public.argo_floats", "public.argo_profiles", "argo_floats", "argo_profiles"]
            if not any(table in sql_query for table in valid_tables):
                return {"valid": False, "error": "Query doesn't reference valid tables"}
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}
    
    def _generate_template_fallback(self, intent: Dict[str, Any], user_query: str) -> Dict[str, Any]:
        """Generate SQL using template fallback"""
        try:
            # Determine appropriate template
            template_key = "basic_floats"
            
            if intent["query_type"] == "profile" or "temperature" in intent["parameters"]:
                template_key = "temperature_profiles"
            elif intent["query_type"] == "trajectory":
                template_key = "trajectory"
            elif intent["float_type"] == "BGC" or any(p in intent["parameters"] for p in ['oxygen', 'chlorophyll', 'nitrate']):
                template_key = "bgc_data"
            
            # Build conditions
            conditions = ["1=1"]
            
            # Add region filter
            if intent["region"]:
                region_config = self.config.REGIONS[intent["region"]]
                conditions.append(
                    f"latitude BETWEEN {region_config['lat_min']} AND {region_config['lat_max']} "
                    f"AND longitude BETWEEN {region_config['lon_min']} AND {region_config['lon_max']}"
                )
            
            # Add float type filter
            if intent["float_type"]:
                conditions.append(f"float_category = '{intent['float_type']}'")
            
            # Add timeframe filter
            if intent["timeframe"]:
                time_condition = self._build_time_condition(intent["timeframe"])
                if time_condition:
                    conditions.append(time_condition)
            
            # Build final query
            conditions_str = " AND ".join(conditions)
            limit = 100 if not intent["statistics"] else 1000
            
            sql_query = self.sql_templates[template_key].format(
                conditions=conditions_str,
                limit=limit
            )
            
            return {
                "success": True,
                "sql_query": sql_query.strip(),
                "explanation": f"Template-based query for {intent['query_type']} analysis",
                "confidence": 0.7,
                "query_type": intent["query_type"],
                "parameters_detected": intent,
                "validation_checks": ["template_based"],
                "suggested_visualizations": self._get_viz_suggestions(intent)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Template fallback failed: {str(e)}",
                "sql_query": None,
                "explanation": "Template generation failed",
                "confidence": 0
            }
    
    def _build_time_condition(self, timeframe: str) -> Optional[str]:
        """Build SQL time condition"""
        now = datetime.now()
        
        if timeframe == "last_month":
            start_date = now - timedelta(days=30)
            return f"profile_date >= '{start_date.strftime('%Y-%m-%d')}'"
        elif timeframe == "last_6_months":
            start_date = now - timedelta(days=180)
            return f"profile_date >= '{start_date.strftime('%Y-%m-%d')}'"
        elif timeframe == "last_year":
            start_date = now - timedelta(days=365)
            return f"profile_date >= '{start_date.strftime('%Y-%m-%d')}'"
        
        return None
    
    def _enhance_response_with_viz(self, response: Dict[str, Any], intent: Dict[str, Any]) -> Dict[str, Any]:
        """Add visualization suggestions to response"""
        if "suggested_visualizations" not in response or not response["suggested_visualizations"]:
            response["suggested_visualizations"] = self._get_viz_suggestions(intent)
        
        if "query_type" not in response:
            response["query_type"] = intent.get("query_type", "basic")

        return response
    
    def _get_viz_suggestions(self, intent: Dict[str, Any]) -> List[str]:
        """Get visualization suggestions based on query intent"""
        suggestions = []
        
        if intent["query_type"] == "profile":
            suggestions.extend(["profiles", "map", "table"])
        elif intent["query_type"] in ["geographic", "trajectory"]:
            suggestions.extend(["map", "trajectory"])
        elif intent["query_type"] in ["comparative"]:
            suggestions.extend(["profiles", "comparison", "statistics"])
        elif intent["query_type"] == "time_series":
            suggestions.extend(["time_series", "trend_analysis"])
        elif intent["query_type"] == "statistical":
            suggestions.extend(["statistics", "histogram"])
        
        if "temperature" in intent["parameters"] and "salinity" in intent["parameters"]:
            suggestions.append("ts_diagram")
        
        if intent["float_type"] == "BGC":
            suggestions.extend(["bgc_profiles"])
        
        # Default suggestions
        if not suggestions:
            suggestions = ["map", "table"]
        
        return list(set(suggestions))