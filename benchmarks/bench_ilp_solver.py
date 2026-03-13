"""
Isolated ILP solver benchmarks and optimality gap extraction.

Tests build_k_assignment directly with synthetic cost matrices.
Verifies that the LP relaxation gap is ~0% (assignment problems
have totally unimodular constraint matrices).

No Docker or network access required.
"""

import os
import re
import tempfile

import numpy as np
import pulp as pl
import pytest

from optimization import build_k_assignment

MATRIX_SIZES = [
    (5, 5),
    (10, 10),
    (20, 20),
    (40, 40),
    (40, 50),
    (40, 100),
]


# --- Solve time benchmarks ---

@pytest.mark.parametrize("A,N", MATRIX_SIZES, ids=lambda *args: f"{args[0]}x{args[1]}" if isinstance(args[0], tuple) else str(args[0]))
def test_ilp_solve_time(benchmark, A, N):
    """Benchmark ILP solve time for various matrix sizes."""
    rng = np.random.default_rng(42)
    cost = rng.uniform(1, 100, size=(A, N))
    k = min(A, N)

    solver = pl.PULP_CBC_CMD(msg=False)

    def run():
        m, x = build_k_assignment(cost, k)
        status = m.solve(solver)
        assert pl.LpStatus[status] == "Optimal"
        return m

    result = benchmark.pedantic(run, iterations=3, rounds=5, warmup_rounds=1)

    benchmark.extra_info["A"] = A
    benchmark.extra_info["N"] = N
    benchmark.extra_info["k"] = k
    benchmark.extra_info["objective"] = result.objective.value()


@pytest.mark.parametrize("k_frac", [0.25, 0.5, 0.75, 1.0], ids=lambda f: f"k={f}")
def test_ilp_partial_assignment(benchmark, k_frac):
    """Benchmark with partial assignment (k < min(A,N))."""
    A, N = 40, 40
    k = max(1, int(min(A, N) * k_frac))
    rng = np.random.default_rng(42)
    cost = rng.uniform(1, 100, size=(A, N))

    solver = pl.PULP_CBC_CMD(msg=False)

    def run():
        m, x = build_k_assignment(cost, k)
        status = m.solve(solver)
        assert pl.LpStatus[status] == "Optimal"
        return m

    result = benchmark.pedantic(run, iterations=3, rounds=5, warmup_rounds=1)
    benchmark.extra_info["k"] = k
    benchmark.extra_info["objective"] = result.objective.value()


# --- Optimality gap extraction ---

@pytest.mark.parametrize("A,N", MATRIX_SIZES,
                         ids=[f"{a}x{n}" for a, n in MATRIX_SIZES])
def test_optimality_gap(A, N):
    """
    Verify that the IP-LP gap is ~0% for assignment problems.

    Assignment problems have totally unimodular constraint matrices,
    so the LP relaxation should always yield an integral solution.
    """
    rng = np.random.default_rng(42)
    cost = rng.uniform(1, 100, size=(A, N))
    k = min(A, N)

    # Solve as IP (binary variables)
    m_ip, x_ip = build_k_assignment(cost, k)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        log_path = f.name

    try:
        solver_ip = pl.PULP_CBC_CMD(msg=True, logPath=log_path)
        status_ip = m_ip.solve(solver_ip)
        assert pl.LpStatus[status_ip] == "Optimal"
        ip_obj = m_ip.objective.value()

        # Parse LP relaxation value from CBC log
        lp_obj = _parse_lp_relaxation(log_path)
    finally:
        os.unlink(log_path)

    if lp_obj is not None:
        gap = abs(ip_obj - lp_obj) / abs(ip_obj) if ip_obj != 0 else 0
        print(f"  [{A}x{N}] IP={ip_obj:.4f}, LP={lp_obj:.4f}, gap={gap:.6f}")
        assert gap < 0.01, f"Optimality gap {gap:.4%} exceeds 1% for {A}x{N}"
    else:
        # If we can't parse the log, verify integrality directly
        # by solving LP relaxation manually
        lp_obj = _solve_lp_relaxation(cost, k)
        gap = abs(ip_obj - lp_obj) / abs(ip_obj) if ip_obj != 0 else 0
        print(f"  [{A}x{N}] IP={ip_obj:.4f}, LP(manual)={lp_obj:.4f}, gap={gap:.6f}")
        assert gap < 0.01, f"Optimality gap {gap:.4%} exceeds 1% for {A}x{N}"


