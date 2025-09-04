"""
Map visualizations for ARGO float data
"""
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Any
import pandas as pd
from config.settings import Config

class ArgoMapVisualizer:
    def __init__(self):
        self.config = Config()
    
    def create_trajectory_map(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create interactive trajectory map with float paths"""
        
        geospatial_data = visualization_data.get("geospatial", {})
        trajectories = geospatial_data.get("trajectories", [])
        
        if not trajectories:
            return self._create_empty_map("No trajectory data available")
        
        fig = go.Figure()
        
        # Color palette for different floats
        colors = px.colors.qualitative.Set1
        
        for i, trajectory in enumerate(trajectories):
            color = colors[i % len(colors)]
            path_coords = trajectory.get("path_coordinates", [])
            
            if not path_coords:
                continue
            
            # Extract coordinates
            lats = [coord["lat"] for coord in path_coords]
            lons = [coord["lon"] for coord in path_coords]
            dates = [coord["date"] for coord in path_coords]
            cycles = [coord["cycle"] for coord in path_coords]
            
            # Create trajectory line
            fig.add_trace(go.Scattermapbox(
                lat=lats,
                lon=lons,
                mode='lines+markers',
                line=dict(width=2, color=color),
                marker=dict(size=6, color=color),
                name=f"Float {trajectory['wmo_id']}",
                text=[f"Date: {date}<br>Cycle: {cycle}" for date, cycle in zip(dates, cycles)],
                hovertemplate="<b>Float %{fullData.name}</b><br>" +
                             "Lat: %{lat}<br>" +
                             "Lon: %{lon}<br>" +
                             "%{text}<br>" +
                             "<extra></extra>"
            ))
            
            # Add deployment marker (first point)
            if path_coords:
                fig.add_trace(go.Scattermapbox(
                    lat=[lats[0]],
                    lon=[lons[0]],
                    mode='markers',
                    marker=dict(
                        size=12,
                        color='green',
                        symbol='star',
                    ),
                    name=f"Deploy {trajectory['wmo_id']}",
                    text=f"Deployment: {dates[0]}",
                    hovertemplate="<b>Deployment</b><br>" +
                                 "Float: %{fullData.name}<br>" +
                                 "Lat: %{lat}<br>" +
                                 "Lon: %{lon}<br>" +
                                 "%{text}<br>" +
                                 "<extra></extra>",
                    showlegend=False
                ))
            
            # Add current position marker (last point)
            if len(path_coords) > 1:
                fig.add_trace(go.Scattermapbox(
                    lat=[lats[-1]],
                    lon=[lons[-1]],
                    mode='markers',
                    marker=dict(
                        size=10,
                        color='red',
                        symbol='circle',
                    ),
                    name=f"Current {trajectory['wmo_id']}",
                    text=f"Last Profile: {dates[-1]}",
                    hovertemplate="<b>Current Position</b><br>" +
                                 "Float: %{fullData.name}<br>" +
                                 "Lat: %{lat}<br>" +
                                 "Lon: %{lon}<br>" +
                                 "%{text}<br>" +
                                 "<extra></extra>",
                    showlegend=False
                ))
        
        # Calculate map bounds
        all_lats = []
        all_lons = []
        for traj in trajectories:
            for coord in traj.get("path_coordinates", []):
                all_lats.append(coord["lat"])
                all_lons.append(coord["lon"])
        
        center_lat = sum(all_lats) / len(all_lats) if all_lats else 0
        center_lon = sum(all_lons) / len(all_lons) if all_lons else 0
        
        # Update layout
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=4
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text=f"ARGO Float Trajectories ({len(trajectories)} floats)",
                x=0.5,
                xanchor='center'
            ),
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor="rgba(255,255,255,0.8)"
            ),
            height=600
        )
        
        return fig
    
    def create_position_map(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create map showing current float positions"""
        
        geospatial_data = visualization_data.get("geospatial", {})
        current_positions = geospatial_data.get("current_positions", [])
        
        if not current_positions:
            return self._create_empty_map("No position data available")
        
        # Create DataFrame for easier plotting
        df_positions = pd.DataFrame(current_positions)
        
        fig = go.Figure()
        
        # Add current positions
        fig.add_trace(go.Scattermapbox(
            lat=df_positions['lat'],
            lon=df_positions['lon'],
            mode='markers',
            marker=dict(
                size=10,
                color='blue',
                opacity=0.8
            ),
            text=[f"WMO ID: {wmo}<br>Last Profile: {date}" 
                  for wmo, date in zip(df_positions['wmo_id'], df_positions['last_profile'])],
            hovertemplate="<b>ARGO Float</b><br>" +
                         "Lat: %{lat}<br>" +
                         "Lon: %{lon}<br>" +
                         "%{text}<br>" +
                         "<extra></extra>",
            name="Float Positions"
        ))
        
        # Calculate center
        center_lat = df_positions['lat'].mean()
        center_lon = df_positions['lon'].mean()
        
        # Update layout
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=5
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text=f"ARGO Float Current Positions ({len(current_positions)} floats)",
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig
    
    def create_regional_map(self, visualization_data: Dict[str, Any], region: str = None) -> go.Figure:
        """Create map with regional boundaries and float data"""
        
        geospatial_data = visualization_data.get("geospatial", {})
        current_positions = geospatial_data.get("current_positions", [])
        
        fig = go.Figure()
        
        # Add regional boundaries if specified
        if region and region in self.config.REGIONS:
            region_bounds = self.config.REGIONS[region]
            self._add_regional_boundary(fig, region_bounds, region)
        
        # Add all known regional boundaries
        for region_name, bounds in self.config.REGIONS.items():
            self._add_regional_boundary(fig, bounds, region_name, show_label=(region == region_name))
        
        # Add float positions if available
        if current_positions:
            df_positions = pd.DataFrame(current_positions)
            
            fig.add_trace(go.Scattermapbox(
                lat=df_positions['lat'],
                lon=df_positions['lon'],
                mode='markers',
                marker=dict(
                    size=8,
                    color='red',
                    opacity=0.8
                ),
                text=[f"WMO ID: {wmo}" for wmo in df_positions['wmo_id']],
                hovertemplate="<b>ARGO Float</b><br>" +
                             "Lat: %{lat}<br>" +
                             "Lon: %{lon}<br>" +
                             "%{text}<br>" +
                             "<extra></extra>",
                name="ARGO Floats"
            ))
            
            center_lat = df_positions['lat'].mean()
            center_lon = df_positions['lon'].mean()
        else:
            # Default to Arabian Sea center if no data
            center_lat = 19
            center_lon = 62.5
        
        # Update layout
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=4
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text=f"ARGO Floats - Regional View" + (f" ({region})" if region else ""),
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig
    
    def create_density_map(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create density heatmap of float positions"""
        
        geospatial_data = visualization_data.get("geospatial", {})
        trajectories = geospatial_data.get("trajectories", [])
        
        if not trajectories:
            return self._create_empty_map("No data available for density map")
        
        # Extract all position points
        all_lats = []
        all_lons = []
        all_counts = []
        
        for trajectory in trajectories:
            for coord in trajectory.get("path_coordinates", []):
                all_lats.append(coord["lat"])
                all_lons.append(coord["lon"])
                all_counts.append(1)  # Each point counts as 1
        
        if not all_lats:
            return self._create_empty_map("No position data available")
        
        # Create density map
        fig = go.Figure(go.Densitymapbox(
            lat=all_lats,
            lon=all_lons,
            z=all_counts,
            radius=20,
            colorscale="Viridis",
            showscale=True,
            hovertemplate="<b>Density</b><br>" +
                         "Lat: %{lat}<br>" +
                         "Lon: %{lon}<br>" +
                         "Count: %{z}<br>" +
                         "<extra></extra>"
        ))
        
        center_lat = sum(all_lats) / len(all_lats)
        center_lon = sum(all_lons) / len(all_lons)
        
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=4
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text="ARGO Float Position Density",
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig
    
    def _add_regional_boundary(self, fig: go.Figure, bounds: Dict, region_name: str, show_label: bool = True):
        """Add regional boundary rectangle to map"""
        
        # Create boundary rectangle
        boundary_lats = [bounds["lat_min"], bounds["lat_max"], bounds["lat_max"], bounds["lat_min"], bounds["lat_min"]]
        boundary_lons = [bounds["lon_min"], bounds["lon_min"], bounds["lon_max"], bounds["lon_max"], bounds["lon_min"]]
        
        fig.add_trace(go.Scattermapbox(
            lat=boundary_lats,
            lon=boundary_lons,
            mode='lines',
            line=dict(width=2, color='orange'),
            name=region_name.replace("_", " ").title(),
            showlegend=show_label,
            hovertemplate=f"<b>{region_name.replace('_', ' ').title()}</b><br>" +
                         "Regional Boundary<br>" +
                         "<extra></extra>"
        ))
        
        # Add region label at center
        if show_label:
            center_lat = (bounds["lat_min"] + bounds["lat_max"]) / 2
            center_lon = (bounds["lon_min"] + bounds["lon_max"]) / 2
            
            fig.add_trace(go.Scattermapbox(
                lat=[center_lat],
                lon=[center_lon],
                mode='text',
                text=[region_name.replace("_", " ").title()],
                textfont=dict(size=12, color='orange'),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    def _create_empty_map(self, message: str) -> go.Figure:
        """Create empty map with message"""
        fig = go.Figure()
        
        fig.add_trace(go.Scattermapbox(
            lat=[0],
            lon=[0],
            mode='text',
            text=[message],
            textfont=dict(size=16, color='gray'),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=20, lon=70),  # Indian Ocean center
                zoom=3
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text="ARGO Float Map",
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig
    
    def create_multi_parameter_map(self, visualization_data: Dict[str, Any], parameter: str = "temperature") -> go.Figure:
        """Create map colored by parameter values"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if not vertical_profiles:
            return self._create_empty_map("No profile data available")
        
        # Extract position and parameter data
        positions = []
        values = []
        
        for profile in vertical_profiles:
            position = profile.get("position", {})
            if position.get("lat") and position.get("lon"):
                measurements = profile.get("measurements", {})
                
                # Get surface value (first element) for the parameter
                param_values = measurements.get(parameter, [])
                if param_values:
                    positions.append({
                        "lat": position["lat"],
                        "lon": position["lon"],
                        "wmo_id": profile.get("wmo_id"),
                        "date": profile.get("profile_date"),
                        "value": param_values[0]  # Surface value
                    })
                    values.append(param_values[0])
        
        if not positions:
            return self._create_empty_map(f"No {parameter} data available")
        
        # Create map with color-coded points
        fig = go.Figure()
        
        fig.add_trace(go.Scattermapbox(
            lat=[pos["lat"] for pos in positions],
            lon=[pos["lon"] for pos in positions],
            mode='markers',
            marker=dict(
                size=8,
                color=values,
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title=parameter.title()),
                opacity=0.8
            ),
            text=[f"WMO: {pos['wmo_id']}<br>Date: {pos['date']}<br>{parameter.title()}: {pos['value']:.2f}" 
                  for pos in positions],
            hovertemplate="<b>ARGO Float</b><br>" +
                         "Lat: %{lat}<br>" +
                         "Lon: %{lon}<br>" +
                         "%{text}<br>" +
                         "<extra></extra>",
            name=f"{parameter.title()} Values"
        ))
        
        center_lat = sum(pos["lat"] for pos in positions) / len(positions)
        center_lon = sum(pos["lon"] for pos in positions) / len(positions)
        
        fig.update_layout(
            mapbox=dict(
                style="open-street-map",
                center=dict(lat=center_lat, lon=center_lon),
                zoom=5
            ),
            margin=dict(r=0, t=50, l=0, b=0),
            title=dict(
                text=f"ARGO Floats - {parameter.title()} Values",
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig