import math
import random
from typing import Dict, List, Tuple

from input_processing import load_atto_record, get_total_records

class WildfireSimulation:
    def __init__(self, size: int = 50):
        self.size = size
        self.grid: List[List[Dict]] = []
        # Start at midday (index 43200 is 12:00 PM on July 1st, 2014)
        self.weather_index = 43200
        self.simulation_step = 0
        self.initialize_grid()

    def initialize_grid(self):
        """Initializes the 50x50 digital twin grid with clustered vegetation, smooth elevation waves, and seed hotspots."""
        self.grid = []
        self.simulation_step = 0

        # Generate vegetation clusters using smooth sine waves + noise
        veg_matrix = []
        elev_matrix = []
        for r in range(self.size):
            veg_row = []
            elev_row = []
            for c in range(self.size):
                # Elevation wave (hills and river valley)
                h1 = 100 * math.sin(r * 0.08) * math.cos(c * 0.08)
                h2 = 40 * math.sin(c * 0.18 + r * 0.05)
                h3 = 15 * math.cos((r - c) * 0.2)
                elevation = 150 + h1 + h2 + h3

                # Vegetation density clusters (forest patches and rivers/clearings)
                v1 = 0.5 + 0.35 * math.sin(r * 0.12 + 1.2) * math.sin(c * 0.15 + 2.5)
                v2 = 0.10 * math.sin(r * 0.4) * math.cos(c * 0.4)
                v3 = random.uniform(-0.05, 0.05)
                veg_density = max(0.05, min(1.0, v1 + v2 + v3))

                veg_row.append(veg_density)
                elev_row.append(elevation)
            veg_matrix.append(veg_row)
            elev_matrix.append(elev_row)

        # Build full grid cells
        for r in range(self.size):
            grid_row = []
            for c in range(self.size):
                # Interpolate lat/long inside Amazon basin near ATTO (-3.0 to -4.0 latitude, -60.0 to -61.0 longitude)
                # Matches the AMAZON_CENTER [-3.5, -60.5] span
                lat = -2.9 - (r / (self.size - 1)) * 1.2
                lon = -61.1 + (c / (self.size - 1)) * 1.2

                veg_density = veg_matrix[r][c]
                elevation = elev_matrix[r][c]

                # Fuel load is correlated with vegetation density, lightly shaped by elevation
                fuel_load = max(0.0, min(1.0, veg_density * 0.85 + (elevation / 400.0) * 0.15))

                cell = {
                    "row": r,
                    "col": c,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "vegetation_density": round(veg_density, 3),
                    "original_vegetation_density": round(veg_density, 3),
                    "fuel_load": round(fuel_load, 3),
                    "elevation": round(elevation, 1),
                    "temperature": 0.0,
                    "humidity": 0.0,
                    "wind_speed": 0.0,
                    "wind_direction": 0.0,
                    "rainfall": 0.0,
                    "atmospheric_pressure": 0.0,
                    "soil_moisture": 0.0,
                    "vpd": 0.0,
                    "solar_radiation": 0.0,
                    "fire_state": "unburned",
                    "burn_duration": 0,
                    "risk_score": 0.0,
                    "risk_level": "low",
                    "recovery_score": 0.0
                }
                grid_row.append(cell)
            self.grid.append(grid_row)

        # Load initial weather record from ATTO CSV
        record = load_atto_record(self.weather_index)
        self.apply_weather_profile(record)

        # Seed initial hotspots
        self.grid[24][24]["fire_state"] = "burning"
        self.grid[24][24]["burn_duration"] = 0
        self.grid[25][24]["fire_state"] = "burning"
        self.grid[25][24]["burn_duration"] = 0

    def get_weather_at_cell(self, row: int, col: int, record: dict) -> dict:
        """Applies spatial smoothing/variation to weather parameters across the grid coordinates."""
        dy_shift = math.sin(row * 0.1) * math.cos(col * 0.1)
        dx_shift = math.cos(row * 0.08) * math.sin(col * 0.08)

        temp = max(18.0, min(42.0, record["temperature"] + 1.2 * dy_shift))
        humidity = max(10.0, min(100.0, record["humidity"] + 5.0 * dx_shift))
        wind_speed = max(0.0, min(60.0, record["wind_speed"] + 2.0 * math.sin((row + col) * 0.15)))
        wind_dir = (record["wind_direction"] + 12.0 * math.cos(row * 0.05)) % 360.0

        # High vegetation areas retain more moisture, low elevation (valleys) are wetter
        veg_factor = self.grid[row][col]["vegetation_density"]
        elev = self.grid[row][col]["elevation"]
        soil_moisture_base = record["soil_moisture"]
        
        soil_moisture = max(0.05, min(1.00, soil_moisture_base * (0.8 + 0.3 * veg_factor - 0.1 * (elev - 150) / 100.0)))
        solar_rad = record["solar_radiation"] * (1.0 - veg_factor * 0.4)
        pressure = record["atmospheric_pressure"] - 0.12 * (elev - 100)
        vpd = max(0.01, record["vpd"] * (1.1 - veg_factor * 0.3))

        return {
            "temperature": round(temp, 1),
            "humidity": round(humidity, 1),
            "wind_speed": round(wind_speed, 1),
            "wind_direction": round(wind_dir, 1),
            "rainfall": round(record["rainfall"], 1),
            "atmospheric_pressure": round(pressure, 1),
            "soil_moisture": round(soil_moisture, 3),
            "vpd": round(vpd, 2),
            "solar_radiation": round(solar_rad, 1)
        }

    def apply_weather_profile(self, record: dict):
        """Applies the parsed weather record to all cells in the grid with spatial variation."""
        for r in range(self.size):
            for c in range(self.size):
                w = self.get_weather_at_cell(r, c, record)
                self.grid[r][c].update(w)
                self.recalculate_risk(r, c)

    def recalculate_risk(self, r: int, c: int):
        """Computes risk score and risk level category for a specific cell."""
        cell = self.grid[r][c]
        if cell["fire_state"] == "burned":
            cell["risk_score"] = 0.0
            cell["risk_level"] = "low"
            return

        fuel_load = cell["fuel_load"]
        humidity = cell["humidity"]
        wind_speed = cell["wind_speed"]
        veg_density = cell["vegetation_density"]
        soil_moisture = cell["soil_moisture"]
        vpd = cell["vpd"]

        dryness_factor = 1.0 - (humidity / 100.0)
        wind_factor = min(1.0, wind_speed / 40.0)
        soil_dryness = 1.0 - soil_moisture
        vpd_factor = min(1.0, vpd / 4.0)

        risk = (
            (fuel_load * 0.25) +
            (dryness_factor * 0.20) +
            (wind_factor * 0.15) +
            (veg_density * 0.15) +
            (soil_dryness * 0.15) +
            (vpd_factor * 0.10)
        )
        
        # Ridge elevation hazard multiplier
        elevation_bonus = max(0.0, (cell["elevation"] - 150) / 1000.0)
        risk = min(1.0, max(0.0, risk + elevation_bonus))

        cell["risk_score"] = round(risk, 3)

        if risk < 0.3:
            cell["risk_level"] = "low"
        elif risk < 0.6:
            cell["risk_level"] = "moderate"
        elif risk < 0.8:
            cell["risk_level"] = "high"
        else:
            cell["risk_level"] = "critical"

    def generate_satellite_hotspot(self, confidence_min: float = 0.70, confidence_max: float = 0.99) -> List[Dict]:
        """Simulates satellite fire detection by selecting random high-risk cells and igniting them."""
        eligible_cells = []
        for r in range(self.size):
            for c in range(self.size):
                cell = self.grid[r][c]
                if cell["fire_state"] == "unburned" and cell["risk_score"] > 0.3:
                    eligible_cells.append((r, c))

        if not eligible_cells:
            eligible_cells = [(r, c) for r in range(self.size) for c in range(self.size) if self.grid[r][c]["fire_state"] == "unburned"]

        if not eligible_cells:
            return []

        num_ignitions = random.randint(1, min(3, len(eligible_cells)))
        ignited_cells = random.sample(eligible_cells, num_ignitions)
        hotspots = []

        for r, c in ignited_cells:
            self.grid[r][c]["fire_state"] = "burning"
            self.grid[r][c]["burn_duration"] = 0
            confidence = round(random.uniform(confidence_min, confidence_max), 2)
            hotspots.append({
                "row": r,
                "col": c,
                "latitude": self.grid[r][c]["latitude"],
                "longitude": self.grid[r][c]["longitude"],
                "confidence": confidence,
                "timestamp": self.simulation_step
            })
        return hotspots

    def generate_atto_weather_reading(self) -> Dict:
        """Advances the weather record index (jumps 2 minutes) and loads it from the ATTO CSV dataset."""
        total = get_total_records()
        if total > 0:
            # Shift index by 120 rows (2 minutes of 1-second readings) to show faster diurnal changes
            self.weather_index = (self.weather_index + 120) % total
        record = load_atto_record(self.weather_index)
        self.apply_weather_profile(record)
        return record

    def calculate_catch_probability(self, burn_r: int, burn_c: int, neigh_r: int, neigh_c: int) -> float:
        """Computes the catching probability based on fuel, risk, wind, and elevation slope."""
        burning = self.grid[burn_r][burn_c]
        neighbor = self.grid[neigh_r][neigh_c]

        fuel = neighbor["fuel_load"]
        risk = neighbor["risk_score"]
        soil_dryness = 1.0 - neighbor["soil_moisture"]

        # Wind Vector angle alignment
        dy = -(neigh_r - burn_r)
        dx = neigh_c - burn_c
        cell_angle_deg = math.degrees(math.atan2(dx, dy)) % 360.0

        wind_dir = burning["wind_direction"]
        wind_spd = burning["wind_speed"]

        angle_diff = abs(wind_dir - cell_angle_deg)
        angle_diff = min(angle_diff, 360.0 - angle_diff)

        wind_alignment = math.cos(math.radians(angle_diff))
        wind_effect = math.exp(wind_alignment * (wind_spd / 15.0))

        # Slope factor (fire spreads faster uphill)
        elev_diff = neighbor["elevation"] - burning["elevation"]
        if elev_diff > 0:
            elev_effect = min(2.5, 1.0 + (elev_diff / 30.0))
        else:
            elev_effect = max(0.15, 1.0 + (elev_diff / 80.0))

        # Rain suppression
        rain_effect = max(0.05, 1.0 - (neighbor["rainfall"] / 15.0))

        p_catch = 0.28 * fuel * risk * soil_dryness * wind_effect * elev_effect * rain_effect
        return min(0.98, max(0.0, p_catch))

    def simulate_step(self) -> Tuple[List[List[Dict]], List[Dict]]:
        """Advances the wildfire digital twin simulation by one time step."""
        self.simulation_step += 1

        old_states = [[self.grid[r][c]["fire_state"] for c in range(self.size)] for r in range(self.size)]
        old_durations = [[self.grid[r][c]["burn_duration"] for c in range(self.size)] for r in range(self.size)]

        newly_ignited = []
        extinguished = []

        for r in range(self.size):
            for c in range(self.size):
                if old_states[r][c] != "burning":
                    continue

                curr_duration = old_durations[r][c] + 1
                self.grid[r][c]["burn_duration"] = curr_duration

                # Spread check (8-connectivity)
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            if old_states[nr][nc] == "unburned" and self.grid[nr][nc]["fire_state"] == "unburned":
                                p_catch = self.calculate_catch_probability(r, c, nr, nc)
                                if random.random() < p_catch:
                                    self.grid[nr][nc]["fire_state"] = "burning"
                                    self.grid[nr][nc]["burn_duration"] = 0
                                    newly_ignited.append({"row": nr, "col": nc})

                # Transition to burned after 3 steps
                if curr_duration >= 3:
                    self.grid[r][c]["fire_state"] = "burned"
                    self.grid[r][c]["fuel_load"] = 0.0
                    self.grid[r][c]["risk_score"] = 0.0
                    self.grid[r][c]["risk_level"] = "low"
                    self.grid[r][c]["soil_moisture"] = max(0.01, self.grid[r][c]["soil_moisture"] - 0.5)
                    self.grid[r][c]["vpd"] = self.grid[r][c]["vpd"] * 1.5
                    extinguished.append({"row": r, "col": c})

        self.recalculate_recovery_scores()

        alerts = []
        for cell in newly_ignited:
            alerts.append({
                "row": cell["row"],
                "col": cell["col"],
                "alert_type": "burning",
                "message": f"New active fire front detected at cell ({cell['row']}, {cell['col']})",
                "timestamp": self.simulation_step
            })

        return self.grid, alerts

    def recalculate_recovery_scores(self):
        """Scores each burned cell for reforestation priority using original vegetation density and neighbor conditions."""
        for r in range(self.size):
            for c in range(self.size):
                cell = self.grid[r][c]
                if cell["fire_state"] != "burned":
                    cell["recovery_score"] = 0.0
                    continue
                
                surrounding_veg = []
                for dr in [-1, 0, 1]:
                    for dc in [-1, 0, 1]:
                        if dr == 0 and dc == 0:
                            continue
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < self.size and 0 <= nc < self.size:
                            neighbor = self.grid[nr][nc]
                            if neighbor["fire_state"] == "unburned":
                                surrounding_veg.append(neighbor["vegetation_density"])
                            else:
                                surrounding_veg.append(0.0)

                avg_surrounding = sum(surrounding_veg) / len(surrounding_veg) if surrounding_veg else 0.0

                original_veg = cell["original_vegetation_density"]
                soil_moisture = cell["soil_moisture"]

                priority = (original_veg * 0.5) + ((1.0 - avg_surrounding) * 0.3) + (soil_moisture * 0.2)
                cell["recovery_score"] = round(max(0.0, min(1.0, priority)), 3)

    def get_risk_scores(self) -> List[Dict]:
        scores = []
        for r in range(self.size):
            for c in range(self.size):
                cell = self.grid[r][c]
                scores.append({
                    "row": r,
                    "col": c,
                    "latitude": cell["latitude"],
                    "longitude": cell["longitude"],
                    "risk_score": cell["risk_score"],
                    "risk_level": cell["risk_level"]
                })
        return scores

    def get_recovery_scores(self) -> List[Dict]:
        scores = []
        for r in range(self.size):
            for c in range(self.size):
                cell = self.grid[r][c]
                if cell["fire_state"] == "burned":
                    scores.append({
                        "row": r,
                        "col": c,
                        "latitude": cell["latitude"],
                        "longitude": cell["longitude"],
                        "original_vegetation_density": cell["original_vegetation_density"],
                        "recovery_score": cell["recovery_score"]
                    })
        return scores

    def get_alerts(self) -> List[Dict]:
        alerts = []
        for r in range(self.size):
            for c in range(self.size):
                cell = self.grid[r][c]
                if cell["fire_state"] == "burning":
                    alerts.append({
                        "row": r,
                        "col": c,
                        "alert_type": "burning",
                        "message": f"Active wildfire spreading at ({r}, {c})",
                        "timestamp": self.simulation_step
                    })
                elif cell["risk_level"] == "critical" and cell["fire_state"] == "unburned":
                    alerts.append({
                        "row": r,
                        "col": c,
                        "alert_type": "critical_risk",
                        "message": f"Critical fire hazard at ({r}, {c}) (risk: {cell['risk_score']})",
                        "timestamp": self.simulation_step
                    })
        return alerts
