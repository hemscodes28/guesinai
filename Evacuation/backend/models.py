from pydantic import BaseModel, Field
from typing import List, Tuple, Optional
from datetime import datetime

class TargetZone(BaseModel):
    settlement_name: str
    centroid: Tuple[float, float]
    estimated_population: int

class HazardTelemetry(BaseModel):
    rate_of_spread_kmh: float
    primary_vector_bearing: float
    time_to_impact_mins: int
    confidence_coefficient: float

class SafeZone(BaseModel):
    id: str
    name: str
    coords: Tuple[float, float]

class RoutingSolution(BaseModel):
    designated_safe_zones: List[SafeZone]
    impassable_infrastructure: List[str]
    recommended_egress_corridors: List[str]

class IncidentPayload(BaseModel):
    incident_id: str
    timestamp: datetime
    emergency_level: str
    target_zone: TargetZone
    hazard_telemetry: HazardTelemetry
    routing_solution: Optional[RoutingSolution] = None
