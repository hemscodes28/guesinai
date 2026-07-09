import requests
import json
from datetime import datetime

url = "http://localhost:8000/api/v1/predict"

payload = {
    "incident_id": "WF-2026-N9821",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "emergency_level": "CRITICAL_MAYDAY_AUTONOMOUS",
    "target_zone": {
        "settlement_name": "Oakridge Village",
        "centroid": [34.0522, -118.2437],
        "estimated_population": 1450
    },
    "hazard_telemetry": {
        "rate_of_spread_kmh": 5.4,
        "primary_vector_bearing": 165.2,
        "time_to_impact_mins": 38,
        "confidence_coefficient": 0.94
    }
}

print("Sending Wildfire Prediction Payload...")
try:
    response = requests.post(url, json=payload)
    print("Response Status Code:", response.status_code)
    print("Response JSON:", response.json())
except Exception as e:
    print("Error connecting to server:", e)
