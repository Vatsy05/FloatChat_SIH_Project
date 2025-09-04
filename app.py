"""
ARGO FloatChat AI - Main Streamlit Application
Interactive oceanographic data analysis with natural language queries
"""
import streamlit as st
import time
import traceback
from typing import Dict, Any, Optional

# Import core modules
from config.settings import Config
from core.rag_system import ArgoRAGSystem
from core.sql_generator import ArgoSQLGenerator
from core.data_processor import ArgoDataProcessor
from core.session_manager import SessionManager
from database.supabase_client import SupabaseClient
from visualizations.maps import ArgoMapVisualizer
from visualizations.profiles import ArgoProfileVisualizer
from visualizations.time_series import ArgoTimeSeriesVisualizer
from visualizations.exporters import ArgoDataExporter
from utils.helpers import format_sql_query, format_duration, time_ago

# Page configuration
st.set_page_config(
    page_title="ARGO FloatChat AI",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'last_query_result' not in st.session_state:
    st.session_state.last_query_result = None

# Initialize system components
@st.cache_resource
def initialize_system():
    """Initialize system components with caching"""
    try:
        # Validate configuration
        config = Config()
        config.validate_config()
        
        # Initialize components
        components = {
            'config': config,
            'rag_system': ArgoRAGSystem(),
            'sql_generator': ArgoSQLGenerator(),
            'data_processor': ArgoDataProcessor(),
            'session_manager': SessionManager(),
            'database_client': SupabaseClient(),
            'map_visualizer': ArgoMapVisualizer(),
            'profile_visualizer': ArgoProfileVisualizer(),
            'time_series_visualizer': ArgoTimeSeriesVisualizer(),
            'data_exporter': ArgoDataExporter()
        }
        
        return components, None
        
    except Exception as e:
        return None, str(e)

def main():
    """Main application function"""
    
    # Header
    st.title("🌊 ARGO FloatChat AI")
    st.markdown("*Interactive oceanographic data analysis with natural language queries*")
    
    # Initialize system
    system_components, error = initialize_system()
    
    if error:
        st.error(f"❌ System Initialization Error: {error}")
        st.info("Please check your configuration and run: `python embeddings_setup.py`")
        return
    
    # Create session if needed
    if not st.session_state.session_id:
        st.session_state.session_id = system_components['session_manager'].create_session()
    
    # Sidebar
    render_sidebar(system_components)
    
    # Main interface
    render_main_interface(system_components)

def render_sidebar(components: Dict[str, Any]):
    """Render sidebar with system information and controls"""
    
    st.sidebar.header("🔧 System Status")
    
    # Database statistics
    with st.sidebar.expander("📊 Database Info", expanded=False):
        try:
            db_stats = components['database_client'].get_database_stats()
            st.metric("Total Floats", db_stats.get("total_floats", 0))
            st.metric("BGC Floats", db_stats.get("bgc_floats", 0))
            st.metric("Total Profiles", db_stats.get("total_profiles", 0))
        except Exception as e:
            st.error(f"Database connection error: {str(e)}")
    
    # Knowledge Base Stats
    with st.sidebar.expander("🧠 Knowledge Base", expanded=False):
        try:
            kb_stats = components['rag_system'].get_collection_stats()
            if "error" not in kb_stats:
                st.metric("Knowledge Chunks", kb_stats.get("total_chunks", 0))
                st.text(f"Model: {kb_stats.get('embedding_model', 'Unknown')}")
            else:
                st.warning("Knowledge base not found. Run embeddings setup.")
        except Exception as e:
            st.error(f"Knowledge base error: {str(e)}")
    
    # API Usage
    with st.sidebar.expander("🔑 API Status", expanded=False):
        try:
            usage_stats = components['sql_generator'].llm_manager.get_usage_stats()
            st.text(f"Active Keys: {usage_stats['total_keys']}")
            st.text(f"Current Key: {usage_stats['current_key']}")
            
            for key_id, key_usage in usage_stats['key_usage'].items():
                status = "🟢" if key_usage['available'] else "🔴"
                st.text(f"{status} {key_id}: {key_usage['requests_this_minute']}/30")
        except Exception as e:
            st.error(f"API status error: {str(e)}")
    
    # Session Info
    with st.sidebar.expander("💭 Session Info", expanded=False):
        try:
            session_stats = components['session_manager'].get_session_stats(st.session_state.session_id)
            if "error" not in session_stats:
                st.metric("Total Queries", session_stats.get("total_queries", 0))
                st.text(f"Session Age: {session_stats.get('session_age_minutes', 0):.1f} min")
                
                # Current focus
                focus = session_stats.get('current_focus', {})
                if any(focus.values()):
                    st.text("Current Focus:")
                    for key, value in focus.items():
                        if value:
                            st.text(f"  {key}: {value}")
            else:
                st.warning("Session information unavailable")
        except Exception as e:
            st.error(f"Session error: {str(e)}")
    
    # Quick Actions
    st.sidebar.header("⚡ Quick Actions")
    
    if st.sidebar.button("🔄 New Session"):
        components['session_manager'].delete_session(st.session_state.session_id)
        st.session_state.session_id = components['session_manager'].create_session()
        st.session_state.chat_history = []
        st.rerun()
    
    if st.sidebar.button("📊 Sample Queries"):
        show_sample_queries()

def show_sample_queries():
    """Display sample queries in sidebar"""
    sample_queries = [
        "Show me BGC floats in the Arabian Sea",
        "Temperature profiles near the equator in 2023",
        "Compare salinity in Bay of Bengal vs Arabian Sea",
        "Show trajectory of float 2902238",
        "What's the average surface temperature last 6 months?"
    ]
    
    st.sidebar.subheader("📝 Sample Queries")
    for query in sample_queries:
        if st.sidebar.button(query, key=f"sample_{query[:20]}"):
            st.session_state.current_query = query

def render_main_interface(components: Dict[str, Any]):
    """Render main chat interface"""
    
    # Chat input
    query_input = st.chat_input("Ask about ARGO float data...", key="main_query_input")
    
    # Handle sample query selection
    if hasattr(st.session_state, 'current_query'):
        query_input = st.session_state.current_query
        del st.session_state.current_query
    
    # Process query
    if query_input:
        process_user_query(query_input, components)
    
    # Display chat history
    render_chat_history(components)

def process_user_query(user_query: str, components: Dict[str, Any]):
    """Process user query and generate response"""
    
    start_time = time.time()
    
    # Add user message to chat
    st.session_state.chat_history.append({
        "role": "user",
        "content": user_query,
        "timestamp": time.time()
    })
    
    try:
        with st.spinner("🤔 Analyzing your query..."):
            
            # Get session context
            session_context = components['session_manager'].get_context_for_query(
                st.session_state.session_id, user_query
            )
            
            # Generate SQL query
            sql_response = components['sql_generator'].generate_query(user_query, session_context)
            
            if not sql_response.get("success"):
                raise Exception(f"SQL Generation failed: {sql_response.get('error', 'Unknown error')}")
            
            sql_query = sql_response["sql_query"]
            
        with st.spinner("🔍 Executing database query..."):
            
            # Execute query
            raw_results = components['database_client'].execute_query(sql_query)
            
        with st.spinner("📊 Processing results..."):
            
            # Process results
            processed_results = components['data_processor'].process_query_results(
                raw_results, sql_response
            )
            
            execution_time = time.time() - start_time
            processed_results["data"]["execution_stats"]["execution_time_ms"] = execution_time * 1000
        
        # Store results
        st.session_state.last_query_result = {
            "user_query": user_query,
            "sql_response": sql_response,
            "raw_results": raw_results,
            "processed_results": processed_results,
            "execution_time": execution_time
        }
        
        # Add to session history
        results_summary = f"Found {len(raw_results)} records in {format_duration(execution_time)}"
        components['session_manager'].add_query_to_history(
            st.session_state.session_id,
            user_query,
            sql_query,
            sql_response,
            results_summary
        )
        
        # Add assistant response to chat
        assistant_response = create_assistant_response(processed_results, sql_response)
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": assistant_response,
            "timestamp": time.time(),
            "processed_results": processed_results,
            "sql_query": sql_query
        })
        
    except Exception as e:
        error_message = f"❌ Error processing query: {str(e)}"
        st.session_state.chat_history.append({
            "role": "assistant",
            "content": error_message,
            "timestamp": time.time(),
            "error": True
        })
        st.error(error_message)
        if st.checkbox("Show detailed error"):
            st.code(traceback.format_exc())

