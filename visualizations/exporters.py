"""
Export functionality for ARGO float data and visualizations
"""
import json
import csv
import io
import zipfile
from typing import Dict, List, Any, Optional
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

class ArgoDataExporter:
    def __init__(self):
        self.supported_formats = ["csv", "json", "netcdf", "ascii", "html"]
    
    def export_data(self, visualization_data: Dict[str, Any], format_type: str = "csv") -> bytes:
        """Export visualization data in specified format"""
        
        if format_type not in self.supported_formats:
            raise ValueError(f"Unsupported format: {format_type}")
        
        if format_type == "csv":
            return self._export_csv(visualization_data)
        elif format_type == "json":
            return self._export_json(visualization_data)
        elif format_type == "ascii":
            return self._export_ascii(visualization_data)
        elif format_type == "html":
            return self._export_html(visualization_data)
        elif format_type == "netcdf":
            return self._export_netcdf_info(visualization_data)
        else:
            raise ValueError(f"Export format {format_type} not implemented")
    
    def _export_csv(self, visualization_data: Dict[str, Any]) -> bytes:
        """Export data as CSV files in ZIP archive"""
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            
            # Export geospatial data
            if "geospatial" in visualization_data:
                self._add_geospatial_csv(zip_file, visualization_data["geospatial"])
            
            # Export profile data
            if "profiles" in visualization_data:
                self._add_profiles_csv(zip_file, visualization_data["profiles"])
            
            # Export time series data
            if "time_series" in visualization_data:
                self._add_time_series_csv(zip_file, visualization_data["time_series"])
            
            # Export metadata
            metadata = {
                "export_timestamp": datetime.now().isoformat(),
                "data_types": list(visualization_data.keys()),
                "format": "CSV",
                "description": "ARGO Float Data Export"
            }
            
            metadata_csv = io.StringIO()
            writer = csv.writer(metadata_csv)
            writer.writerow(["key", "value"])
            for key, value in metadata.items():
                writer.writerow([key, str(value)])
            
            zip_file.writestr("metadata.csv", metadata_csv.getvalue())
        
        zip_buffer.seek(0)
        return zip_buffer.read()
    
    def _add_geospatial_csv(self, zip_file: zipfile.ZipFile, geospatial_data: Dict[str, Any]):
        """Add geospatial data CSV files to ZIP"""
        
        # Float positions
        if "current_positions" in geospatial_data:
            positions = geospatial_data["current_positions"]
            if positions:
                df_positions = pd.DataFrame(positions)
                csv_buffer = io.StringIO()
                df_positions.to_csv(csv_buffer, index=False)
                zip_file.writestr("float_positions.csv", csv_buffer.getvalue())
        
        # Trajectories
        if "trajectories" in geospatial_data:
            trajectories = geospatial_data["trajectories"]
            trajectory_rows = []
            
            for traj in trajectories:
                wmo_id = traj.get("wmo_id")
                float_type = traj.get("float_type", "Unknown")
                institution = traj.get("institution", "Unknown")
                
                for coord in traj.get("path_coordinates", []):
                    trajectory_rows.append({
                        "wmo_id": wmo_id,
                        "float_type": float_type,
                        "institution": institution,
                        "latitude": coord.get("lat"),
                        "longitude": coord.get("lon"),
                        "date": coord.get("date"),
                        "cycle_number": coord.get("cycle")
                    })
            
            if trajectory_rows:
                df_trajectories = pd.DataFrame(trajectory_rows)
                csv_buffer = io.StringIO()
                df_trajectories.to_csv(csv_buffer, index=False)
                zip_file.writestr("float_trajectories.csv", csv_buffer.getvalue())
    
    def _add_profiles_csv(self, zip_file: zipfile.ZipFile, profiles_data: Dict[str, Any]):
        """Add profile data CSV files to ZIP"""
        
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        for i, profile in enumerate(vertical_profiles):
            wmo_id = profile.get("wmo_id", f"profile_{i}")
            cycle_number = profile.get("cycle_number", 0)
            
            # Core measurements
            measurements = profile.get("measurements", {})
            pressure = measurements.get("pressure", [])
            temperature = measurements.get("temperature", [])
            salinity = measurements.get("salinity", [])
            
            # Quality flags
            quality_flags = measurements.get("quality_flags", {})
            pressure_qc = quality_flags.get("pressure_qc", [])
            temperature_qc = quality_flags.get("temperature_qc", [])
            salinity_qc = quality_flags.get("salinity_qc", [])
            
            # Create DataFrame
            profile_data = {
                "pressure_dbar": pressure,
                "temperature_celsius": temperature,
                "salinity_psu": salinity,
                "pressure_qc": pressure_qc,
                "temperature_qc": temperature_qc,
                "salinity_qc": salinity_qc
            }
            
            # Add BGC parameters if available
            bgc_params = profile.get("bgc_parameters", {})
            if bgc_params:
                profile_data.update({
                    "dissolved_oxygen_umol_kg": bgc_params.get("dissolved_oxygen", []),
                    "chlorophyll_ug_l": bgc_params.get("chlorophyll", []),
                    "nitrate_umol_kg": bgc_params.get("nitrate", [])
                })
                
                bgc_qc = bgc_params.get("quality_flags", {})
                profile_data.update({
                    "doxy_qc": bgc_qc.get("doxy_qc", []),
                    "chla_qc": bgc_qc.get("chla_qc", []),
                    "nitrate_qc": bgc_qc.get("nitrate_qc", [])
                })
            
            # Find maximum array length and pad shorter arrays
            max_length = max(len(arr) for arr in profile_data.values() if isinstance(arr, list))
            
            for key, arr in profile_data.items():
                if isinstance(arr, list) and len(arr) < max_length:
                    profile_data[key] = arr + [None] * (max_length - len(arr))
            
            # Create DataFrame and export
            df_profile = pd.DataFrame(profile_data)
            csv_buffer = io.StringIO()
            df_profile.to_csv(csv_buffer, index=False)
            
            filename = f"profile_{wmo_id}_cycle_{cycle_number}.csv"
            zip_file.writestr(filename, csv_buffer.getvalue())
    
    def _add_time_series_csv(self, zip_file: zipfile.ZipFile, time_series_data: Dict[str, Any]):
        """Add time series data CSV files to ZIP"""
        
        parameter_evolution = time_series_data.get("parameter_evolution", [])
        
        for float_series in parameter_evolution:
            wmo_id = float_series.get("wmo_id", "unknown")
            parameter = float_series.get("parameter", "unknown")
            temporal_data = float_series.get("temporal_data", [])
            
            if temporal_data:
                df_timeseries = pd.DataFrame(temporal_data)
                csv_buffer = io.StringIO()
                df_timeseries.to_csv(csv_buffer, index=False)
                
                filename = f"timeseries_{wmo_id}_{parameter}.csv"
                zip_file.writestr(filename, csv_buffer.getvalue())
    
    def _export_json(self, visualization_data: Dict[str, Any]) -> bytes:
        """Export data as JSON"""
        
        export_data = {
            "metadata": {
                "export_timestamp": datetime.now().isoformat(),
                "format": "JSON",
                "description": "ARGO Float Data Export"
            },
            "data": visualization_data
        }
        
        return json.dumps(export_data, indent=2, default=str).encode('utf-8')
    
    def _export_ascii(self, visualization_data: Dict[str, Any]) -> bytes:
        """Export data in ODV ASCII format"""
        
        output_buffer = io.StringIO()
        
        # Write ODV header
        output_buffer.write("//ODV ASCII Export\n")
        output_buffer.write(f"//Created: {datetime.now().isoformat()}\n")
        output_buffer.write("//Data from ARGO Float Analysis\n")
        output_buffer.write("//\n")
        
        # Process profile data for ODV format
        profiles_data = visualization_data.get("profiles", {})
        vertical_profiles = profiles_data.get("vertical_profiles", [])
        
        if vertical_profiles:
            # Write column headers
            headers = ["Cruise", "Station", "Type", "Date", "Longitude", "Latitude", 
                      "Depth", "Temperature", "Salinity"]
            
            # Check for BGC parameters
            has_bgc = any(profile.get("bgc_parameters") for profile in vertical_profiles)
            if has_bgc:
                headers.extend(["Oxygen", "Chlorophyll", "Nitrate"])
            
            output_buffer.write("\t".join(headers) + "\n")
            
            # Write data
            for profile in vertical_profiles:
                cruise = f"ARGO_{profile.get('wmo_id', 'UNKNOWN')}"
                station = str(profile.get('cycle_number', 0))
                data_type = "BO"  # Bottle data type
                date = profile.get('profile_date', '')
                
                position = profile.get('position', {})
                longitude = position.get('lon', '')
                latitude = position.get('lat', '')
                
                measurements = profile.get('measurements', {})
                pressure = measurements.get('pressure', [])
                temperature = measurements.get('temperature', [])
                salinity = measurements.get('salinity', [])
                
                bgc_params = profile.get('bgc_parameters', {})
                
                # Write each depth level
                for i, depth in enumerate(pressure):
                    row = [cruise, station, data_type, date, longitude, latitude, depth]
                    
                    # Add core parameters
                    if i < len(temperature):
                        row.append(temperature[i])
                    else:
                        row.append('')
                    
                    if i < len(salinity):
                        row.append(salinity[i])
                    else:
                        row.append('')
                    
                    # Add BGC parameters if available
                    if has_bgc:
                        oxygen = bgc_params.get('dissolved_oxygen', [])
                        chlorophyll = bgc_params.get('chlorophyll', [])
                        nitrate = bgc_params.get('nitrate', [])
                        
                        row.append(oxygen[i] if i < len(oxygen) else '')
                        row.append(chlorophyll[i] if i < len(chlorophyll) else '')
                        row.append(nitrate[i] if i < len(nitrate) else '')
                    
                    output_buffer.write("\t".join(str(x) for x in row) + "\n")
        
        return output_buffer.getvalue().encode('utf-8')
    
    def _export_html(self, visualization_data: Dict[str, Any]) -> bytes:
        """Export data as HTML report"""
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>ARGO Float Data Export</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f0f8ff; padding: 20px; border-radius: 5px; }}
        .section {{ margin: 20px 0; }}
        .data-table {{ border-collapse: collapse; width: 100%; }}
        .data-table th, .data-table td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        .data-table th {{ background-color: #4CAF50; color: white; }}
        .metadata {{ background-color: #f9f9f9; padding: 10px; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>ARGO Float Data Export</h1>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    </div>
    
    <div class="section">
        <h2>Data Summary</h2>
        <div class="metadata">
"""
        
        # Add summary statistics
        if "geospatial" in visualization_data:
            trajectories = visualization_data["geospatial"].get("trajectories", [])
            html_content += f"<p><strong>Number of floats:</strong> {len(trajectories)}</p>\n"
        
        if "profiles" in visualization_data:
            profiles = visualization_data["profiles"].get("vertical_profiles", [])
            html_content += f"<p><strong>Number of profiles:</strong> {len(profiles)}</p>\n"
        
        html_content += """
        </div>
    </div>
    
    <div class="section">
        <h2>Raw Data (JSON)</h2>
        <pre style="background-color: #f5f5f5; padding: 15px; overflow: auto; max-height: 400px;">
"""
        
        html_content += json.dumps(visualization_data, indent=2, default=str)[:5000]
        if len(json.dumps(visualization_data, default=str)) > 5000:
            html_content += "\n... (truncated)"
        
        html_content += """
        </pre>
    </div>
    
    <div class="section">
        <h2>Export Information</h2>
        <p>This data can be further processed using oceanographic analysis software such as:</p>
        <ul>
            <li>ODV (Ocean Data View)</li>
            <li>Python (pandas, xarray)</li>
            <li>R (oce package)</li>
            <li>MATLAB</li>
        </ul>
    </div>
</body>
</html>
"""
        
        return html_content.encode('utf-8')
    
    def _export_netcdf_info(self, visualization_data: Dict[str, Any]) -> bytes:
        """Export NetCDF metadata and structure information"""
        
        # Since we don't have xarray/netCDF4 in requirements, 
        # we'll export the structure information instead
        
        netcdf_info = {
            "format": "CF-1.8 compliant NetCDF",
            "conventions": "CF-1.8, Argo-3.1",
            "global_attributes": {
                "title": "ARGO Float Oceanographic Data",
                "institution": "FloatChat AI System",
                "source": "ARGO profiling floats",
                "history": f"Created {datetime.now().isoformat()}",
                "Conventions": "CF-1.8",
                "featureType": "trajectoryProfile"
            },
            "dimensions": {
                "N_PROF": "number of profiles",
                "N_LEVELS": "number of pressure levels",
                "N_PARAM": "number of parameters"
            },
            "variables": {
                "PLATFORM_NUMBER": {
                    "long_name": "Float unique identifier",
                    "cf_role": "trajectory_id"
                },
                "CYCLE_NUMBER": {
                    "long_name": "Float cycle number"
                },
                "JULD": {
                    "long_name": "Julian day",
                    "units": "days since 1950-01-01 00:00:00 UTC"
                },
                "LATITUDE": {
                    "long_name": "Latitude of the station",
                    "units": "degree_north"
                },
                "LONGITUDE": {
                    "long_name": "Longitude of the station", 
                    "units": "degree_east"
                },
                "PRES": {
                    "long_name": "Sea water pressure",
                    "units": "dbar"
                },
                "TEMP": {
                    "long_name": "Sea water temperature",
                    "units": "degree_Celsius"
                },
                "PSAL": {
                    "long_name": "Practical salinity",
                    "units": "psu"
                }
            },
            "note": "This is metadata information for NetCDF export. Actual NetCDF file creation requires xarray/netCDF4 libraries."
        }
        
        # Add BGC variables if present
        profiles = visualization_data.get("profiles", {}).get("vertical_profiles", [])
        has_bgc = any(profile.get("bgc_parameters") for profile in profiles)
        
        if has_bgc:
            netcdf_info["variables"].update({
                "DOXY": {
                    "long_name": "Dissolved oxygen",
                    "units": "micromole/kg"
                },
                "CHLA": {
                    "long_name": "Chlorophyll-A",
                    "units": "mg/m3"
                },
                "NITRATE": {
                    "long_name": "Nitrate",
                    "units": "micromole/kg"
                }
            })
        
        return json.dumps(netcdf_info, indent=2).encode('utf-8')
    
    def export_figure(self, figure: go.Figure, format_type: str = "html") -> bytes:
        """Export Plotly figure in specified format"""
        
        if format_type == "html":
            return figure.to_html().encode('utf-8')
        elif format_type == "png":
            return figure.to_image(format="png")
        elif format_type == "svg":
            return figure.to_image(format="svg")
        elif format_type == "pdf":
            return figure.to_image(format="pdf")
        elif format_type == "json":
            return figure.to_json().encode('utf-8')
        else:
            raise ValueError(f"Unsupported figure format: {format_type}")
    
    def get_export_filename(self, format_type: str, data_type: str = "argo_data") -> str:
        """Generate appropriate filename for export"""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format_type == "csv":
            return f"{data_type}_{timestamp}.zip"
        else:
            return f"{data_type}_{timestamp}.{format_type}"