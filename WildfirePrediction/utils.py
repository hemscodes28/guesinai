# Coordinate & weather helper functions
# Code will be pasted here by the user.
"""
=========================================================
utils.py

Utility functions for Continuous Wildfire Spread Simulator

Author : Hemkumar R

Functions
---------
✔ Latitude / Longitude Conversion
✔ Distance Calculation
✔ Bearing Calculation
✔ Burn Area Calculation
✔ Weather Lookup
✔ Time Conversion
=========================================================
"""

import numpy as np
import pandas as pd

EARTH_RADIUS = 6371000.0  # metres


# ==========================================================
# LATITUDE/LONGITUDE <-> XY
# ==========================================================

def latlon_to_xy(lat, lon, ref_lat, ref_lon):
    """
    Convert Latitude/Longitude into
    local x-y coordinates (metres).
    """

    lat = np.asarray(lat)
    lon = np.asarray(lon)

    dlat = np.radians(lat - ref_lat)
    dlon = np.radians(lon - ref_lon)

    x = dlon * EARTH_RADIUS * np.cos(np.radians(ref_lat))
    y = dlat * EARTH_RADIUS

    return x, y


def xy_to_latlon(x, y, ref_lat, ref_lon):
    """
    Convert local x-y coordinates
    into Latitude/Longitude.
    """

    x = np.asarray(x)
    y = np.asarray(y)

    lat = ref_lat + np.degrees(y / EARTH_RADIUS)

    lon = ref_lon + np.degrees(
        x /
        (
            EARTH_RADIUS *
            np.cos(np.radians(ref_lat))
        )
    )

    return lat, lon


# ==========================================================
# DISTANCE
# ==========================================================

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Haversine Distance
    Returns metres.
    """

    lat1 = np.radians(lat1)
    lon1 = np.radians(lon1)

    lat2 = np.radians(lat2)
    lon2 = np.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        np.sin(dlat / 2) ** 2
        +
        np.cos(lat1)
        * np.cos(lat2)
        * np.sin(dlon / 2) ** 2
    )

    c = 2 * np.arctan2(
        np.sqrt(a),
        np.sqrt(1 - a)
    )

    return EARTH_RADIUS * c


# ==========================================================
# BEARING
# ==========================================================

def calculate_bearing(lat1, lon1, lat2, lon2):
    """
    Bearing between two locations.
    """

    lat1 = np.radians(lat1)
    lat2 = np.radians(lat2)

    dlon = np.radians(lon2 - lon1)

    x = np.sin(dlon) * np.cos(lat2)

    y = (
        np.cos(lat1)
        * np.sin(lat2)
        -
        np.sin(lat1)
        * np.cos(lat2)
        * np.cos(dlon)
    )

    bearing = np.degrees(
        np.arctan2(x, y)
    )

    return (bearing + 360) % 360


# ==========================================================
# FIRE SPEED
# ==========================================================

def fire_speed(distance_m, minutes):
    """
    Fire Spread Speed (m/min)
    """

    if minutes == 0:
        return 0

    return distance_m / minutes


# ==========================================================
# BURN AREA
# ==========================================================

def burn_area(number_of_cells, cell_size):
    """
    Burned Area (square metres)
    """

    return number_of_cells * (cell_size ** 2)


# ==========================================================
# WEATHER LOOKUP
# ==========================================================

def weather_lookup(weather_df, current_time):
    """
    Nearest Weather Record
    """

    current_time = pd.Timestamp(current_time)

    day = weather_df.timestamp.iloc[0].normalize()

    tod = current_time - current_time.normalize()

    wrapped = day + tod

    idx = (
        weather_df.timestamp - wrapped
    ).abs().idxmin()

    return weather_df.loc[idx]


# ==========================================================
# TIME FORMAT
# ==========================================================

def simulation_time(minutes):
    """
    Convert Minutes
    Example:
        130
        ->
        02h 10m
    """

    hours = int(minutes // 60)

    mins = int(minutes % 60)

    return f"{hours:02d}h {mins:02d}m"


# ==========================================================
# RANDOM FUEL MAP
# ==========================================================

def create_uniform_fuel(size, value=1.0):
    """
    Uniform Fuel Map
    """

    return np.full(
        (size, size),
        value,
        dtype=float
    )


# ==========================================================
# NORMALIZE
# ==========================================================

def normalize(data):
    """
    Normalize values between 0 and 1.
    """

    data = np.asarray(data)

    minimum = np.min(data)

    maximum = np.max(data)

    if maximum == minimum:
        return np.zeros_like(data)

    return (data - minimum) / (maximum - minimum)


# ==========================================================
# EXPORT CSV
# ==========================================================

def export_dataframe(df, filename):
    """
    Save dataframe to CSV.
    """

    df.to_csv(
        filename,
        index=False
    )

    print(f"Saved -> {filename}")


# ==========================================================
# LOAD WEATHER
# ==========================================================

def load_weather(csv_file):
    """
    Load Weather Dataset
    """

    weather = pd.read_csv(
        csv_file,
        parse_dates=["timestamp"]
    )

    weather = weather.sort_values(
        "timestamp"
    )

    weather = weather.reset_index(
        drop=True
    )

    return weather


# ==========================================================
# PRINT SIMULATION SUMMARY
# ==========================================================

def print_summary(centroid_df):

    print("\n========== FIRE SUMMARY ==========")

    print("Simulation Steps :", len(centroid_df))

    print("Final Latitude  :", centroid_df.iloc[-1]["lat"])

    print("Final Longitude :", centroid_df.iloc[-1]["lon"])

    if "spread_radius_m" in centroid_df.columns:

        print(
            "Max Radius :",
            centroid_df["spread_radius_m"].max(),
            "m"
        )

    if "n_burning" in centroid_df.columns:

        print(
            "Peak Burning Cells :",
            centroid_df["n_burning"].max()
        )

    print("==================================")