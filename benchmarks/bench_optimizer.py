"""
Parametric benchmarks of the full dispatch optimizer.

Tests run_weighted_dispatch_with_hospitals across a matrix of:
  - Ambulance counts: [5, 10, 20, 40]
  - Incident counts: [1, 5, 10, 20, 50, 100]
  - Priority distributions: [realistic, all_purple, uniform]

Uses pytest-benchmark in pedantic mode for stable timing.
No Docker or network access required.
"""

import math

import numpy as np
import pulp as pl
import pytest

from generators import (
    HOSPITALS,
    generate_ambulances,
    generate_incidents,
    timed_dispatch,
)
from optimization import run_weighted_dispatch_with_hospitals

AMBULANCE_COUNTS = [5, 10, 20, 40]
INCIDENT_COUNTS = [1, 5, 10, 20, 50, 100]
PRIORITY_DISTS = ["realistic", "all_purple", "uniform"]


def _run_and_validate(n_amb, n_inc, priority_dist, hospitals):
    """Run optimizer and validate correctness. Returns timed result."""
    rng_amb = np.random.default_rng(42)
    rng_inc = np.random.default_rng(123)
    ambulances = generate_ambulances(n_amb, rng=rng_amb)
    incidents = generate_incidents(n_inc, priority_dist=priority_dist, rng=rng_inc)

    result = timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    # Validate: all incidents assigned
    total_assigned = sum(
        len(r["assignments"]) for r in result["rounds"]
    )
    assert total_assigned == n_inc, f"Expected {n_inc} assignments, got {total_assigned}"

    # Validate: correct number of rounds
    expected_rounds = math.ceil(n_inc / n_amb)
    assert len(result["rounds"]) == expected_rounds, (
        f"Expected {expected_rounds} rounds, got {len(result['rounds'])}"
    )

    # Validate: no ambulance used twice in same round
    for rnd in result["rounds"]:
        amb_ids = [a["ambulance_id"] for a in rnd["assignments"]]
        assert len(amb_ids) == len(set(amb_ids)), "Ambulance assigned twice in one round"

    return result


# --- Parametric sweep ---

@pytest.mark.parametrize("n_amb", AMBULANCE_COUNTS, ids=lambda n: f"{n}amb")
@pytest.mark.parametrize("n_inc", INCIDENT_COUNTS, ids=lambda n: f"{n}inc")
@pytest.mark.parametrize("priority_dist", PRIORITY_DISTS)
def test_optimizer_scaling(benchmark, n_amb, n_inc, priority_dist):
    """Benchmark optimizer across ambulance × incident × priority matrix."""
    hospitals = HOSPITALS.copy()

    def run():
        return _run_and_validate(n_amb, n_inc, priority_dist, hospitals)

    result = benchmark.pedantic(run, iterations=1, rounds=3, warmup_rounds=1)

    # Store extra info in benchmark
    benchmark.extra_info["n_ambulances"] = n_amb
    benchmark.extra_info["n_incidents"] = n_inc
    benchmark.extra_info["priority_dist"] = priority_dist
    benchmark.extra_info["total_ms"] = result["timings"]["total_ms"]
    benchmark.extra_info["ilp_solve_ms"] = result["timings"]["ilp_solve_ms"]
    benchmark.extra_info["cost_matrix_ms"] = result["timings"]["cost_matrix_ms"]
    benchmark.extra_info["n_rounds"] = len(result["rounds"])
    benchmark.extra_info["total_weighted_cost"] = result["total_weighted_cost"]


# --- Focused scenarios ---

def test_single_incident(benchmark):
    """Most common real-world case: 1 new incident, ~40 ambulances."""
    hospitals = HOSPITALS.copy()
    ambulances = generate_ambulances(40)
    incidents = generate_incidents(1, priority_dist="realistic")

    def run():
        return timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    result = benchmark.pedantic(run, iterations=3, rounds=5, warmup_rounds=1)
    assert len(result["rounds"]) == 1
    assert len(result["rounds"][0]["assignments"]) == 1
    benchmark.extra_info["total_ms"] = result["timings"]["total_ms"]
    benchmark.extra_info["ilp_solve_ms"] = result["timings"]["ilp_solve_ms"]


def test_overload(benchmark):
    """Stress test: 100 incidents, 10 ambulances → 10 rounds."""
    hospitals = HOSPITALS.copy()
    ambulances = generate_ambulances(10)
    incidents = generate_incidents(100, priority_dist="realistic")

    def run():
        return timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    result = benchmark.pedantic(run, iterations=1, rounds=3, warmup_rounds=1)
    assert len(result["rounds"]) == 10
    total = sum(len(r["assignments"]) for r in result["rounds"])
    assert total == 100
    benchmark.extra_info["total_ms"] = result["timings"]["total_ms"]
    benchmark.extra_info["n_rounds"] = 10


def test_mass_casualty(benchmark):
    """Geographically clustered incidents (MCI scenario)."""
    hospitals = HOSPITALS.copy()
    ambulances = generate_ambulances(40)
    incidents = generate_incidents(20, priority_dist="mass_casualty")

    def run():
        return timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    result = benchmark.pedantic(run, iterations=1, rounds=3, warmup_rounds=1)
    assert len(result["rounds"]) == 1  # 20 incidents, 40 ambulances → 1 round
    benchmark.extra_info["total_ms"] = result["timings"]["total_ms"]
    benchmark.extra_info["total_weighted_cost"] = result["total_weighted_cost"]


def test_assignment_quality():
    """Verify that higher-weight incidents get closer ambulances."""
    hospitals = HOSPITALS.copy()
    ambulances = generate_ambulances(40)

    # Create two incidents: one Purple (weight=16), one Green (weight=1)
    incidents = [
        {"id": "purple-1", "lat": 43.45, "lon": -80.50, "weight": 16},
        {"id": "green-1", "lat": 43.45, "lon": -80.49, "weight": 1},
    ]

    result = timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    assignments = result["rounds"][0]["assignments"]
    assert len(assignments) == 2

    # The purple incident should have a lower weighted cost
    purple_assign = next(a for a in assignments if a["incident_id"] == 0)
    green_assign = next(a for a in assignments if a["incident_id"] == 1)
    assert purple_assign["weighted_cost"] < green_assign["weighted_cost"], (
        "Purple incident should have lower weighted cost due to weight=16"
    )


def test_max_assignment_distance():
    """Ensure no assignment has unreasonably large distance (within Waterloo Region)."""
    hospitals = HOSPITALS.copy()
    ambulances = generate_ambulances(40)
    incidents = generate_incidents(40, priority_dist="realistic")

    result = timed_dispatch(ambulances, incidents, hospitals, verbose=False)

    for rnd in result["rounds"]:
        for a in rnd["assignments"]:
            # Waterloo Region is ~40km across; no assignment should exceed 100km
            assert a["unweighted_dist"] < 100, (
                f"Unreasonable distance: {a['unweighted_dist']:.1f} km"
            )
