# FloatChat - ARGO Oceanographic Data AI Assistant

An intelligent conversational AI system for querying and analyzing ARGO float oceanographic data. FloatChat transforms natural language questions into precise PostgreSQL queries and provides insights about ocean temperature, salinity, and biogeochemical parameters.

## Features

### 🤖 Natural Language to SQL
- Convert plain English questions into optimized PostgreSQL queries
- Support for complex oceanographic queries with temporal and spatial filtering
- Intelligent context awareness and query optimization

### 🌊 ARGO Float Data Support
- **Core Parameters**: Temperature, Salinity, Pressure profiles
- **BGC Parameters**: Dissolved Oxygen, Chlorophyll-a, Nitrate
- **Quality Control**: Automated QC flag filtering and data validation
- **Geographic Regions**: Pre-defined boundaries for Arabian Sea, Bay of Bengal, etc.

### 📊 Advanced Features
- **RAG System**: Enhanced knowledge retrieval with semantic search
- **Multi-API Support**: Groq LLM with intelligent key rotation and rate limiting
- **Data Visualization**: Interactive maps, profiles, and time series
- **Session Management**: Context-aware conversations
- **Export Capabilities**: CSV, JSON data export

## Architecture

```
FloatChat/
├── core/                   # Core processing modules
│   ├── rag_system.py      # Enhanced RAG with MarkdownHeaderTextSplitter
│   ├── llm_manager.py     # Multi-key Groq LLM management
│   ├── data_processor.py  # Database query execution
│   └── session_manager.py # Session and context management
├── config/                # Configuration
│   └── settings.py        # Environment and settings management
├── database/              # Database connectivity
│   └── supabase_client.py # Supabase PostgreSQL client
├── visualizations/        # Data visualization
│   ├── maps.py           # Geographic visualizations
│   ├── profiles.py       # Vertical profile plots
│   └── time_series.py    # Temporal analysis
├── data/                  # Data and knowledge base
│   ├── improved_knowledge_base.md # Domain knowledge
│   └── chroma_db/        # Vector database (ignored)
└── app.py                # Main Streamlit application
```

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL database with ARGO float data
- Groq API key(s)

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/AnshAggr1303/FloatChat.git
   cd FloatChat
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configurations
   ```

4. **Initialize embeddings**
   ```bash
   python embeddings_setup.py --force-rebuild
   ```

5. **Run the application**
   ```bash
   streamlit run app.py
   ```

## Environment Setup

Create a `.env` file with the following variables:

```bash
# Database Configuration
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_anon_key

# Groq API Keys (comma-separated for rotation)
GROQ_API_KEYS=your_groq_key1,your_groq_key2
GROQ_MODEL=llama-3.1-70b-versatile
GROQ_TEMPERATURE=0.1
GROQ_MAX_TOKENS=2048

# RAG System Configuration
EMBEDDING_MODEL=all-MiniLM-L6-v2
CHROMA_PERSIST_DIRECTORY=./data/chroma_db
COLLECTION_NAME=argo_knowledge_base
```

## Usage Examples

### Natural Language Queries
```
"Show me temperature profiles in the Arabian Sea for March 2023"
"What is the average surface salinity in Bay of Bengal last year?"
"Compare BGC parameters between Arabian Sea and Bay of Bengal"
"Which institution has deployed the most BGC floats?"
"Show the trajectory of float 1900722"
```

### API Usage
```python
from core.llm_manager import GroqLLMManager
from core.rag_system import ArgoRAGSystem

# Initialize components
rag_system = ArgoRAGSystem()
llm_manager = GroqLLMManager()

# Generate SQL query
context = rag_system.retrieve_context("temperature profiles Arabian Sea")
response = llm_manager.generate_sql_query(
    "Show temperature profiles in Arabian Sea", 
    context
)
```

## Database Schema

### Core Tables
- **`public.argo_floats`**: Float metadata (WMO ID, deployment info, institution)
- **`public.argo_profiles`**: Profile measurements (temperature, salinity, BGC parameters)

### Key Features
- Array-based storage for vertical profiles
- Quality control flags for all measurements
- Support for both Core and BGC float categories
- Temporal and spatial indexing for efficient queries

## Advanced Features

### Enhanced RAG System
- **MarkdownHeaderTextSplitter**: Structure-aware document parsing
- **Semantic Scoring**: Importance-based chunk ranking
- **Multi-category Search**: Schema, geography, examples, BGC-specific queries
- **Context Optimization**: Intelligent chunk selection and metadata tracking

### Multi-API Management
- **Key Rotation**: Automatic switching between multiple Groq API keys
- **Rate Limiting**: Intelligent usage tracking and throttling
- **Retry Logic**: Robust error handling and fallback strategies
- **Usage Analytics**: Real-time API usage monitoring

### Data Visualization
- **Interactive Maps**: Geographic distribution of floats and measurements
- **Profile Plots**: Vertical oceanographic profiles with quality indicators
- **Time Series**: Temporal analysis with statistical overlays
- **Export Options**: Publication-ready visualizations

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Development Setup

```bash
# Install development dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/

# Check code quality
flake8 core/ config/ database/
black core/ config/ database/

# Validate embeddings setup
python embeddings_setup.py --check-deps --validate-only
```

## Troubleshooting

### Common Issues

1. **Embeddings not found**
   ```bash
   python embeddings_setup.py --reset --force-rebuild
   ```

2. **Database connection issues**
   - Verify SUPABASE_URL and SUPABASE_KEY in .env
   - Check database connectivity and permissions

3. **LLM generation failures**
   - Ensure valid Groq API keys in .env
   - Check rate limits and API quotas

4. **Missing dependencies**
   ```bash
   python embeddings_setup.py --check-deps
   pip install -r requirements.txt
   ```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- ARGO Program for providing global oceanographic data
- Groq for high-performance LLM inference
- ChromaDB for vector database capabilities
- Streamlit for the interactive web interface

## Technical Specifications

- **Language**: Python 3.8+
- **Framework**: Streamlit
- **Database**: PostgreSQL (via Supabase)
- **Vector DB**: ChromaDB
- **LLM**: Groq (Llama 3.1)
- **Embeddings**: sentence-transformers
- **Visualization**: Plotly, Folium

## Performance

- **Query Generation**: ~2-3 seconds average
- **Embedding Retrieval**: <500ms for most queries  
- **Database Queries**: Optimized with proper indexing
- **Memory Usage**: ~200-500MB typical operation

## Roadmap

- [ ] Add support for more LLM providers
- [ ] Implement advanced statistical analysis
- [ ] Add real-time data streaming
- [ ] Develop mobile-responsive interface
- [ ] Add multi-language support
- [ ] Implement user authentication
- [ ] Add query history and favorites