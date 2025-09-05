#llm_manager.py

"""
LLM Manager with Groq API multi-key rotation and rate limiting
"""
import time
import json
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from langchain_groq import ChatGroq
try:
    from langchain.schema import HumanMessage, SystemMessage
except ImportError:
    from langchain_core.messages import HumanMessage, SystemMessage
from config.settings import Config

class GroqLLMManager:
    def __init__(self):  # Fixed: was _init_ before
        self.config = Config()
        self.api_keys = self.config.GROQ_API_KEYS
        self.current_key_index = 0
        self.key_usage = {i: {"requests": 0, "last_reset": datetime.now()} for i in range(len(self.api_keys))}
        self.rate_limit_per_minute = 30  # Adjust based on Groq limits
        
        # Initialize LangChain Groq clients
        self.clients = []
        for api_key in self.api_keys:
            try:
                client = ChatGroq(
                    groq_api_key=api_key,
                    model_name=self.config.GROQ_MODEL,
                    temperature=self.config.GROQ_TEMPERATURE,
                    max_tokens=self.config.GROQ_MAX_TOKENS
                )
                self.clients.append(client)
            except Exception as e:
                print(f"⚠️ Failed to initialize client with key {len(self.clients)+1}: {str(e)}")
        
        if not self.clients:
            raise ValueError("No valid Groq API clients could be initialized")
        
        print(f"✅ Initialized {len(self.clients)} Groq LLM clients")
    
    def _get_next_available_client(self) -> Optional[ChatGroq]:
        """Get the next available client with rate limiting"""
        attempts = 0
        max_attempts = len(self.clients)
        
        while attempts < max_attempts:
            current_time = datetime.now()
            key_stats = self.key_usage[self.current_key_index]
            
            # Reset counter if a minute has passed
            if current_time - key_stats["last_reset"] > timedelta(minutes=1):
                key_stats["requests"] = 0
                key_stats["last_reset"] = current_time
            
            # Check if current key is available
            if key_stats["requests"] < self.rate_limit_per_minute:
                client = self.clients[self.current_key_index]
                key_stats["requests"] += 1
                print(f"🔑 Using API key {self.current_key_index + 1} (Usage: {key_stats['requests']}/{self.rate_limit_per_minute})")
                return client
            
            # Move to next key
            self.current_key_index = (self.current_key_index + 1) % len(self.clients)
            attempts += 1
            
            if attempts < max_attempts:
                print(f"⚠️ Key {self.current_key_index} rate limited, switching to key {self.current_key_index + 1}")
        
        # All keys are rate limited
        print("⏳ All API keys rate limited, waiting...")
        return None
    
    def generate_sql_query(self, user_query: str, context_chunks: List[Dict], session_context: str = "") -> Dict[str, Any]:
        """Generate SQL query using LLM with context"""
        
        # Build system prompt
        system_prompt = self._build_system_prompt(context_chunks, session_context)
        
        # Build user prompt
        user_prompt = self._build_user_prompt(user_query)
        
        # Attempt to get response with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            client = self._get_next_available_client()
            
            if client is None:
                if attempt < max_retries - 1:
                    print("⏳ Waiting 60 seconds for rate limit reset...")
                    time.sleep(60)
                    continue
                else:
                    return {
                        "success": False,
                        "error": "All API keys rate limited. Please try again later.",
                        "sql_query": None,
                        "explanation": "Rate limit exceeded",
                        "confidence": 0
                    }
            
            try:
                # Create messages
                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ]
                
                # Get response
                response = client.invoke(messages)
                
                # Parse JSON response
                response_json = self._parse_response(response.content)
                
                if response_json:
                    response_json["success"] = True
                    return response_json
                else:
                    raise ValueError("Failed to parse JSON response")
                    
            except Exception as e:
                print(f"❌ Attempt {attempt + 1} failed: {str(e)}")
                if attempt < max_retries - 1:
                    # Try next key
                    self.current_key_index = (self.current_key_index + 1) % len(self.clients)
                    time.sleep(2)  # Brief pause before retry
                else:
                    return {
                        "success": False,
                        "error": f"Failed after {max_retries} attempts: {str(e)}",
                        "sql_query": None,
                        "explanation": "LLM generation failed",
                        "confidence": 0
                    }
        
        return {
            "success": False,
            "error": "Unexpected error in SQL generation",
            "sql_query": None,
            "explanation": "Unknown error",
            "confidence": 0
        }

    def _build_system_prompt(self, context_chunks: List[Dict], session_context: str) -> str:
        """Build comprehensive system prompt with embedded database schema"""
        context_text = "\n\n".join([chunk['content'] for chunk in context_chunks])

        system_prompt = f"""You are an expert oceanographic data analyst specializing in ARGO float data. Your task is to convert natural language queries into precise PostgreSQL queries for the ARGO float database.

DATABASE SCHEMA:

public.argo_floats (Static metadata about each unique ARGO float):
- wmo_id: INTEGER (PRIMARY KEY) - Unique 7-digit WMO identifier
- deployment_date: TIMESTAMP - Full timestamp of initial ocean deployment
- float_type: VARCHAR - Hardware model (APEX, PROVOR, NAVIS_A)
- institution: VARCHAR - Managing organization (INCOIS, CSIRO, AOML)
- float_category: VARCHAR(10) - 'Core' or 'BGC'

public.argo_profiles (Scientific measurements from individual dive cycles):
- profile_id: SERIAL (PRIMARY KEY) - Auto-incrementing unique identifier
- wmo_id: INTEGER (FOREIGN KEY -> argo_floats.wmo_id) - Links to float
- cycle_number: INTEGER - Dive number for the float
- profile_date: TIMESTAMP - Date/time of profile measurement
- latitude: REAL - Geographical latitude (decimal degrees, North positive)
- longitude: REAL - Geographical longitude (decimal degrees, East positive)
- float_category: VARCHAR(10) - 'Core' or 'BGC' (CRITICAL FILTER)
- data_mode: CHAR(1) - 'D' (Delayed-Mode, verified) or 'R' (Real-Time)

CORE MEASUREMENT ARRAYS (always check array_length first):
- pressure_dbar: REAL[] - Pressure measurements (decibars)
- temperature_celsius: REAL[] - Temperature measurements (°C)
- salinity_psu: REAL[] - Salinity measurements (PSU)

BGC MEASUREMENT ARRAYS (BGC floats only - empty {{}} for Core floats):
- doxy_micromol_per_kg: REAL[] - Dissolved Oxygen measurements
- chla_microgram_per_l: REAL[] - Chlorophyll-a measurements
- nitrate_micromol_per_kg: REAL[] - Nitrate concentration measurements

QUALITY CONTROL ARRAYS:
- pressure_qc: INTEGER[] - Quality flags for pressure (0=no QC, 1=good, 2=probably good, 3=probably bad, 4=bad, 8=interpolated, 9=missing)
- temperature_qc: INTEGER[] - Quality flags for temperature
- salinity_qc: INTEGER[] - Quality flags for salinity
- doxy_qc: INTEGER[] - Quality flags for oxygen (BGC only)
- chla_qc: INTEGER[] - Quality flags for chlorophyll (BGC only)
- nitrate_qc: INTEGER[] - Quality flags for nitrate (BGC only)

RELATIONSHIPS:
- argo_profiles.wmo_id -> argo_floats.wmo_id (many-to-one)

GEOGRAPHIC REGIONS:
- Arabian Sea: latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75
- Bay of Bengal: latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100
- Near Equator: latitude BETWEEN -5 AND 5
- Indian Ocean: latitude BETWEEN -40 AND 30 AND longitude BETWEEN 20 AND 120

CRITICAL: You must respond ONLY with valid JSON in this exact format:
{{
  "sql_query": "SELECT ... FROM ...",
  "explanation": "Clear explanation of what the query does",
  "confidence": 0.95,
  "query_type": "geographic_temporal|statistical|trajectory|comparative",
  "parameters_detected": {{
    "region": "detected_region_or_null",
    "timeframe": "detected_time_or_null",
    "data_type": "Core|BGC|both",
    "parameters": ["temperature", "salinity", "etc"]
  }},
  "validation_checks": ["array_length", "qc_filters", "date_range"],
  "suggested_visualizations": ["map", "profile", "time_series"]
}}

DOMAIN KNOWLEDGE:
{context_text}

SESSION CONTEXT:
{session_context}

MANDATORY RULES - ALWAYS FOLLOW:
1. ALWAYS include array_length(column_name, 1) > 0 for ANY array column usage
2. Use public.table_name format for all tables
3. BGC parameters ONLY when float_category = 'BGC'
4. Use wmo_id to JOIN argo_profiles with argo_floats
5. Include appropriate LIMIT (default 100, max 1000)
6. Use [1] for surface values, full array for profiles
7. Prefer data_mode = 'D' for verified data
8. Apply regional boundaries for named regions
9. Order results logically (by date, cycle, etc.)
10. Handle QC filtering with flags 1 or 2 for good data

EXAMPLES OF CORRECT SYNTAX:
- Array check: WHERE array_length(temperature_celsius, 1) > 0
- BGC filter: WHERE float_category = 'BGC' AND array_length(doxy_micromol_per_kg, 1) > 0
- Surface value: temperature_celsius[1] AS surface_temperature
- Join: FROM public.argo_profiles p JOIN public.argo_floats f ON p.wmo_id = f.wmo_id

DO NOT include any text outside the JSON structure. Your entire response must be valid JSON."""

        return system_prompt
    
    def _build_user_prompt(self, user_query: str) -> str:
        """Build user prompt"""
        return f"""Convert this oceanographic query to PostgreSQL:
Query: "{user_query}"

Remember: Respond ONLY with the JSON format specified in the system prompt."""
    
    def _parse_response(self, response_content: str) -> Optional[Dict[str, Any]]:
        """Parse LLM response into JSON"""
        try:
            # Clean response - remove any markdown formatting
            content = response_content.strip()
            if content.startswith('```json'):
                content = content.replace('```json', '').replace('```', '').strip()
            elif content.startswith('```'):
                content = content.replace('```', '').strip()
            
            # Parse JSON
            parsed = json.loads(content)
            
            # Validate required fields
            required_fields = ['sql_query', 'explanation', 'confidence']
            for field in required_fields:
                if field not in parsed:
                    print(f"⚠️ Missing required field: {field}")
                    return None
            
            return parsed
            
        except json.JSONDecodeError as e:
            print(f"❌ JSON parsing error: {str(e)}")
            print(f"Raw response: {response_content[:200]}...")
            return None

    def generate_tool_analysis(self, analysis_request: Dict) -> Dict[str, Any]:
        """Generate tool analysis for MCP"""
        
        # More explicit JSON-only prompt
        system_prompt = """You are an ARGO data tool orchestrator. You MUST respond with ONLY valid JSON, no other text.

Available tools:
""" + json.dumps(analysis_request['available_tools'], indent=2) + """

Your response MUST be a valid JSON object with this EXACT structure:
{
    "success": true,
    "query_type": "spatial|statistical|comparative|trajectory|general",
    "tool_calls": [
        {"name": "tool_name", "parameters": {}}
    ],
    "sql_query": "SELECT ... FROM ...",
    "explanation": "Brief explanation",
    "confidence": 0.85
}

CRITICAL RULES:
1. ONLY output valid JSON - no explanatory text before or after
2. For nearest float queries: use find_nearest_floats tool
3. For comparisons between regions: use get_regional_stats tool twice (once per region)
4. For trajectory: use get_float_trajectory tool
5. For general queries: use execute_validated_query tool
6. Always include a backup sql_query"""
        
        user_prompt = f"""Query: {analysis_request['query']}

Remember: Output ONLY the JSON object, nothing else."""
        
        # Try to get JSON response
        from langchain_core.messages import HumanMessage, SystemMessage
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        for attempt in range(3):
            client = self._get_next_available_client()
            if not client:
                continue
                
            try:
                response = client.invoke(messages)  # Use invoke instead of __call__
                content = response.content.strip()
                
                # Try to extract JSON if wrapped in markdown
                if '```json' in content:
                    content = content.split('```json')[1].split('```')[0].strip()
                elif '```' in content:
                    content = content.split('```')[1].split('```')[0].strip()
                
                # Parse JSON
                parsed = json.loads(content)
                
                # Ensure required fields
                if 'success' not in parsed:
                    parsed['success'] = True
                if 'tool_calls' not in parsed:
                    parsed['tool_calls'] = []
                
                return parsed
                
            except json.JSONDecodeError as e:
                print(f"JSON parse error attempt {attempt + 1}: {str(e)}")
                if attempt == 2:  # Last attempt - create fallback response
                    # Analyze query to create structured response
                    query_lower = analysis_request['query'].lower()
                    
                    if 'nearest' in query_lower or 'closest' in query_lower:
                        # Extract lat/lon if possible
                        lat_match = re.search(r'latitude?\s*(\d+\.?\d*)', query_lower)
                        lon_match = re.search(r'longitude?\s*(\d+\.?\d*)', query_lower)
                        
                        return {
                            "success": True,
                            "query_type": "spatial",
                            "tool_calls": [{
                                "name": "find_nearest_floats",
                                "parameters": {
                                    "latitude": float(lat_match.group(1)) if lat_match else 15.0,
                                    "longitude": float(lon_match.group(1)) if lon_match else 70.0,
                                    "limit": 5
                                }
                            }],
                            "sql_query": "SELECT * FROM argo_profiles LIMIT 10",
                            "explanation": "Finding nearest floats using spatial search",
                            "confidence": 0.7
                        }
                    
                    elif 'compare' in query_lower and ('oxygen' in query_lower or 'bgc' in query_lower):
                        return {
                            "success": True,
                            "query_type": "comparative",
                            "tool_calls": [
                                {
                                    "name": "get_regional_stats",
                                    "parameters": {
                                        "region_name": "arabian_sea",
                                        "parameter": "oxygen"
                                    }
                                },
                                {
                                    "name": "get_regional_stats",
                                    "parameters": {
                                        "region_name": "bay_of_bengal",
                                        "parameter": "oxygen"
                                    }
                                }
                            ],
                            "sql_query": "SELECT * FROM argo_profiles WHERE float_category='BGC' LIMIT 100",
                            "explanation": "Comparing oxygen levels between regions",
                            "confidence": 0.75
                        }
                    
                    elif 'trajectory' in query_lower:
                        # Extract WMO ID if possible
                        wmo_match = re.search(r'\d{7}', query_lower)
                        
                        return {
                            "success": True,
                            "query_type": "trajectory",
                            "tool_calls": [{
                                "name": "get_float_trajectory",
                                "parameters": {
                                    "wmo_id": int(wmo_match.group()) if wmo_match else 2902238,
                                    "days_back": 60
                                }
                            }],
                            "sql_query": "SELECT * FROM argo_profiles WHERE wmo_id=2902238 ORDER BY profile_date",
                            "explanation": "Retrieving float trajectory",
                            "confidence": 0.8
                        }
                    
                    # Default fallback
                    return {
                        "success": False,
                        "error": f"Could not parse LLM response after 3 attempts",
                        "tool_calls": [],
                        "sql_query": "",
                        "explanation": "Failed to analyze query",
                        "confidence": 0.0
                    }
            except Exception as e:
                if attempt == 2:
                    return {
                        "success": False,
                        "error": str(e),
                        "tool_calls": [],
                        "sql_query": "",
                        "explanation": "Error in tool analysis",
                        "confidence": 0.0
                    }
        
        return {
            "success": False,
            "error": "Failed to get LLM response",
            "tool_calls": [],
            "sql_query": "",
            "explanation": "No response from LLM",
            "confidence": 0.0
        }

    def _get_llm_response_with_retry(self, system_prompt: str, user_prompt: str) -> Dict:
        """Helper method for LLM calls with retry logic"""
        from langchain_core.messages import HumanMessage, SystemMessage
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt)
        ]
        
        for attempt in range(3):
            client = self._get_next_available_client()
            if client:
                try:
                    response = client.invoke(messages)
                    return self._parse_response(response.content)
                except Exception as e:
                    if attempt < 2:
                        time.sleep(2)
                        continue
                    return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "All API keys exhausted"}
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """Get current usage statistics"""
        stats = {
            "total_keys": len(self.api_keys),
            "current_key": self.current_key_index + 1,
            "key_usage": {}
        }
        
        for i, usage in self.key_usage.items():
            stats["key_usage"][f"key_{i+1}"] = {
                "requests_this_minute": usage["requests"],
                "last_reset": usage["last_reset"].strftime("%H:%M:%S"),
                "available": usage["requests"] < self.rate_limit_per_minute
            }
        
        return stats