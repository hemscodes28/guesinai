import csv
import math
import random
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from PIL import Image

# Path to the ATTO dataset in the workspace
ATTO_CSV_PATH = "c:/Users/Hemkumar Ramesh/Desktop/Guesin/atto_2014.csv"

def get_total_records() -> int:
    """Returns the total number of data records in the ATTO CSV file."""
    try:
        with open(ATTO_CSV_PATH, "r", encoding="utf-8") as f:
            # Subtracted 1 for the header
            return sum(1 for line in f) - 1
    except Exception:
        return 0

def load_atto_record(index: int) -> Dict:
    """
    Reads a single record from the ATTO CSV file by index.
    Derives missing weather parameters (VPD, Solar Radiation, Soil Moisture, Pressure, Rainfall)
    using physical equations and local diurnal variations.
    """
    total = get_total_records()
    if total == 0:
        # Fallback default values if file is missing/empty
        return {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "temperature": 28.5,
            "humidity": 75.0,
            "wind_speed": 8.5,
            "wind_direction": 120.0,
            "vegetation_index": 0.85,
            "vpd": 0.95,
            "solar_radiation": 400.0,
            "soil_moisture": 0.78,
            "atmospheric_pressure": 1011.5,
            "rainfall": 0.0,
            "hour": 12
        }

    # Ensure index is within bounds
    target_idx = max(0, min(total - 1, index))

    record = {}
    with open(ATTO_CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i == target_idx:
                record = row
                break

    # Parse baseline values
    timestamp_str = record.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    try:
        dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
        except ValueError:
            dt = datetime.now()

    hour = dt.hour

    temp = float(record.get("temperature_C", 28.0))
    humidity = float(record.get("humidity_percent", 75.0))
    
    # Convert wind speed from m/s to km/h (1 m/s = 3.6 km/h)
    wind_speed_mps = float(record.get("windspeed_mps", 2.5))
    wind_speed = round(wind_speed_mps * 3.6, 1)
    
    wind_dir = float(record.get("wind_direction_deg", 90.0))
    veg_index = float(record.get("vegetation_index", 0.85))

    # METEOROLOGICAL EQUATIONS DERIVATIONS
    
    # 1. VPD (Vapor Pressure Deficit)
    # Saturated vapor pressure (e_s) in kPa using Tetens equation
    e_s = 0.6108 * math.exp((17.27 * temp) / (temp + 237.3))
    # Actual vapor pressure (e_a) in kPa
    e_a = e_s * (humidity / 100.0)
    # VPD is the difference
    vpd = round(max(0.01, e_s - e_a), 2)

    # 2. Solar Radiation (W/m2)
    # Diurnal solar cycle peaking at 12:00 (midday)
    if 6 <= hour < 18:
        # Solar elevation angle representation
        solar_rad = 950.0 * math.sin(math.pi * (hour - 6) / 12.0)
        # Slight variation for clouds based on humidity
        cloud_attenuation = 1.0 - (humidity / 100.0) * 0.4
        solar_radiation = round(solar_rad * cloud_attenuation, 1)
    else:
        solar_radiation = 0.0

    # 3. Soil Moisture (0.0 to 1.0)
    # Correlates with high relative humidity and high vegetation canopy, decreases with heat/VPD
    soil_m = 0.2 * veg_index + 0.65 * (humidity / 100.0) + 0.05
    # Apply a daily temperature lag effect
    soil_m -= 0.1 * math.sin(math.pi * (hour - 8) / 12.0) if 8 <= hour < 20 else 0.0
    soil_moisture = round(max(0.05, min(1.0, soil_m)), 3)

    # 4. Atmospheric Pressure (hPa)
    # Simulated tropical pressure tide centered around 1012 hPa
    # Standard pressure drops slightly as temperature increases, and shows semi-diurnal tides
    pressure_tide = 1.5 * math.sin(2.0 * math.pi * hour / 12.0)
    temp_effect = -0.06 * (temp - 25.0)
    atmospheric_pressure = round(1011.5 + pressure_tide + temp_effect, 1)

    # 5. Rainfall (mm)
    # Convective rain events are common in late afternoon when humidity is high (> 92%)
    rainfall = 0.0
    if humidity > 92.0:
        if 13 <= hour < 19:  # Afternoon convective storm hours
            # 15% probability of a downpour
            if random.random() < 0.15:
                rainfall = round(random.uniform(2.0, 25.0), 1)
        else:
            # 5% chance of light night showers
            if random.random() < 0.05:
                rainfall = round(random.uniform(0.5, 4.0), 1)

    return {
        "timestamp": timestamp_str,
        "temperature": round(temp, 1),
        "humidity": round(humidity, 1),
        "wind_speed": wind_speed,
        "wind_direction": round(wind_dir, 1),
        "vegetation_index": round(veg_index, 3),
        "vpd": vpd,
        "solar_radiation": solar_radiation,
        "soil_moisture": soil_moisture,
        "atmospheric_pressure": atmospheric_pressure,
        "rainfall": rainfall,
        "hour": hour
    }

def extract_hotspots_from_image(image_path: str, grid_size: int = 50) -> List[Tuple[int, int, float]]:
    """
    Analyzes an uploaded satellite photo using Pillow.
    Resizes image to 50x50 to fit the grid and scans for red/orange fire pixels.
    Returns a list of tuples containing (row, col, confidence_score) of detected fires.
    """
    hotspots = []
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if it isn't
            if img.mode != "RGB":
                img = img.convert("RGB")
                
            # Resize image to match our grid size (50x50)
            img_resized = img.resize((grid_size, grid_size), Image.Resampling.NEAREST)
            
            # Scan pixels
            for r in range(grid_size):
                for c in range(grid_size):
                    red, green, blue = img_resized.getpixel((c, r)) # col is X, row is Y
                    
                    # Fire signature rules: High Red, low Green, very low Blue.
                    # Red should dominate and stand out from background vegetation
                    if red > 120 and green < 100 and blue < 90 and (red - green) > 30:
                        # Higher redness = higher detection confidence
                        redness = red - max(green, blue)
                        confidence = 0.70 + (redness / 255.0) * 0.29
                        confidence = round(min(0.99, max(0.70, confidence)), 2)
                        hotspots.append((r, c, confidence))
                        
    except Exception as e:
        print(f"Error analyzing satellite image: {e}")
        
    return hotspots
