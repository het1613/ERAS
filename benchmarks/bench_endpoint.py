"""
Integration benchmarks for the dispatch endpoint.

Requires Docker stack running (dashboard-api on :8000).
Tests end-to-end latency and burst/stress scenarios.

Run with: pytest benchmarks/bench_endpoint.py -v -s
"""

import asyncio
import time
import uuid

import httpx
import pytest

API_BASE = "http://localhost:8000"

# Burst test scenarios
BURST_SCENARIOS = [
    {"name": "light_surge", "count": 5, "interval": 2.0, "desc": "Normal busy period"},
    {"name": "moderate_surge", "count": 10, "interval": 1.0, "desc": "Multi-vehicle accident"},
    {"name": "heavy_surge", "count": 20, "interval": 0.5, "desc": "Mass casualty incident"},
    {"name": "extreme", "count": 20, "interval": 0.0, "desc": "Simultaneous (upper bound)"},
]


def _is_api_reachable():
    """Check if the dashboard API is reachable."""
    try:
        resp = httpx.get(f"{API_BASE}/incidents", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


# Skip all tests in this module if API is not reachable
pytestmark = pytest.mark.skipif(
    not _is_api_reachable(),
    reason="Dashboard API not reachable at localhost:8000 (Docker stack not running?)",
)


class TestSingleRequest:
    """Single-request end-to-end latency tests."""

    def test_find_best_e2e_latency(self):
        """Measure full POST /assignments/find-best roundtrip."""
        # Create a test incident (source=manual, won't pollute dispatcher view)
        incident = {
            "lat": 43.45,
            "lon": -80.50,
            "location": "Benchmark Test Location",
            "type": "Medical Emergency",
            "priority": "Yellow",
            "source": "manual",
        }

        with httpx.Client(base_url=API_BASE, timeout=30) as client:
            # Create incident
            resp = client.post("/incidents", json=incident)
            assert resp.status_code == 200, f"Failed to create incident: {resp.text}"
            incident_id = resp.json()["id"]

            try:
                # Measure find-best latency
                t0 = time.perf_counter()
                resp = client.post(
                    "/assignments/find-best",
                    json={"incident_id": incident_id},
                )
                latency_ms = (time.perf_counter() - t0) * 1000

                print(f"\n  E2E find-best latency: {latency_ms:.1f} ms")
                print(f"  Status: {resp.status_code}")

                if resp.status_code == 200:
                    data = resp.json()
                    print(f"  Vehicle: {data.get('suggested_vehicle_id')}")
                    print(f"  Hospital: {data.get('hospital', {}).get('name')}")
                    route_len = len(data.get("route_preview", []))
                    print(f"  Route points: {route_len}")

                    # Decline the suggestion to clean up
                    suggestion_id = data.get("suggestion_id")
                    if suggestion_id:
                        client.post(f"/assignments/{suggestion_id}/decline")

                assert resp.status_code == 200
                assert latency_ms < 30000, f"E2E latency {latency_ms:.0f}ms exceeds 30s"
            finally:
                # Resolve the test incident
                client.patch(f"/incidents/{incident_id}", json={"status": "resolved"})

    def test_find_best_without_osrm(self):
        """Measure optimizer-only time (OSRM may add variable latency)."""
        incident = {
            "lat": 43.45,
            "lon": -80.50,
            "location": "Benchmark No-OSRM Test",
            "type": "Trauma",
            "priority": "Red",
            "source": "manual",
        }

        with httpx.Client(base_url=API_BASE, timeout=30) as client:
            resp = client.post("/incidents", json=incident)
            assert resp.status_code == 200
            incident_id = resp.json()["id"]

            try:
                t0 = time.perf_counter()
                resp = client.post(
                    "/assignments/find-best",
                    json={"incident_id": incident_id},
                )
                latency_ms = (time.perf_counter() - t0) * 1000

                print(f"\n  Find-best total latency: {latency_ms:.1f} ms")
                assert resp.status_code == 200

                # If route_preview is empty, OSRM was unreachable (pure optimizer time)
                data = resp.json()
                has_route = len(data.get("route_preview", [])) > 0
                print(f"  OSRM route present: {has_route}")

                suggestion_id = data.get("suggestion_id")
                if suggestion_id:
                    client.post(f"/assignments/{suggestion_id}/decline")
            finally:
                client.patch(f"/incidents/{incident_id}", json={"status": "resolved"})


class TestBurstScenarios:
    """Burst/stress tests that create multiple incidents and measure degradation."""

    @pytest.mark.parametrize(
        "scenario",
        BURST_SCENARIOS,
        ids=[s["name"] for s in BURST_SCENARIOS],
    )
    def test_burst(self, scenario):
        """
        Create N incidents at given intervals, measuring latency degradation.

        Uses source=manual incidents with manual find-best calls so we can
        measure each request independently.
        """
        count = scenario["count"]
        interval = scenario["interval"]
        print(f"\n  === {scenario['name']}: {count} incidents, {interval}s interval ===")

        created_ids = []
        suggestion_ids = []
        latencies = []

        with httpx.Client(base_url=API_BASE, timeout=60) as client:
            try:
                for i in range(count):
                    # Create incident
                    incident = {
                        "lat": 43.40 + (i * 0.005),
                        "lon": -80.50 + (i * 0.003),
                        "location": f"Burst test #{i+1}",
                        "type": "Medical Emergency",
                        "priority": ["Purple", "Red", "Orange", "Yellow", "Green"][i % 5],
                        "source": "manual",
                    }
                    resp = client.post("/incidents", json=incident)
                    if resp.status_code != 200:
                        print(f"  Failed to create incident {i+1}: {resp.text}")
                        continue
                    incident_id = resp.json()["id"]
                    created_ids.append(incident_id)

                    # Measure find-best
                    t0 = time.perf_counter()
                    resp = client.post(
                        "/assignments/find-best",
                        json={"incident_id": incident_id},
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000
                    latencies.append(latency_ms)

                    if resp.status_code == 200:
                        sid = resp.json().get("suggestion_id")
                        if sid:
                            suggestion_ids.append(sid)
                            # Decline so next find-best can use same vehicles
                            client.post(f"/assignments/{sid}/decline")

                    status_str = "OK" if resp.status_code == 200 else f"ERR:{resp.status_code}"
                    print(f"  [{i+1}/{count}] {latency_ms:8.1f} ms  {status_str}")

                    if interval > 0 and i < count - 1:
                        time.sleep(interval)

                # Summary
                if latencies:
                    import statistics
                    print(f"\n  --- Summary ---")
                    print(f"  Count:  {len(latencies)}")
                    print(f"  Min:    {min(latencies):.1f} ms")
                    print(f"  Max:    {max(latencies):.1f} ms")
                    print(f"  Mean:   {statistics.mean(latencies):.1f} ms")
                    print(f"  Median: {statistics.median(latencies):.1f} ms")
                    if len(latencies) > 1:
                        print(f"  Stdev:  {statistics.stdev(latencies):.1f} ms")
                    print(f"  P95:    {sorted(latencies)[int(len(latencies)*0.95)]:.1f} ms")

            finally:
                # Cleanup: resolve all created incidents
                for iid in created_ids:
                    try:
                        client.patch(f"/incidents/{iid}", json={"status": "resolved"})
                    except Exception:
                        pass


@pytest.mark.asyncio
class TestConcurrentStress:
    """Concurrent request tests using asyncio."""

    async def test_concurrent_find_best(self):
        """Fire N simultaneous find-best requests."""
        n_concurrent = 5
        print(f"\n  === Concurrent stress: {n_concurrent} simultaneous requests ===")

        created_ids = []

        async with httpx.AsyncClient(base_url=API_BASE, timeout=60) as client:
            try:
                # Pre-create incidents
                for i in range(n_concurrent):
                    incident = {
                        "lat": 43.42 + (i * 0.01),
                        "lon": -80.48 + (i * 0.01),
                        "location": f"Concurrent test #{i+1}",
                        "type": "Medical Emergency",
                        "priority": "Orange",
                        "source": "manual",
                    }
                    resp = await client.post("/incidents", json=incident)
                    assert resp.status_code == 200
                    created_ids.append(resp.json()["id"])

                # Fire all find-best requests simultaneously
                async def timed_find_best(incident_id, idx):
                    t0 = time.perf_counter()
                    resp = await client.post(
                        "/assignments/find-best",
                        json={"incident_id": incident_id},
                    )
                    latency_ms = (time.perf_counter() - t0) * 1000
                    return {
                        "idx": idx,
                        "latency_ms": latency_ms,
                        "status": resp.status_code,
                        "suggestion_id": resp.json().get("suggestion_id") if resp.status_code == 200 else None,
                    }

                t_total = time.perf_counter()
                results = await asyncio.gather(
                    *[timed_find_best(iid, i) for i, iid in enumerate(created_ids)]
                )
                total_ms = (time.perf_counter() - t_total) * 1000

                # Print results
                for r in sorted(results, key=lambda x: x["idx"]):
                    print(f"  [{r['idx']+1}] {r['latency_ms']:8.1f} ms  status={r['status']}")

                latencies = [r["latency_ms"] for r in results]
                successes = sum(1 for r in results if r["status"] == 200)
                print(f"\n  Total wall time: {total_ms:.1f} ms")
                print(f"  Successes: {successes}/{n_concurrent}")
                print(f"  Throughput: {successes / (total_ms / 1000):.2f} req/s")
                print(f"  Mean latency: {sum(latencies)/len(latencies):.1f} ms")

                # Clean up suggestions
                for r in results:
                    if r.get("suggestion_id"):
                        try:
                            await client.post(f"/assignments/{r['suggestion_id']}/decline")
                        except Exception:
                            pass

            finally:
                for iid in created_ids:
                    try:
                        await client.patch(f"/incidents/{iid}", json={"status": "resolved"})
                    except Exception:
                        pass
