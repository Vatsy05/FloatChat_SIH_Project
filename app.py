"""
ARGO FloatChat AI - Streamlit Frontend
Enhanced with proper data visualization and export capabilities
"""
import streamlit as st
import requests
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import json
import csv
import io
from datetime import datetime
import folium
from streamlit_folium import st_folium
import time

# Configuration
API_BASE_URL = "http://localhost:8000"

# Page config
st.set_page_config(
    page_title="ARGO FloatChat AI",
    page_icon="🌊",
    layout="wide"
)

# Initialize session state
if 'session_id' not in st.session_state:
    st.session_state.session_id = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'current_data' not in st.session_state:
    st.session_state.current_data = None

def create_session():
    """Create new API session"""
    try:
        response = requests.post(f"{API_BASE_URL}/api/sessions")
        if response.status_code == 200:
            data = response.json()
            st.session_state.session_id = data['session_id']
            return data['session_id']
    except Exception as e:
        st.error(f"Failed to create session: {e}")
    return None

def process_query(query: str):
    """Send query to API and get results"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/query",
            json={
                "query": query,
                "session_id": st.session_state.session_id
            }
        )
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"API Error: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

def render_profile_visualization(profiles_data):
    """Render profile plots with Plotly"""
    if not profiles_data or not profiles_data.get('data'):
        st.warning("No profile data available for visualization")
        return
    
    profiles = profiles_data['data']
    
    # Create tabs for multiple profiles
    if len(profiles) > 1:
        profile_tabs = st.tabs([f"Float {p['wmo_id']}" for p in profiles[:5]])  # Limit to 5
    else:
        profile_tabs = [st.container()]
    
    for idx, (tab, profile) in enumerate(zip(profile_tabs, profiles[:5])):
        with tab:
            measurements = profile.get('measurements', {})
            
            if not measurements:
                st.warning(f"No measurements for float {profile.get('wmo_id')}")
                continue
            
            # Create subplots for temperature and salinity
            fig = go.Figure()
            
            # Temperature profile
            if 'temperature' in measurements and 'depth' in measurements:
                fig.add_trace(go.Scatter(
                    x=measurements['temperature'],
                    y=measurements['depth'],
                    mode='lines+markers',
                    name='Temperature (°C)',
                    line=dict(color='red', width=2),
                    marker=dict(size=4)
                ))
            
            # Salinity profile
            if 'salinity' in measurements and 'depth' in measurements:
                fig.add_trace(go.Scatter(
                    x=measurements['salinity'],
                    y=measurements['depth'],
                    mode='lines+markers',
                    name='Salinity (PSU)',
                    line=dict(color='blue', width=2),
                    marker=dict(size=4),
                    xaxis='x2'
                ))
            
            # Oxygen profile (if BGC)
            if 'oxygen' in measurements and 'depth' in measurements:
                fig.add_trace(go.Scatter(
                    x=measurements['oxygen'],
                    y=measurements['depth'],
                    mode='lines+markers',
                    name='Oxygen (μmol/kg)',
                    line=dict(color='green', width=2),
                    marker=dict(size=4),
                    xaxis='x3'
                ))
            
            # Update layout
            fig.update_layout(
                title=f"Profile - WMO {profile.get('wmo_id')} | {profile.get('profile_date', '')[:10]}",
                xaxis=dict(title="Temperature (°C)", side='top', color='red'),
                xaxis2=dict(title="Salinity (PSU)", overlaying='x', side='bottom', color='blue'),
                xaxis3=dict(title="Oxygen (μmol/kg)", overlaying='x', side='bottom', position=0.15, color='green'),
                yaxis=dict(title="Depth (m)", autorange='reversed'),
                height=600,
                hovermode='y unified',
                showlegend=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Profile info
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Location", f"{profile.get('latitude', 'N/A')}°, {profile.get('longitude', 'N/A')}°")
            with col2:
                st.metric("Float Type", profile.get('float_category', 'Unknown'))
            with col3:
                st.metric("Cycle", profile.get('cycle_number', 'N/A'))

def render_table_visualization(table_data):
    """Render tabular data"""
    if not table_data:
        return
    
    columns = table_data.get('columns', [])
    rows = table_data.get('rows', [])
    
    if columns and rows:
        df = pd.DataFrame(rows, columns=columns)
        
        # Display with formatting
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                col: st.column_config.NumberColumn(format="%.3f")
                if any(x in col.lower() for x in ['lat', 'lon', 'temp', 'sal'])
                else None
                for col in columns
            }
        )
        
        return df
    return None

def export_data(data, filename_prefix="argo_data", unique_key=""):
    """Provide multiple export options with unique keys"""
    export_options = st.columns(4)
    
    with export_options[0]:
        if st.button("📄 Export CSV", key=f"csv_{unique_key}"):
            csv_data = None
            
            # Try to extract table data
            if isinstance(data, dict):
                if 'table' in data and data['table'].get('rows'):
                    # Export table data
                    df = pd.DataFrame(data['table']['rows'], 
                                      columns=data['table'].get('columns', []))
                    csv_data = df.to_csv(index=False)
                elif 'statistics' in data and 'regions' in data.get('statistics', {}):
                    # Convert statistics to CSV
                    rows = []
                    for region, stats in data['statistics']['regions'].items():
                        if 'surface_values' in stats:
                            values = stats['surface_values']
                            rows.append({
                                'Region': region.replace('_', ' ').title(),
                                'Parameter': stats.get('parameter', '').title(),
                                'Mean': values.get('mean', 0),
                                'Min': values.get('min', 0),
                                'Max': values.get('max', 0),
                                'Std Dev': values.get('std_dev', 0),
                                'Profile Count': stats.get('profile_count', 0),
                                'Float Count': stats.get('float_count', 0)
                            })
                    if rows:
                        df = pd.DataFrame(rows)
                        csv_data = df.to_csv(index=False)
            
            if not csv_data:
                csv_data = "No tabular data available for export"
            
            st.download_button(
                label="Download CSV",
                data=csv_data,
                file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"download_csv_{unique_key}"
            )
    
    with export_options[1]:
        # JSON Export with unique key
        if st.button("📊 Export JSON", key=f"json_{unique_key}"):
            json_data = json.dumps(data, indent=2) if not isinstance(data, pd.DataFrame) else data.to_json(orient='records', indent=2)
            st.download_button(
                label="Download JSON",
                data=json_data,
                file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"download_json_{unique_key}"
            )
    
    with export_options[2]:
        # ASCII Export with unique key
        if st.button("📝 Export ASCII", key=f"ascii_{unique_key}"):
            if isinstance(data, pd.DataFrame):
                ascii_data = data.to_string()
            else:
                ascii_data = json.dumps(data, indent=2)
            
            st.download_button(
                label="Download ASCII",
                data=ascii_data,
                file_name=f"{filename_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                key=f"download_ascii_{unique_key}"
            )
    
    with export_options[3]:
        # NetCDF note with unique key
        if st.button("🌐 Export NetCDF", key=f"netcdf_{unique_key}"):
            st.info("NetCDF export requires additional processing. Contact admin for bulk NetCDF exports.")

def format_response_text(query, response_data):
    """Create informative response text based on query and data"""
    
    # First check if there's a summary field
    if response_data and response_data.get('summary'):
        return response_data['summary']
    
    # Otherwise generate from data...
    if not response_data:
        return "No data retrieved."
    
    data = response_data.get('data') or {}
    
    # Statistical queries
    if 'statistics' in data:
        stats = data['statistics']
        if 'regions' in stats:
            response_text = "📊 Statistical Analysis:\n"
            for region, region_data in stats['regions'].items():
                region_name = region.replace('_', ' ').title()
                if 'surface_values' in region_data:
                    param = region_data.get('parameter', 'parameter').title()
                    mean_val = region_data['surface_values'].get('mean', 0)
                    response_text += f"\n**{region_name} {param}:**\n"
                    response_text += f"- Mean: {mean_val:.2f}\n"
                    response_text += f"- Range: {region_data['surface_values'].get('min', 0):.2f} - {region_data['surface_values'].get('max', 0):.2f}\n"
                    response_text += f"- Profiles analyzed: {region_data.get('profile_count', 0)}\n"
            return response_text
    
    # Profile queries
    if 'profiles' in data:
        profiles = data['profiles'].get('data', [])
        if profiles:
            param_list = list(profiles[0]['measurements'].keys()) if profiles[0].get('measurements') else []
            param_str = ', '.join([p for p in param_list if p != 'depth'])
            return f"📊 Found {len(profiles)} profile(s) with {param_str} measurements at various depths."
    
    # Geographic queries
    if 'geospatial' in data:
        features = data['geospatial'].get('features', [])
        if features:
            if features[0].get('distance_km'):
                return f"📍 Located {len(features)} ARGO float(s). Nearest: {features[0]['distance_km']:.1f} km away."
            else:
                return f"🗺️ Displaying {len(features)} ARGO float(s) in the region."
    
    # Default
    return f"✅ Query processed successfully. Retrieved data for analysis."

def main():
    st.title("🌊 ARGO FloatChat AI")
    st.markdown("### Interactive Oceanographic Data Analysis System")
    
    # Sidebar
    with st.sidebar:
        st.header("📊 System Status")
        
        # Session info
        if not st.session_state.session_id:
            if st.button("🚀 Initialize Session"):
                create_session()
        else:
            st.success(f"✅ Session Active")
            st.caption(f"ID: {st.session_state.session_id[:8]}...")
        
        # Database stats
        try:
            response = requests.get(f"{API_BASE_URL}/api/database/stats")
            if response.status_code == 200:
                stats = response.json()['data']
                st.metric("Total Floats", f"{stats.get('total_floats', 0):,}")
                st.metric("BGC Floats", f"{stats.get('bgc_floats', 0):,}")
                st.metric("Total Profiles", f"{stats.get('total_profiles', 0):,}")
        except:
            st.warning("⚠️ Cannot connect to backend")
        
        # Sample queries
        st.header("💡 Sample Queries")
        
        st.subheader("🗺️ Spatial")
        spatial_queries = [
            "Find nearest 5 floats to latitude 15 longitude 70",
            "Show floats in Arabian Sea"
        ]
        for q in spatial_queries:
            if st.button(q, key=f"spatial_{q[:10]}"):
                st.session_state.pending_query = q
        
        st.subheader("📊 Profiles")
        profile_queries = [
            "Show temperature profiles in Arabian Sea",
            "Display BGC oxygen profiles"
        ]
        for q in profile_queries:
            if st.button(q, key=f"profile_{q[:10]}"):
                st.session_state.pending_query = q
        
        st.subheader("📈 Analysis")
        analysis_queries = [
            "Compare oxygen levels between Arabian Sea and Bay of Bengal",
            "Show trajectory of float 2902238 for last 10 years"
        ]
        for q in analysis_queries:
            if st.button(q, key=f"analysis_{q[:10]}"):
                st.session_state.pending_query = q
    
    # Main chat interface
    st.header("💬 Query Interface")
    
    # Handle pending query from sidebar
    if hasattr(st.session_state, 'pending_query'):
        query = st.session_state.pending_query
        del st.session_state.pending_query
    else:
        query = st.chat_input("Ask about ARGO float data...")
    
    # Process query
    if query:
        # Add to chat history
        st.session_state.chat_history.append({
            "role": "user",
            "content": query,
            "timestamp": datetime.now()
        })
        
        # Get response
        with st.spinner("🔍 Processing query..."):
            response = process_query(query)
        
        if response and response.get('success'):
            # Use summary if available, otherwise format a response
            response_text = response.get('summary') or format_response_text(query, response)

            # Add response to chat
            st.session_state.chat_history.append({
                "role": "assistant",
                "content": response_text,
                "data": response.get('data', {}),  # Pass only the data object
                "execution_path": response.get('execution_path'),
                "timestamp": datetime.now()
            })
            st.session_state.current_data = response.get('data', {})
    
    # Display chat history
    for idx, message in enumerate(st.session_state.chat_history):
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            # Display visualizations for assistant messages
            if message["role"] == "assistant" and message.get("data"):
                data = message["data"]
                
                # Show execution info
                if message.get('execution_path'):
                    st.caption(f"Execution: {message['execution_path']} pipeline")
                
                # Check what data is available
                has_profiles = 'profiles' in data
                has_geo = 'geospatial' in data
                has_stats = 'statistics' in data and data.get('statistics') and 'regions' in data.get('statistics', {})
                has_table = 'table' in data
                has_trajectory = 'trajectory' in data
                
                # Create appropriate tabs
                tabs = []
                if has_profiles:
                    tabs.append("📊 Profiles")
                if has_geo:
                    tabs.append("🗺️ Map")
                if has_stats:
                    tabs.append("📈 Statistics")
                if has_trajectory:
                    tabs.append("🛤️ Trajectory")
                if has_table:
                    tabs.append("📋 Table")
                tabs.append("💾 Export")
                
                if tabs:
                    tab_objects = st.tabs(tabs)
                    tab_idx = 0
                    
                    if has_profiles:
                        with tab_objects[tab_idx]:
                            render_profile_visualization(data.get('profiles'))
                        tab_idx += 1
                    
                    if has_geo:
                        with tab_objects[tab_idx]:
                            render_map_visualization(data.get('geospatial'))
                        tab_idx += 1
                    
                    if has_stats:
                        with tab_objects[tab_idx]:
                            render_statistics_visualization(data.get('statistics'))
                        tab_idx += 1
                    
                    if has_trajectory:
                        with tab_objects[tab_idx]:
                            render_trajectory_visualization(data.get('trajectory'))
                        tab_idx += 1
                    
                    if has_table:
                        with tab_objects[tab_idx]:
                            df = render_table_visualization(data.get('table'))
                        tab_idx += 1
                    
                    # Export tab with unique key based on message index
                    with tab_objects[tab_idx]:
                        st.markdown("### Export Options")
                        export_data(data, 
                                    f"argo_{message['timestamp'].strftime('%Y%m%d')}",
                                    unique_key=f"{idx}_{message['timestamp'].strftime('%Y%m%d%H%M%S')}")

def render_map_visualization(geospatial_data):
    """Render map with Folium"""
    if not geospatial_data:
        return
    
    # Get center point
    center = geospatial_data.get('center', {'lat': 15, 'lon': 70})
    
    # Create map
    m = folium.Map(
        location=[center['lat'], center['lon']],
        zoom_start=5,
        tiles='OpenStreetMap'
    )
    
    # Add features
    features = geospatial_data.get('features', [])
    for feature in features:
        color = 'green' if feature.get('float_category') == 'BGC' else 'blue'
        
        popup_text = f"""
        <b>WMO ID:</b> {feature.get('wmo_id')}<br>
        <b>Type:</b> {feature.get('float_category', 'Unknown')}<br>
        <b>Date:</b> {feature.get('profile_date', '')[:10]}<br>
        """
        
        if feature.get('distance_km'):
            popup_text += f"<b>Distance:</b> {feature['distance_km']:.1f} km"
        
        folium.Marker(
            [feature['latitude'], feature['longitude']],
            popup=folium.Popup(popup_text, max_width=300),
            icon=folium.Icon(color=color, icon='info-sign')
        ).add_to(m)
    
    # Display map
    st_folium(m, height=500, width=None, returned_objects=[])

def render_statistics_visualization(stats_data):
    """Render statistics visualization"""
    if not stats_data:
        st.warning("No statistics data available")
        return
    
    # Handle the regions structure
    if 'regions' in stats_data:
        regions = stats_data['regions']
        
        for region_name, region_data in regions.items():
            # Create a nice display card
            region_title = region_name.replace('_', ' ').title()
            parameter = region_data.get('parameter', 'Unknown').title()
            
            st.subheader(f"{region_title} - {parameter} Statistics")
            
            if 'surface_values' in region_data:
                values = region_data['surface_values']
                
                # Display metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Mean", f"{values.get('mean', 0):.2f} PSU")
                with col2:
                    st.metric("Min", f"{values.get('min', 0):.2f} PSU")
                with col3:
                    st.metric("Max", f"{values.get('max', 0):.2f} PSU")
                with col4:
                    st.metric("Std Dev", f"{values.get('std_dev', 0):.3f}")
                
                # Additional info
                st.info(f"Based on {region_data.get('profile_count', 0)} profiles from {region_data.get('float_count', 0)} floats")
                
                if 'date_range' in region_data:
                    st.caption(f"Period: {region_data['date_range'].get('earliest', '')[:10]} to {region_data['date_range'].get('latest', '')[:10]}")

def render_trajectory_visualization(trajectory_data):
    """Render trajectory visualization"""
    if not trajectory_data:
        return
    
    path = trajectory_data.get('path', [])
    
    if path:
        # Create DataFrame for plotting
        df = pd.DataFrame(path)
        
        # Plotly map
        fig = px.line_mapbox(
            df,
            lat='lat',
            lon='lon',
            hover_data=['date', 'cycle'],
            mapbox_style="open-street-map",
            zoom=4,
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Stats
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Points", trajectory_data.get('point_count', 0))
        with col2:
            st.metric("Duration (days)", trajectory_data.get('duration_days', 0))
        with col3:
            st.metric("Distance (km)", trajectory_data.get('total_distance_km', 0))

if __name__ == "__main__":
    if not st.session_state.session_id:
        create_session()
    main()