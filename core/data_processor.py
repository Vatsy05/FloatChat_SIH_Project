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
            
            # Determine processing strategy based on query type
            query_type = query_metadata.get("query_type", "basic")
            
            if query_type == "geographic" or "map" in query_metadata.get("suggested_visualizations", []):
                return self._process_geographic_data(raw_results, query_metadata)
            elif query_type == "profile" or "depth_profile" in query_metadata.get("suggested_visualizations", []):
                return self._process_profile_data(raw_results, query_metadata)
            elif query_type == "time_series" or "time_series" in query_metadata.get("suggested_visualizations", []):
                return self._process_time_series_data(raw_results, query_metadata)
            elif query_type == "comparative":
                return self._process_comparative_data(raw_results, query_metadata)
            elif query_type == "statistical":
                return self._process_statistical_data(raw_results, query_metadata)
            else:
                return self._process_general_data(raw_results, query_metadata)
                
        except Exception as e:
            print(f"❌ Error processing query results: {str(e)}")
            return self._create_error_response(str(e), query_metadata)
    
    def _process_geographic_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for geographic/map visualizations"""
        trajectories = []
        current_positions = []
        deployment_markers = []
        
        # Group by float ID for trajectories
        float_groups = {}
        for row in raw_results:
            wmo_id = row.get('wmo_id')
            if wmo_id:
                if wmo_id not in float_groups:
                    float_groups[wmo_id] = []
                float_groups[wmo_id].append(row)
        
        # Process each float's trajectory
        for wmo_id, float_data in float_groups.items():
            # Sort by date for trajectory
            float_data.sort(key=lambda x: x.get('profile_date') or datetime.min)
            
            # Extract path coordinates
            path_coordinates = []
            for row in float_data:
                if row.get('latitude') and row.get('longitude'):
                    coord_point = {
                        "lat": float(row['latitude']),
                        "lon": float(row['longitude']),
                        "date": self._format_datetime(row.get('profile_date')),
                        "cycle": row.get('cycle_number', 0)
                    }
                    path_coordinates.append(coord_point)
            
            if path_coordinates:
                # Get float metadata (assuming it might be in results or use defaults)
                trajectory = {
                    "wmo_id": wmo_id,
                    "float_type": row.get('float_type', 'Unknown'),
                    "institution": row.get('institution', 'Unknown'),
                    "path_coordinates": path_coordinates,
                    "deployment_location": {
                        "lat": path_coordinates[0]["lat"] if path_coordinates else 0,
                        "lon": path_coordinates[0]["lon"] if path_coordinates else 0
                    },
                    "current_status": "active" if len(path_coordinates) > 1 else "unknown"
                }
                trajectories.append(trajectory)
                
                # Add current position
                if path_coordinates:
                    current_positions.append({
                        "wmo_id": wmo_id,
                        "lat": path_coordinates[-1]["lat"],
                        "lon": path_coordinates[-1]["lon"],
                        "last_profile": path_coordinates[-1]["date"]
                    })
        
        # Calculate bounding box
        all_lats = [pos["lat"] for pos in current_positions]
        all_lons = [pos["lon"] for pos in current_positions]
        
        bounding_box = {
            "north": max(all_lats) if all_lats else 0,
            "south": min(all_lats) if all_lats else 0,
            "east": max(all_lons) if all_lons else 0,
            "west": min(all_lons) if all_lons else 0
        } if all_lats and all_lons else {"north": 0, "south": 0, "east": 0, "west": 0}
        
        # Create GeoJSON features
        geojson_features = {
            "type": "FeatureCollection",
            "features": []
        }
        
        for pos in current_positions:
            feature = {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [pos["lon"], pos["lat"]]
                },
                "properties": {
                    "wmo_id": pos["wmo_id"],
                    "last_profile": pos["last_profile"]
                }
            }
            geojson_features["features"].append(feature)
        
        return {
            "success": True,
            "data": {
                "title": f"ARGO Float Geographic Analysis - {len(trajectories)} floats",
                "summary": f"Geographic analysis of {len(trajectories)} ARGO floats with {len(current_positions)} position records",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["map", "trajectories", "export"],
                "query_results": raw_results,  # Backwards compatibility
                "visualization_data": {
                    "geospatial": {
                        "trajectories": trajectories,
                        "current_positions": current_positions,
                        "deployment_markers": deployment_markers,
                        "regions": {
                            "bounding_box": bounding_box,
                            "ocean_basins": self._identify_ocean_basins(bounding_box),
                            "geographical_features": self._identify_geographic_features(bounding_box)
                        },
                        "geojson_features": geojson_features
                    }
                },
                "execution_stats": {
                    "floats_processed": len(trajectories),
                    "positions_processed": len(current_positions),
                    "execution_time_ms": 0  # Would be filled by calling function
                }
            }
        }
    
    def _process_profile_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for profile visualizations"""
        vertical_profiles = []
        
        for row in raw_results:
            # Extract array data
            pressure = self._extract_array_data(row.get('pressure_dbar', []))
            temperature = self._extract_array_data(row.get('temperature_celsius', []))
            salinity = self._extract_array_data(row.get('salinity_psu', []))
            
            # Extract QC data
            pressure_qc = self._extract_array_data(row.get('pressure_qc', []), dtype=int)
            temperature_qc = self._extract_array_data(row.get('temperature_qc', []), dtype=int)
            salinity_qc = self._extract_array_data(row.get('salinity_qc', []), dtype=int)
            
            # Extract BGC data if available
            doxy = self._extract_array_data(row.get('doxy_micromol_per_kg', []))
            chla = self._extract_array_data(row.get('chla_microgram_per_l', []))
            nitrate = self._extract_array_data(row.get('nitrate_micromol_per_kg', []))
            
            # Extract BGC QC data
            doxy_qc = self._extract_array_data(row.get('doxy_qc', []), dtype=int)
            chla_qc = self._extract_array_data(row.get('chla_qc', []), dtype=int)
            nitrate_qc = self._extract_array_data(row.get('nitrate_qc', []), dtype=int)
            
            # Create profile object
            profile = {
                "wmo_id": row.get('wmo_id'),
                "profile_date": self._format_datetime(row.get('profile_date')),
                "cycle_number": row.get('cycle_number'),
                "position": {
                    "lat": float(row['latitude']) if row.get('latitude') else None,
                    "lon": float(row['longitude']) if row.get('longitude') else None
                },
                "measurements": {
                    "pressure": pressure,
                    "temperature": temperature,
                    "salinity": salinity,
                    "quality_flags": {
                        "pressure_qc": pressure_qc,
                        "temperature_qc": temperature_qc,
                        "salinity_qc": salinity_qc
                    }
                }
            }
            
            # Add BGC parameters if available
            if any([doxy, chla, nitrate]):
                profile["bgc_parameters"] = {
                    "dissolved_oxygen": doxy,
                    "chlorophyll": chla,
                    "nitrate": nitrate,
                    "quality_flags": {
                        "doxy_qc": doxy_qc,
                        "chla_qc": chla_qc,
                        "nitrate_qc": nitrate_qc
                    }
                }
                
                # Calculate derived parameters
                profile["derived_parameters"] = self._calculate_derived_parameters(
                    pressure, temperature, salinity, doxy, chla
                )
            
            vertical_profiles.append(profile)
        
        # Calculate comparison data and statistics
        comparison_data = self._create_comparison_data(vertical_profiles)
        
        return {
            "success": True,
            "data": {
                "title": f"ARGO Profile Analysis - {len(vertical_profiles)} profiles",
                "summary": f"Vertical profile analysis of {len(vertical_profiles)} ARGO measurements",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["profiles", "comparison", "export"],
                "query_results": raw_results,
                "visualization_data": {
                    "profiles": {
                        "vertical_profiles": vertical_profiles,
                        "comparison_data": comparison_data
                    }
                },
                "execution_stats": {
                    "profiles_processed": len(vertical_profiles),
                    "arrays_unpacked": len(vertical_profiles) * 3,  # pressure, temp, salinity
                    "qc_flags_applied": sum(len(p["measurements"]["quality_flags"]["temperature_qc"]) for p in vertical_profiles)
                }
            }
        }
    
    def _process_time_series_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for time series visualizations"""
        # Group data by float for temporal analysis
        float_time_series = {}
        
        for row in raw_results:
            wmo_id = row.get('wmo_id')
            if not wmo_id:
                continue
                
            if wmo_id not in float_time_series:
                float_time_series[wmo_id] = []
            
            # Extract surface values (first element of arrays)
            temperature = self._extract_array_data(row.get('temperature_celsius', []))
            salinity = self._extract_array_data(row.get('salinity_psu', []))
            
            time_point = {
                "date": self._format_datetime(row.get('profile_date')),
                "latitude": float(row['latitude']) if row.get('latitude') else None,
                "longitude": float(row['longitude']) if row.get('longitude') else None,
                "surface_temperature": temperature[0] if temperature else None,
                "surface_salinity": salinity[0] if salinity else None,
                "cycle_number": row.get('cycle_number')
            }
            
            float_time_series[wmo_id].append(time_point)
        
        # Sort each float's data by date
        for wmo_id in float_time_series:
            float_time_series[wmo_id].sort(key=lambda x: x['date'] or '')
        
        # Create time series objects
        parameter_evolution = []
        for wmo_id, time_data in float_time_series.items():
            if time_data:
                evolution = {
                    "wmo_id": wmo_id,
                    "parameter": "sea_surface_temperature",
                    "temporal_data": [
                        {
                            "date": point["date"],
                            "value": point["surface_temperature"],
                            "depth": 5.0  # Assuming surface ~5m
                        }
                        for point in time_data
                        if point["surface_temperature"] is not None
                    ]
                }
                parameter_evolution.append(evolution)
        
        return {
            "success": True,
            "data": {
                "title": f"ARGO Time Series Analysis - {len(parameter_evolution)} float time series",
                "summary": f"Temporal analysis of {len(parameter_evolution)} ARGO floats",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["time_series", "trends", "export"],
                "query_results": raw_results,
                "visualization_data": {
                    "time_series": {
                        "parameter_evolution": parameter_evolution,
                        "regional_aggregates": {},  # Could be computed if needed
                        "anomaly_detection": []  # Could be computed if needed
                    }
                },
                "execution_stats": {
                    "time_series_processed": len(parameter_evolution),
                    "data_points": sum(len(ts["temporal_data"]) for ts in parameter_evolution)
                }
            }
        }
    
    def _process_comparative_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for comparative analysis"""
        # This would implement comparative analysis logic
        # For now, delegate to profile processing with comparison focus
        result = self._process_profile_data(raw_results, query_metadata)
        result["data"]["title"] = f"ARGO Comparative Analysis - {len(raw_results)} records"
        result["data"]["display_components"] = ["comparison", "profiles", "statistics", "export"]
        return result
    
    def _process_statistical_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for statistical analysis"""
        statistics = {}
        
        # Extract numeric columns for statistics
        numeric_columns = ['latitude', 'longitude']
        array_columns = ['temperature_celsius', 'salinity_psu', 'pressure_dbar']
        
        for col in numeric_columns:
            values = [float(row[col]) for row in raw_results if row.get(col) is not None]
            if values:
                statistics[col] = {
                    "count": len(values),
                    "min": min(values),
                    "max": max(values),
                    "mean": sum(values) / len(values),
                    "std": np.std(values) if len(values) > 1 else 0
                }
        
        # Process array columns
        for col in array_columns:
            all_values = []
            for row in raw_results:
                array_data = self._extract_array_data(row.get(col, []))
                all_values.extend(array_data)
            
            if all_values:
                statistics[col] = {
                    "count": len(all_values),
                    "min": min(all_values),
                    "max": max(all_values),
                    "mean": sum(all_values) / len(all_values),
                    "std": np.std(all_values) if len(all_values) > 1 else 0
                }
        
        return {
            "success": True,
            "data": {
                "title": f"ARGO Statistical Analysis - {len(raw_results)} records",
                "summary": f"Statistical analysis of {len(raw_results)} ARGO records",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["statistics", "histograms", "export"],
                "query_results": raw_results,
                "visualization_data": {
                    "statistics": statistics
                },
                "execution_stats": {
                    "records_analyzed": len(raw_results),
                    "statistics_computed": len(statistics)
                }
            }
        }
    
    def _process_general_data(self, raw_results: List[Dict], query_metadata: Dict) -> Dict[str, Any]:
        """Process data for general display"""
        return {
            "success": True,
            "data": {
                "title": f"ARGO Data Query Results - {len(raw_results)} records",
                "summary": f"Query returned {len(raw_results)} ARGO records",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["data_table", "export"],
                "query_results": raw_results,
                "visualization_data": {
                    "general": {
                        "records": raw_results,
                        "column_info": self._analyze_columns(raw_results)
                    }
                },
                "execution_stats": {
                    "records_processed": len(raw_results)
                }
            }
        }
    
    def _extract_array_data(self, array_field, dtype=float):
        """Extract and clean array data from PostgreSQL array field"""
        if not array_field:
            return []
        
        try:
            if isinstance(array_field, str):
                # Parse string representation of array
                array_field = array_field.strip('{}').split(',')
                array_field = [x.strip() for x in array_field if x.strip()]
            
            if not array_field:
                return []
            
            # Convert to specified dtype and filter out invalid values
            cleaned_data = []
            for val in array_field:
                try:
                    if val is not None and str(val).lower() not in ['null', 'nan', '']:
                        cleaned_data.append(dtype(val))
                except (ValueError, TypeError):
                    continue
            
            return cleaned_data
            
        except Exception as e:
            print(f"⚠️ Error extracting array data: {str(e)}")
            return []
    
    def _format_datetime(self, dt) -> str:
        """Format datetime for JSON serialization"""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.isoformat() if hasattr(dt, 'isoformat') else str(dt)
    
    def _calculate_derived_parameters(self, pressure, temperature, salinity, doxy=None, chla=None) -> Dict[str, Any]:
        """Calculate derived oceanographic parameters"""
        derived = {}
        
        try:
            if pressure and temperature:
                # Simple mixed layer depth estimation (temperature gradient)
                if len(temperature) > 10:
                    temp_diff = [abs(temperature[i] - temperature[0]) for i in range(len(temperature))]
                    mld_idx = next((i for i, diff in enumerate(temp_diff) if diff > 0.2), None)
                    if mld_idx and mld_idx < len(pressure):
                        derived["mixed_layer_depth"] = pressure[mld_idx]
                
                # Simple thermocline depth (max temperature gradient)
                if len(temperature) > 5:
                    temp_gradients = [temperature[i] - temperature[i+1] for i in range(len(temperature)-1)]
                    max_grad_idx = temp_gradients.index(max(temp_gradients)) if temp_gradients else 0
                    if max_grad_idx < len(pressure):
                        derived["thermocline_depth"] = pressure[max_grad_idx]
            
            # Chlorophyll maximum depth
            if chla and pressure:
                max_chla_idx = chla.index(max(chla)) if chla else 0
                if max_chla_idx < len(pressure):
                    derived["max_chlorophyll_depth"] = pressure[max_chla_idx]
            
            # Oxygen minimum zone (simplified)
            if doxy and pressure:
                if len(doxy) > 10:
                    min_oxy_val = min(doxy)
                    min_oxy_idx = doxy.index(min_oxy_val)
                    derived["oxygen_minimum_zone"] = {
                        "depth": pressure[min_oxy_idx] if min_oxy_idx < len(pressure) else None,
                        "min_value": min_oxy_val
                    }
        
        except Exception as e:
            print(f"⚠️ Error calculating derived parameters: {str(e)}")
        
        return derived
    
    def _create_comparison_data(self, profiles: List[Dict]) -> Dict[str, Any]:
        """Create comparison data for multiple profiles"""
        if len(profiles) < 2:
            return {}
        
        # Extract all temperature and salinity data for statistics
        all_temps = []
        all_sals = []
        
        for profile in profiles:
            temps = profile["measurements"].get("temperature", [])
            sals = profile["measurements"].get("salinity", [])
            all_temps.extend(temps)
            all_sals.extend(sals)
        
        comparison_data = {}
        
        if all_temps:
            comparison_data["statistical_summary"] = {
                "temperature": {
                    "min": min(all_temps),
                    "max": max(all_temps),
                    "mean": sum(all_temps) / len(all_temps),
                    "std": np.std(all_temps) if len(all_temps) > 1 else 0
                }
            }
        
        if all_sals:
            comparison_data["statistical_summary"]["salinity"] = {
                "min": min(all_sals),
                "max": max(all_sals),
                "mean": sum(all_sals) / len(all_sals),
                "std": np.std(all_sals) if len(all_sals) > 1 else 0
            }
        
        return comparison_data
    
    def _identify_ocean_basins(self, bounding_box: Dict) -> List[str]:
        """Identify ocean basins based on bounding box"""
        basins = []
        
        # Simple logic based on coordinates
        if 40 <= bounding_box["east"] <= 100 and -10 <= bounding_box["north"] <= 30:
            basins.append("Indian Ocean")
        if -90 <= bounding_box["south"] <= -40:
            basins.append("Southern Ocean")
        
        return basins if basins else ["Unknown Ocean"]
    
    def _identify_geographic_features(self, bounding_box: Dict) -> List[str]:
        """Identify geographic features based on bounding box"""
        features = []
        
        # Check for known regions
        for region_name, region_bounds in self.config.REGIONS.items():
            if (region_bounds["lat_min"] <= bounding_box["north"] and 
                region_bounds["lat_max"] >= bounding_box["south"] and
                region_bounds["lon_min"] <= bounding_box["east"] and 
                region_bounds["lon_max"] >= bounding_box["west"]):
                features.append(region_name.replace("_", " ").title())
        
        return features
    
    def _analyze_columns(self, raw_results: List[Dict]) -> Dict[str, Any]:
        """Analyze column structure of results"""
        if not raw_results:
            return {}
        
        sample_row = raw_results[0]
        column_info = {}
        
        for col, val in sample_row.items():
            col_type = type(val).__name__
            is_array = isinstance(val, (list, tuple))
            has_nulls = any(row.get(col) is None for row in raw_results)
            
            column_info[col] = {
                "type": col_type,
                "is_array": is_array,
                "has_nulls": has_nulls,
                "sample_value": str(val)[:50] if val else "NULL"
            }
        
        return column_info
    
    def _create_empty_response(self, query_metadata: Dict) -> Dict[str, Any]:
        """Create empty response structure"""
        return {
            "success": True,
            "data": {
                "title": "No Results Found",
                "summary": "Query returned no matching records",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["message"],
                "query_results": [],
                "visualization_data": {},
                "execution_stats": {
                    "records_processed": 0
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
                "summary": f"Error processing query results: {error_message}",
                "sql_query": query_metadata.get("sql_query", ""),
                "display_components": ["error"],
                "query_results": [],
                "visualization_data": {},
                "execution_stats": {
                    "error": error_message
                }
            }
        }