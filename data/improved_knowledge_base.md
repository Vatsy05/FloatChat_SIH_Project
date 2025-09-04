# FloatChat RAG Knowledge Base

This document serves as the central knowledge source for the FloatChat AI. Its purpose is to provide the necessary context for a Large Language Model (LLM) to translate user questions into precise and efficient PostgreSQL queries against the ARGO float database.

---

## 1. Database Architecture Overview

### Database Structure
The database consists of two primary tables within the `public` schema:

- **`public.argo_floats`** - Static metadata about each unique ARGO float
- **`public.argo_profiles`** - Scientific measurements from individual dives/profiles

### Table Relationships
- Each float is uniquely identified by its `wmo_id` (Primary Key in `argo_floats`)
- The `argo_profiles` table links to `argo_floats` via a many-to-one relationship on `wmo_id`
- Each profile represents a single dive cycle performed by a float

---

## 2. Schema Reference

### 2.1 Float Metadata Table: `public.argo_floats`

Contains immutable metadata about each ARGO float.

| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `wmo_id` | `INTEGER` | **Primary Key.** Unique 7-digit World Meteorological Organization identifier |
| `deployment_date` | `TIMESTAMP` | Full timestamp of initial ocean deployment |
| `float_type` | `VARCHAR` | Hardware model/platform (e.g., 'APEX', 'PROVOR', 'NAVIS_A') |
| `institution` | `VARCHAR` | Managing organization/data center (e.g., 'INCOIS', 'CSIRO', 'AOML') |
| `float_category` | `VARCHAR(10)` | The assigned category of the float: 'Core' or 'BGC'. |

### 2.2 Profile Data Table: `public.argo_profiles`

Contains all scientific measurements from float dive cycles.

#### Core Identification Columns
| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `profile_id` | `SERIAL` | **Primary Key.** Auto-incrementing unique identifier |
| `wmo_id` | `INTEGER` | **Foreign Key.** Links to float in `argo_floats` table |
| `cycle_number` | `INTEGER` | Dive number for the float (`wmo_id` + `cycle_number` = unique) |

#### Temporal & Spatial Columns
| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `profile_date` | `TIMESTAMP` | Precise date/time of profile measurement |
| `latitude` | `REAL` | Geographical latitude (decimal degrees, North positive) |
| `longitude` | `REAL` | Geographical longitude (decimal degrees, East positive) |

#### Data Classification Columns
| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `float_category` | `VARCHAR(10)` | **Critical filter:** 'Core' (Temp/Salinity) or 'BGC' (Bio-Geo-Chemical) |
| `data_mode` | `CHAR(1)` | Quality status: 'D' (Delayed-Mode, verified) or 'R' (Real-Time, raw) |

#### Core Measurement Arrays
| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `pressure_dbar` | `REAL[]` | Pressure measurements (decibars) - vertical ocean dimension |
| `temperature_celsius` | `REAL[]` | Temperature measurements (°C) |
| `salinity_psu` | `REAL[]` | Salinity measurements (Practical Salinity Units) |

#### BGC Measurement Arrays
*Available only for 'BGC' category floats. Empty arrays `{}` for 'Core' floats.*

| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `doxy_micromol_per_kg` | `REAL[]` | Dissolved Oxygen measurements |
| `chla_microgram_per_l` | `REAL[]` | Chlorophyll-a measurements (phytoplankton biomass proxy) |
| `nitrate_micromol_per_kg` | `REAL[]` | Nitrate concentration measurements |

#### Quality Control Arrays
| Column Name | Data Type | Description |
|-------------|-----------|-------------|
| `pressure_qc` | `INTEGER[]` | Quality control flags corresponding to each `pressure_dbar` measurement. |
| `temperature_qc`| `INTEGER[]` | Quality control flags corresponding to each `temperature_celsius` measurement. |
| `salinity_qc` | `INTEGER[]` | Quality control flags corresponding to each `salinity_psu` measurement. |
| `doxy_qc` | `INTEGER[]` | Quality control flags for `doxy_micromol_per_kg`. |
| `chla_qc` | `INTEGER[]` | Quality control flags for `chla_microgram_per_l`. |
| `nitrate_qc` | `INTEGER[]` | Quality control flags for `nitrate_micromol_per_kg`. |


