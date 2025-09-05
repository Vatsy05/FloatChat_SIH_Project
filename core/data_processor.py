"""
Data Processor for ARGO float query results
Transforms raw PostgreSQL results into visualization-ready JSON format
"""
import json
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
from config.settings import Config

class ArgoDataProcessor:
    def __init__(self):
        self.config = Config()
    
    def process_query_results(self, raw_results: List[Dict], query_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process raw query results into comprehensive visualization format"""
        try:
            if not raw_results:
                return self._create_empty_response(query_metadata)
            
            # Determine processing strategy based on query type and content
            query_type = query_metadata.get("query_type", "basic")
            query_text = query_metadata.get("query_text", "").lower()
            
            # Check for specific data patterns in results
            has_arrays = any('temperature_celsius' in r or 'pressure_dbar' in r for r in raw_results)
            has_coordinates = all('latitude' in r and 'longitude' in r for r in raw_results)
            
            # Route to appropriate processor
            if has_arrays and ('profile' in query_text or 'temperature' in query_text or 'vertical' in query_text):
                return self._process_profile_data(raw_results, query_metadata)
            elif query_type == "geographic" or ('map' in query_text or 'nearest' in query_text):
                return self._process_geographic_data(raw_results, query_metadata)
            elif 'trajectory' in query_text or 'path' in query_text:
                return self._process_trajectory_data(raw_results, query_metadata)
            elif query_type == "time_series" or 'time' in query_text:
                return self._process_time_series_data(raw_results, query_metadata)
            elif query_type == "comparative" or 'compare' in query_text:
                return self._process_comparative_data(raw_results, query_metadata)
            elif query_type == "statistical":
                return self._process_statistical_data(raw_results, query_metadata)
            else:
                # Default: if it has arrays, treat as profile, else as general
                if has_arrays:
                    return self._process_profile_data(raw_results, query_metadata)
                else:
                    return self._process_general_data(raw_results, query_metadata)
                
        except Exception as e:
            print(f"❌ Error processing query results: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._create_error_response(str(e), query_metadata)
    
    def _process_profile_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for profile visualizations - properly formatted"""
        profiles_data = []
        
        for row in raw_results:
            # Extract array data
            pressure = self._extract_array_data(row.get('pressure_dbar', []))
            temperature = self._extract_array_data(row.get('temperature_celsius', []))
            salinity = self._extract_array_data(row.get('salinity_psu', []))
            
            # Skip if no valid profile data
            if not pressure or not temperature:
                continue
            
            # Create profile object with correct structure for frontend
            profile = {
                "wmo_id": row.get('wmo_id'),
                "profile_date": self._format_datetime(row.get('profile_date')),
                "cycle_number": row.get('cycle_number'),
                "latitude": float(row['latitude']) if row.get('latitude') else None,
                "longitude": float(row['longitude']) if row.get('longitude') else None,
                "float_category": row.get('float_category', 'Core'),
                "measurements": {
                    "depth": pressure,  # Use pressure as depth proxy
                    "temperature": temperature,
                    "salinity": salinity if salinity else []
                }
            }
            
            # Add BGC parameters if available
            doxy = self._extract_array_data(row.get('doxy_micromol_per_kg', []))
            chla = self._extract_array_data(row.get('chla_microgram_per_l', []))
            nitrate = self._extract_array_data(row.get('nitrate_micromol_per_kg', []))
            
            if doxy:
                profile["measurements"]["oxygen"] = doxy
            if chla:
                profile["measurements"]["chlorophyll"] = chla
            if nitrate:
                profile["measurements"]["nitrate"] = nitrate
            
            profiles_data.append(profile)
        
        # Format for visualization
        return {
            "success": True,
            "data": {
                "title": f"ARGO Profile Analysis - {len(profiles_data)} profiles",
                "summary": f"Vertical profile analysis of {len(profiles_data)} ARGO measurements",
                "display_components": ["profiles", "map", "table"],
                "profiles": {
                    "type": "vertical",
                    "data": profiles_data
                },
                "geospatial": {
                    "type": "points",
                    "features": [
                        {
                            "wmo_id": p["wmo_id"],
                            "latitude": p["latitude"],
                            "longitude": p["longitude"],
                            "profile_date": p["profile_date"],
                            "float_category": p["float_category"]
                        }
                        for p in profiles_data if p["latitude"] and p["longitude"]
                    ]
                },
                "table": {
                    "columns": ["WMO ID", "Date", "Latitude", "Longitude", "Category"],
                    "rows": [
                        [
                            p["wmo_id"],
                            p["profile_date"][:10] if p["profile_date"] else "",
                            f"{p['latitude']:.2f}" if p["latitude"] else "",
                            f"{p['longitude']:.2f}" if p["longitude"] else "",
                            p["float_category"]
                        ]
                        for p in profiles_data
                    ]
                },
                "export_data": {
                    "format_options": ["csv", "json", "netcdf"],
                    "raw_data": profiles_data[:10],  # Limit for performance
                    "metadata": {
                        "total_profiles": len(profiles_data),
                        "parameters": list(profiles_data[0]["measurements"].keys()) if profiles_data else []
                    }
                }
            }
        }
    
    def _process_geographic_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for geographic/map visualizations"""
        features = []
        
        for row in raw_results:
            if row.get('latitude') and row.get('longitude'):
                feature = {
                    "wmo_id": row.get('wmo_id'),
                    "latitude": float(row['latitude']),
                    "longitude": float(row['longitude']),
                    "profile_date": self._format_datetime(row.get('profile_date')),
                    "float_category": row.get('float_category', 'Core'),
                    "cycle_number": row.get('cycle_number'),
                    "distance_km": row.get('distance_km')  # For nearest float queries
                }
                features.append(feature)
        
        # Calculate center and bounds
        if features:
            lats = [f['latitude'] for f in features]
            lons = [f['longitude'] for f in features]
            center = {
                "lat": sum(lats) / len(lats),
                "lon": sum(lons) / len(lons)
            }
            bounds = {
                "north": max(lats),
                "south": min(lats),
                "east": max(lons),
                "west": min(lons)
            }
        else:
            center = {"lat": 15, "lon": 70}
            bounds = {"north": 30, "south": -10, "east": 100, "west": 40}
        
        return {
            "success": True,
            "data": {
                "title": f"Geographic Distribution - {len(features)} floats",
                "summary": f"Spatial distribution of {len(features)} ARGO floats",
                "display_components": ["map", "table"],
                "geospatial": {
                    "type": "points",
                    "features": features,
                    "center": center,
                    "bounds": bounds
                },
                "table": {
                    "columns": ["WMO ID", "Latitude", "Longitude", "Date", "Distance (km)"],
                    "rows": [
                        [
                            f["wmo_id"],
                            f"{f['latitude']:.3f}",
                            f"{f['longitude']:.3f}",
                            f["profile_date"][:10] if f["profile_date"] else "",
                            f"{f['distance_km']:.1f}" if f.get('distance_km') else ""
                        ]
                        for f in features
                    ]
                },
                "export_data": {
                    "format_options": ["csv", "geojson", "kml"],
                    "raw_data": features[:100]
                }
            }
        }
    
    def _process_trajectory_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for trajectory visualization"""
        # Group by float ID
        float_groups = {}
        for row in raw_results:
            wmo_id = row.get('wmo_id')
            if wmo_id and row.get('latitude') and row.get('longitude'):
                if wmo_id not in float_groups:
                    float_groups[wmo_id] = []
                float_groups[wmo_id].append(row)
        
        trajectories = {}
        for wmo_id, points in float_groups.items():
            # Sort by date
            points.sort(key=lambda x: x.get('profile_date') or '')
            
            trajectory_points = [
                {
                    "lat": float(p['latitude']),
                    "lon": float(p['longitude']),
                    "date": self._format_datetime(p.get('profile_date')),
                    "cycle": p.get('cycle_number')
                }
                for p in points
            ]
            
            trajectories[wmo_id] = {
                "wmo_id": wmo_id,
                "path": trajectory_points,
                "point_count": len(trajectory_points),
                "duration_days": self._calculate_duration(trajectory_points),
                "total_distance_km": self._calculate_path_distance(trajectory_points)
            }
        
        # Format for single or multiple trajectories
        if len(trajectories) == 1:
            trajectory_data = list(trajectories.values())[0]
        else:
            trajectory_data = {"floats": list(trajectories.values())}
        
        return {
            "success": True,
            "data": {
                "title": f"Float Trajectory - {len(trajectories)} float(s)",
                "summary": f"Trajectory analysis for {len(trajectories)} ARGO float(s)",
                "display_components": ["map", "trajectory", "table"],
                "trajectory": trajectory_data,
                "geospatial": {
                    "type": "trajectory",
                    "trajectories": list(trajectories.values())
                },
                "export_data": {
                    "format_options": ["csv", "geojson", "gpx"],
                    "raw_data": list(trajectories.values())
                }
            }
        }
    
    def _process_statistical_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for statistical analysis"""
        # This is already handled well by MCP for comparisons
        # For direct SQL, provide basic statistics
        
        stats = {}
        numeric_cols = ['latitude', 'longitude']
        
        for col in numeric_cols:
            values = [float(row[col]) for row in raw_results if row.get(col)]
            if values:
                stats[col] = {
                    "mean": np.mean(values),
                    "std": np.std(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values)
                }
        
        return {
            "success": True,
            "data": {
                "title": f"Statistical Analysis - {len(raw_results)} records",
                "summary": f"Statistical summary of {len(raw_results)} records",
                "display_components": ["statistics", "table"],
                "statistics": {
                    "type": "summary",
                    "metrics": stats,
                    "record_count": len(raw_results)
                },
                "table": {
                    "columns": list(raw_results[0].keys()) if raw_results else [],
                    "rows": [list(row.values())[:10] for row in raw_results[:20]]  # Limit display
                },
                "export_data": {
                    "format_options": ["csv", "json"],
                    "raw_data": raw_results[:100]
                }
            }
        }
    
    def _process_time_series_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for time series visualization"""
        # Group by date
        time_series = []
        
        for row in raw_results:
            if row.get('profile_date'):
                # Extract surface values if arrays present
                temp = self._extract_array_data(row.get('temperature_celsius', []))
                sal = self._extract_array_data(row.get('salinity_psu', []))
                
                point = {
                    "datetime": self._format_datetime(row['profile_date']),
                    "wmo_id": row.get('wmo_id'),
                    "value": temp[0] if temp else None,
                    "parameter": "temperature",
                    "depth": 0
                }
                time_series.append(point)
        
        # Sort by date
        time_series.sort(key=lambda x: x['datetime'])
        
        return {
            "success": True,
            "data": {
                "title": f"Time Series Analysis - {len(time_series)} points",
                "summary": f"Temporal analysis of {len(time_series)} data points",
                "display_components": ["timeseries", "table"],
                "timeseries": {
                    "type": "parameter_evolution",
                    "data": time_series
                },
                "export_data": {
                    "format_options": ["csv", "json"],
                    "raw_data": time_series[:100]
                }
            }
        }
    
    def _process_comparative_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for comparative analysis"""
        # Delegate to profile processing for now
        return self._process_profile_data(raw_results, query_metadata)
    
    def _process_general_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for general display"""
        # Handle different result structures
        if not raw_results:
            return self._create_empty_response(query_metadata)
        
        # Ensure raw_results is a list
        if not isinstance(raw_results, list):
            raw_results = [raw_results]
        
        # Check if first element exists and is a dict
        if len(raw_results) == 0 or not isinstance(raw_results[0], dict):
            print(f"Unexpected raw_results structure: {type(raw_results)}, length: {len(raw_results)}")
            return self._create_empty_response(query_metadata)
        
        # Get columns from first row
        columns = list(raw_results[0].keys())
        
        # Limit columns for display
        display_columns = [c for c in columns if not c.endswith('_qc')][:10]
        
        rows = []
        for row in raw_results[:100]:  # Limit rows
            row_data = []
            for col in display_columns:
                val = row.get(col)
                if isinstance(val, (list, dict)):
                    row_data.append(str(val)[:50])  # Truncate long values
                else:
                    row_data.append(str(val) if val is not None else "")
            rows.append(row_data)
        
        return {
            "success": True,
            "data": {
                "title": f"Query Results - {len(raw_results)} records",
                "summary": f"Retrieved {len(raw_results)} records",
                "display_components": ["table"],
                "table": {
                    "columns": display_columns,
                    "rows": rows
                },
                "export_data": {
                    "format_options": ["csv", "json"],
                    "raw_data": raw_results[:100],
                    "metadata": {
                        "total_records": len(raw_results),
                        "columns": columns
                    }
                }
            }
        }
    
    def _extract_array_data(self, array_field, dtype=float):
        """Extract and clean array data from PostgreSQL array field"""
        if not array_field:
            return []
        
        try:
            # Handle different array formats from Supabase
            if isinstance(array_field, str):
                # Remove curly braces and split
                cleaned = array_field.strip('{}[]')
                if not cleaned:
                    return []
                # Split by comma
                array_field = [x.strip() for x in cleaned.split(',')]
            elif isinstance(array_field, (list, tuple)):
                # Already an array
                pass
            else:
                print(f"Unknown array format: {type(array_field)}")
                return []
            
            # Convert to specified dtype
            cleaned_data = []
            for val in array_field:
                try:
                    if val is not None and str(val).strip() not in ['null', 'nan', '', 'NULL']:
                        cleaned_val = dtype(val)
                        if not (dtype == float and np.isnan(cleaned_val)):
                            cleaned_data.append(cleaned_val)
                except (ValueError, TypeError) as e:
                    continue
            
            return cleaned_data
            
        except Exception as e:
            print(f"Error extracting array data: {e}")
            print(f"Array field type: {type(array_field)}")
            print(f"Array field sample: {str(array_field)[:100]}")
            return []
    
    def _format_datetime(self, dt) -> str:
        """Format datetime for JSON serialization"""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
    
    def _calculate_duration(self, trajectory_points):
        """Calculate duration in days between first and last point"""
        if len(trajectory_points) < 2:
            return 0
        try:
            first_date = datetime.fromisoformat(trajectory_points[0]['date'].replace('+00:00', ''))
            last_date = datetime.fromisoformat(trajectory_points[-1]['date'].replace('+00:00', ''))
            return (last_date - first_date).days
        except:
            return 0
    
    def _calculate_path_distance(self, trajectory_points):
        """Calculate approximate total distance of trajectory"""
        if len(trajectory_points) < 2:
            return 0
        
        total_distance = 0
        for i in range(len(trajectory_points) - 1):
            lat1, lon1 = trajectory_points[i]['lat'], trajectory_points[i]['lon']
            lat2, lon2 = trajectory_points[i+1]['lat'], trajectory_points[i+1]['lon']
            
            # Haversine formula (approximate)
            distance = 111.12 * np.sqrt((lat2-lat1)**2 + ((lon2-lon1) * np.cos(np.radians(lat1)))**2)
            total_distance += distance
        
        return round(total_distance, 2)
    
    def _create_empty_response(self, query_metadata: Dict) -> Dict[str, Any]:
        """Create empty response structure"""
        return {
            "success": True,
            "data": {
                "title": "No Results Found",
                "summary": "Query returned no matching records",
                "display_components": ["message"],
                "message": "No data found matching your query criteria.",
                "export_data": {
                    "format_options": [],
                    "raw_data": []
                }
            }
        }
    
    def _create_error_response(self, error_message: str, query_metadata: Dict) -> Dict[str, Any]:
        """Create error response structure"""
        return {
            "success": False,
            "error": error_message,
            "data": {
                "title": "Processing Error",
                "summary": f"Error: {error_message}",
                "display_components": ["error"],
                "error_message": error_message
            }
        }
    
    def _create_comparison_data(self, data):
        """Create comparison data structure for MCP tool results"""
        # This is called by tool_factory for profile comparisons
        if not data:
            return {}
        
        return {
            "profiles_compared": len(data),
            "comparison_type": "multi_float",
            "statistics": self._calculate_comparison_stats(data)
        }
    
    def _calculate_comparison_stats(self, data):
        """Calculate statistics for comparison"""
        stats = {}
        # Add comparison logic here as needed
        return stats