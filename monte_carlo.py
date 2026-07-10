"""
monte_carlo.py — Monte Carlo Fire Spread Forecasting
-----------------------------------------------------
Runs N stochastic rollouts from the current simulation state to compute
the *probability* of each cell catching fire in the next `steps_ahead` steps.

Usage:
    from monte_carlo import monte_carlo_forecast
    result = monte_carlo_forecast(sim, steps_ahead=10, trials=100)
    # result['probability_grid'] → list of {row, col, probability, already_burning}
    # result['high_risk_count'] → cells with probability >= 0.70
"""

import copy
import math
import random
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger("guesin_backend")

# ─────────────────────────────────────────────────────────────────────────────

def monte_carlo_forecast(sim, steps_ahead: int = 10, trials: int = 100) -> Dict:
    """
    Performs a Monte Carlo rollout forecast.

    Parameters
    ----------
    sim          : WildfireSimulation — the live simulation instance (read-only)
    steps_ahead  : int — number of simulation steps to project forward
    trials       : int — number of stochastic trials to run (higher = more accurate)

    Returns
    -------
    dict with keys:
        probability_grid  : List[dict]  — [{row, col, probability, already_burning}, ...]
        trials            : int
        steps_ahead       : int
        high_risk_count   : int — cells with p >= 0.70 that aren't already burning
        moderate_risk_count : int — cells with 0.3 <= p < 0.70
        grid_size         : int
        expected_new_cells : float — expected number of new cells that will catch fire
    """
    grid_size = sim.size
    logger.info(f"Monte Carlo forecast: {trials} trials × {steps_ahead} steps on {grid_size}×{grid_size} grid")

    # Counters: how many trials resulted in fire reaching each cell
    fire_hit = [[0 for _ in range(grid_size)] for _ in range(grid_size)]

    # Track cells that are already on fire in the current state
    already_burning = set()
    for r in range(grid_size):
        for c in range(grid_size):
            if sim.grid[r][c]["fire_state"] in ("burning", "burned"):
                already_burning.add((r, c))

    for trial_idx in range(trials):
        # Deep copy the current grid state for this trial
        trial_grid = _deep_copy_grid(sim.grid, grid_size)

        # Run simulation steps with slight random variation per trial
        trial_seed = trial_idx * 31 + random.randint(0, 999)
        random.seed(trial_seed)

        for _ in range(steps_ahead):
            trial_grid = _step(trial_grid, grid_size, sim)

        # Record cells that caught fire in this trial
        for r in range(grid_size):
            for c in range(grid_size):
                if trial_grid[r][c]["fire_state"] in ("burning", "burned"):
                    fire_hit[r][c] += 1

    # Reset random seed so simulation is not affected
    random.seed()

    # Build probability grid output
    probability_grid = []
    high_risk_count = 0
    moderate_risk_count = 0
    expected_new_cells = 0.0

    for r in range(grid_size):
        for c in range(grid_size):
            is_already = (r, c) in already_burning
            if is_already:
                prob = 1.0
            else:
                prob = round(fire_hit[r][c] / trials, 4)
                expected_new_cells += prob
                if prob >= 0.70:
                    high_risk_count += 1
                elif prob >= 0.30:
                    moderate_risk_count += 1

            probability_grid.append({
                "row": r,
                "col": c,
                "probability": prob,
                "already_burning": is_already,
            })

    logger.info(
        f"Monte Carlo complete. High risk: {high_risk_count} cells, "
        f"Moderate: {moderate_risk_count} cells, "
        f"Expected new: {expected_new_cells:.1f}"
    )

    return {
        "probability_grid": probability_grid,
        "trials": trials,
        "steps_ahead": steps_ahead,
        "high_risk_count": high_risk_count,
        "moderate_risk_count": moderate_risk_count,
        "grid_size": grid_size,
        "expected_new_cells": round(expected_new_cells, 1),
    }


# ─── Fork Simulation (used by /fork-simulation endpoint) ─────────────────────

