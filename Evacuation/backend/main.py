from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from models import IncidentPayload, SafeZone, RoutingSolution
from trigger_engine import TriggerEngine
from routing_engine import RoutingEngine
from dispatch_engine import DispatchEngine
import asyncio

app = FastAPI(title="Autonomous Wildfire Evacuation System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow frontend to connect
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

trigger_engine = TriggerEngine()
dispatch_engine = DispatchEngine()
routing_engine = None # Deferred initialization

@app.on_event("startup")
async def startup_event():
    global routing_engine
    routing_engine = RoutingEngine()
    if not dispatch_engine.smtp_user or not dispatch_engine.smtp_password:
        print("SMTP email delivery is not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, and SMTP_FROM to enable real emails.")

@app.post("/api/v1/predict")
async def receive_prediction(payload: IncidentPayload):
    """
    Receives incoming geospatial vector fields from the Wildfire Spread Predictor.
    """
    # 1. Trigger Engine Evaluates Risk
    is_emergency = trigger_engine.check_trigger(payload)
    
    if is_emergency:
        # 2. Dynamic Evacuation & Rerouting Engine
        payload.routing_solution = RoutingSolution(
            designated_safe_zones=[
                SafeZone(id="SZ-01", name="North County Fairgrounds", coords=(34.1205, -118.2102))
            ],
            impassable_infrastructure=["Forest_Route_9", "Bridge_Sector_B"],
            recommended_egress_corridors=routing_engine.calculate_egress(
                payload.target_zone.centroid, []
            )
        )
        
        # 3. Multi-Agency Automated Dispatch
        await dispatch_engine.dispatch(payload)
        return {"status": "CRITICAL_MAYDAY_AUTONOMOUS_TRIGGERED"}

    return {"status": "MONITORING", "message": "Thresholds not met."}

@app.websocket("/ws/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    await dispatch_engine.add_subscriber(websocket)
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        await dispatch_engine.remove_subscriber(websocket)