---

## 3. Natural Language to SQL Translation

### 3.1 Geographic Regions 🗺️

#### Pre-defined Regional Boundaries

```sql
-- Arabian Sea
WHERE latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75

-- Bay of Bengal  
WHERE latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100

-- Near Equator
WHERE latitude BETWEEN -5 AND 5

-- Indian Ocean (broad)
WHERE latitude BETWEEN -40 AND 30 AND longitude BETWEEN 20 AND 120
```

### 3.2 Temporal References 🕰️

*Based on fixed reference date: August 30, 2025*

#### Common Time Periods
| User Term | Time Range | SQL Condition |
|-----------|------------|---------------|
| "last 6 months" | March 1, 2025 - Present | `profile_date >= '2025-03-01'` |
| "last year" | Calendar year 2024 | `profile_date >= '2024-01-01' AND profile_date < '2025-01-01'` |
| "in March 2023" | March 2023 only | `profile_date >= '2023-03-01' AND profile_date < '2023-04-01'` |

### 3.3 Domain Terminology 🧪

#### Float Categories
| User Terms | Technical Meaning | SQL Condition |
|------------|-------------------|---------------|
| "BGC", "Bio-Geo-Chemical floats", "floats with BGC sensors" | Floats with biochemical sensors | `float_category = 'BGC'` |
| "Core float", "standard float", "regular float" | Standard temperature/salinity floats | `float_category = 'Core'` |

#### BGC Parameters
| User Terms | Technical Parameter | SQL Column |
|------------|-------------------|-------------|
| "oxygen", "dissolved oxygen", "DOXY" | Dissolved Oxygen | `doxy_micromol_per_kg` |
| "chlorophyll", "phytoplankton", "CHLA" | Chlorophyll-a | `chla_microgram_per_l` |
| "nitrate", "NITRATE" | Nitrate concentration | `nitrate_micromol_per_kg` |

---

## 4. SQL Implementation Patterns

### 4.1 Array Data Handling

#### Checking for Valid Array Data
Use `array_length()` function to ensure arrays contain data:

```sql
-- Check for valid temperature data
WHERE array_length(temperature_celsius, 1) > 0
```

#### Accessing Array Elements
```sql
-- Surface temperature (first element)
temperature_celsius[1]

-- All temperature measurements
temperature_celsius
```

#### BGC Data Patterns
```sql
-- BGC parameters only exist for BGC floats
WHERE float_category = 'BGC' 
  AND array_length(doxy_micromol_per_kg, 1) > 0
  AND array_length(chla_microgram_per_l, 1) > 0
```

### 4.2 Data Quality Filtering

#### Prefer High-Quality Data
```sql
-- Prioritize delayed-mode (verified) data
WHERE data_mode = 'D'

-- Include both modes if necessary
WHERE data_mode IN ('D', 'R')
```

### 4.3 Quality Control (QC) Flag Definitions
The `*_qc` columns contain integer flags for each measurement. The primary values are:
- **`0`**: No QC was performed.
- **`1`**: Good data. (Highest quality)
- **`2`**: Probably good data.
- **`3`**: Probably bad data.
- **`4`**: Bad data. (Should be ignored)
- **`8`**: Interpolated value (estimated, not measured).
- **`9`**: Missing value.

- **QC Filtering:** To search for a specific QC flag within an array, use the PostgreSQL `ANY` operator.
  - **Example:** `WHERE 1 = ANY(temperature_qc)` finds profiles with at least one good temperature reading.


---

## 5. Common Query Templates

### 5.1 Profile Retrieval

#### **Pattern:** Show [parameter] profiles [location] [time]
```sql
-- Template
SELECT wmo_id, cycle_number, profile_date, pressure_dbar, [parameter_array]
FROM public.argo_profiles 
WHERE [geographic_condition]
  AND [temporal_condition]
  AND array_length([parameter_array], 1) > 0
ORDER BY profile_date DESC
LIMIT [reasonable_number];

-- Example: "Show salinity profiles in Arabian Sea for March 2023"
SELECT wmo_id, cycle_number, profile_date, pressure_dbar, salinity_psu
FROM public.argo_profiles 
WHERE latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75
  AND profile_date >= '2023-03-01' AND profile_date < '2023-04-01'
  AND array_length(salinity_psu, 1) > 0
ORDER BY profile_date DESC
LIMIT 50;
```

