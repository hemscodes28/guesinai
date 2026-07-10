import asyncio
import json
import logging
import os
import smtplib
import pandas as pd
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from typing import Dict, List, Optional
from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from database import init_db, SessionLocal, WeatherLog, AlertLog, SimulationSnapshot, User, hash_password, verify_password, SituationReport, FireSpreadSample
from simulation import WildfireSimulation
from input_processing import get_total_records, load_atto_record
from ai_engine import calculate_evacuation_route, allocate_mitigation_resources
from WildfirePrediction.fire_spread_model import FireSpreadSimulator, calculate_burn_area
from ml_fire_model import ml_model
from monte_carlo import monte_carlo_forecast, run_fork_simulation


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("guesin_backend")

# Initialize Digital Twin Simulation Singleton
sim = WildfireSimulation()

# Background Feed States
WEATHER_FEED_ACTIVE = False
HOTSPOT_FEED_ACTIVE = False

# WebSocket Connection Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"Client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Error broadcasting to socket: {e}")
                self.disconnect(connection)

manager = ConnectionManager()

# Helper for broadcasting current state
async def broadcast_current_state(extra_alerts: List[dict] = None):
    healthy = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "unburned")
    burning = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burning")
    burned = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burned")

    w_record = load_atto_record(sim.weather_index)

    payload = {
        "step": sim.simulation_step,
        "grid": sim.grid,
        "weather": w_record,
        "aggregates": {
            "healthy": healthy,
            "burning": burning,
            "burned": burned
        },
        "alerts": extra_alerts or []
    }
    await manager.broadcast(payload)

# Background tasks loops
async def weather_feed_loop():
    global WEATHER_FEED_ACTIVE
    while True:
        try:
            if WEATHER_FEED_ACTIVE:
                # Cycle weather and apply
                weather = sim.generate_atto_weather_reading()
                logger.info(f"Background Weather Feed: advanced to index {sim.weather_index} (time: {weather['timestamp']})")

                # Log weather update to SQLite
                db = SessionLocal()
                try:
                    db_log = WeatherLog(
                        temperature=weather["temperature"],
                        humidity=weather["humidity"],
                        wind_speed=weather["wind_speed"],
                        wind_direction=weather["wind_direction"],
                        rainfall=weather["rainfall"],
                        atmospheric_pressure=weather["atmospheric_pressure"],
                        soil_moisture=weather["soil_moisture"],
                        vpd=weather["vpd"],
                        solar_radiation=weather["solar_radiation"]
                    )
                    db.add(db_log)
                    db.commit()
                except Exception as e:
                    logger.error(f"Error saving weather log to SQLite: {e}")
                    db.rollback()
                finally:
                    db.close()

                # Broadcast
                await broadcast_current_state()
        except Exception as e:
            logger.error(f"Error in weather feed loop: {e}")
        await asyncio.sleep(5.0)

async def hotspot_feed_loop():
    global HOTSPOT_FEED_ACTIVE
    while True:
        try:
            if HOTSPOT_FEED_ACTIVE:
                hotspots = sim.generate_satellite_hotspot()
                if hotspots:
                    logger.info(f"Background Hotspot Feed: generated {len(hotspots)} satellite detections")
                    
                    db = SessionLocal()
                    db_alerts = []
                    for h in hotspots:
                        alert = AlertLog(
                            row=h["row"],
                            col=h["col"],
                            alert_type="burning",
                            message=f"Satellite hot spot detected (Confidence: {int(h['confidence']*100)}%)"
                        )
                        db.add(alert)
                        db_alerts.append({
                            "row": h["row"],
                            "col": h["col"],
                            "alert_type": "burning",
                            "message": alert.message,
                            "timestamp": sim.simulation_step
                        })
                    
                    try:
                        db.commit()
                    except Exception as e:
                        logger.error(f"Error saving alerts to SQLite: {e}")
                        db.rollback()
                    finally:
                        db.close()

                    await broadcast_current_state(extra_alerts=db_alerts)
        except Exception as e:
            logger.error(f"Error in hotspot feed loop: {e}")
        await asyncio.sleep(12.0)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup tasks
    logger.info("Initializing SQLite database...")
    init_db()
    
    # Seed default user if not exists
    db_session = SessionLocal()
    try:
        user_check = db_session.query(User).filter(User.username == "operator@guesin.ai").first()
        if not user_check:
            hashed = hash_password("password123!")
            db_session.add(User(username="operator@guesin.ai", hashed_password=hashed))
            db_session.commit()
            logger.info("Default operator user seeded in database.")
    except Exception as err:
        db_session.rollback()
        logger.error(f"Error seeding default user: {err}")
    finally:
        db_session.close()
    
    # Start background task loops
    logger.info("Starting background feed tasks...")
    weather_task = asyncio.create_task(weather_feed_loop())
    hotspot_task = asyncio.create_task(hotspot_feed_loop())
    
    yield
    
    # Shutdown tasks
    logger.info("Canceling background tasks...")
    weather_task.cancel()
    hotspot_task.cancel()

