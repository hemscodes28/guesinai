import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(method, path, data=None, params=None):
    url = f"{BASE_URL}{path}"
    print(f"[TEST] Testing {method} {path} ...")
    try:
        if method == "GET":
            r = requests.get(url, params=params)
        else:
            r = requests.post(url, json=data)
        
        print(f"Status Code: {r.status_code}")
        if r.status_code == 200:
            res = r.json()
            # Encode to ascii to prevent cp1252 console printing issues
            summary = str(res)[:200]
            clean_summary = summary.encode('ascii', errors='ignore').decode('ascii') + "..."
            print(f"Response (truncated): {clean_summary}")
            return res
        else:
            print(f"Error Response: {r.text}")
    except Exception as e:
        print(f"Connection failed: {e}")
    return None

def main():
    print("=== Guesin.ai API Verification Script ===")
    
    # 1. Test ML Model Status
    test_endpoint("GET", "/ml-model-status")

    # 2. Test AQI Grid
    test_endpoint("GET", "/aqi-grid")

    # 3. Test Situation Report
    test_endpoint("GET", "/situation-report")

    # 4. Trigger Ignition
    print("\n[STEP] Igniting cell (25, 25)...")
    test_endpoint("POST", "/generate-hotspot", data={"row": 25, "col": 25})

    # 5. Simulate Step
    print("\n[STEP] Advancing simulation by 1 step...")
    test_endpoint("POST", "/simulate-step")

    # 6. Test Monte Carlo Fire Forecast
    test_endpoint("GET", "/fire-forecast", params={"steps": 5, "trials": 30})

    # 7. Test What-If Fork Simulation
    test_endpoint("POST", "/fork-simulation", data={
        "wind_speed": 15.0,
        "wind_direction": 180.0,
        "firebreak_cells": [[26, 25], [26, 26]],
        "steps": 5
    })

    # 8. Test Situation Report after fire spreads
    test_endpoint("GET", "/situation-report")

if __name__ == "__main__":
    main()