### 5.2 Statistical Analysis

#### **Pattern:** Average/mean [parameter] [location] [time]
```sql
-- Template
SELECT AVG([parameter_array][1]) AS average_surface_[parameter]
FROM public.argo_profiles 
WHERE [geographic_condition]
  AND [temporal_condition]
  AND array_length([parameter_array], 1) > 0;

-- Example: "Average surface temperature in Bay of Bengal last year"
SELECT AVG(temperature_celsius[1]) AS average_surface_temperature
FROM public.argo_profiles 
WHERE latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100
  AND profile_date >= '2024-01-01' AND profile_date < '2025-01-01'
  AND array_length(temperature_celsius, 1) > 0;
```

### 5.3 BGC Comparison

#### **Pattern:** Compare BGC parameters [location] [time]
```sql
-- Template for multi-parameter BGC analysis
SELECT profile_date, latitude, longitude,
       doxy_micromol_per_kg[1] AS surface_oxygen,
       chla_microgram_per_l[1] AS surface_chlorophyll,
       nitrate_micromol_per_kg[1] AS surface_nitrate
FROM public.argo_profiles 
WHERE float_category = 'BGC'
  AND [geographic_condition]
  AND [temporal_condition]
  AND array_length(doxy_micromol_per_kg, 1) > 0
ORDER BY profile_date DESC;
```

### 5.4 Cross-Table Analysis

#### **Pattern:** Institution/float type analysis
```sql
-- Template
SELECT f.[metadata_column], COUNT(DISTINCT p.wmo_id) AS float_count
FROM public.argo_profiles p
JOIN public.argo_floats f ON p.wmo_id = f.wmo_id
WHERE [filter_conditions]
GROUP BY f.[metadata_column]
ORDER BY float_count DESC;

-- Example: "Which institution has most BGC floats?"
SELECT f.institution, COUNT(DISTINCT p.wmo_id) AS bgc_float_count
FROM public.argo_profiles p
JOIN public.argo_floats f ON p.wmo_id = f.wmo_id
WHERE p.float_category = 'BGC'
GROUP BY f.institution
ORDER BY bgc_float_count DESC
LIMIT 10;
```

### 5.5 Trajectory Analysis

#### **Pattern:** Float path/trajectory
```sql
-- Template
SELECT latitude, longitude, profile_date, cycle_number
FROM public.argo_profiles 
WHERE wmo_id = [float_id]
ORDER BY cycle_number ASC;

-- Example: "Show path of float 1900722"
SELECT latitude, longitude, profile_date, cycle_number
FROM public.argo_profiles 
WHERE wmo_id = 1900722
ORDER BY cycle_number ASC;
```

---


## 6. Query Examples by Use Case

### 6.1 Basic Data Retrieval

#### **User Question:** *"Show me salinity profiles near the equator in March 2023"*

**Requirements:** Geographic filtering + temporal filtering + data validation

```sql
SELECT 
    wmo_id, 
    cycle_number, 
    pressure_dbar, 
    salinity_psu 
FROM public.argo_profiles 
WHERE latitude BETWEEN -5 AND 5 
    AND profile_date >= '2023-03-01' 
    AND profile_date < '2023-04-01' 
    AND array_length(salinity_psu, 1) > 0 
LIMIT 10;
```

### 6.2 Multi-Parameter Analysis

#### **User Question:** *"Compare BGC parameters in the Arabian Sea for the last 6 months"*

**Requirements:** BGC filtering + geographic filtering + temporal filtering

```sql
SELECT 
    profile_date, 
    doxy_micromol_per_kg, 
    chla_microgram_per_l, 
    nitrate_micromol_per_kg 
FROM public.argo_profiles 
WHERE float_category = 'BGC' 
    AND latitude BETWEEN 8 AND 30 
    AND longitude BETWEEN 50 AND 75 
    AND profile_date >= '2025-03-01' 
ORDER BY profile_date;
```

### 6.3 Statistical Analysis