# Instantiate FastAPI application
app = FastAPI(
    title="Guesin.ai Wildfire Digital Twin API",
    description="Backend simulating wildfire spread over a synthetic Amazon rainforest grid.",
    version="2.0.0",
    lifespan=lifespan
)

# Mount static files to serve generated plots and GIF
app.mount("/static", StaticFiles(directory="WildfirePrediction"), name="static")

# CORS Policy configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic Schemas for validation and self-documentation
class CellSchema(BaseModel):
    row: int
    col: int
    latitude: float
    longitude: float
    vegetation_density: float
    original_vegetation_density: float
    fuel_load: float
    elevation: float
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: float
    rainfall: float
    atmospheric_pressure: float
    soil_moisture: float
    vpd: float
    solar_radiation: float
    fire_state: str
    burn_duration: int
    risk_score: float
    risk_level: str
    recovery_score: float

class HotspotRequest(BaseModel):
    row: Optional[int] = None
    col: Optional[int] = None

class HotspotResponse(BaseModel):
    row: int
    col: int
    latitude: float
    longitude: float
    confidence: float
    timestamp: int

class RiskScoreResponse(BaseModel):
    row: int
    col: int
    latitude: float
    longitude: float
    risk_score: float
    risk_level: str

class RecoveryScoreResponse(BaseModel):
    row: int
    col: int
    latitude: float
    longitude: float
    original_vegetation_density: float
    recovery_score: float

class AlertResponse(BaseModel):
    row: int
    col: int
    alert_type: str
    message: str
    timestamp: int

class WeatherResponse(BaseModel):
    timestamp: str
    temperature: float
    humidity: float
    wind_speed: float
    wind_direction: float
    vegetation_index: float
    vpd: float
    solar_radiation: float
    soil_moisture: float
    atmospheric_pressure: float
    rainfall: float
    hour: int

class ToggleRequest(BaseModel):
    weather_feed: bool
    hotspot_feed: bool

class ResetResponse(BaseModel):
    status: str
    grid: List[List[CellSchema]]

class EvacRequest(BaseModel):
    row: int
    col: int

class ResourceAllocationSchema(BaseModel):
    asset_id: str
    type: str
    row: int
    col: int
    latitude: float
    longitude: float
    status: str
    impact_score: float
    message: str

class AIPlanResponse(BaseModel):
    status: str
    evacuation_path: Optional[List[List[int]]] = None
    path_length: Optional[int] = None
    resources: List[ResourceAllocationSchema]
    message: Optional[str] = None

class AuthRequest(BaseModel):
    username: str
    password: str


# REST ENDPOINTS

@app.post("/signup")
def signup(req: AuthRequest):
    # Enforce password requirements: at least 6 characters, at least 1 symbol
    if len(req.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters long."
        )
    
    # Check for symbols: !@#$%^&*()_+-=[]{}|;':",./<>?
    symbols = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
    if not any(char in symbols for char in req.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least 1 special character/symbol."
        )
        
    db = SessionLocal()
    try:
        # Check if username exists
        existing_user = db.query(User).filter(User.username == req.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username is already taken."
            )
            
        hashed = hash_password(req.password)
        new_user = User(username=req.username, hashed_password=hashed)
        db.add(new_user)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred during registration."
        )
    finally:
        db.close()
        
    return {"status": "success", "message": "User registered successfully."}

@app.post("/signin")
def signin(req: AuthRequest):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == req.username).first()
        if not user or not verify_password(req.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password."
            )
    finally:
        db.close()
        
    return {"status": "success", "message": "Authenticated successfully."}

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_dashboard():
    """Serves the user-friendly interactive digital twin dashboard."""
    try:
        with open("templates/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read(), status_code=200)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Dashboard HTML template file not found."
        )

@app.get("/grid-state", response_model=List[List[CellSchema]])
def get_grid_state():
    """Returns the full current digital twin grid state (all 50x50 cells)."""
    return sim.grid

