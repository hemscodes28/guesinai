"""
==========================================================
Continuous Wildfire Spread Prediction Model
Author : Hemkumar R
Dataset : attto_2014.csv

Features
--------
✔ Continuous wildfire spread
✔ Dynamic weather updates
✔ Wind-driven propagation
✔ Continuous latitude & longitude prediction
✔ Fire centroid tracking
✔ Burned area estimation
✔ Fire arrival time map
✔ Animation support
==========================================================
"""

import numpy as np
import pandas as pd

from scipy.ndimage import gaussian_filter

from math import radians
from math import degrees
from math import cos
from math import sin
from math import atan2
from math import sqrt

# ==========================================================
# EARTH CONSTANTS
# ==========================================================

EARTH_RADIUS = 6371000.0      # metres

# Cell states

UNBURNED = 0
BURNING = 1
BURNED = 2

# ==========================================================
# 8-DIRECTION FIRE SPREAD
# ==========================================================

DIRECTIONS = [

    (-1,-1),
    (-1,0),
    (-1,1),

    (0,-1),
    (0,1),

    (1,-1),
    (1,0),
    (1,1)

]
# ==========================================================
# LATITUDE <-> METRE CONVERSION
# ==========================================================

def latlon_to_xy(lat, lon, ref_lat, ref_lon):

    lat = np.asarray(lat)
    lon = np.asarray(lon)

    dlat = np.radians(lat - ref_lat)
    dlon = np.radians(lon - ref_lon)

    x = dlon * EARTH_RADIUS * np.cos(np.radians(ref_lat))
    y = dlat * EARTH_RADIUS

    return x, y


def xy_to_latlon(x, y, ref_lat, ref_lon):

    x = np.asarray(x)
    y = np.asarray(y)

    lat = ref_lat + np.degrees(y / EARTH_RADIUS)

    lon = ref_lon + np.degrees(
        x / (EARTH_RADIUS * np.cos(np.radians(ref_lat)))
    )

    return lat, lon
# ==========================================================
# WEATHER LOADER
# ==========================================================

def load_weather(csv_path):

    """
    Load ATTO weather dataset.

    Required Columns

    timestamp
    temperature_C
    humidity_percent
    windspeed_mps
    wind_direction_deg
    vegetation_index
    """

    weather = pd.read_csv(
        csv_path,
        parse_dates=["timestamp"]
    )

    weather = weather.sort_values("timestamp")

    weather = weather.reset_index(drop=True)

    return weather

# ==========================================================
# WEATHER LOOKUP
# ==========================================================

def get_weather(weather_df, current_time):

    """
    Returns nearest weather record
    for the current simulation time.
    """

    current_time = pd.Timestamp(current_time)

    day_start = weather_df.timestamp.iloc[0].normalize()

    time_of_day = current_time - current_time.normalize()

    wrapped_time = day_start + time_of_day

    idx = (
        weather_df.timestamp - wrapped_time
    ).abs().idxmin()

    return weather_df.loc[idx]
# ==========================================================
# FIRE STATISTICS
# ==========================================================

def calculate_distance(x1, y1, x2, y2):

    return np.sqrt((x2-x1)**2 + (y2-y1)**2)


def calculate_burn_area(number_of_cells,
                        cell_size):

    """
    Returns burned area in square metres.
    """

    return number_of_cells * (cell_size ** 2)