#### **User Question:** *"What is the average surface temperature in the Bay of Bengal for the last year?"*

**Requirements:** Geographic filtering + temporal filtering + aggregation + array indexing

```sql
SELECT AVG(temperature_celsius[1]) AS average_surface_temperature 
FROM public.argo_profiles 
WHERE latitude BETWEEN 5 AND 22 
    AND longitude BETWEEN 80 AND 100 
    AND profile_date >= '2024-01-01' 
    AND profile_date < '2025-01-01' 
    AND array_length(temperature_celsius, 1) > 0;
```

### 6.4 Comparative Analysis Between Regions

#### **User Question:** *"Compare surface temperature between Arabian Sea and Bay of Bengal"*

**Requirements:** For comparing a statistic between two or more regions, the most efficient method is to use a `CASE` statement inside a `GROUP BY` clause. This creates virtual regions and calculates the aggregate for each in a single query.

```sql
  SELECT
    CASE
      WHEN (latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75) THEN 'Arabian Sea'
      WHEN (latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100) THEN 'Bay of Bengal'
    END AS region,
    AVG(temperature_celsius[1]) as avg_surface_temp
  FROM public.argo_profiles
  WHERE
    (
      (latitude BETWEEN 8 AND 30 AND longitude BETWEEN 50 AND 75) OR
      (latitude BETWEEN 5 AND 22 AND longitude BETWEEN 80 AND 100)
    )
    AND temperature_celsius IS NOT NULL AND array_length(temperature_celsius, 1) > 0
  GROUP BY region;
```

### 6.5 Cross-Table Analysis

#### **User Question:** *"Which institution has deployed the most BGC floats?"*

**Requirements:** JOIN operation + BGC filtering + grouping + counting

```sql
SELECT 
    f.institution, 
    COUNT(DISTINCT p.wmo_id) AS bgc_float_count 
FROM public.argo_profiles AS p 
JOIN public.argo_floats AS f ON p.wmo_id = f.wmo_id 
WHERE p.float_category = 'BGC' 
GROUP BY f.institution 
ORDER BY bgc_float_count DESC 
LIMIT 10;
```

### 6.6 Trajectory Analysis

#### **User Question:** *"Show me the complete path of float 1900722"*

**Requirements:** Single float filtering + temporal ordering + trajectory data

```sql
SELECT 
    latitude, 
    longitude, 
    profile_date 
FROM public.argo_profiles 
WHERE wmo_id = 1900722 
ORDER BY cycle_number ASC;
```

---

## 7. Critical Implementation Rules

### 7.1 Data Validation (ALWAYS REQUIRED)
```sql
-- For any array usage, ALWAYS include:
AND array_length([array_name], 1) > 0
```

### 7.2 Result Limiting
```sql
-- For large datasets, include reasonable limits:
LIMIT 100  -- for data exploration
LIMIT 10   -- for examples/samples
LIMIT 1000 -- for analysis (max recommended)
```

### 7.3 Quality Preference
```sql
-- When quality matters, prefer:
WHERE data_mode = 'D'  -- Delayed mode (verified)

-- When coverage matters more:
WHERE data_mode IN ('D', 'R')  -- Include real-time
```

### 7.4 BGC Data Rules
- BGC parameters only exist when `float_category = 'BGC'`
- Core floats have empty arrays `{}` for BGC parameters
- Always filter by `float_category = 'BGC'` when querying BGC parameters

### 7.5 Performance Optimization
- Use specific date ranges rather than open-ended queries
- Include geographic bounds for regional queries  
- Use appropriate indexes (assume they exist on key columns)
- Avoid `SELECT *` for large result sets

---

## 8. Best Practices Summary

### Query Optimization
- Always use `array_length()` to validate array data before processing
- Prefer `data_mode = 'D'` for high-quality analysis
- Use appropriate LIMIT clauses for large result sets
- Order results logically (by date, cycle, etc.)

### Data Validation
- Check for non-empty arrays before accessing measurement data
- Consider data quality flags when precision is critical
- Be aware that BGC parameters are empty for 'Core' floats

### Geographic Queries
- Use pre-defined bounding boxes for named regions
- Remember longitude conventions (East is positive)
- Consider seasonal/temporal aspects of oceanographic phenomena