@app.post("/simulate-step")
async def simulate_step():
    """Advances the wildfire cellular automata simulation by one time-step. Returns updated grid and step alerts."""
    updated_grid, new_alerts = sim.simulate_step()

    # Log simulation step to SQLite history
    healthy = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "unburned")
    burning = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burning")
    burned = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burned")
    active_fires = [[cell["row"], cell["col"]] for r in range(sim.size) for cell in sim.grid[r] if cell["fire_state"] == "burning"]

    db = SessionLocal()
    try:
        snapshot = SimulationSnapshot(
            step=sim.simulation_step,
            unburned_count=healthy,
            burning_count=burning,
            burned_count=burned,
            active_fires=json.dumps(active_fires)
        )
        db.add(snapshot)

        # Log alerts to SQLite
        db_alerts = []
        for a in new_alerts:
            alert_log = AlertLog(
                row=a["row"],
                col=a["col"],
                alert_type=a["alert_type"],
                message=a["message"]
            )
            db.add(alert_log)
            db_alerts.append({
                "row": a["row"],
                "col": a["col"],
                "alert_type": a["alert_type"],
                "message": a["message"],
                "timestamp": sim.simulation_step
            })
            
        db.commit()
    except Exception as e:
        logger.error(f"Error saving simulation snapshot to SQLite: {e}")
        db.rollback()
        db_alerts = new_alerts
    finally:
        db.close()

    await broadcast_current_state(extra_alerts=db_alerts)

    return {"status": "success", "step": sim.simulation_step, "grid": updated_grid, "alerts": db_alerts}

@app.get("/risk-scores", response_model=List[RiskScoreResponse])
def get_risk_scores():
    """Returns a lightweight payload containing only risk scores and categories per cell."""
    return sim.get_risk_scores()

@app.post("/generate-hotspot", response_model=List[HotspotResponse])
async def generate_hotspot(req: Optional[HotspotRequest] = None):
    """Triggers wildfire ignition manually (clicks) or synthetically (satellite detections)."""
    hotspots = []
    
    if req and req.row is not None and req.col is not None:
        r, c = req.row, req.col
        if 0 <= r < sim.size and 0 <= c < sim.size:
            cell = sim.grid[r][c]
            if cell["fire_state"] == "unburned":
                cell["fire_state"] = "burning"
                cell["burn_duration"] = 0
                confidence = 0.99
                h = {
                    "row": r,
                    "col": c,
                    "latitude": cell["latitude"],
                    "longitude": cell["longitude"],
                    "confidence": confidence,
                    "timestamp": sim.simulation_step
                }
                hotspots.append(h)
                
                db = SessionLocal()
                try:
                    alert = AlertLog(
                        row=r,
                        col=c,
                        alert_type="burning",
                        message=f"Manual operator ignition triggered at coordinate ({r}, {c})"
                    )
                    db.add(alert)
                    db.commit()
                except Exception as e:
                    logger.error(f"Error logging manual ignition to SQLite: {e}")
                    db.rollback()
                finally:
                    db.close()
    else:
        hotspots = sim.generate_satellite_hotspot()
        if hotspots:
            db = SessionLocal()
            try:
                for h in hotspots:
                    alert = AlertLog(
                        row=h["row"],
                        col=h["col"],
                        alert_type="burning",
                        message=f"Satellite hot spot detected (Confidence: {int(h['confidence']*100)}%)"
                    )
                    db.add(alert)
                db.commit()
            except Exception as e:
                logger.error(f"Error logging satellite hotspots to SQLite: {e}")
                db.rollback()
            finally:
                db.close()

    if hotspots:
        formatted_alerts = [{
            "row": h["row"],
            "col": h["col"],
            "alert_type": "burning",
            "message": f"Wildfire ignition confirmed at coordinates ({h['row']}, {h['col']})",
            "timestamp": sim.simulation_step
        } for h in hotspots]
        await broadcast_current_state(extra_alerts=formatted_alerts)

    return hotspots



@app.post("/generate-weather", response_model=WeatherResponse)
async def generate_weather():
    """Triggers weather timeline update, shifting temperature, wind, and humidity from the ATTO CSV dataset."""
    weather = sim.generate_atto_weather_reading()

    # Log weather event to SQLite
    db = SessionLocal()
    try:
        db_log = WeatherLog(
            temperature=weather["temperature"],
            humidity=weather["humidity"],
            wind_speed=weather["wind_speed"],
            wind_direction=weather["wind_direction"],
            rainfall=weather["rainfall"],
            atmospheric_pressure=weather["atmospheric_pressure"],
            soil_moisture=weather["soil_moisture"],
            vpd=weather["vpd"],
            solar_radiation=weather["solar_radiation"]
        )
        db.add(db_log)
        db.commit()
    except Exception as e:
        logger.error(f"Error saving weather change to SQLite: {e}")
        db.rollback()
    finally:
        db.close()

    # Broadcast update
    await broadcast_current_state()

    return weather

@app.get("/recovery-scores", response_model=List[RecoveryScoreResponse])
def get_recovery_scores():
    """Returns post-fire reforestation priority scores for cells classified as 'burned'."""
    return sim.get_recovery_scores()

