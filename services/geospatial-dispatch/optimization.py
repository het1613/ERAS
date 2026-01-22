
import math
import numpy as np
import pandas as pd
import pulp as pl
from collections import defaultdict

def coord_distance(origins: list[tuple[float, float]], 
                         destinations: list[tuple[float, float]],
                         mode: str = "driving") -> dict:
    """
    Mock Google Maps Distance Matrix API using Euclidean distance.
    
    Args:
        origins: List of (lat, lng) tuples
        destinations: List of (lat, lng) tuples
        mode: Travel mode (ignored, but kept for interface compatibility)
    
    Returns:
        Response dict matching Google Maps API structure
    """
    
    def euclidean_distance_km(origin: tuple[float, float], 
                               destination: tuple[float, float]) -> float:
        """Calculate Euclidean distance in km (approximate, using lat/lng)."""
        lat1, lng1 = origin
        lat2, lng2 = destination
        
        # Rough conversion: 1 degree lat ≈ 111 km, 1 degree lng ≈ 111 km * cos(lat)
        avg_lat = math.radians((lat1 + lat2) / 2)
        
        delta_lat_km = (lat2 - lat1) * 111
        delta_lng_km = (lng2 - lng1) * 111 * math.cos(avg_lat)
        
        return math.sqrt(delta_lat_km**2 + delta_lng_km**2)
    
    def estimate_duration(distance_km: float) -> int:
        """Estimate travel time in seconds (assuming ~40 km/h average)."""
        return int(distance_km / 40 * 3600)
    
    rows = []
    for origin in origins:
        elements = []
        for destination in destinations:
            distance_km = euclidean_distance_km(origin, destination)
            distance_m = int(distance_km * 1000)
            duration_s = estimate_duration(distance_km)
            
            elements.append({
                "distance": {
                    "text": f"{distance_km:.1f} km",
                    "value": distance_m
                },
                "duration": {
                    "text": f"{duration_s // 60} mins",
                    "value": duration_s
                },
                "status": "OK"
            })
        
        rows.append({"elements": elements})
    
    return {
        "destination_addresses": [f"{lat}, {lng}" for lat, lng in destinations],
        "origin_addresses": [f"{lat}, {lng}" for lat, lng in origins],
        "rows": rows,
        "status": "OK"
    }

def build_k_assignment(cost_AxN: np.ndarray, k: int):
    """
    Build a k-assignment ILP (choose exactly k pairs) on cost matrix (A x N).
    Constraints:
      - each ambulance used at most once
      - each incident served at most once
      - total assigned equals k
    """
    A, N = cost_AxN.shape
    assert 0 <= k <= min(A, N), "k must be <= min(A, N)"
    
    m = pl.LpProblem("k_assignment", pl.LpMinimize)
    x = pl.LpVariable.dicts("x", (range(A), range(N)), 0, 1, pl.LpBinary)

    # Objective
    m += pl.lpSum(cost_AxN[a, i] * x[a][i] for a in range(A) for i in range(N))

    # Each ambulance at most one
    for a in range(A):
        m += pl.lpSum(x[a][i] for i in range(N)) <= 1, f"cap_ambulance_{a}"

    # Each incident at most one
    for i in range(N):
        m += pl.lpSum(x[a][i] for a in range(A)) <= 1, f"cap_incident_{i}"

    # Exactly k assignments
    m += pl.lpSum(x[a][i] for a in range(A) for i in range(N)) == k, "exact_k"

    return m, x

def nearest_hospital(incident_latlong, hospitals_latlong):
    """
    Find nearest hospital to an incident using coord_distance.
    
    Args:
        incident_latlong: (lat, lng) tuple
        hospitals_latlong: numpy array of shape (H, 2) with (lat, lng) pairs
    
    Returns:
        (hospital_index, distance_in_km)
    """
    origins = [tuple(incident_latlong)]
    destinations = [(hospitals_latlong[h, 0], hospitals_latlong[h, 1])
                    for h in range(len(hospitals_latlong))]

    result = coord_distance(origins, destinations)

    # Find minimum distance hospital
    min_dist_km = float('inf')
    min_idx = 0

    for h in range(len(hospitals_latlong)):
        dist_m = result['rows'][0]['elements'][h]['distance']['value']
        dist_km = dist_m / 1000.0
        if dist_km < min_dist_km:
            min_dist_km = dist_km
            min_idx = h

    return min_idx, min_dist_km

