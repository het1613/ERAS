"""
Data generators for benchmarking the dispatch optimizer.

Generates realistic Waterloo Region ambulance/incident data and provides
a timing wrapper around the optimizer.
"""

import math
import time
import uuid
import numpy as np
from shared.types import Vehicle, PRIORITY_WEIGHT_MAP

# Waterloo Region bounding box (matches real vehicle seed data in init.sql)
LAT_MIN, LAT_MAX = 43.28, 43.60  # Ayr to Elmira
LON_MIN, LON_MAX = -80.72, -80.30  # New Hamburg to Cambridge

# City centers for clustered generation
CITY_CENTERS = {
    "kitchener": (43.4516, -80.4925),
    "waterloo": (43.4643, -80.5204),
    "cambridge": (43.3600, -80.3150),
}

# Hospital coordinates from init.sql
HOSPITALS = np.array([
    [43.43863840, -80.50070577],  # St. Mary's General
    [43.37850136, -80.32882889],  # Cambridge Memorial
    [43.42630976, -80.40818941],  # Grand River Freeport
    [43.45684165, -80.51168502],  # Grand River Hospital
])

# Priority distributions
PRIORITY_DISTRIBUTIONS = {
    "realistic": {"Purple": 0.05, "Red": 0.10, "Orange": 0.25, "Yellow": 0.40, "Green": 0.20},
    "all_purple": {"Purple": 1.0, "Red": 0.0, "Orange": 0.0, "Yellow": 0.0, "Green": 0.0},
    "uniform": {"Purple": 0.2, "Red": 0.2, "Orange": 0.2, "Yellow": 0.2, "Green": 0.2},
    "mass_casualty": {"Purple": 0.30, "Red": 0.40, "Orange": 0.20, "Yellow": 0.10, "Green": 0.0},
}


def generate_ambulances(n, rng=None):
    """
    Generate n ambulances with positions clustered around KW/Cambridge.

    Returns list[Vehicle].
    """
    if rng is None:
        rng = np.random.default_rng(42)

    centers = list(CITY_CENTERS.values())
    vehicles = []
    for i in range(n):
        center = centers[i % len(centers)]
        lat = center[0] + rng.normal(0, 0.02)
        lon = center[1] + rng.normal(0, 0.02)
        # Clamp to bounding box
        lat = max(LAT_MIN, min(LAT_MAX, lat))
        lon = max(LON_MIN, min(LON_MAX, lon))
        vehicles.append(Vehicle(
            id=f"bench-amb-{i+1}",
            lat=lat,
            lon=lon,
            status="available",
            vehicle_type="ambulance",
        ))
    return vehicles


def generate_incidents(n, priority_dist="realistic", rng=None, cluster_center=None):
    """
    Generate n incidents with specified priority distribution.

    Args:
        n: Number of incidents.
        priority_dist: Key into PRIORITY_DISTRIBUTIONS, or "mass_casualty"
            which also clusters incidents geographically.
        rng: numpy random generator.
        cluster_center: Optional (lat, lon) center for mass casualty clustering.

    Returns list[dict] with lat, lon, weight, id keys.
    """
    if rng is None:
        rng = np.random.default_rng(123)

    dist = PRIORITY_DISTRIBUTIONS[priority_dist]
    priorities = list(dist.keys())
    probs = list(dist.values())

    # For mass_casualty, cluster incidents within ~500m of a center
    if priority_dist == "mass_casualty":
        if cluster_center is None:
            cluster_center = CITY_CENTERS["kitchener"]
        spread = 0.005  # ~500m in degrees
    else:
        cluster_center = None
        spread = None

    incidents = []
    for i in range(n):
        priority = rng.choice(priorities, p=probs)
        weight = PRIORITY_WEIGHT_MAP[priority]

        if cluster_center is not None:
            lat = cluster_center[0] + rng.normal(0, spread)
            lon = cluster_center[1] + rng.normal(0, spread)
        else:
            # Spread across Waterloo Region, biased toward city centers
            center = list(CITY_CENTERS.values())[rng.integers(0, len(CITY_CENTERS))]
            lat = center[0] + rng.normal(0, 0.03)
            lon = center[1] + rng.normal(0, 0.03)

        lat = max(LAT_MIN, min(LAT_MAX, lat))
        lon = max(LON_MIN, min(LON_MAX, lon))

        incidents.append({
            "id": str(uuid.uuid4()),
            "lat": float(lat),
            "lon": float(lon),
            "weight": weight,
        })
    return incidents


def timed_dispatch(ambulances, incidents, hospitals, solver=None, verbose=False):
    """
    Wrapper around run_weighted_dispatch_with_hospitals that captures timing.

    Monkey-patches build_k_assignment to time each ILP solve separately.

    Returns the optimizer result dict with an added 'timings' key:
        {
            "total_ms": float,
            "ilp_solve_ms": float,    # sum of all m.solve() calls
            "cost_matrix_ms": float,   # total - ilp_solve
            "per_round": list[dict],   # per-round timing breakdown
        }
    """
    import optimization
    import pulp as pl

    solve_times = []
    round_timings = []

    # Monkey-patch: wrap m.solve() to capture timing
    original_build = optimization.build_k_assignment

    def timed_build(cost_AxN, k):
        m, x = original_build(cost_AxN, k)
        original_solve = m.solve

        def timed_solve(solver_arg=None):
            t0 = time.perf_counter()
            result = original_solve(solver_arg)
            elapsed = (time.perf_counter() - t0) * 1000
            solve_times.append(elapsed)
            return result

        m.solve = timed_solve
        return m, x

    optimization.build_k_assignment = timed_build
    try:
        t_total_start = time.perf_counter()
        result = optimization.run_weighted_dispatch_with_hospitals(
            ambulances, incidents, hospitals, solver=solver, verbose=verbose
        )
        total_ms = (time.perf_counter() - t_total_start) * 1000
    finally:
        optimization.build_k_assignment = original_build

    ilp_solve_ms = sum(solve_times)
    cost_matrix_ms = total_ms - ilp_solve_ms

    # Build per-round breakdown
    for i, st in enumerate(solve_times):
        round_timings.append({
            "round": i + 1,
            "ilp_solve_ms": st,
        })

    result["timings"] = {
        "total_ms": total_ms,
        "ilp_solve_ms": ilp_solve_ms,
        "cost_matrix_ms": cost_matrix_ms,
        "per_round": round_timings,
    }
    return result
