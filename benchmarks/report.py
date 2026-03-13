#!/usr/bin/env python3
"""
Parse pytest-benchmark JSON output and generate charts + summary tables.

Usage:
    python benchmarks/report.py benchmarks/results/unit.json
    python benchmarks/report.py  # uses default path
"""

import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tabulate import tabulate

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")


def load_results(path):
    with open(path) as f:
        return json.load(f)


def extract_scaling_data(benchmarks):
    """Extract data for scaling heatmap from parametric sweep results."""
    data = defaultdict(dict)  # (n_amb, n_inc) -> median_ms

    for b in benchmarks:
        extra = b.get("extra_info", {})
        n_amb = extra.get("n_ambulances")
        n_inc = extra.get("n_incidents")
        if n_amb is None or n_inc is None:
            continue

        # Use total_ms from our timed_dispatch wrapper
        total_ms = extra.get("total_ms")
        if total_ms is None:
            # Fallback to pytest-benchmark stats (seconds → ms)
            total_ms = b["stats"]["median"] * 1000

        key = (n_amb, n_inc)
        if key not in data:
            data[key] = []
        data[key].append(total_ms)

    # Average across priority distributions
    averaged = {}
    for key, values in data.items():
        averaged[key] = np.median(values)

    return averaged


def plot_scaling_heatmap(data, output_path):
    """Ambulances × Incidents heatmap, color = median solve time."""
    amb_counts = sorted(set(k[0] for k in data))
    inc_counts = sorted(set(k[1] for k in data))

    matrix = np.zeros((len(amb_counts), len(inc_counts)))
    for i, a in enumerate(amb_counts):
        for j, n in enumerate(inc_counts):
            matrix[i, j] = data.get((a, n), 0)

    fig, ax = plt.subplots(figsize=(10, 6))
    im = ax.imshow(matrix, cmap="YlOrRd", aspect="auto")

    ax.set_xticks(range(len(inc_counts)))
    ax.set_xticklabels(inc_counts)
    ax.set_yticks(range(len(amb_counts)))
    ax.set_yticklabels(amb_counts)
    ax.set_xlabel("Number of Incidents")
    ax.set_ylabel("Number of Ambulances")
    ax.set_title("Dispatch Optimizer: Median Total Time (ms)")

    # Add text annotations
    for i in range(len(amb_counts)):
        for j in range(len(inc_counts)):
            val = matrix[i, j]
            color = "white" if val > matrix.max() * 0.6 else "black"
            ax.text(j, i, f"{val:.0f}", ha="center", va="center", color=color, fontsize=9)

    plt.colorbar(im, ax=ax, label="Time (ms)")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Saved heatmap: {output_path}")


def extract_breakdown_data(benchmarks):
    """Extract ILP solve vs cost matrix time for stacked bar chart."""
    rows = []
    for b in benchmarks:
        extra = b.get("extra_info", {})
        n_amb = extra.get("n_ambulances")
        n_inc = extra.get("n_incidents")
        ilp_ms = extra.get("ilp_solve_ms")
        cost_ms = extra.get("cost_matrix_ms")

        if n_amb is None or ilp_ms is None:
            continue

        # Only use "realistic" distribution to avoid clutter
        if extra.get("priority_dist", "realistic") != "realistic":
            continue

        rows.append({
            "label": f"{n_amb}A×{n_inc}I",
            "ilp_ms": ilp_ms,
            "cost_ms": cost_ms,
            "n_amb": n_amb,
            "n_inc": n_inc,
        })

    rows.sort(key=lambda r: (r["n_amb"], r["n_inc"]))
    return rows


def plot_latency_breakdown(rows, output_path):
    """Stacked bar chart: cost_matrix_ms + ilp_solve_ms per config."""
    if not rows:
        print("  No breakdown data to plot")
        return

    labels = [r["label"] for r in rows]
    ilp = [r["ilp_ms"] for r in rows]
    cost = [r["cost_ms"] for r in rows]

    x = np.arange(len(labels))
    width = 0.6

    fig, ax = plt.subplots(figsize=(14, 6))
    ax.bar(x, cost, width, label="Cost Matrix Build", color="#2196F3")
    ax.bar(x, ilp, width, bottom=cost, label="ILP Solve", color="#FF9800")

    ax.set_xlabel("Configuration (Ambulances × Incidents)")
    ax.set_ylabel("Time (ms)")
    ax.set_title("Latency Breakdown: Cost Matrix vs ILP Solve")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")
    ax.legend()

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Saved breakdown chart: {output_path}")


