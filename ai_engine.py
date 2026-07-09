import heapq
import math
from typing import Dict, List, Tuple, Optional

def calculate_evacuation_route(grid: List[List[Dict]], start_row: int, start_col: int) -> Optional[List[Tuple[int, int]]]:
    """
    Computes the safest, shortest evacuation path from a starting cell to a safe boundary cell.
    Uses Dijkstra's algorithm. High spread risk cells are penalized; burning/burned cells are impassable obstacles.
    """
    grid_size = len(grid)
    
    # Verify starting point is valid and not on fire
    if not (0 <= start_row < grid_size and 0 <= start_col < grid_size):
        return None
        
    start_cell = grid[start_row][start_col]
    if start_cell["fire_state"] != "unburned":
        return None

    # Priority queue stores tuples of (cumulative_cost, row, col, path_list)
    # Start path with the starting node
    pq = [(0.0, start_row, start_col, [(start_row, start_col)])]
    
    # Keep track of minimum cost to reach each node
    visited = {}

    while pq:
        cost, r, c, path = heapq.heappop(pq)

        # Check if we reached the boundary (safe zone)
        # Boundary cell must be unburned and have low/moderate risk (< 0.7 risk_score)
        is_boundary = (r == 0 or r == grid_size - 1 or c == 0 or c == grid_size - 1)
        if is_boundary and grid[r][c]["fire_state"] == "unburned" and grid[r][c]["risk_score"] < 0.7:
            # Found a safe boundary cell, return path!
            return path

        if (r, c) in visited and visited[(r, c)] <= cost:
            continue
        visited[(r, c)] = cost

        # Check 8-way neighbors
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc

                if 0 <= nr < grid_size and 0 <= nc < grid_size:
                    neighbor = grid[nr][nc]
                    
                    # Burning or burned cells are impassable
                    if neighbor["fire_state"] != "unburned":
                        continue

                    # Base movement cost (1.0 for orthogonal, sqrt(2) for diagonal)
                    move_dist = 1.414 if (dr != 0 and dc != 0) else 1.0
                    
                    # Risk penalty: cells with higher risk are significantly costlier
                    # This steers the path away from dangerous critical zones
                    risk_penalty = neighbor["risk_score"] * 12.0
                    
                    # Elevation cost: going uphill adds friction
                    elev_diff = neighbor["elevation"] - grid[r][c]["elevation"]
                    slope_penalty = (elev_diff / 25.0) if elev_diff > 0 else 0.0

                    step_cost = move_dist * (1.0 + risk_penalty + slope_penalty)
                    new_cost = cost + step_cost

                    if (nr, nc) not in visited or visited[(nr, nc)] > new_cost:
                        heapq.heappush(pq, (new_cost, nr, nc, path + [(nr, nc)]))

    return None

def allocate_mitigation_resources(grid: List[List[Dict]]) -> List[Dict]:
    """
    Simulates an AI Resource Allocator that deploys containment assets based on fire fronts and terrain features:
    1. Deploys "Fire Engines" to high-risk unburned cells along the active fire perimeter.
    2. Deploys "Water-Drop Helicopters" to active burning zones adjacent to water bodies (low elevation valleys).
    """
    grid_size = len(grid)
    resources = []
    
    # 1. Identify active burning cells and water sources
    burning_cells = []
    water_cells = []
    
    for r in range(grid_size):
        for c in range(grid_size):
            cell = grid[r][c]
            if cell["fire_state"] == "burning":
                burning_cells.append(cell)
            # Low elevation areas represent streams/water channels
            if cell["elevation"] < 105.0:
                water_cells.append(cell)

    if not burning_cells:
        return []

    # 2. Deploy Fire Engines to contain fire front (unburned cells adjacent to burning cells)
    perimeter_candidates = []
    visited_perimeter = set()

    for fire in burning_cells:
        fr, fc = fire["row"], fire["col"]
        for dr in [-1, 0, 1]:
            for dc in [-1, 0, 1]:
                if dr == 0 and dc == 0:
                    continue
                nr, nc = fr + dr, fc + dc
                if 0 <= nr < grid_size and 0 <= nc < grid_size:
                    neighbor = grid[nr][nc]
                    if neighbor["fire_state"] == "unburned" and (nr, nc) not in visited_perimeter:
                        visited_perimeter.add((nr, nc))
                        # Score candidates: prioritize high fuel load and risk (where fire engine breaks are most critical)
                        score = neighbor["risk_score"] * 0.6 + neighbor["fuel_load"] * 0.4
                        perimeter_candidates.append((score, neighbor))

    # Sort perimeter candidates by importance
    perimeter_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Deploy up to 4 Fire Engines on critical front lines
    engines_to_deploy = min(4, len(perimeter_candidates))
    for i in range(engines_to_deploy):
        _, cell = perimeter_candidates[i]
        resources.append({
            "asset_id": f"ENG-{i+1:02d}",
            "type": "Fire Engine",
            "row": cell["row"],
            "col": cell["col"],
            "latitude": cell["latitude"],
            "longitude": cell["longitude"],
            "status": "Establishing Containment Line",
            "impact_score": round(0.70 + (cell["fuel_load"] * 0.25), 2),
            "message": f"Engine {i+1} deployed at ({cell['row']}, {cell['col']}) to build dynamic firebreak."
        })

    # 3. Deploy Water-Drop Helicopters to burning cells near water sources
    helicopter_candidates = []
    for fire in burning_cells:
        fr, fc = fire["row"], fire["col"]
        
        # Calculate distance to closest water source
        min_dist = 999.0
        for water in water_cells:
            dist = math.sqrt((fr - water["row"])**2 + (fc - water["col"])**2)
            if dist < min_dist:
                min_dist = dist

        # If water source is within 6 units, helicopter operations are highly efficient
        if min_dist <= 6.0:
            # Score: prioritize extinguishing cells with high fuel load and high risk to suppress spread
            score = fire["risk_score"] * 0.5 + fire["fuel_load"] * 0.5 - (min_dist * 0.05)
            helicopter_candidates.append((score, fire))

    # Sort candidates
    helicopter_candidates.sort(key=lambda x: x[0], reverse=True)
    
    # Deploy up to 2 Helicopters
    copters_to_deploy = min(2, len(helicopter_candidates))
    for i in range(copters_to_deploy):
        _, cell = helicopter_candidates[i]
        resources.append({
            "asset_id": f"HELI-{i+1:02d}",
            "type": "Helicopter",
            "row": cell["row"],
            "col": cell["col"],
            "latitude": cell["latitude"],
            "longitude": cell["longitude"],
            "status": "Aerial Water Suppress",
            "impact_score": round(0.80 + (cell["fuel_load"] * 0.18), 2),
            "message": f"Helicopter {i+1} executing water drop cycles on hot spot at ({cell['row']}, {cell['col']})."
        })

    return resources
