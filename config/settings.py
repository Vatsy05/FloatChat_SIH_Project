"""
Configuration settings for FloatChat AI
"""
import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Groq API Configuration
    GROQ_API_KEYS: List[str] = [
        os.getenv("GROQ_API_KEY_1"),
        os.getenv("GROQ_API_KEY_2"),
        os.getenv("GROQ_API_KEY_3"),
    ]
    
    GROQ_MODEL = "llama-3.3-70b-versatile"
    GROQ_MAX_TOKENS = 8000
    GROQ_TEMPERATURE = 0.1
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
    
    # Embedding Configuration
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    CHROMA_PERSIST_DIRECTORY = "./data/chroma_db"
    COLLECTION_NAME = "argo_knowledge_base"
    
    # Session Configuration
    SESSION_TIMEOUT_MINUTES = 45
    MAX_CONTEXT_LENGTH = 10
    
    # Data Processing Configuration
    VALID_QC_FLAGS = [1, 2]  # 1=good, 2=probably good
    MAX_QUERY_RESULTS = 1000
    
    # Regional Boundaries
    REGIONS = {
        "arabian_sea": {
            "lat_min": 8, "lat_max": 30,
            "lon_min": 50, "lon_max": 75
        },
        "bay_of_bengal": {
            "lat_min": 5, "lat_max": 22,
            "lon_min": 80, "lon_max": 100
        },
        "equator": {
            "lat_min": -5, "lat_max": 5,
            "lon_min": -180, "lon_max": 180
        }
    }
    
    # Visualization Configuration
    PLOTLY_CONFIG = {
        'displayModeBar': True,
        'displaylogo': False,
        'modeBarButtonsToRemove': ['pan2d', 'lasso2d']
    }
    
    @classmethod
    def validate_config(cls):
        """Validate configuration settings"""
        # Check required environment variables
        required_vars = [
            "SUPABASE_URL", "SUPABASE_ANON_KEY",
            "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3"
        ]
        
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        # Filter out None API keys
        cls.GROQ_API_KEYS = [key for key in cls.GROQ_API_KEYS if key is not None]
        
        if len(cls.GROQ_API_KEYS) == 0:
            raise ValueError("At least one GROQ API key must be provided")
        
        print(f"✅ Configuration validated successfully")
        print(f"📊 Found {len(cls.GROQ_API_KEYS)} Groq API keys")
        print(f"🗄️ Supabase URL: {cls.SUPABASE_URL}")
        
        return True