"""
Profile visualizations for ARGO float oceanographic data
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from config.settings import Config

class ArgoProfileVisualizer:
    def __init__(self):
        self.config = Config()
        self.qc_colors = {1: 'green', 2: 'yellow', 3: 'orange', 4: 'red', 9: 'gray'}
    
    def create_depth_profile(self, visualization_data: Dict[str, Any], parameter: str = "temperature") -> go.Figure:
        """Create depth profile plot for temperature/salinity/BGC parameters"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if not vertical_profiles:
            return self._create_empty_plot("No profile data available")
        
        fig = go.Figure()
        colors = px.colors.qualitative.Set1
        
        for i, profile in enumerate(vertical_profiles[:10]):  # Limit to 10 profiles for readability
            color = colors[i % len(colors)]
            
            # Extract data
            measurements = profile.get("measurements", {})
            bgc_parameters = profile.get("bgc_parameters", {})
            
            pressure = measurements.get("pressure", [])
            
            # Get the requested parameter
            if parameter == "temperature":
                values = measurements.get("temperature", [])
                qc_flags = measurements.get("quality_flags", {}).get("temperature_qc", [])
                unit = "°C"
            elif parameter == "salinity":
                values = measurements.get("salinity", [])
                qc_flags = measurements.get("quality_flags", {}).get("salinity_qc", [])
                unit = "PSU"
            elif parameter == "dissolved_oxygen":
                values = bgc_parameters.get("dissolved_oxygen", [])
                qc_flags = bgc_parameters.get("quality_flags", {}).get("doxy_qc", [])
                unit = "μmol/kg"
            elif parameter == "chlorophyll":
                values = bgc_parameters.get("chlorophyll", [])
                qc_flags = bgc_parameters.get("quality_flags", {}).get("chla_qc", [])
                unit = "μg/L"
            elif parameter == "nitrate":
                values = bgc_parameters.get("nitrate", [])
                qc_flags = bgc_parameters.get("quality_flags", {}).get("nitrate_qc", [])
                unit = "μmol/kg"
            else:
                continue
            
            if not values or not pressure:
                continue
            
            # Create color array based on QC flags
            marker_colors = []
            for j, qc in enumerate(qc_flags):
                if j < len(values):
                    marker_colors.append(self.qc_colors.get(qc, 'blue'))
                else:
                    marker_colors.append('blue')
            
            # Pad marker_colors if needed
            while len(marker_colors) < len(values):
                marker_colors.append('blue')
            
            # Add trace
            fig.add_trace(go.Scatter(
                x=values,
                y=pressure,
                mode='lines+markers',
                name=f"Float {profile.get('wmo_id', 'Unknown')}",
                line=dict(color=color, width=2),
                marker=dict(
                    color=marker_colors,
                    size=4,
                    line=dict(width=1, color='white')
                ),
                hovertemplate=f"<b>Float {profile.get('wmo_id', 'Unknown')}</b><br>" +
                             f"{parameter.title()}: %{{x}}<br>" +
                             "Depth: %{y} dbar<br>" +
                             f"Date: {profile.get('profile_date', 'Unknown')}<br>" +
                             "<extra></extra>"
            ))
        
        # Update layout
        fig.update_layout(
            title=dict(
                text=f"{parameter.title()} Depth Profiles ({len(vertical_profiles)} profiles)",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title=f"{parameter.title()} ({unit})",
            yaxis_title="Pressure (dbar)",
            yaxis=dict(autorange='reversed'),  # Depth increases downward
            hovermode='closest',
            height=600,
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=1.01
            )
        )
        
        return fig
    
    def create_ts_diagram(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create Temperature-Salinity diagram"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if not vertical_profiles:
            return self._create_empty_plot("No T-S data available")
        
        fig = go.Figure()
        colors = px.colors.qualitative.Set1
        
        for i, profile in enumerate(vertical_profiles[:15]):  # Limit for readability
            measurements = profile.get("measurements", {})
            
            temperature = measurements.get("temperature", [])
            salinity = measurements.get("salinity", [])
            pressure = measurements.get("pressure", [])
            
            if not temperature or not salinity:
                continue
            
            color = colors[i % len(colors)]
            
            # Create hover text with depth information
            hover_text = []
            for j, (temp, sal, pres) in enumerate(zip(temperature, salinity, pressure)):
                hover_text.append(f"Depth: {pres:.1f} dbar<br>T: {temp:.2f}°C<br>S: {sal:.2f} PSU")
            
            fig.add_trace(go.Scatter(
                x=salinity,
                y=temperature,
                mode='lines+markers',
                name=f"Float {profile.get('wmo_id', 'Unknown')}",
                line=dict(color=color, width=2),
                marker=dict(
                    color=pressure,
                    colorscale='Viridis_r',
                    size=6,
                    showscale=True if i == 0 else False,
                    colorbar=dict(title="Pressure (dbar)") if i == 0 else None,
                    line=dict(width=1, color='white')
                ),
                text=hover_text,
                hovertemplate="<b>Float %{fullData.name}</b><br>" +
                             "Salinity: %{x}<br>" +
                             "Temperature: %{y}<br>" +
                             "%{text}<br>" +
                             "<extra></extra>"
            ))
        
        fig.update_layout(
            title=dict(
                text=f"Temperature-Salinity Diagram ({len(vertical_profiles)} profiles)",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Salinity (PSU)",
            yaxis_title="Temperature (°C)",
            hovermode='closest',
            height=600,
            showlegend=True
        )
        
        return fig
    
    def create_multi_parameter_profile(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create multi-parameter profile plot"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if not vertical_profiles:
            return self._create_empty_plot("No profile data available")
        
        # Take first profile for detailed analysis
        profile = vertical_profiles[0]
        measurements = profile.get("measurements", {})
        bgc_parameters = profile.get("bgc_parameters", {})
        
        pressure = measurements.get("pressure", [])
        if not pressure:
            return self._create_empty_plot("No pressure data available")
        
        # Determine available parameters
        available_params = []
        if measurements.get("temperature"):
            available_params.append(("temperature", "Temperature (°C)", measurements["temperature"]))
        if measurements.get("salinity"):
            available_params.append(("salinity", "Salinity (PSU)", measurements["salinity"]))
        if bgc_parameters.get("dissolved_oxygen"):
            available_params.append(("oxygen", "Dissolved Oxygen (μmol/kg)", bgc_parameters["dissolved_oxygen"]))
        if bgc_parameters.get("chlorophyll"):
            available_params.append(("chlorophyll", "Chlorophyll-a (μg/L)", bgc_parameters["chlorophyll"]))
        if bgc_parameters.get("nitrate"):
            available_params.append(("nitrate", "Nitrate (μmol/kg)", bgc_parameters["nitrate"]))
        
        if not available_params:
            return self._create_empty_plot("No parameter data available")
        
        # Create subplots
        n_params = len(available_params)
        fig = make_subplots(
            rows=1, 
            cols=n_params,
            subplot_titles=[param[1] for param in available_params],
            shared_yaxes=True,
            horizontal_spacing=0.1
        )
        
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        
        for i, (param_name, param_title, param_values) in enumerate(available_params):
            if len(param_values) != len(pressure):
                # Align arrays if different lengths
                min_len = min(len(param_values), len(pressure))
                param_values = param_values[:min_len]
                plot_pressure = pressure[:min_len]
            else:
                plot_pressure = pressure
            
            fig.add_trace(
                go.Scatter(
                    x=param_values,
                    y=plot_pressure,
                    mode='lines+markers',
                    name=param_name.title(),
                    line=dict(color=colors[i % len(colors)], width=2),
                    marker=dict(size=4),
                    hovertemplate=f"<b>{param_name.title()}</b><br>" +
                                 f"Value: %{{x}}<br>" +
                                 "Depth: %{y} dbar<br>" +
                                 "<extra></extra>"
                ),
                row=1, col=i+1
            )
        
        # Update y-axes to be reversed (depth increases downward)
        for i in range(n_params):
            fig.update_yaxes(autorange='reversed', row=1, col=i+1)
            if i == 0:  # Only show y-axis title on first subplot
                fig.update_yaxes(title_text="Pressure (dbar)", row=1, col=i+1)
        
        fig.update_layout(
            title=dict(
                text=f"Multi-Parameter Profile - Float {profile.get('wmo_id', 'Unknown')}",
                x=0.5,
                xanchor='center'
            ),
            height=600,
            showlegend=False
        )
        
        return fig
    
    def create_profile_comparison(self, visualization_data: Dict[str, Any], parameter: str = "temperature") -> go.Figure:
        """Create comparison plot of multiple profiles"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        comparison_data = profiles_data.get("comparison_data", {})
        
        if not vertical_profiles:
            return self._create_empty_plot("No profile data for comparison")
        
        fig = go.Figure()
        
        # Add individual profiles
        colors = px.colors.qualitative.Pastel1
        for i, profile in enumerate(vertical_profiles[:8]):  # Limit to 8 profiles
            measurements = profile.get("measurements", {})
            bgc_parameters = profile.get("bgc_parameters", {})
            
            pressure = measurements.get("pressure", [])
            
            if parameter == "temperature":
                values = measurements.get("temperature", [])
                unit = "°C"
            elif parameter == "salinity":
                values = measurements.get("salinity", [])
                unit = "PSU"
            elif parameter == "dissolved_oxygen":
                values = bgc_parameters.get("dissolved_oxygen", [])
                unit = "μmol/kg"
            else:
                continue
            
            if not values or not pressure:
                continue
            
            fig.add_trace(go.Scatter(
                x=values,
                y=pressure,
                mode='lines',
                name=f"Float {profile.get('wmo_id')}",
                line=dict(color=colors[i % len(colors)], width=1),
                opacity=0.6,
                hovertemplate=f"<b>Float {profile.get('wmo_id')}</b><br>" +
                             f"{parameter.title()}: %{{x}}<br>" +
                             "Depth: %{y} dbar<br>" +
                             "<extra></extra>"
            ))
        
        # Add mean profile if available in comparison data
        stats = comparison_data.get("statistical_summary", {}).get(parameter, {})
        if stats and len(vertical_profiles) > 1:
            # Calculate mean profile (simplified)
            all_pressures = []
            all_values = []
            
            for profile in vertical_profiles:
                measurements = profile.get("measurements", {})
                bgc_parameters = profile.get("bgc_parameters", {})
                
                pressure = measurements.get("pressure", [])
                
                if parameter == "temperature":
                    values = measurements.get("temperature", [])
                elif parameter == "salinity":
                    values = measurements.get("salinity", [])
                elif parameter == "dissolved_oxygen":
                    values = bgc_parameters.get("dissolved_oxygen", [])
                else:
                    continue
                
                if values and pressure:
                    for p, v in zip(pressure, values):
                        all_pressures.append(p)
                        all_values.append(v)
            
            if all_pressures and all_values:
                # Create binned average (simplified approach)
                pressure_bins = np.linspace(0, max(all_pressures), 50)
                mean_values = []
                
                for i in range(len(pressure_bins)-1):
                    bin_values = [v for p, v in zip(all_pressures, all_values) 
                                 if pressure_bins[i] <= p < pressure_bins[i+1]]
                    if bin_values:
                        mean_values.append(np.mean(bin_values))
                    else:
                        mean_values.append(None)
                
                fig.add_trace(go.Scatter(
                    x=mean_values,
                    y=pressure_bins[:-1],
                    mode='lines',
                    name=f"Mean {parameter.title()}",
                    line=dict(color='black', width=3),
                    hovertemplate=f"<b>Mean Profile</b><br>" +
                                 f"{parameter.title()}: %{{x}}<br>" +
                                 "Depth: %{y} dbar<br>" +
                                 "<extra></extra>"
                ))
        
        fig.update_layout(
            title=dict(
                text=f"{parameter.title()} Profile Comparison ({len(vertical_profiles)} profiles)",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title=f"{parameter.title()} ({unit})",
            yaxis_title="Pressure (dbar)",
            yaxis=dict(autorange='reversed'),
            hovermode='closest',
            height=600,
            showlegend=True
        )
        
        return fig
    
    def create_bgc_profiles(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create BGC parameter profiles (oxygen, chlorophyll, nitrate)"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        # Filter profiles that have BGC data
        bgc_profiles = [p for p in vertical_profiles if p.get("bgc_parameters")]
        
        if not bgc_profiles:
            return self._create_empty_plot("No BGC profile data available")
        
        # Create subplots for BGC parameters
        fig = make_subplots(
            rows=1, 
            cols=3,
            subplot_titles=["Dissolved Oxygen", "Chlorophyll-a", "Nitrate"],
            shared_yaxes=True,
            horizontal_spacing=0.1
        )
        
        colors = px.colors.qualitative.Set1
        
        for i, profile in enumerate(bgc_profiles[:5]):  # Limit to 5 profiles
            color = colors[i % len(colors)]
            bgc_params = profile.get("bgc_parameters", {})
            measurements = profile.get("measurements", {})
            pressure = measurements.get("pressure", [])
            
            if not pressure:
                continue
            
            # Oxygen profile
            oxygen = bgc_params.get("dissolved_oxygen", [])
            if oxygen:
                fig.add_trace(
                    go.Scatter(
                        x=oxygen,
                        y=pressure[:len(oxygen)],
                        mode='lines+markers',
                        name=f"Float {profile.get('wmo_id')}",
                        line=dict(color=color, width=2),
                        marker=dict(size=4),
                        showlegend=True if i == 0 else False,
                        hovertemplate=f"<b>Float {profile.get('wmo_id')}</b><br>" +
                                     "Oxygen: %{x} μmol/kg<br>" +
                                     "Depth: %{y} dbar<br>" +
                                     "<extra></extra>"
                    ),
                    row=1, col=1
                )
            
            # Chlorophyll profile
            chla = bgc_params.get("chlorophyll", [])
            if chla:
                fig.add_trace(
                    go.Scatter(
                        x=chla,
                        y=pressure[:len(chla)],
                        mode='lines+markers',
                        name=f"Float {profile.get('wmo_id')}",
                        line=dict(color=color, width=2),
                        marker=dict(size=4),
                        showlegend=False,
                        hovertemplate=f"<b>Float {profile.get('wmo_id')}</b><br>" +
                                     "Chlorophyll: %{x} μg/L<br>" +
                                     "Depth: %{y} dbar<br>" +
                                     "<extra></extra>"
                    ),
                    row=1, col=2
                )
            
            # Nitrate profile
            nitrate = bgc_params.get("nitrate", [])
            if nitrate:
                fig.add_trace(
                    go.Scatter(
                        x=nitrate,
                        y=pressure[:len(nitrate)],
                        mode='lines+markers',
                        name=f"Float {profile.get('wmo_id')}",
                        line=dict(color=color, width=2),
                        marker=dict(size=4),
                        showlegend=False,
                        hovertemplate=f"<b>Float {profile.get('wmo_id')}</b><br>" +
                                     "Nitrate: %{x} μmol/kg<br>" +
                                     "Depth: %{y} dbar<br>" +
                                     "<extra></extra>"
                    ),
                    row=1, col=3
                )
        
        # Update axes
        fig.update_yaxes(autorange='reversed', row=1, col=1)
        fig.update_yaxes(autorange='reversed', row=1, col=2)
        fig.update_yaxes(autorange='reversed', row=1, col=3)
        
        fig.update_yaxes(title_text="Pressure (dbar)", row=1, col=1)
        fig.update_xaxes(title_text="Dissolved Oxygen (μmol/kg)", row=1, col=1)
        fig.update_xaxes(title_text="Chlorophyll-a (μg/L)", row=1, col=2)
        fig.update_xaxes(title_text="Nitrate (μmol/kg)", row=1, col=3)
        
        fig.update_layout(
            title=dict(
                text=f"BGC Parameter Profiles ({len(bgc_profiles)} floats)",
                x=0.5,
                xanchor='center'
            ),
            height=600
        )
        
        return fig
    
    def create_qc_visualization(self, visualization_data: Dict[str, Any], parameter: str = "temperature") -> go.Figure:
        """Create quality control visualization for data"""
        
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if not vertical_profiles:
            return self._create_empty_plot("No QC data available")
        
        fig = go.Figure()
        
        # Count QC flags across all profiles
        qc_counts = {1: 0, 2: 0, 3: 0, 4: 0, 9: 0}
        all_pressure = []
        all_values = []
        all_qc = []
        
        for profile in vertical_profiles:
            measurements = profile.get("measurements", {})
            quality_flags = measurements.get("quality_flags", {})
            
            pressure = measurements.get("pressure", [])
            
            if parameter == "temperature":
                values = measurements.get("temperature", [])
                qc_flags = quality_flags.get("temperature_qc", [])
            elif parameter == "salinity":
                values = measurements.get("salinity", [])
                qc_flags = quality_flags.get("salinity_qc", [])
            else:
                continue
            
            if values and pressure and qc_flags:
                all_pressure.extend(pressure[:len(qc_flags)])
                all_values.extend(values[:len(qc_flags)])
                all_qc.extend(qc_flags)
                
                for qc in qc_flags:
                    if qc in qc_counts:
                        qc_counts[qc] += 1
        
        if not all_qc:
            return self._create_empty_plot("No QC flag data available")
        
        # Group data by QC flag for plotting
        qc_data = {}
        for pressure, value, qc in zip(all_pressure, all_values, all_qc):
            if qc not in qc_data:
                qc_data[qc] = {"pressure": [], "values": []}
            qc_data[qc]["pressure"].append(pressure)
            qc_data[qc]["values"].append(value)
        
        qc_labels = {
            1: "Good data",
            2: "Probably good data",
            3: "Bad data (correctable)",
            4: "Bad data",
            9: "Missing/No QC"
        }
        
        # Plot each QC category
        for qc_flag, data in qc_data.items():
            if data["pressure"] and qc_flag in self.qc_colors:
                fig.add_trace(go.Scatter(
                    x=data["values"],
                    y=data["pressure"],
                    mode='markers',
                    name=f"QC {qc_flag}: {qc_labels.get(qc_flag, 'Unknown')}",
                    marker=dict(
                        color=self.qc_colors[qc_flag],
                        size=4,
                        opacity=0.7
                    ),
                    hovertemplate=f"<b>{qc_labels.get(qc_flag, 'Unknown')}</b><br>" +
                                 f"{parameter.title()}: %{{x}}<br>" +
                                 "Depth: %{y} dbar<br>" +
                                 f"QC Flag: {qc_flag}<br>" +
                                 "<extra></extra>"
                ))
        
        fig.update_layout(
            title=dict(
                text=f"Quality Control Visualization - {parameter.title()}",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title=f"{parameter.title()}",
            yaxis_title="Pressure (dbar)",
            yaxis=dict(autorange='reversed'),
            hovermode='closest',
            height=600,
            showlegend=True
        )
        
        return fig
    
    def _create_empty_plot(self, message: str) -> go.Figure:
        """Create empty plot with message"""
        fig = go.Figure()
        
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            xanchor='center', yanchor='middle',
            font=dict(size=16, color="gray")
        )
        
        fig.update_layout(
            title="ARGO Profile Visualization",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400
        )
        
        return fig