def create_assistant_response(processed_results: Dict[str, Any], sql_response: Dict[str, Any]) -> str:
    """Create assistant response message"""
    
    if not processed_results.get("success"):
        return f"❌ {processed_results.get('error', 'Unknown error occurred')}"
    
    data = processed_results["data"]
    title = data.get("title", "Query Results")
    summary = data.get("summary", "")
    
    # Format response
    response_parts = [
        f"**{title}**",
        f"{summary}",
    ]
    
    # Add execution stats
    exec_stats = data.get("execution_stats", {})
    if exec_stats:
        stats_parts = []
        if "execution_time_ms" in exec_stats:
            stats_parts.append(f"⏱️ {exec_stats['execution_time_ms']:.0f}ms")
        if "records_processed" in exec_stats:
            stats_parts.append(f"📊 {exec_stats['records_processed']} records")
        if "profiles_processed" in exec_stats:
            stats_parts.append(f"🌊 {exec_stats['profiles_processed']} profiles")
        
        if stats_parts:
            response_parts.append(f"*{' • '.join(stats_parts)}*")
    
    # Add explanation
    explanation = sql_response.get("explanation", "")
    if explanation:
        response_parts.append(f"📝 {explanation}")
    
    return "\n\n".join(response_parts)

def render_chat_history(components: Dict[str, Any]):
    """Render chat history with visualizations"""
    
    if not st.session_state.chat_history:
        # Welcome message
        with st.chat_message("assistant"):
            st.markdown("""
            👋 **Welcome to ARGO FloatChat AI!**
            
            I can help you analyze oceanographic data from ARGO floats using natural language queries.
            
            **Try asking:**
            - "Show me BGC floats in the Arabian Sea"
            - "Temperature profiles near the equator in 2023"
            - "Compare salinity data between regions"
            - "What's the trajectory of float 2902238?"
            
            🚀 **Get started by typing a query below!**
            """)
        return
    
    # Render chat messages
    for message in st.session_state.chat_history:
        role = message["role"]
        content = message["content"]
        timestamp = message["timestamp"]
        
        with st.chat_message(role):
            st.markdown(content)
            
            # Show timestamp
            time_str = time_ago(time.time() - timestamp)
            st.caption(f"*{time_str}*")
            
            # Show visualizations for assistant messages
            if role == "assistant" and "processed_results" in message and not message.get("error"):
                render_visualizations(message["processed_results"], components)
                
                # Show SQL query in expander
                if "sql_query" in message:
                    with st.expander("🔍 View SQL Query"):
                        st.code(format_sql_query(message["sql_query"]), language="sql")

def render_visualizations(processed_results: Dict[str, Any], components: Dict[str, Any]):
    """Render visualizations based on processed results"""
    
    if not processed_results.get("success"):
        return
    
    data = processed_results["data"]
    visualization_data = data.get("visualization_data", {})
    display_components = data.get("display_components", [])
    
    if not visualization_data or not display_components:
        return
    
    # Create tabs for different visualizations
    available_tabs = []
    tab_functions = []
    
    if "map" in display_components and "geospatial" in visualization_data:
        available_tabs.append("🗺️ Map")
        tab_functions.append(lambda: render_map_visualizations(visualization_data, components))
    
    if "profiles" in display_components and "profiles" in visualization_data:
        available_tabs.append("📊 Profiles")
        tab_functions.append(lambda: render_profile_visualizations(visualization_data, components))
    
    if "time_series" in display_components and "time_series" in visualization_data:
        available_tabs.append("📈 Time Series")
        tab_functions.append(lambda: render_time_series_visualizations(visualization_data, components))
    
    if "data_table" in display_components or "export" in display_components:
        available_tabs.append("📋 Data")
        tab_functions.append(lambda: render_data_table(data, components))
    
    if available_tabs:
        tabs = st.tabs(available_tabs)
        for tab, func in zip(tabs, tab_functions):
            with tab:
                func()

def render_map_visualizations(visualization_data: Dict[str, Any], components: Dict[str, Any]):
    """Render map visualizations"""
    
    map_viz = components['map_visualizer']
    
    # Map type selector
    map_types = {
        "Trajectories": "trajectory",
        "Current Positions": "position", 
        "Regional View": "regional",
        "Parameter Map": "parameter"
    }
    
    map_type = st.selectbox("Map Type", list(map_types.keys()), key="map_type_selector")
    
    try:
        if map_type == "Trajectories":
            fig = map_viz.create_trajectory_map(visualization_data)
        elif map_type == "Current Positions":
            fig = map_viz.create_position_map(visualization_data)
        elif map_type == "Regional View":
            fig = map_viz.create_regional_map(visualization_data)
        elif map_type == "Parameter Map":
            parameter = st.selectbox("Parameter", ["temperature", "salinity"], key="param_selector")
            fig = map_viz.create_multi_parameter_map(visualization_data, parameter)
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error creating map: {str(e)}")

