import requests

url = "http://127.0.0.1:8000/run-wildfire-prediction"
data = {
    "temp": 28.0,
    "humidity": 75.0,
    "wind_speed": 3.5,
    "wind_direction": 120.0,
    "latitude": -2.145,
    "longitude": -59.000,
    "duration": 240,
    "step": 3
}

try:
    response = requests.post(url, data=data, timeout=60)
    res_data = response.json()
    print("Status:", res_data.get("status"))
    ignite_t = res_data.get("ignite_t")
    fuel = res_data.get("fuel")
    centroids = res_data.get("centroids")
    
    print("ignite_t type:", type(ignite_t))
    print("ignite_t rows:", len(ignite_t) if ignite_t else "None")
    print("ignite_t cols:", len(ignite_t[0]) if ignite_t and len(ignite_t) > 0 else "None")
    
    # Flatten ignite_t to find min/max values other than 9999
    flat_ignite = [val for row in ignite_t for val in row]
    non_empty = [val for val in flat_ignite if val < 9999]
    print("Non-empty ignitions:", len(non_empty))
    if non_empty:
        print("Min ignition time:", min(non_empty))
        print("Max ignition time:", max(non_empty))
        
    print("fuel type:", type(fuel))
    print("fuel rows:", len(fuel) if fuel else "None")
    
    print("Centroids count:", len(centroids) if centroids else "None")
    print("Sample centroid:", centroids[0] if centroids and len(centroids) > 0 else "None")
except Exception as e:
    print("Error:", e)
