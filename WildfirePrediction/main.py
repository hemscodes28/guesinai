# Runs the complete simulation
# Code will be pasted here by the user.
"""
=========================================================
main.py

Run the Continuous Wildfire Spread Simulation
=========================================================
"""

import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from fire_spread_model import (
    load_weather,
    FireSpreadSimulator
)

# ---------------------------------------------------------
# USER INPUTS
# ---------------------------------------------------------

WEATHER_FILE = "attto_2014.csv"

IGNITION_LAT = -2.145
IGNITION_LON = -59.000

START_TIME = "2014-07-01 12:21:32"

SIMULATION_DURATION = 240      # minutes
TIME_STEP = 3                  # minutes

# ---------------------------------------------------------
# LOAD WEATHER
# ---------------------------------------------------------

print("Loading weather dataset...")

weather = load_weather(WEATHER_FILE)

print("Weather Loaded Successfully")
print(weather.head())

# ---------------------------------------------------------
# CREATE SIMULATOR
# ---------------------------------------------------------

print("\nInitializing Fire Spread Simulator...")

sim = FireSpreadSimulator(weather)

print("Simulator Ready")

# ---------------------------------------------------------
# RUN MODEL
# ---------------------------------------------------------

print("\nRunning Simulation...")

history_df, centroid_df, state, ignite_t, fuel = sim.run(

    ignition_lat=IGNITION_LAT,
    ignition_lon=IGNITION_LON,
    start_time=START_TIME,
    duration_min=SIMULATION_DURATION,
    dt_min=TIME_STEP

)

print("\nSimulation Completed")

# ---------------------------------------------------------
# SAVE RESULTS
# ---------------------------------------------------------

history_df.to_csv(
    "fire_history.csv",
    index=False
)

centroid_df.to_csv(
    "centroid_history.csv",
    index=False
)

print("\nCSV Files Saved")

print("fire_history.csv")
print("centroid_history.csv")

# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------

print("\nHistory Shape :", history_df.shape)
print("Centroid Shape:", centroid_df.shape)

print("\nCentroid Preview")

print(centroid_df.tail())

# ---------------------------------------------------------
# ARRIVAL TIME MAP
# ---------------------------------------------------------

fig, axes = plt.subplots(
    1,
    2,
    figsize=(13,5)
)

image = axes[0].imshow(
    ignite_t,
    origin="upper",
    cmap="inferno"
)

axes[0].contour(
    ignite_t,
    levels=8,
    colors="white",
    linewidths=0.6
)

axes[0].set_title("Fire Arrival Time")

plt.colorbar(
    image,
    ax=axes[0],
    label="Minutes Since Ignition"
)

# ---------------------------------------------------------
# CENTROID PATH
# ---------------------------------------------------------

axes[1].plot(

    centroid_df["lon"],
    centroid_df["lat"],

    "-o",

    color="firebrick",

    linewidth=2,

    markersize=4

)

axes[1].set_xlabel("Longitude")
axes[1].set_ylabel("Latitude")

axes[1].set_title("Fire Centroid Trajectory")

plt.tight_layout()

plt.savefig(
    "fire_arrival_map.png",
    dpi=300
)

plt.show()

print("\nArrival Time Map Saved")

# ---------------------------------------------------------
# FINAL STATISTICS
# ---------------------------------------------------------

print("\n============== FINAL REPORT ==============")

print(f"Total Burning Records : {len(history_df)}")

print(f"Simulation Steps      : {len(centroid_df)}")

print(f"Final Latitude        : {centroid_df.iloc[-1]['lat']:.6f}")

print(f"Final Longitude       : {centroid_df.iloc[-1]['lon']:.6f}")

print(f"Maximum Spread Radius : {centroid_df['spread_radius_m'].max():.2f} m")

print(f"Maximum Burning Cells : {centroid_df['n_burning'].max()}")

print("==========================================")

from visualization import FireVisualizer

viz = FireVisualizer(
    history_df,
    centroid_df,
    ignite_t
)

viz.generate_all()