def run_weighted_dispatch_with_hospitals(ambulances, incidents, hospitals, solver=None, jitter=0.0, verbose=True):
      """
      Multi-round assignment with weighted incidents where each service consists of:
      ambulance -> incident -> hospital (nearest)
      
      Uses coord_distance for realistic travel distances in km.
      The cost is: (dist_to_incident + dist_to_hospital) / weight[incident]
      Higher weight = LOWER cost = higher priority.
      """
      if solver is None:
          solver = pl.PULP_CBC_CMD(msg=False)

      num_ambulances = len(ambulances)
      num_incidents = len(incidents)
      
      coords_ambulances = np.array([[v.lat, v.lon] for v in ambulances])
      coords_incidents = np.array([[i['lat'], i['lon']] for i in incidents])
      incident_weights = np.array([i['weight'] for i in incidents])
      
      remaining = list(range(num_incidents))
      amb_pos = coords_ambulances.copy()  # Current ambulance positions (lat, lng)

      total_weighted_cost = 0.0
      total_unweighted_distance = 0.0
      round_id = 0
      round_summaries = []

      while remaining:
          round_id += 1
          k = min(num_ambulances, len(remaining))

          # Build WEIGHTED composite cost using coord_distance
          cost = np.zeros((num_ambulances, len(remaining)), dtype=float)
          chosen_hospital = [[None]*len(remaining) for _ in range(num_ambulances)]

          for a in range(num_ambulances):
              # Compute ambulance -> all remaining incidents
              origins = [(amb_pos[a, 0], amb_pos[a, 1])]
              destinations = [(coords_incidents[j, 0], coords_incidents[j, 1])
                             for j in remaining]

              result_a_to_i = coord_distance(origins, destinations)

              for col, j in enumerate(remaining):
                  # Distance from ambulance to incident (in km)
                  amb_to_inc = result_a_to_i['rows'][0]['elements'][col]['distance']['value'] / 1000.0

                  # Find nearest hospital from this incident
                  h_idx, inc_to_h = nearest_hospital(coords_incidents[j], hospitals)

                  # Weighted cost: distance / weight (higher weight = lower cost = higher priority)
                  unweighted_dist = amb_to_inc + inc_to_h
                  weighted_cost = unweighted_dist / incident_weights[j]

                  cost[a, col] = weighted_cost + (np.random.uniform(0, jitter) if jitter>0 else 0.0)
                  chosen_hospital[a][col] = (h_idx, amb_to_inc, inc_to_h, unweighted_dist)

          # Solve k-assignment
          m, x = build_k_assignment(cost, k)
          status = m.solve(solver)
          if pl.LpStatus[status] != "Optimal":
              raise RuntimeError(f"Round {round_id}: solver returned {pl.LpStatus[status]}")

          # Apply assignments
          served_this_round = set()
          round_weighted_cost = 0.0
          round_unweighted_dist = 0.0
          round_assignments = []

          for a in range(num_ambulances):
              for col, j in enumerate(remaining):
                  if (x[a][col].value() or 0) > 0.5:
                      h_idx, amb_to_inc, inc_to_h, unweighted_dist = chosen_hospital[a][col]
                      weight = incident_weights[j]

                      # Update ambulance position to hospital
                      amb_pos[a] = hospitals[h_idx].copy()
                      served_this_round.add(j)

                      weighted_cost = unweighted_dist / weight
                      total_weighted_cost += weighted_cost
                      total_unweighted_distance += unweighted_dist
                      round_weighted_cost += weighted_cost
                      round_unweighted_dist += unweighted_dist

                      round_assignments.append({
                          "ambulance_id": ambulances[a].id,
                          "incident_id": j,
                          "hospital_id": h_idx,
                          "weighted_cost": float(weighted_cost),
                          "unweighted_dist": float(unweighted_dist),
                          "weight": int(weight)
                      })

          remaining = [j for j in remaining if j not in served_this_round]
          round_summaries.append({
              "round": round_id,
              "assignments": round_assignments,
              "round_weighted_cost": round_weighted_cost,
              "round_unweighted_dist": round_unweighted_dist,
              "remaining_after": len(remaining),
          })

          if verbose:
              print(f"Round {round_id}: weighted_cost={round_weighted_cost:.3f}, "
                    f"unweighted_dist={round_unweighted_dist:.3f} km, "
                    f"served={len(round_assignments)}, remaining={len(remaining)}")
      
      return {
          "rounds": round_summaries,
          "total_weighted_cost": total_weighted_cost,
          "total_unweighted_distance": total_unweighted_distance,
      }
