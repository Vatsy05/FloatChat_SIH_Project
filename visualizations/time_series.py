"""
Time series visualizations for ARGO float data
"""
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from config.settings import Config

class ArgoTimeSeriesVisualizer:
    def __init__(self):
        self.config = Config()
    
    def create_parameter_evolution(self, visualization_data: Dict[str, Any], parameter: str = "sea_surface_temperature") -> go.Figure:
        """Create time series plot showing parameter evolution"""
        
        time_series_data = visualization_data.get("time_series", {})
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        
        if not parameter_evolution:
            return self._create_empty_plot("No time series data available")
        
        fig = go.Figure()
        colors = px.colors.qualitative.Set1
        
        for i, float_series in enumerate(parameter_evolution[:10]):  # Limit to 10 floats
            temporal_data = float_series.get("temporal_data", [])
            if not temporal_data:
                continue
            
            # Extract time series data
            dates = []
            values = []
            for data_point in temporal_data:
                if data_point.get("date") and data_point.get("value") is not None:
                    try:
                        date = pd.to_datetime(data_point["date"])
                        dates.append(date)
                        values.append(data_point["value"])
                    except:
                        continue
            
            if not dates or not values:
                continue
            
            color = colors[i % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines+markers',
                name=f"Float {float_series.get('wmo_id', 'Unknown')}",
                line=dict(color=color, width=2),
                marker=dict(size=6, color=color),
                hovertemplate=f"<b>Float {float_series.get('wmo_id')}</b><br>" +
                             "Date: %{x}<br>" +
                             f"{parameter.replace('_', ' ').title()}: %{{y}}<br>" +
                             "<extra></extra>"
            ))
        
        # Determine parameter unit and title
        param_info = self._get_parameter_info(parameter)
        
        fig.update_layout(
            title=dict(
                text=f"{param_info['title']} Evolution Over Time ({len(parameter_evolution)} floats)",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Date",
            yaxis_title=f"{param_info['title']} ({param_info['unit']})",
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
    
    def create_seasonal_analysis(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create seasonal analysis plot"""
        
        time_series_data = visualization_data.get("time_series", {})
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        
        if not parameter_evolution:
            return self._create_empty_plot("No data for seasonal analysis")
        
        # Aggregate data by month
        monthly_data = {}
        
        for float_series in parameter_evolution:
            temporal_data = float_series.get("temporal_data", [])
            
            for data_point in temporal_data:
                try:
                    date = pd.to_datetime(data_point["date"])
                    value = data_point["value"]
                    
                    if value is not None:
                        month = date.month
                        if month not in monthly_data:
                            monthly_data[month] = []
                        monthly_data[month].append(value)
                except:
                    continue
        
        if not monthly_data:
            return self._create_empty_plot("Insufficient data for seasonal analysis")
        
        # Calculate monthly statistics
        months = sorted(monthly_data.keys())
        month_names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                       'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        means = []
        stds = []
        month_labels = []
        
        for month in months:
            values = monthly_data[month]
            means.append(np.mean(values))
            stds.append(np.std(values))
            month_labels.append(month_names[month])
        
        fig = go.Figure()
        
        # Add mean line
        fig.add_trace(go.Scatter(
            x=month_labels,
            y=means,
            mode='lines+markers',
            name='Monthly Mean',
            line=dict(color='blue', width=3),
            marker=dict(size=8, color='blue'),
            error_y=dict(
                type='data',
                array=stds,
                visible=True,
                color='lightblue'
            ),
            hovertemplate="<b>Monthly Statistics</b><br>" +
                         "Month: %{x}<br>" +
                         "Mean: %{y:.2f}<br>" +
                         "Std Dev: %{error_y.array:.2f}<br>" +
                         "<extra></extra>"
        ))
        
        fig.update_layout(
            title=dict(
                text="Seasonal Analysis - Monthly Temperature Patterns",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Month",
            yaxis_title="Temperature (°C)",
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
        return fig
    
    def create_multi_float_comparison(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create comparison of multiple floats over time"""
        
        time_series_data = visualization_data.get("time_series", {})
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        
        if len(parameter_evolution) < 2:
            return self._create_empty_plot("Need at least 2 floats for comparison")
        
        # Create subplots for individual float time series
        n_floats = min(len(parameter_evolution), 4)  # Maximum 4 subplots
        
        fig = make_subplots(
            rows=n_floats,
            cols=1,
            subplot_titles=[f"Float {series.get('wmo_id', 'Unknown')}" 
                          for series in parameter_evolution[:n_floats]],
            shared_xaxes=True,
            vertical_spacing=0.08
        )
        
        colors = px.colors.qualitative.Set1
        
        for i, float_series in enumerate(parameter_evolution[:n_floats]):
            temporal_data = float_series.get("temporal_data", [])
            
            dates = []
            values = []
            
            for data_point in temporal_data:
                try:
                    date = pd.to_datetime(data_point["date"])
                    value = data_point["value"]
                    if value is not None:
                        dates.append(date)
                        values.append(value)
                except:
                    continue
            
            if dates and values:
                color = colors[i % len(colors)]
                
                fig.add_trace(
                    go.Scatter(
                        x=dates,
                        y=values,
                        mode='lines+markers',
                        name=f"Float {float_series.get('wmo_id')}",
                        line=dict(color=color, width=2),
                        marker=dict(size=4, color=color),
                        hovertemplate=f"<b>Float {float_series.get('wmo_id')}</b><br>" +
                                     "Date: %{x}<br>" +
                                     "Value: %{y:.2f}<br>" +
                                     "<extra></extra>",
                        showlegend=True if i == 0 else False
                    ),
                    row=i+1, col=1
                )
        
        fig.update_layout(
            title=dict(
                text=f"Multi-Float Time Series Comparison ({n_floats} floats)",
                x=0.5,
                xanchor='center'
            ),
            height=150 * n_floats + 100,
            showlegend=False
        )
        
        # Update x-axis for bottom subplot
        fig.update_xaxes(title_text="Date", row=n_floats, col=1)
        
        # Update y-axes
        for i in range(n_floats):
            fig.update_yaxes(title_text="Temperature (°C)", row=i+1, col=1)
        
        return fig
    
    def create_anomaly_detection_plot(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create plot highlighting anomalies in time series"""
        
        time_series_data = visualization_data.get("time_series", {})
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        anomalies = time_series_data.get("anomaly_detection", [])
        
        if not parameter_evolution:
            return self._create_empty_plot("No time series data for anomaly detection")
        
        fig = go.Figure()
        
        # Plot normal data
        for float_series in parameter_evolution[:5]:  # Limit to 5 floats
            temporal_data = float_series.get("temporal_data", [])
            
            dates = []
            values = []
            
            for data_point in temporal_data:
                try:
                    date = pd.to_datetime(data_point["date"])
                    value = data_point["value"]
                    if value is not None:
                        dates.append(date)
                        values.append(value)
                except:
                    continue
            
            if dates and values:
                fig.add_trace(go.Scatter(
                    x=dates,
                    y=values,
                    mode='lines',
                    name=f"Float {float_series.get('wmo_id')}",
                    line=dict(width=2),
                    opacity=0.7,
                    hovertemplate=f"<b>Float {float_series.get('wmo_id')}</b><br>" +
                                 "Date: %{x}<br>" +
                                 "Value: %{y:.2f}<br>" +
                                 "<extra></extra>"
                ))
        
        # Highlight anomalies if available
        if anomalies:
            anomaly_dates = []
            anomaly_values = []
            anomaly_texts = []
            
            for anomaly in anomalies:
                try:
                    anomaly_date = pd.to_datetime(anomaly.get("detected_at", {}).get("date"))
                    anomaly_value = anomaly.get("detected_at", {}).get("value", 0)
                    anomaly_type = anomaly.get("anomaly_type", "unknown")
                    severity = anomaly.get("severity", "unknown")
                    
                    anomaly_dates.append(anomaly_date)
                    anomaly_values.append(anomaly_value)
                    anomaly_texts.append(f"Type: {anomaly_type}<br>Severity: {severity}")
                except:
                    continue
            
            if anomaly_dates:
                fig.add_trace(go.Scatter(
                    x=anomaly_dates,
                    y=anomaly_values,
                    mode='markers',
                    name='Anomalies',
                    marker=dict(
                        size=12,
                        color='red',
                        symbol='x',
                        line=dict(width=2, color='darkred')
                    ),
                    text=anomaly_texts,
                    hovertemplate="<b>Anomaly Detected</b><br>" +
                                 "Date: %{x}<br>" +
                                 "Value: %{y:.2f}<br>" +
                                 "%{text}<br>" +
                                 "<extra></extra>"
                ))
        
        fig.update_layout(
            title=dict(
                text="Time Series with Anomaly Detection",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Date",
            yaxis_title="Temperature (°C)",
            hovermode='closest',
            height=600,
            showlegend=True
        )
        
        return fig
    
    def create_regional_time_series(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create regional aggregated time series"""
        
        time_series_data = visualization_data.get("time_series", {})
        regional_aggregates = time_series_data.get("regional_aggregates", {})
        
        if not regional_aggregates:
            return self._create_empty_plot("No regional time series data available")
        
        fig = go.Figure()
        colors = ['blue', 'red', 'green', 'orange', 'purple']
        
        color_idx = 0
        for region_name, region_data in regional_aggregates.items():
            if isinstance(region_data, dict) and 'monthly_means' in region_data:
                monthly_means = region_data['monthly_means']
                
                dates = []
                values = []
                float_counts = []
                
                for data_point in monthly_means:
                    try:
                        date = pd.to_datetime(data_point['month'])
                        value = data_point['value']
                        count = data_point.get('float_count', 1)
                        
                        dates.append(date)
                        values.append(value)
                        float_counts.append(count)
                    except:
                        continue
                
                if dates and values:
                    fig.add_trace(go.Scatter(
                        x=dates,
                        y=values,
                        mode='lines+markers',
                        name=region_name.replace('_', ' ').title(),
                        line=dict(color=colors[color_idx % len(colors)], width=3),
                        marker=dict(size=8, color=colors[color_idx % len(colors)]),
                        hovertemplate=f"<b>{region_name.replace('_', ' ').title()}</b><br>" +
                                     "Date: %{x}<br>" +
                                     "Mean SST: %{y:.2f}°C<br>" +
                                     "Float Count: %{text}<br>" +
                                     "<extra></extra>",
                        text=float_counts
                    ))
                    color_idx += 1
        
        fig.update_layout(
            title=dict(
                text="Regional Time Series - Sea Surface Temperature",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Date",
            yaxis_title="Sea Surface Temperature (°C)",
            hovermode='x unified',
            height=500,
            showlegend=True
        )
        
        return fig
    
    def create_trend_analysis(self, visualization_data: Dict[str, Any]) -> go.Figure:
        """Create trend analysis with linear regression"""
        
        time_series_data = visualization_data.get("time_series", {})
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        
        if not parameter_evolution:
            return self._create_empty_plot("No data for trend analysis")
        
        # Combine all data points
        all_dates = []
        all_values = []
        
        for float_series in parameter_evolution:
            temporal_data = float_series.get("temporal_data", [])
            
            for data_point in temporal_data:
                try:
                    date = pd.to_datetime(data_point["date"])
                    value = data_point["value"]
                    if value is not None:
                        all_dates.append(date)
                        all_values.append(value)
                except:
                    continue
        
        if len(all_dates) < 10:
            return self._create_empty_plot("Insufficient data for trend analysis")
        
        # Convert dates to numerical format for regression
        date_nums = pd.to_numeric(pd.Series(all_dates))
        
        # Calculate linear trend
        coeffs = np.polyfit(date_nums, all_values, 1)
        trend_line = np.poly1d(coeffs)
        trend_values = trend_line(date_nums)
        
        fig = go.Figure()
        
        # Add scatter plot of all data
        fig.add_trace(go.Scatter(
            x=all_dates,
            y=all_values,
            mode='markers',
            name='Observations',
            marker=dict(
                size=4,
                color='lightblue',
                opacity=0.6
            ),
            hovertemplate="<b>Observation</b><br>" +
                         "Date: %{x}<br>" +
                         "Temperature: %{y:.2f}°C<br>" +
                         "<extra></extra>"
        ))
        
        # Add trend line
        fig.add_trace(go.Scatter(
            x=all_dates,
            y=trend_values,
            mode='lines',
            name=f'Trend (slope: {coeffs[0]:.4f}°C/year)',
            line=dict(color='red', width=3),
            hovertemplate="<b>Trend Line</b><br>" +
                         "Date: %{x}<br>" +
                         "Predicted: %{y:.2f}°C<br>" +
                         "<extra></extra>"
        ))
        
        # Calculate R-squared
        ss_res = np.sum((all_values - trend_values) ** 2)
        ss_tot = np.sum((all_values - np.mean(all_values)) ** 2)
        r_squared = 1 - (ss_res / ss_tot)
        
        fig.update_layout(
            title=dict(
                text=f"Temperature Trend Analysis (R² = {r_squared:.3f})",
                x=0.5,
                xanchor='center'
            ),
            xaxis_title="Date",
            yaxis_title="Temperature (°C)",
            hovermode='closest',
            height=600,
            showlegend=True,
            annotations=[
                dict(
                    x=0.02,
                    y=0.98,
                    xref='paper',
                    yref='paper',
                    text=f"Trend: {coeffs[0]*365.25:.3f}°C/year<br>R² = {r_squared:.3f}",
                    showarrow=False,
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="gray",
                    borderwidth=1
                )
            ]
        )
        
        return fig
    
    def _get_parameter_info(self, parameter: str) -> Dict[str, str]:
        """Get parameter display information"""
        param_mapping = {
            "sea_surface_temperature": {"title": "Sea Surface Temperature", "unit": "°C"},
            "temperature": {"title": "Temperature", "unit": "°C"},
            "salinity": {"title": "Salinity", "unit": "PSU"},
            "sea_surface_salinity": {"title": "Sea Surface Salinity", "unit": "PSU"},
            "dissolved_oxygen": {"title": "Dissolved Oxygen", "unit": "μmol/kg"},
            "chlorophyll": {"title": "Chlorophyll-a", "unit": "μg/L"},
            "nitrate": {"title": "Nitrate", "unit": "μmol/kg"}
        }
        
        return param_mapping.get(parameter, {"title": parameter.replace("_", " ").title(), "unit": ""})
    
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
            title="ARGO Time Series Visualization",
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=400
        )
        
        return fig