@app.get("/alerts", response_model=List[AlertResponse])
def get_active_alerts():
    """Returns a list of all cells currently burning or under critical wildfire hazard risk."""
    return sim.get_alerts()

@app.post("/toggle-feed")
def toggle_feed(req: ToggleRequest):
    """Enables/Disables background simulation timers for satellite and weather sensors."""
    global WEATHER_FEED_ACTIVE, HOTSPOT_FEED_ACTIVE
    WEATHER_FEED_ACTIVE = req.weather_feed
    HOTSPOT_FEED_ACTIVE = req.hotspot_feed
    logger.info(f"Sensor timers toggled. Weather feed: {WEATHER_FEED_ACTIVE}, Hotspot feed: {HOTSPOT_FEED_ACTIVE}")
    return {"status": "success", "weather_feed": WEATHER_FEED_ACTIVE, "hotspot_feed": HOTSPOT_FEED_ACTIVE}

@app.post("/reset", response_model=ResetResponse)
async def reset_grid():
    """Resets the digital twin forest grid to initial conditions with default burning seeds."""
    sim.initialize_grid()
    
    db = SessionLocal()
    try:
        db.add(AlertLog(row=-1, col=-1, alert_type="system", message="Digital twin environment reset initiated."))
        db.commit()
    except Exception as e:
        logger.error(f"Error logging reset to SQLite: {e}")
        db.rollback()
    finally:
        db.close()

    await broadcast_current_state()

    return {"status": "reset_success", "grid": sim.grid}

@app.post("/ai-plan", response_model=AIPlanResponse)
def get_ai_decision_plan(req: EvacRequest):
    """
    AI Decision Engine endpoint. Computes safest evacuation route from user location
    using Dijkstra grid pathfinding, and recommends optimal firefighting containment lines.
    """
    # 1. Calculate safest path avoiding active fires and high risk zones
    path = calculate_evacuation_route(sim.grid, req.row, req.col)
    
    # 2. Deploys trucks and water drops based on active front
    resources = allocate_mitigation_resources(sim.grid)

    if path is None:
        return AIPlanResponse(
            status="error",
            resources=resources,
            message="ALL EVACUATION BOUNDARIES BLOCKED. Active fire fronts have cut off escape routes."
        )

    return AIPlanResponse(
        status="success",
        evacuation_path=path,
        path_length=len(path),
        resources=resources
    )


# WEBSOCKET ENDPOINT