def render_profile_visualizations(visualization_data: Dict[str, Any], components: Dict[str, Any]):
    """Render profile visualizations"""
    
    profile_viz = components['profile_visualizer']
    
    # Profile type selector
    col1, col2 = st.columns(2)
    
    with col1:
        profile_types = {
            "Temperature": "temperature",
            "Salinity": "salinity",
            "T-S Diagram": "ts_diagram",
            "Multi-Parameter": "multi_parameter"
        }
        
        # Check for BGC data
        profiles = visualization_data.get("profiles", {}).get("vertical_profiles", [])
        has_bgc = any(profile.get("bgc_parameters") for profile in profiles)
        
        if has_bgc:
            profile_types.update({
                "BGC Profiles": "bgc",
                "Dissolved Oxygen": "dissolved_oxygen",
                "Chlorophyll": "chlorophyll"
            })
        
        profile_type = st.selectbox("Profile Type", list(profile_types.keys()), key="profile_type_selector")
    
    with col2:
        if profile_type in ["Temperature", "Salinity", "Dissolved Oxygen", "Chlorophyll"]:
            show_qc = st.checkbox("Show Quality Control", key="show_qc_checkbox")
    
    try:
        if profile_type == "T-S Diagram":
            fig = profile_viz.create_ts_diagram(visualization_data)
        elif profile_type == "Multi-Parameter":
            fig = profile_viz.create_multi_parameter_profile(visualization_data)
        elif profile_type == "BGC Profiles":
            fig = profile_viz.create_bgc_profiles(visualization_data)
        else:
            parameter = profile_types[profile_type]
            if show_qc:
                fig = profile_viz.create_qc_visualization(visualization_data, parameter)
            else:
                fig = profile_viz.create_depth_profile(visualization_data, parameter)
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error creating profile plot: {str(e)}")

def render_time_series_visualizations(visualization_data: Dict[str, Any], components: Dict[str, Any]):
    """Render time series visualizations"""
    
    ts_viz = components['time_series_visualizer']
    
    # Time series type selector
    ts_types = {
        "Parameter Evolution": "evolution",
        "Seasonal Analysis": "seasonal",
        "Multi-Float Comparison": "comparison",
        "Trend Analysis": "trend"
    }
    
    ts_type = st.selectbox("Time Series Type", list(ts_types.keys()), key="ts_type_selector")
    
    try:
        if ts_type == "Parameter Evolution":
            fig = ts_viz.create_parameter_evolution(visualization_data)
        elif ts_type == "Seasonal Analysis":
            fig = ts_viz.create_seasonal_analysis(visualization_data)
        elif ts_type == "Multi-Float Comparison":
            fig = ts_viz.create_multi_float_comparison(visualization_data)
        elif ts_type == "Trend Analysis":
            fig = ts_viz.create_trend_analysis(visualization_data)
        
        st.plotly_chart(fig, use_container_width=True)
        
    except Exception as e:
        st.error(f"Error creating time series plot: {str(e)}")

def render_data_table(data: Dict[str, Any], components: Dict[str, Any]):
    """Render data table and export options"""
    
    raw_results = data.get("query_results", [])
    
    if raw_results:
        # Display data table
        st.subheader("📋 Query Results")
        st.dataframe(raw_results, use_container_width=True)
        
        # Export options
        st.subheader("💾 Export Data")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            export_format = st.selectbox(
                "Export Format",
                ["CSV", "JSON", "ASCII (ODV)", "HTML Report"],
                key="export_format_selector"
            )
        
        with col2:
            if st.button("📥 Export Data", key="export_button"):
                try:
                    exporter = components['data_exporter']
                    format_map = {
                        "CSV": "csv",
                        "JSON": "json", 
                        "ASCII (ODV)": "ascii",
                        "HTML Report": "html"
                    }
                    
                    export_data = exporter.export_data(
                        data.get("visualization_data", {}),
                        format_map[export_format]
                    )
                    
                    filename = exporter.get_export_filename(
                        format_map[export_format],
                        "argo_floatchat_export"
                    )
                    
                    st.download_button(
                        label=f"📁 Download {export_format}",
                        data=export_data,
                        file_name=filename,
                        mime="application/octet-stream",
                        key="download_button"
                    )
                    
                except Exception as e:
                    st.error(f"Export error: {str(e)}")
        
        with col3:
            st.metric("Records", len(raw_results))
    else:
        st.info("No data to display")

if __name__ == "__main__":
    main()