class FireSpreadSimulator:
    def __init__(self, weather_df):
        self.weather = weather_df

    def run(self, ignition_lat, ignition_lon, start_time, duration_min, dt_min=3):
        # 1. Initialize grid parameters
        N = 50
        cell_size = 30.0  # meters per cell
        
        # Grid state: 0 = UNBURNED, 1 = BURNING, 2 = BURNED
        state = np.zeros((N, N), dtype=int)
        
        # Center cell (25, 25) is the ignition cell
        r_ignite, c_ignite = 25, 25
        state[r_ignite, c_ignite] = 1 # BURNING
        
        # Arrival time map (ignite_t)
        ignite_t = np.full((N, N), float(duration_min), dtype=float)
        ignite_t[r_ignite, c_ignite] = 0.0
        
        # Burn duration in minutes for cells currently burning
        burn_time = np.zeros((N, N), dtype=float)
        
        # Generate a realistic fuel map (using gaussian filter on noise)
        np.random.seed(42)
        raw_noise = np.random.uniform(0.3, 1.0, (N, N))
        fuel = gaussian_filter(raw_noise, sigma=2.0)
        # Normalize between 0.2 and 1.0
        fuel = (fuel - fuel.min()) / (fuel.max() - fuel.min()) * 0.8 + 0.2
        
        # History log for active cells
        history_records = []
        # Centroid log
        centroid_records = []
        
        # Helper: convert cell (r, c) to lat/lon
        def cell_to_latlon(r, c):
            x = (c - c_ignite) * cell_size
            y = (r_ignite - r) * cell_size
            return xy_to_latlon(x, y, ignition_lat, ignition_lon)
            
        # Add initial ignition to history
        init_lat, init_lon = cell_to_latlon(r_ignite, c_ignite)
        history_records.append({
            "t_min": 0.0,
            "lon": init_lon,
            "lat": init_lat
        })
        centroid_records.append({
            "t_min": 0.0,
            "lon": init_lon,
            "lat": init_lat,
            "n_burning": 1,
            "spread_radius_m": 0.0
        })
        
        # Simulation loop
        current_time = pd.Timestamp(start_time)
        t = 0.0
        
        while t < duration_min:
            t += dt_min
            current_time += pd.Timedelta(minutes=dt_min)
            
            # Get weather
            weather_record = get_weather(self.weather, current_time)
            temp = float(weather_record.get('temperature_C', 28.0))
            rh = float(weather_record.get('humidity_percent', 75.0))
            ws = float(weather_record.get('windspeed_mps', 2.5))
            wd = float(weather_record.get('wind_direction_deg', 90.0))
            
            # Temporary state copy to prevent order-of-evaluation bias
            next_state = state.copy()
            
            # Update currently burning cells
            burning_indices = np.argwhere(state == 1)
            for r, c in burning_indices:
                burn_time[r, c] += dt_min
                # Transition to burned if it has been burning for 15+ minutes
                if burn_time[r, c] >= 15.0:
                    next_state[r, c] = 2 # BURNED
                    
            # Spread check from burning cells
            for r, c in burning_indices:
                for dr, dc in DIRECTIONS:
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < N and 0 <= nc < N:
                        if state[nr, nc] == 0 and next_state[nr, nc] == 0:
                            # Distance between cells
                            dist = cell_size if (dr == 0 or dc == 0) else cell_size * np.sqrt(2.0)
                            
                            # Wind alignment
                            # angle from burning cell to neighbor
                            dy = -(nr - r)
                            dx = nc - c
                            angle = degrees(atan2(dx, dy)) % 360.0
                            
                            angle_diff = abs(wd - angle)
                            angle_diff = min(angle_diff, 360.0 - angle_diff)
                            
                            wind_effect = np.exp(np.cos(radians(angle_diff)) * (ws / 5.0))
                            
                            # Fuel, temperature and humidity effects
                            fuel_effect = fuel[nr, nc]
                            temp_factor = 1.0 + 0.03 * (temp - 25.0)
                            rh_factor = max(0.1, 1.0 - (rh - 50.0) * 0.01)
                            
                            # Base ignition probability per minute
                            base_p = 0.05
                            p_ignite = base_p * dt_min * fuel_effect * temp_factor * rh_factor * wind_effect
                            p_ignite = min(0.95, max(0.0, p_ignite))
                            
                            if np.random.random() < p_ignite:
                                next_state[nr, nc] = 1 # BURNING
                                burn_time[nr, nc] = 0.0
                                ignite_t[nr, nc] = t
                                
                                # Add to history
                                n_lat, n_lon = cell_to_latlon(nr, nc)
                                history_records.append({
                                    "t_min": t,
                                    "lon": n_lon,
                                    "lat": n_lat
                                })
            
            state = next_state
            
            # Record centroids for this step
            curr_burning = np.argwhere(state == 1)
            if len(curr_burning) > 0:
                lats = []
                lons = []
                max_dist = 0.0
                for br, bc in curr_burning:
                    clat, clon = cell_to_latlon(br, bc)
                    lats.append(clat)
                    lons.append(clon)
                    
                    # Compute distance from ignition point in meters
                    dist_m = np.sqrt(((bc - c_ignite) * cell_size)**2 + (((r_ignite - br) * cell_size)**2))
                    if dist_m > max_dist:
                        max_dist = dist_m
                        
                centroid_records.append({
                    "t_min": t,
                    "lon": np.mean(lons),
                    "lat": np.mean(lats),
                    "n_burning": len(curr_burning),
                    "spread_radius_m": max_dist
                })
            else:
                # If nothing is burning, copy last or set to 0
                if len(centroid_records) > 0:
                    last = centroid_records[-1].copy()
                    last["t_min"] = t
                    last["n_burning"] = 0
                    centroid_records.append(last)
                else:
                    centroid_records.append({
                        "t_min": t,
                        "lon": ignition_lon,
                        "lat": ignition_lat,
                        "n_burning": 0,
                        "spread_radius_m": 0.0
                    })
                    
        history_df = pd.DataFrame(history_records)
        centroid_df = pd.DataFrame(centroid_records)
        
        return history_df, centroid_df, state, ignite_t, fuel

    