@app.websocket("/ws/live-updates")
async def websocket_endpoint(websocket: WebSocket):
    """Establishes a WebSocket connection to stream live digital twin state updates to client dashboards."""
    await manager.connect(websocket)
    try:
        healthy = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "unburned")
        burning = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burning")
        burned = sum(1 for r in range(sim.size) for c in range(sim.size) if sim.grid[r][c]["fire_state"] == "burned")
        w_record = load_atto_record(sim.weather_index)

        await websocket.send_json({
            "step": sim.simulation_step,
            "grid": sim.grid,
            "weather": w_record,
            "aggregates": {
                "healthy": healthy,
                "burning": burning,
                "burned": burned
            },
            "alerts": []
        })
        
        while True:
            data = await websocket.receive_text()
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.post("/run-wildfire-prediction")
async def run_wildfire_prediction(
    temp: Optional[float] = Form(None),
    humidity: Optional[float] = Form(None),
    wind_speed: Optional[float] = Form(None),
    wind_direction: Optional[float] = Form(None),
    duration: Optional[int] = Form(240),
    step: Optional[int] = Form(3),
    latitude: Optional[float] = Form(-2.145),
    longitude: Optional[float] = Form(-59.000)
):
    try:
        ignited_lat = latitude
        ignited_lon = longitude
        
        # Load weather dataset to fill in missing overrides
        from WildfirePrediction.fire_spread_model import load_weather, get_weather
        base_weather_df = load_weather("attto_2014.csv")
        default_rec = get_weather(base_weather_df, "2014-07-01 12:00:00")
        
        override_temp = temp if temp is not None else float(default_rec.get('temperature_C', 28.0))
        override_rh = humidity if humidity is not None else float(default_rec.get('humidity_percent', 75.0))
        override_ws = wind_speed if wind_speed is not None else float(default_rec.get('windspeed_mps', 2.5))
        override_wd = wind_direction if wind_direction is not None else float(default_rec.get('wind_direction_deg', 90.0))
        
        # Generate weather DataFrame matching the custom user variables
        n_periods = int(duration / step) + 1
        timestamps = pd.date_range(start="2014-07-01 12:00:00", periods=n_periods, freq=f"{step}min")
        weather_df = pd.DataFrame({
            "timestamp": timestamps,
            "temperature_C": [override_temp] * n_periods,
            "humidity_percent": [override_rh] * n_periods,
            "windspeed_mps": [override_ws] * n_periods,
            "wind_direction_deg": [override_wd] * n_periods,
            "vegetation_index": [0.85] * n_periods
        })
        
        # Run Simulator
        sim_model = FireSpreadSimulator(weather_df)
        history_df, centroid_df, state_grid, ignite_t, fuel = sim_model.run(
            ignition_lat=ignited_lat,
            ignition_lon=ignited_lon,
            start_time="2014-07-01 12:21:32",
            duration_min=duration,
            dt_min=step
        )
        
        # Save plots under WildfirePrediction folder
        old_cwd = os.getcwd()
        os.makedirs("WildfirePrediction", exist_ok=True)
        os.chdir("WildfirePrediction")
        try:
            import matplotlib.pyplot as plt
            plt.close('all')
            from WildfirePrediction.visualization import FireVisualizer
            viz = FireVisualizer(history_df, centroid_df, ignite_t)
            viz.plot_arrival_time()
            viz.plot_centroid()
            viz.plot_growth()
            viz.plot_radius()
        finally:
            os.chdir(old_cwd)
            
        # Return optimized JSON payload containing arrays, centroids, stats, and plot image paths
        return JSONResponse(content={
            "status": "success",
            "ignition_lat": float(ignited_lat),
            "ignition_lon": float(ignited_lon),
            "ignite_t": ignite_t.tolist(),
            "fuel": fuel.tolist(),
            "centroids": centroid_df.to_dict(orient="records"),
            "stats": {
                "total_burning_records": len(history_df),
                "simulation_steps": len(centroid_df),
                "final_lat": float(centroid_df.iloc[-1]['lat']),
                "final_lon": float(centroid_df.iloc[-1]['lon']),
                "max_spread_radius": float(centroid_df['spread_radius_m'].max()),
                "max_burning_cells": int(centroid_df['n_burning'].max()),
                "total_burned_area": float(calculate_burn_area(len(history_df), 30.0))
            },
            "plots": {
                "arrival_time": "/static/fire_arrival_time.png",
                "centroid": "/static/fire_centroid.png",
                "growth": "/static/fire_growth.png",
                "radius": "/static/fire_radius.png",
                "live_gif": "/static/fire_spread_live.gif"
            }
        })
        
    except Exception as e:
        logger.error(f"Error running wildfire prediction model: {e}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"status": "error", "message": f"Simulation failed: {str(e)}"}
        )


# ============================================================
# EMAIL ALERT DISPATCH ENGINE
# ============================================================

