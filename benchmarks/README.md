# Dispatch Optimizer Benchmarks

Load testing and benchmarking suite for the ERAS ILP dispatch optimizer (`services/geospatial-dispatch/optimization.py`). Measures solve time, optimality gap, latency breakdown, and assignment quality across a range of fleet sizes and incident loads.

## Quick Start

```bash
# Create conda environment
conda env create -f benchmarks/environment.yml
conda activate eras-bench

# Run unit benchmarks (no Docker needed)
python -m pytest benchmarks/bench_optimizer.py benchmarks/bench_ilp_solver.py \
  --benchmark-only --benchmark-json=benchmarks/results/unit.json -v

# Run integration benchmarks (requires Docker stack)
docker compose up -d
python -m pytest benchmarks/bench_endpoint.py -v -s

# Generate charts and tables from results
python benchmarks/report.py benchmarks/results/unit.json
```

## Test Levels

### Level 1: Pure Optimizer (no Docker, no network)

| File | Tests | What it covers |
|------|-------|----------------|
| `bench_ilp_solver.py` | 20 | Isolated ILP solve times across matrix sizes, optimality gap verification, edge cases |
| `bench_optimizer.py` | 77 | Full `run_weighted_dispatch_with_hospitals` across 4 fleet sizes x 6 incident counts x 3 priority distributions, plus focused scenarios (single incident, overload, mass casualty, assignment quality) |

### Level 2: Integration (requires Docker stack on localhost:8000)

| File | Tests | What it covers |
|------|-------|----------------|
| `bench_endpoint.py` | 7 | End-to-end `POST /assignments/find-best` latency, burst/stress scenarios (5-20 incidents at varying intervals), concurrent request throughput |

## Results

All benchmarks run on Apple M1 Pro (10-core), Python 3.11, PuLP 3.3.0 / CBC 2.10.

### Scaling Heatmap

Median total optimizer time (ms) across ambulances x incidents, averaged over all priority distributions:

![Scaling Heatmap](results/scaling_heatmap.png)

| Ambulances \ Incidents | 1 | 5 | 10 | 20 | 50 | 100 |
|------------------------|---|---|----|----|----|----|
| **5** | 14 | 17 | 32 | 71 | 210 | 590 |
| **10** | 14 | 17 | 18 | 42 | 150 | 417 |
| **20** | 15 | 19 | 24 | 33 | 126 | 393 |
| **40** | 16 | 24 | 32 | 49 | 154 | 472 |

**Key observations:**
- **Single incident dispatch (most common real-world case): ~14-16ms** regardless of fleet size. Well under any human-perceptible threshold.
- **20 incidents / 20 ambulances: ~33ms.** Easily real-time.
- **100 incidents / 40 ambulances (extreme overload): ~470-590ms.** Still sub-second, acceptable for dispatch decision support.
- Incident count is the dominant scaling factor. Adding more ambulances has modest impact because the ILP per round grows with min(A, N), not A alone.
- Fewer ambulances with many incidents means more rounds (ceil(N/A)), which compounds — 100 incidents / 5 ambulances takes 590ms across 20 rounds.

### Latency Breakdown

![Latency Breakdown](results/latency_breakdown.png)

ILP solve time dominates total optimizer time at ~65-80%, with cost matrix construction (the A x N x H nested loop computing Euclidean distances + nearest hospital) as a minor contributor. This means:
- The cost matrix build (pure Python loops + `coord_distance`) is **not** the bottleneck.
- Optimization efforts should focus on the ILP formulation or solver configuration if faster times are needed at scale.

### ILP Solve Time Scaling

![ILP Scaling](results/ilp_scaling.png)

| Matrix (A x N) | Median Solve (ms) |
|-----------------|-------------------|
| 5 x 5 | 15 |
| 10 x 10 | 17 |
| 20 x 20 | 27 |
| 40 x 40 | 74 |
| 40 x 50 | 94 |
| 40 x 100 | 222 |

Solve time scales super-linearly with matrix size, as expected for a MILP solver, though the assignment structure keeps it tractable.

### Optimality Gap

The k-assignment ILP has a totally unimodular constraint matrix, which means the LP relaxation always yields an integral solution. Benchmarks confirm this empirically — **the IP-LP gap is exactly 0% across all tested matrix sizes**:

| Size | IP Objective | LP Relaxation | Gap | Integral? |
|------|-------------|---------------|-----|-----------|
| 5x5 | 105.1318 | 105.1318 | 0.000000 | YES |
| 10x10 | 155.4577 | 155.4577 | 0.000000 | YES |
| 20x20 | 168.5654 | 168.5654 | 0.000000 | YES |
| 40x40 | 206.0667 | 206.0667 | 0.000000 | YES |
| 40x50 | 161.4153 | 161.4153 | 0.000000 | YES |
| 40x100 | 84.3799 | 84.3799 | 0.000000 | YES |

This confirms the solver always finds the true global optimum — no approximation loss from the integer programming formulation.

### Focused Scenarios

| Scenario | Config | Median Time | Notes |
|----------|--------|-------------|-------|
| Single incident | 40 amb, 1 inc | 16ms | Most common real-world dispatch call |
| Overload | 10 amb, 100 inc | 431ms | 10 optimization rounds, all incidents served |
| Mass casualty | 40 amb, 20 inc clustered | 53ms | Geographically co-located incidents |

### Assignment Quality

- Higher-priority incidents (Purple, weight=16) consistently receive lower weighted costs than lower-priority incidents (Green, weight=1), confirming the optimizer correctly prioritizes.
- No assignment exceeds 100km in the Waterloo Region test data, validating geographic realism.

## File Structure

```
benchmarks/
  environment.yml       # Conda env spec
  requirements.txt      # pip fallback
  conftest.py           # sys.path setup + shared fixtures
  generators.py         # Waterloo-region data generators + timing wrapper
  bench_optimizer.py    # Full optimizer parametric benchmarks
  bench_ilp_solver.py   # Isolated ILP solve + optimality gap
  bench_endpoint.py     # HTTP endpoint integration tests
  report.py             # JSON results → charts + tables
  results/              # Generated output (gitignored except .gitkeep)
```

## Design Decisions

- **pytest-benchmark over Locust:** The bottleneck is optimizer compute, not HTTP throughput. pytest-benchmark provides statistical rigor (warmup, outlier detection, IQR) suited for compute-bound benchmarks.
- **No production code changes:** All timing is done via wrappers and monkey-patching in the benchmark layer. The optimizer, endpoints, and shared types are untouched.
- **`benchmark.pedantic` mode:** Gives explicit control over iterations/rounds, avoiding confusing auto-calibration for solver benchmarks (50-500ms per call).
- **PuLP via pip (not conda):** The conda-forge PuLP 2.8.0 build has a broken `available()` method that hardcodes `False`. PuLP 3.3.0 from PyPI bundles its own CBC binary and works out of the box.
