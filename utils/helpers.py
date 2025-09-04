"""
Utility functions and helpers for ARGO FloatChat AI
"""
import re
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union
import pandas as pd
import numpy as np

def format_sql_query(sql_query: str) -> str:
    """Format SQL query for display"""
    # Basic SQL formatting
    formatted = sql_query.strip()
    
    # Add line breaks for readability
    keywords = ['SELECT', 'FROM', 'WHERE', 'ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'JOIN']
    for keyword in keywords:
        formatted = re.sub(f'\\b{keyword}\\b', f'\n{keyword}', formatted, flags=re.IGNORECASE)
    
    # Clean up extra whitespace
    formatted = re.sub(r'\n\s*\n', '\n', formatted)
    formatted = re.sub(r'^\n', '', formatted)
    
    return formatted

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate text to specified length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse various date string formats"""
    if not date_str:
        return None
    
    date_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%m/%d/%Y",
        "%d/%m/%Y"
    ]
    
    for fmt in date_formats:
        try:
            return datetime.strptime(str(date_str), fmt)
        except ValueError:
            continue
    
    return None

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points using Haversine formula (km)"""
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    r = 6371  # Earth's radius in kilometers
    
    return c * r

def is_in_region(lat: float, lon: float, region_bounds: Dict[str, float]) -> bool:
    """Check if coordinates are within regional boundaries"""
    return (region_bounds["lat_min"] <= lat <= region_bounds["lat_max"] and
            region_bounds["lon_min"] <= lon <= region_bounds["lon_max"])

def extract_surface_value(array_data: List[Union[float, int]], depth_index: int = 0) -> Optional[float]:
    """Extract surface value from depth profile array"""
    if not array_data or len(array_data) <= depth_index:
        return None
    
    try:
        value = array_data[depth_index]
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None

def calculate_mixed_layer_depth(pressure: List[float], temperature: List[float], 
                               threshold: float = 0.2) -> Optional[float]:
    """Calculate mixed layer depth based on temperature threshold"""
    if not pressure or not temperature or len(pressure) != len(temperature):
        return None
    
    if len(temperature) < 2:
        return None
    
    surface_temp = temperature[0]
    
    for i, (pres, temp) in enumerate(zip(pressure[1:], temperature[1:]), 1):
        if abs(temp - surface_temp) > threshold:
            return pres
    
    return None

def quality_control_filter(values: List[float], qc_flags: List[int], 
                          valid_flags: List[int] = [1, 2]) -> List[float]:
    """Filter values based on quality control flags"""
    if not qc_flags:
        return values
    
    filtered_values = []
    for i, (value, qc) in enumerate(zip(values, qc_flags)):
        if qc in valid_flags:
            filtered_values.append(value)
    
    return filtered_values

def generate_cache_key(query: str, parameters: Dict[str, Any]) -> str:
    """Generate cache key for query and parameters"""
    # Create a deterministic string from query and parameters
    cache_string = f"{query}_{json.dumps(parameters, sort_keys=True)}"
    
    # Create MD5 hash for shorter key
    return hashlib.md5(cache_string.encode()).hexdigest()

def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate latitude and longitude values"""
    try:
        lat = float(lat)
        lon = float(lon)
        return -90 <= lat <= 90 and -180 <= lon <= 180
    except (TypeError, ValueError):
        return False

def parse_array_string(array_str: str) -> List[float]:
    """Parse PostgreSQL array string format to Python list"""
    if not array_str:
        return []
    
    # Remove curly braces and split by comma
    array_str = array_str.strip('{}')
    
    if not array_str:
        return []
    
    try:
        # Split and convert to float
        values = []
        for item in array_str.split(','):
            item = item.strip()
            if item and item.lower() not in ['null', 'nan', '']:
                try:
                    values.append(float(item))
                except ValueError:
                    continue
        return values
    except Exception:
        return []

def format_number(value: Union[int, float], decimal_places: int = 2) -> str:
    """Format number for display"""
    if value is None:
        return "N/A"
    
    try:
        if isinstance(value, int):
            return f"{value:,}"
        else:
            return f"{value:,.{decimal_places}f}"
    except (TypeError, ValueError):
        return str(value)

def get_data_quality_summary(qc_flags: List[int]) -> Dict[str, Any]:
    """Generate data quality summary from QC flags"""
    if not qc_flags:
        return {"total": 0, "good": 0, "questionable": 0, "bad": 0, "missing": 0}
    
    qc_counts = {}
    for qc in qc_flags:
        qc_counts[qc] = qc_counts.get(qc, 0) + 1
    
    return {
        "total": len(qc_flags),
        "good": qc_counts.get(1, 0),  # QC flag 1
        "probably_good": qc_counts.get(2, 0),  # QC flag 2
        "questionable": qc_counts.get(3, 0),  # QC flag 3
        "bad": qc_counts.get(4, 0),  # QC flag 4
        "missing": qc_counts.get(9, 0),  # QC flag 9
        "quality_percentage": (qc_counts.get(1, 0) + qc_counts.get(2, 0)) / len(qc_flags) * 100
    }

def detect_outliers(values: List[float], method: str = "iqr", factor: float = 1.5) -> List[bool]:
    """Detect outliers in data using specified method"""
    if not values or len(values) < 4:
        return [False] * len(values)
    
    values_array = np.array(values)
    
    if method == "iqr":
        Q1 = np.percentile(values_array, 25)
        Q3 = np.percentile(values_array, 75)
        IQR = Q3 - Q1
        lower_bound = Q1 - factor * IQR
        upper_bound = Q3 + factor * IQR
        
        return [(v < lower_bound or v > upper_bound) for v in values]
    
    elif method == "zscore":
        mean_val = np.mean(values_array)
        std_val = np.std(values_array)
        
        if std_val == 0:
            return [False] * len(values)
        
        z_scores = np.abs((values_array - mean_val) / std_val)
        return [z > factor for z in z_scores]
    
    else:
        return [False] * len(values)

def interpolate_missing_values(values: List[Optional[float]], 
                              method: str = "linear") -> List[Optional[float]]:
    """Interpolate missing values in array"""
    if not values:
        return values
    
    # Convert to pandas Series for interpolation
    series = pd.Series(values)
    
    if method == "linear":
        interpolated = series.interpolate(method='linear')
    elif method == "polynomial":
        interpolated = series.interpolate(method='polynomial', order=2)
    else:
        interpolated = series.fillna(method='ffill').fillna(method='bfill')
    
    return interpolated.tolist()

def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """Calculate basic statistics for a list of values"""
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None,
            "range": None
        }
    
    values_array = np.array(values)
    
    return {
        "count": len(values),
        "mean": float(np.mean(values_array)),
        "median": float(np.median(values_array)),
        "std": float(np.std(values_array)),
        "min": float(np.min(values_array)),
        "max": float(np.max(values_array)),
        "range": float(np.max(values_array) - np.min(values_array))
    }

def time_ago(date_time: datetime) -> str:
    """Generate human-readable time ago string"""
    now = datetime.now()
    
    if date_time.tzinfo:
        # If datetime is timezone-aware, make now timezone-aware too
        from datetime import timezone
        now = now.replace(tzinfo=timezone.utc)
    
    diff = now - date_time
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years != 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months != 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    else:
        return "Just now"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage"""
    # Remove or replace unsafe characters
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove leading/trailing whitespace and periods
    sanitized = sanitized.strip('. ')
    
    # Limit length
    if len(sanitized) > 255:
        sanitized = sanitized[:255]
    
    # Ensure not empty
    if not sanitized:
        sanitized = "unnamed_file"
    
    return sanitized

def chunk_list(data_list: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split list into chunks of specified size"""
    chunks = []
    for i in range(0, len(data_list), chunk_size):
        chunks.append(data_list[i:i + chunk_size])
    return chunks

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ValueError):
        return default

def format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string"""
    if seconds < 1:
        return f"{seconds * 1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes:.0f}m {remaining_seconds:.0f}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours:.0f}h {minutes:.0f}m"

class DataValidator:
    """Data validation utilities"""
    
    @staticmethod
    def validate_profile_data(profile_data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate profile data structure and return errors"""
        errors = {
            "missing_fields": [],
            "invalid_values": [],
            "array_length_mismatches": []
        }
        
        # Check required fields
        required_fields = ["wmo_id", "measurements"]
        for field in required_fields:
            if field not in profile_data:
                errors["missing_fields"].append(field)
        
        # Check measurements structure
        measurements = profile_data.get("measurements", {})
        if measurements:
            core_params = ["pressure", "temperature", "salinity"]
            arrays_lengths = {}
            
            for param in core_params:
                if param in measurements:
                    param_data = measurements[param]
                    if isinstance(param_data, list):
                        arrays_lengths[param] = len(param_data)
                    else:
                        errors["invalid_values"].append(f"{param} should be a list")
            
            # Check array length consistency
            if arrays_lengths:
                reference_length = list(arrays_lengths.values())[0]
                for param, length in arrays_lengths.items():
                    if length != reference_length:
                        errors["array_length_mismatches"].append(
                            f"{param} length ({length}) doesn't match reference ({reference_length})"
                        )
        
        return errors
    
    @staticmethod
    def validate_coordinates(lat: float, lon: float) -> bool:
        """Validate geographic coordinates"""
        try:
            lat = float(lat)
            lon = float(lon)
            return -90 <= lat <= 90 and -180 <= lon <= 180
        except (TypeError, ValueError):
            return False