class AlertDispatcher:
    """Lightweight email dispatcher adapted from Evacuation/backend/dispatch_engine.py."""

    def __init__(self):
        self.enabled = False
        self.threshold = "HIGH"  # BAD | HIGH | EXTREMELY HIGH
        self.smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "theguesin.ai@gmail.com")
        self.smtp_password = os.getenv("SMTP_PASSWORD", "jtrnkorvcmqtvowc")
        self.smtp_from = os.getenv("SMTP_FROM", self.smtp_user)
        self.recipients = [
            {"id": "fire",      "name": "Fire Department",  "email": os.getenv("FIRE_DEPT_EMAIL",  "sarveshbala27@gmail.com")},
            {"id": "ambulance", "name": "Ambulance",         "email": os.getenv("AMBULANCE_EMAIL",  "barathrithish7@gmail.com")},
            {"id": "rescue",   "name": "Rescue Team",       "email": os.getenv("RESCUE_EMAIL",     "sarveshbala27@gmail.com")},
        ]
        # Debounce: maps threat_level -> last sent datetime
        self._last_sent: Dict[str, datetime] = {}
        self.DEBOUNCE_MINUTES = 5

    def configure(self, config: dict):
        self.enabled = config.get("enabled", self.enabled)
        self.threshold = config.get("threshold", self.threshold)
        self.smtp_host = config.get("smtp_host", self.smtp_host)
        self.smtp_port = int(config.get("smtp_port", self.smtp_port))
        self.smtp_user = config.get("smtp_user", self.smtp_user)
        self.smtp_password = config.get("smtp_password", self.smtp_password)
        self.smtp_from = config.get("smtp_from", self.smtp_user)
        recips = config.get("recipients")
        if recips:
            self.recipients = recips

    def _can_send(self, threat_level: str) -> bool:
        last = self._last_sent.get(threat_level)
        if last is None:
            return True
        return datetime.now(timezone.utc) - last > timedelta(minutes=self.DEBOUNCE_MINUTES)

    def _threshold_met(self, threat_level: str) -> bool:
        order = {"GOOD": 0, "BAD": 1, "HIGH": 2, "EXTREMELY HIGH": 3}
        return order.get(threat_level, 0) >= order.get(self.threshold, 1)

    def _send_email_sync(self, recipient: str, subject: str, body: str) -> bool:
        if not self.smtp_user or not self.smtp_password:
            return False
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.smtp_from
        msg["To"] = recipient
        msg.set_content(body)
        strategies = [
            (False, self.smtp_host, self.smtp_port, True),
            (True,  self.smtp_host, 465, False),
            (False, self.smtp_host, 587, True),
        ]
        for use_ssl, host, port, use_tls in strategies:
            try:
                if use_ssl:
                    with smtplib.SMTP_SSL(host, port, timeout=10) as srv:
                        srv.login(self.smtp_user, self.smtp_password)
                        srv.send_message(msg)
                else:
                    with smtplib.SMTP(host, port, timeout=10) as srv:
                        srv.ehlo()
                        if use_tls:
                            srv.starttls()
                            srv.ehlo()
                        srv.login(self.smtp_user, self.smtp_password)
                        srv.send_message(msg)
                return True
            except Exception:
                pass
        return False

    async def dispatch(self, threat_level: str, d_factor: float, lat: float, lon: float) -> dict:
        """
        Sends email alerts to all configured recipients.
        Returns a status dict with per-recipient results.
        """
        now = datetime.now(timezone.utc)
        self._last_sent[threat_level] = now
        ts = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        subject = f"[GUESIN.AI] WILDFIRE ALERT — {threat_level} Threat Detected"
        body = (
            f"GUESIN.AI Wildfire Digital Twin — Automated Alert\n"
            f"{'='*50}\n"
            f"Threat Level  : {threat_level}\n"
            f"Damage Factor : {d_factor:.2f}% of monitored grid area burned/burning\n"
            f"Fire Centroid : Lat {lat:.6f}, Lon {lon:.6f}\n"
            f"Time          : {ts}\n"
            f"{'='*50}\n"
            f"Immediate response is recommended. Monitor the Guesin.ai digital twin\n"
            f"dashboard for real-time directional spread coordinates.\n"
        )

        results = []
        for dept in self.recipients:
            email = dept.get("email", "")
            if not email:
                results.append({"id": dept["id"], "name": dept["name"], "status": "skipped", "message": "No email configured"})
                continue
            success = await asyncio.get_event_loop().run_in_executor(None, self._send_email_sync, email, subject, body)
            results.append({
                "id": dept["id"],
                "name": dept["name"],
                "email": email,
                "status": "sent" if success else "failed",
                "message": "Email delivered" if success else "SMTP delivery failed — check credentials",
                "timestamp": ts
            })
        return {"dispatched_at": ts, "recipients": results}


# Global alert dispatcher instance
alert_dispatcher = AlertDispatcher()


class AlertConfigRequest(BaseModel):
    enabled: Optional[bool] = None
    threshold: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None
    recipients: Optional[List[Dict]] = None


class TriggerAlertRequest(BaseModel):
    threat_level: str
    d_factor: float
    lat: float
    lon: float
    force: Optional[bool] = False


@app.post("/alert-config")
async def configure_alert(config: AlertConfigRequest):
    """Update email alert configuration from the dashboard."""
    alert_dispatcher.configure(config.model_dump(exclude_none=True))
    return {
        "status": "ok",
        "enabled": alert_dispatcher.enabled,
        "threshold": alert_dispatcher.threshold,
        "smtp_user": alert_dispatcher.smtp_user,
        "recipients": alert_dispatcher.recipients
    }


@app.get("/alert-config")
async def get_alert_config():
    """Get current email alert configuration."""
    return {
        "enabled": alert_dispatcher.enabled,
        "threshold": alert_dispatcher.threshold,
        "smtp_host": alert_dispatcher.smtp_host,
        "smtp_port": alert_dispatcher.smtp_port,
        "smtp_user": alert_dispatcher.smtp_user,
        "smtp_from": alert_dispatcher.smtp_from,
        "recipients": alert_dispatcher.recipients
    }


@app.post("/trigger-alert")
async def trigger_alert(req: TriggerAlertRequest):
    """Trigger email alert if thresholds are met. Called from the frontend simulation player."""
    if not alert_dispatcher.enabled:
        return {"status": "skipped", "reason": "Email alerts are disabled"}

    if not alert_dispatcher._threshold_met(req.threat_level):
        return {"status": "skipped", "reason": f"Threat level {req.threat_level} is below configured threshold ({alert_dispatcher.threshold})"}

    if not req.force and not alert_dispatcher._can_send(req.threat_level):
        return {"status": "debounced", "reason": f"Alert for {req.threat_level} was already sent within the last {alert_dispatcher.DEBOUNCE_MINUTES} minutes"}

    logger.info(f"Dispatching email alert — Level: {req.threat_level}, D-Factor: {req.d_factor:.2f}%")
    result = await alert_dispatcher.dispatch(req.threat_level, req.d_factor, req.lat, req.lon)
    return {"status": "triggered", "result": result}