def run_fork_simulation(
    sim,
    wind_speed_override: float = None,
    wind_direction_override: float = None,
    firebreak_cells: List[Tuple[int, int]] = None,
    steps: int = 10,
) -> Dict:
    """
    Clones the current simulation state, applies scenario modifications,
    runs `steps` ahead, and returns a comparison with the original trajectory.

    Parameters
    ----------
    sim                     : WildfireSimulation
    wind_speed_override     : float | None — override wind speed for the fork
    wind_direction_override : float | None — override wind direction for the fork
    firebreak_cells         : list of (row, col) — cells to have fuel cleared (firebreaks)
    steps                   : int — steps to run on the fork

    Returns
    -------
    dict with keys:
        original_snapshot   : grid state after `steps` on real sim (approximate)
        fork_snapshot       : grid state after `steps` on forked sim
        comparison          : {original_burned, fork_burned, saved_cells, pct_reduction}
        scenario            : description of what was changed
    """
    grid_size = sim.size
    firebreak_cells = firebreak_cells or []

    # ── Build original trajectory (run on a copy too, for fair comparison) ──
    original_grid = _deep_copy_grid(sim.grid, grid_size)
    for _ in range(steps):
        original_grid = _step(original_grid, grid_size, sim)

    original_burned = sum(
        1 for r in range(grid_size) for c in range(grid_size)
        if original_grid[r][c]["fire_state"] in ("burning", "burned")
    )

    # ── Build forked trajectory ───────────────────────────────────────────────
    fork_grid = _deep_copy_grid(sim.grid, grid_size)

    # Apply wind overrides
    if wind_speed_override is not None or wind_direction_override is not None:
        for r in range(grid_size):
            for c in range(grid_size):
                if wind_speed_override is not None:
                    fork_grid[r][c]["wind_speed"] = wind_speed_override
                if wind_direction_override is not None:
                    fork_grid[r][c]["wind_direction"] = wind_direction_override

    # Apply firebreaks (clear fuel load)
    for (fb_r, fb_c) in firebreak_cells:
        if 0 <= fb_r < grid_size and 0 <= fb_c < grid_size:
            if fork_grid[fb_r][fb_c]["fire_state"] == "unburned":
                fork_grid[fb_r][fb_c]["fuel_load"] = 0.0
                fork_grid[fb_r][fb_c]["vegetation_density"] = 0.0
                fork_grid[fb_r][fb_c]["risk_score"] = 0.0

    # Run the fork
    for _ in range(steps):
        fork_grid = _step(fork_grid, grid_size, sim)

    fork_burned = sum(
        1 for r in range(grid_size) for c in range(grid_size)
        if fork_grid[r][c]["fire_state"] in ("burning", "burned")
    )

    saved_cells = max(0, original_burned - fork_burned)
    pct_reduction = (saved_cells / original_burned * 100) if original_burned > 0 else 0.0

    # Build compact snapshot (just fire_state per cell for rendering)
    def _snapshot(grid):
        return [
            {"row": r, "col": c,
             "fire_state": grid[r][c]["fire_state"],
             "risk_score": round(grid[r][c]["risk_score"], 3)}
            for r in range(grid_size) for c in range(grid_size)
        ]

    # Build scenario description
    scenario_parts = []
    if wind_speed_override is not None:
        scenario_parts.append(f"Wind speed: {wind_speed_override} m/s")
    if wind_direction_override is not None:
        scenario_parts.append(f"Wind direction: {wind_direction_override}°")
    if firebreak_cells:
        scenario_parts.append(f"{len(firebreak_cells)} firebreak cell(s) cleared")
    scenario_desc = ", ".join(scenario_parts) if scenario_parts else "No modifications (baseline)"

    return {
        "original_snapshot": _snapshot(original_grid),
        "fork_snapshot": _snapshot(fork_grid),
        "comparison": {
            "original_burned": original_burned,
            "fork_burned": fork_burned,
            "saved_cells": saved_cells,
            "pct_reduction": round(pct_reduction, 1),
        },
        "scenario": scenario_desc,
        "steps": steps,
        "grid_size": grid_size,
    }


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _deep_copy_grid(grid: List[List[Dict]], grid_size: int) -> List[List[Dict]]:
    """Fast shallow-dict copy of the grid (avoids full deepcopy overhead)."""
    return [[dict(grid[r][c]) for c in range(grid_size)] for r in range(grid_size)]


def _step(grid: List[List[Dict]], grid_size: int, sim) -> List[List[Dict]]:
    """
    Runs one cellular automata step on a copied grid using the sim's
    catch-probability logic (which includes ML model if available).
    Adds ±30% random variance per trial to create stochastic spread.
    """
    old_states    = [[grid[r][c]["fire_state"]    for c in range(grid_size)] for r in range(grid_size)]
    old_durations = [[grid[r][c]["burn_duration"] for c in range(grid_size)] for r in range(grid_size)]

    for r in range(grid_size):
        for c in range(grid_size):
            if old_states[r][c] != "burning":
                continue

            curr_dur = old_durations[r][c] + 1
            grid[r][c]["burn_duration"] = curr_dur

            # Spread to 8 neighbors
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0:
                        continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < grid_size and 0 <= nc < grid_size:
                        if old_states[nr][nc] == "unburned" and grid[nr][nc]["fire_state"] == "unburned":
                            # Use sim's probability (includes ML) + random variance for stochasticity
                            p = sim.calculate_catch_probability(r, c, nr, nc)
                            p_varied = min(0.98, p * random.uniform(0.75, 1.25))
                            if random.random() < p_varied:
                                grid[nr][nc]["fire_state"] = "burning"
                                grid[nr][nc]["burn_duration"] = 0

            # Burn out after 3 steps
            if curr_dur >= 3:
                grid[r][c]["fire_state"] = "burned"
                grid[r][c]["fuel_load"] = 0.0
                grid[r][c]["risk_score"] = 0.0

    return grid