def test_optimality_gap_summary():
    """
    Run all matrix sizes and print a summary table.

    This is a standalone test that doesn't use pytest-benchmark,
    just prints results for easy reading.
    """
    print("\n=== Optimality Gap Summary ===")
    print(f"{'Size':>10s}  {'IP Obj':>10s}  {'LP Obj':>10s}  {'Gap':>10s}  {'Integral?':>10s}")
    print("-" * 55)

    for A, N in MATRIX_SIZES:
        rng = np.random.default_rng(42)
        cost = rng.uniform(1, 100, size=(A, N))
        k = min(A, N)

        # IP solve
        m_ip, x_ip = build_k_assignment(cost, k)
        solver = pl.PULP_CBC_CMD(msg=False)
        m_ip.solve(solver)
        ip_obj = m_ip.objective.value()

        # LP relaxation
        lp_obj = _solve_lp_relaxation(cost, k)
        gap = abs(ip_obj - lp_obj) / abs(ip_obj) if ip_obj != 0 else 0
        integral = "YES" if gap < 1e-6 else "NO"

        print(f"{A}x{N:>3d}       {ip_obj:10.4f}  {lp_obj:10.4f}  {gap:10.6f}  {integral:>10s}")

    print()


def _parse_lp_relaxation(log_path):
    """Parse CBC log file for the continuous (LP relaxation) objective value."""
    try:
        with open(log_path, "r") as f:
            content = f.read()

        # CBC logs "Continuous objective value is X.XX"
        match = re.search(r"Continuous objective value is\s+([\d.e+-]+)", content)
        if match:
            return float(match.group(1))

        # Alternative: "LP relaxation solution"
        match = re.search(r"LP relaxation.*?objective\s*=?\s*([\d.e+-]+)", content)
        if match:
            return float(match.group(1))
    except Exception:
        pass
    return None


def _solve_lp_relaxation(cost, k):
    """Solve the LP relaxation of the k-assignment problem directly."""
    A, N = cost.shape
    m = pl.LpProblem("k_assignment_lp", pl.LpMinimize)
    # Continuous variables [0, 1] instead of binary
    x = pl.LpVariable.dicts("x", (range(A), range(N)), 0, 1, pl.LpContinuous)

    m += pl.lpSum(cost[a, i] * x[a][i] for a in range(A) for i in range(N))

    for a in range(A):
        m += pl.lpSum(x[a][i] for i in range(N)) <= 1
    for i in range(N):
        m += pl.lpSum(x[a][i] for a in range(A)) <= 1
    m += pl.lpSum(x[a][i] for a in range(A) for i in range(N)) == k

    solver = pl.PULP_CBC_CMD(msg=False)
    m.solve(solver)
    return m.objective.value()


# --- Edge cases ---

def test_single_ambulance_single_incident():
    """Trivial 1x1 case."""
    cost = np.array([[42.0]])
    m, x = build_k_assignment(cost, 1)
    solver = pl.PULP_CBC_CMD(msg=False)
    status = m.solve(solver)
    assert pl.LpStatus[status] == "Optimal"
    assert abs(m.objective.value() - 42.0) < 1e-6
    assert x[0][0].value() > 0.5


def test_zero_assignment():
    """k=0 should produce zero-cost solution."""
    cost = np.array([[10.0, 20.0], [30.0, 40.0]])
    m, x = build_k_assignment(cost, 0)
    solver = pl.PULP_CBC_CMD(msg=False)
    status = m.solve(solver)
    assert pl.LpStatus[status] == "Optimal"
    assert abs(m.objective.value()) < 1e-6


def test_rectangular_matrix():
    """More incidents than ambulances (typical overload scenario)."""
    rng = np.random.default_rng(99)
    cost = rng.uniform(1, 50, size=(5, 20))
    m, x = build_k_assignment(cost, 5)
    solver = pl.PULP_CBC_CMD(msg=False)
    status = m.solve(solver)
    assert pl.LpStatus[status] == "Optimal"

    # Verify exactly 5 assignments
    total = sum(x[a][i].value() for a in range(5) for i in range(20) if x[a][i].value() > 0.5)
    assert abs(total - 5) < 1e-6