# ============================================================
# NEW FEATURE ENDPOINTS
# ============================================================

# ── 1. ML Model Status ────────────────────────────────────────────────────────

@app.get("/ml-model-status")
def get_ml_model_status():
    """Returns current ML fire spread model status, training sample count, and metadata."""
    return ml_model.get_status()


# ── 4. AQI / Smoke Plume Grid ─────────────────────────────────────────────────

@app.get("/aqi-grid")
def get_aqi_grid():
    """
    Returns the current Smoke/AQI overlay grid computed via Gaussian plume dispersion.
    Each cell has: row, col, aqi (0-500), category, color.
    """
    return sim.get_aqi_grid()


# ── 3. What-If Fork Simulation ────────────────────────────────────────────────

class ForkRequest(BaseModel):
    wind_speed: Optional[float] = None
    wind_direction: Optional[float] = None
    firebreak_cells: Optional[List[List[int]]] = None  # [[row, col], ...]
    steps: int = 10


@app.post("/fork-simulation")
async def fork_simulation(req: ForkRequest):
    """
    Clones the current simulation grid, applies scenario modifications
    (wind change, firebreaks), and runs `steps` ahead. Returns a comparison
    between the live timeline and the forked scenario.
    """
    try:
        fb_cells = [tuple(pair) for pair in (req.firebreak_cells or [])]
        
        # Run in thread pool to avoid blocking (deep copy + N steps can be slow)
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_fork_simulation(
                sim,
                wind_speed_override=req.wind_speed,
                wind_direction_override=req.wind_direction,
                firebreak_cells=fb_cells,
                steps=req.steps,
            )
        )
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Fork simulation error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fork simulation failed: {str(e)}"
        )


# ── 5. LLM Situation Report ───────────────────────────────────────────────────