def print_summary_table(benchmarks):
    """Print a markdown summary table to console."""
    rows = []
    for b in benchmarks:
        extra = b.get("extra_info", {})
        name = b["name"]
        stats = b["stats"]

        row = {
            "Test": name,
            "Mean (ms)": f"{stats['mean']*1000:.1f}",
            "Median (ms)": f"{stats['median']*1000:.1f}",
            "StdDev (ms)": f"{stats['stddev']*1000:.1f}",
            "Rounds": stats.get("rounds", "?"),
        }

        if "total_ms" in extra:
            row["Optimizer (ms)"] = f"{extra['total_ms']:.1f}"
        if "ilp_solve_ms" in extra:
            row["ILP (ms)"] = f"{extra['ilp_solve_ms']:.1f}"

        rows.append(row)

    rows.sort(key=lambda r: r["Test"])

    print("\n=== Benchmark Summary ===\n")
    print(tabulate(rows, headers="keys", tablefmt="github"))
    print()


def plot_ilp_scaling(benchmarks, output_path):
    """Plot ILP solve time vs matrix size."""
    points = []
    for b in benchmarks:
        extra = b.get("extra_info", {})
        a = extra.get("A")
        n = extra.get("N")
        if a is None or n is None:
            continue
        median_s = b["stats"]["median"]
        points.append((a * n, a, n, median_s * 1000))

    if not points:
        return

    points.sort()
    sizes = [p[0] for p in points]
    labels = [f"{p[1]}×{p[2]}" for p in points]
    times = [p[3] for p in points]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(range(len(sizes)), times, "o-", color="#4CAF50", markersize=8)
    ax.set_xticks(range(len(sizes)))
    ax.set_xticklabels(labels)
    ax.set_xlabel("Matrix Size (A × N)")
    ax.set_ylabel("Median Solve Time (ms)")
    ax.set_title("ILP Solve Time Scaling")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()
    print(f"  Saved ILP scaling chart: {output_path}")


def main():
    if len(sys.argv) > 1:
        results_path = sys.argv[1]
    else:
        results_path = os.path.join(RESULTS_DIR, "unit.json")

    if not os.path.exists(results_path):
        print(f"Results file not found: {results_path}")
        print("Run benchmarks first:")
        print("  pytest benchmarks/bench_optimizer.py benchmarks/bench_ilp_solver.py \\")
        print("    --benchmark-only --benchmark-json=benchmarks/results/unit.json -v")
        sys.exit(1)

    data = load_results(results_path)
    benchmarks = data.get("benchmarks", [])

    if not benchmarks:
        print("No benchmark data found in results file")
        sys.exit(1)

    print(f"Loaded {len(benchmarks)} benchmark results from {results_path}\n")

    # Summary table
    print_summary_table(benchmarks)

    # Scaling heatmap
    scaling_data = extract_scaling_data(benchmarks)
    if scaling_data:
        plot_scaling_heatmap(scaling_data, os.path.join(RESULTS_DIR, "scaling_heatmap.png"))

    # Latency breakdown
    breakdown_rows = extract_breakdown_data(benchmarks)
    if breakdown_rows:
        plot_latency_breakdown(breakdown_rows, os.path.join(RESULTS_DIR, "latency_breakdown.png"))

    # ILP scaling (from bench_ilp_solver)
    ilp_benches = [b for b in benchmarks if b.get("extra_info", {}).get("A")]
    if ilp_benches:
        plot_ilp_scaling(ilp_benches, os.path.join(RESULTS_DIR, "ilp_scaling.png"))

    print("Done! Charts saved to benchmarks/results/")


if __name__ == "__main__":
    main()