def _build_situation_context() -> dict:
    """Builds a structured context dict from the current simulation state."""
    grid_size = sim.size
    healthy = burning = burned = 0
    top_risk_cells = []
    
    for r in range(grid_size):
        for c in range(grid_size):
            cell = sim.grid[r][c]
            state = cell["fire_state"]
            if state == "unburned":
                healthy += 1
                if cell["risk_score"] >= 0.75:
                    top_risk_cells.append(cell)
            elif state == "burning":
                burning += 1
            else:
                burned += 1

    top_risk_cells.sort(key=lambda x: x["risk_score"], reverse=True)
    top_3 = top_risk_cells[:3]

    total = grid_size * grid_size
    d_factor = (burning + burned) / total * 100

    sample_cell = sim.grid[grid_size // 2][grid_size // 2]
    
    return {
        "step": sim.simulation_step,
        "healthy": healthy,
        "burning": burning,
        "burned": burned,
        "d_factor": round(d_factor, 2),
        "wind_speed": round(sample_cell.get("wind_speed", 0), 1),
        "wind_direction": round(sample_cell.get("wind_direction", 0), 1),
        "temperature": round(sample_cell.get("temperature", 0), 1),
        "humidity": round(sample_cell.get("humidity", 0), 1),
        "top_risk_zones": [
            {"row": c["row"], "col": c["col"], "risk": round(c["risk_score"], 3)}
            for c in top_3
        ],
    }


def _generate_template_report(ctx: dict) -> str:
    """Generates a structured situation report using a template (no LLM required)."""
    threat = "CRITICAL" if ctx["d_factor"] >= 40 else "HIGH" if ctx["d_factor"] >= 15 else "MODERATE" if ctx["d_factor"] >= 5 else "LOW"
    wind_compass = {
        (0, 22.5): "N", (22.5, 67.5): "NE", (67.5, 112.5): "E",
        (112.5, 157.5): "SE", (157.5, 202.5): "S", (202.5, 247.5): "SW",
        (247.5, 292.5): "W", (292.5, 337.5): "NW", (337.5, 360): "N"
    }
    wd = ctx["wind_direction"] % 360
    compass = next((v for (lo, hi), v in wind_compass.items() if lo <= wd < hi), "N")
    
    risk_lines = ""
    for z in ctx["top_risk_zones"]:
        risk_lines += f"\n   • Grid [{z['row']},{z['col']}] — Risk Score: {z['risk']:.3f} (CRITICAL)"
    if not risk_lines:
        risk_lines = "\n   • No critical-risk zones identified."

    return f"""━━━ GUESIN.AI TACTICAL SITUATION REPORT ━━━
📍 Simulation Step: {ctx['step']}
🚨 Threat Level: {threat}

📊 FIRE STATUS SUMMARY
   • Healthy Cells  : {ctx['healthy']:,} ({ctx['healthy']/2500*100:.1f}% of grid)
   • Active Burning : {ctx['burning']:,} cells
   • Burned Out     : {ctx['burned']:,} cells  
   • Damage Factor  : {ctx['d_factor']:.2f}%

🌬️ WEATHER CONDITIONS
   • Wind: {ctx['wind_speed']} m/s from {compass} ({ctx['wind_direction']}°)
   • Temperature: {ctx['temperature']}°C | Humidity: {ctx['humidity']}%

⚠️ HIGH-RISK ZONES (Unburned, Imminent Threat)
{risk_lines}

🛡️ RECOMMENDED ACTIONS
   {'• EVACUATE all personnel from high-risk zones immediately.' if threat == 'CRITICAL' else '• Monitor fire perimeter closely and prepare containment resources.' if threat == 'HIGH' else '• Maintain observation posts and verify suppression resource staging.'}
   • Deploy AI-calculated evacuation routes via the dashboard.
   • Position fire engines at critical perimeter cells.
   {'• Activate smoke/AQI evacuation corridor assessment.' if ctx['burning'] > 5 else ''}

⏱️ Generated at Step {ctx['step']} | Guesin.ai Digital Twin v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


async def _generate_llm_report(ctx: dict) -> tuple[str, str]:
    """Tries to generate a Gemini LLM report. Returns (report_text, model_name)."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return _generate_template_report(ctx), "template"

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = f"""You are an emergency wildfire management AI. Generate a concise tactical situation report for a wildfire digital twin.

Current state:
- Simulation step: {ctx['step']}
- Healthy cells: {ctx['healthy']}, Burning: {ctx['burning']}, Burned: {ctx['burned']}
- Damage Factor: {ctx['d_factor']:.2f}% (% of grid burned or burning)
- Wind: {ctx['wind_speed']} m/s at {ctx['wind_direction']}°
- Temperature: {ctx['temperature']}°C, Humidity: {ctx['humidity']}%
- Top risk zones: {ctx['top_risk_zones']}

Write a professional emergency situation report with: threat assessment, current fire status, key risks, and recommended actions. Use clear headers. Keep it under 300 words."""

        response = model.generate_content(prompt)
        return response.text, "gemini-1.5-flash"
    except Exception as e:
        logger.warning(f"Gemini API error: {e}. Falling back to template report.")
        return _generate_template_report(ctx), "template"


@app.get("/situation-report")
async def get_situation_report():
    """
    Generates a human-readable tactical situation report from the current simulation state.
    Uses Gemini LLM if GEMINI_API_KEY env variable is set, otherwise uses a rich template.
    Report is cached in SQLite for audit trail.
    """
    try:
        ctx = _build_situation_context()
        report_text, model_name = await _generate_llm_report(ctx)

        # Cache in SQLite
        db = SessionLocal()
        try:
            db.add(SituationReport(
                simulation_step=ctx["step"],
                report_text=report_text,
                model_used=model_name,
                burning_count=ctx["burning"],
                burned_count=ctx["burned"],
                healthy_count=ctx["healthy"],
            ))
            db.commit()
        except Exception as db_err:
            logger.warning(f"Failed to cache situation report: {db_err}")
            db.rollback()
        finally:
            db.close()

        return {
            "status": "success",
            "report": report_text,
            "model": model_name,
            "context": ctx,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Situation report error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate situation report: {str(e)}"
        )


# ── 7. Monte Carlo Fire Forecast ──────────────────────────────────────────────

@app.get("/fire-forecast")
async def get_fire_forecast(
    steps: int = 10,
    trials: int = 100,
):
    """
    Runs Monte Carlo stochastic rollouts to forecast fire probability per cell.
    Returns a probability grid (0.0 - 1.0) for each of the 2500 cells.
    
    Query params:
      steps  — steps ahead to forecast (default: 10, max: 50)
      trials — number of stochastic trials (default: 100, max: 300)
    """
    # Guard bounds
    steps  = max(1, min(50, steps))
    trials = max(10, min(300, trials))

    if sim.simulation_step == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Run at least one simulation step before requesting a forecast."
        )

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: monte_carlo_forecast(sim, steps_ahead=steps, trials=trials)
        )
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"Monte Carlo forecast error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast failed: {str(e)}"
        )
