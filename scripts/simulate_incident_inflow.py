#!/usr/bin/env python3
"""Incident Inflow Simulator — creates waves of incidents for ERAS user testing.

Usage:
    python scripts/simulate_incident_inflow.py --count 10          # 5s delay
    python scripts/simulate_incident_inflow.py --count 20          # 4s delay
    python scripts/simulate_incident_inflow.py --count 40          # 3s delay
    python scripts/simulate_incident_inflow.py --count 80          # 2s delay
    python scripts/simulate_incident_inflow.py --count 10 --delay 8
    python scripts/simulate_incident_inflow.py --count 10 --api-url http://some-host:8000
"""

import argparse
import random
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Incident type pools by priority
# ---------------------------------------------------------------------------
INCIDENT_TYPES = {
    "Purple": [
        "Cardiac Arrest", "Drowning", "Electrocution",
        "Severe Anaphylaxis", "Major Trauma",
    ],
    "Red": [
        "Chest Pain", "Overdose", "Anaphylaxis",
        "Severe Bleeding", "Stabbing", "Gunshot Wound",
    ],
    "Orange": [
        "Seizure", "Motor Vehicle Accident", "Burns",
        "Diabetic Emergency", "Head Injury", "Compound Fracture",
    ],
    "Yellow": [
        "Abdominal Pain", "Breathing Difficulty", "Suspected Stroke",
        "Back Injury", "Sprained Ankle", "Anxiety Attack",
    ],
    "Green": [
        "Minor Fall", "Minor Laceration", "Nosebleed",
        "Allergic Reaction (Mild)", "Insect Bite", "Minor Burn",
    ],
}

# Street names for random location generation
STREET_NAMES = [
    "King St", "Queen St", "Weber St", "Victoria St", "Frederick St",
    "Duke St", "Cedar St", "Park St", "Erb St W", "Bridgeport Rd",
    "Lancaster St", "Union St", "Margaret Ave", "Highland Rd",
    "Fischer-Hallman Rd", "Ira Needles Blvd", "Westmount Rd",
    "Homer Watson Blvd", "Fairway Rd", "Hespeler Rd",
    "Coronation Blvd", "Greengate Rd", "Maple Grove Rd",
    "Woolwich St", "Conestoga Blvd",
]

CITIES = ["Kitchener", "Waterloo", "Cambridge"]

# ---------------------------------------------------------------------------
# Hand-crafted scenarios
# ---------------------------------------------------------------------------

SCENARIO_10 = [
    # --- Reroute setup (1-4): auto-accepted low-priority incidents ---
    {
        "priority": "Green", "type": "Minor Laceration",
        "location": "24 Gaukel St, Kitchener",
        "lat": 43.4510, "lon": -80.4920,
        "auto_accept": True,
    },
    {
        "priority": "Green", "type": "Minor Fall",
        "location": "150 Main St, Cambridge",
        "lat": 43.3600, "lon": -80.3140,
        "auto_accept": True,
    },
    {
        "priority": "Yellow", "type": "Abdominal Pain",
        "location": "100 Regina St S, Waterloo",
        "lat": 43.4600, "lon": -80.5230,
        "auto_accept": True,
    },
    {
        "priority": "Green", "type": "Allergic Reaction (Mild)",
        "location": "55 Northfield Dr E, Waterloo",
        "lat": 43.4860, "lon": -80.5200,
        "auto_accept": True,
    },
    # --- Reroute trigger (5): Purple near incident #1 ---
    {
        "priority": "Purple", "type": "Cardiac Arrest",
        "location": "25 Gaukel St, Kitchener",
        "lat": 43.4512, "lon": -80.4918,
        "auto_accept": False,
    },
    # --- Remaining incidents (6-10): user handles ---
    {
        "priority": "Orange", "type": "Seizure",
        "location": "450 Columbia St W, Waterloo",
        "lat": 43.4690, "lon": -80.5500,
        "auto_accept": False,
    },
    {
        "priority": "Yellow", "type": "Breathing Difficulty",
        "location": "385 Fairway Rd S, Kitchener",
        "lat": 43.4300, "lon": -80.4700,
        "auto_accept": False,
    },
    {
        "priority": "Red", "type": "Chest Pain",
        "location": "73 Water St N, Cambridge",
        "lat": 43.3650, "lon": -80.3170,
        "auto_accept": False,
    },
    {
        "priority": "Orange", "type": "Motor Vehicle Accident",
        "location": "Homer Watson Blvd, Kitchener",
        "lat": 43.4100, "lon": -80.4500,
        "auto_accept": False,
    },
    {
        "priority": "Yellow", "type": "Suspected Stroke",
        "location": "15 King St N, Waterloo",
        "lat": 43.4650, "lon": -80.5240,
        "auto_accept": False,
    },
]

SCENARIO_20_EXTRA = [
    {
        "priority": "Red", "type": "Overdose",
        "location": "305 King St W, Kitchener",
        "lat": 43.4520, "lon": -80.4960,
    },
    {
        "priority": "Yellow", "type": "Back Injury",
        "location": "200 Conestoga Blvd, Cambridge",
        "lat": 43.3890, "lon": -80.3370,
    },
    {
        "priority": "Orange", "type": "Diabetic Emergency",
        "location": "160 University Ave W, Waterloo",
        "lat": 43.4710, "lon": -80.5380,
    },
    {
        "priority": "Green", "type": "Nosebleed",
        "location": "100 Ainslie St S, Cambridge",
        "lat": 43.3560, "lon": -80.3120,
    },
    {
        "priority": "Red", "type": "Anaphylaxis",
        "location": "800 King St W, Kitchener",
        "lat": 43.4475, "lon": -80.5120,
    },
    {
        "priority": "Yellow", "type": "Sprained Ankle",
        "location": "50 Woolwich St S, Breslau",
        "lat": 43.4340, "lon": -80.4080,
    },
    {
        "priority": "Orange", "type": "Burns",
        "location": "120 Pioneer Dr, Kitchener",
        "lat": 43.4190, "lon": -80.4680,
    },
    {
        "priority": "Purple", "type": "Drowning",
        "location": "101 Queen St S, Kitchener",
        "lat": 43.4470, "lon": -80.4900,
    },
    {
        "priority": "Yellow", "type": "Anxiety Attack",
        "location": "330 Phillip St, Waterloo",
        "lat": 43.4740, "lon": -80.5440,
    },
    {
        "priority": "Orange", "type": "Head Injury",
        "location": "650 Hespeler Rd, Cambridge",
        "lat": 43.3950, "lon": -80.3310,
    },
]


# ---------------------------------------------------------------------------
# Random incident generation
# ---------------------------------------------------------------------------

def generate_random_incidents(count, priority_weights=None):
    """Generate incidents with random coords in Waterloo Region."""
    if priority_weights is None:
        # Default: 30% Green, 30% Yellow, 25% Orange, 10% Red, 5% Purple
        priority_weights = {
            "Green": 0.30, "Yellow": 0.30, "Orange": 0.25,
            "Red": 0.10, "Purple": 0.05,
        }

    priorities = list(priority_weights.keys())
    weights = list(priority_weights.values())

    incidents = []
    for _ in range(count):
        priority = random.choices(priorities, weights=weights, k=1)[0]
        inc_type = random.choice(INCIDENT_TYPES[priority])
        lat = round(random.uniform(43.30, 43.55), 4)
        lon = round(random.uniform(-80.70, -80.30), 4)
        street_num = random.randint(1, 999)
        street = random.choice(STREET_NAMES)
        city = random.choice(CITIES)
        incidents.append({
            "priority": priority,
            "type": inc_type,
            "location": f"{street_num} {street}, {city}",
            "lat": lat,
            "lon": lon,
        })
    return incidents


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def create_incident(api_url, data):
    """POST a new incident to dashboard-api. Returns response JSON."""
    payload = {
        "lat": data["lat"],
        "lon": data["lon"],
        "location": data["location"],
        "type": data["type"],
        "priority": data["priority"],
        "source": "call_taker",
    }
    resp = requests.post(f"{api_url}/incidents", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def find_best(api_url, incident_id):
    """Call find-best for an incident. Returns suggestion data."""
    resp = requests.post(
        f"{api_url}/assignments/find-best",
        json={"incident_id": incident_id},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def accept_suggestion(api_url, suggestion_id):
    """Accept a dispatch suggestion."""
    resp = requests.post(
        f"{api_url}/assignments/{suggestion_id}/accept", timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Main run loop
# ---------------------------------------------------------------------------

DEFAULT_DELAYS = {10: 5, 20: 4, 40: 3, 80: 2}


def build_scenario(count):
    """Build the incident list for the given count."""
    if count == 10:
        return [dict(inc) for inc in SCENARIO_10]

    # 20+: start with SCENARIO_10 + SCENARIO_20_EXTRA
    incidents = [dict(inc) for inc in SCENARIO_10]
    incidents += [dict(inc) for inc in SCENARIO_20_EXTRA]

    if count == 20:
        return incidents

    if count == 40:
        extra = generate_random_incidents(20)
        return incidents + extra

    if count == 80:
        # Higher Red/Orange proportion to simulate mass event
        mass_weights = {
            "Green": 0.15, "Yellow": 0.20, "Orange": 0.30,
            "Red": 0.25, "Purple": 0.10,
        }
        extra = generate_random_incidents(60, priority_weights=mass_weights)
        return incidents + extra

    # Shouldn't reach here due to argparse choices
    raise ValueError(f"Unsupported count: {count}")


def run(count, delay, api_url):
    """Run the incident inflow simulation."""
    incidents = build_scenario(count)

    print(f"\n{'=' * 50}")
    print(f"  ERAS Incident Inflow Simulator")
    print(f"  Scenario: {count} incidents | Delay: {delay}s | API: {api_url}")
    print(f"{'=' * 50}\n")

    for i, inc in enumerate(incidents):
        auto_accept = inc.pop("auto_accept", False)
        label = f"[{i + 1}/{count}]"
        print(f"{label} {inc['priority']} - {inc['type']} at {inc['location']}")

        try:
            result = create_incident(api_url, inc)
        except requests.RequestException as e:
            print(f"  ✗ Failed to create incident: {e}")
            continue

        incident_id = result.get("incident", {}).get("id")
        if not incident_id:
            print("  ✗ No incident ID in response")
            continue

        # Find best vehicle for this incident
        suggestion = None
        try:
            suggestion = find_best(api_url, incident_id)
        except requests.RequestException as e:
            print(f"  ✗ find-best failed: {e}")

        if auto_accept and suggestion:
            suggestion_id = suggestion.get("suggestion_id")
            vehicle_id = suggestion.get("suggested_vehicle_id", "unknown")
            try:
                accept_suggestion(api_url, suggestion_id)
                print(f"  → Auto-accepted: {vehicle_id}")
            except requests.RequestException as e:
                print(f"  ✗ Auto-accept failed: {e}")
        elif suggestion:
            vehicle_id = suggestion.get("suggested_vehicle_id", "unknown")
            is_reroute = suggestion.get("is_reroute", False)
            if is_reroute:
                preempted = suggestion.get("preempted_incident_priority", "")
                print(
                    f"  ★ REROUTE SUGGESTED: {vehicle_id} "
                    f"rerouted from {preempted} case → check frontend!"
                )
            else:
                print(f"  → Dispatch suggestion: {vehicle_id} (waiting for user)")
        else:
            print("  → No dispatch suggestion returned")

        # Print reroute setup message after last auto-accepted incident
        if auto_accept and i + 1 < len(incidents) and not incidents[i + 1].get("auto_accept", False):
            next_inc = incidents[i + 1]
            if next_inc.get("priority") == "Purple":
                print(
                    f"\n  ★ Reroute scenario ready — "
                    f"next incident will trigger reroute\n"
                )

        # Delay between incidents (skip after the last one)
        if i < len(incidents) - 1:
            time.sleep(delay)

    print(f"\n{'=' * 50}")
    print(f"  Done! {count} incidents created.")
    print(f"{'=' * 50}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="ERAS Incident Inflow Simulator",
    )
    parser.add_argument(
        "--count", type=int, required=True, choices=[10, 20, 40, 80],
        help="Number of incidents to simulate (10, 20, 40, or 80)",
    )
    parser.add_argument(
        "--delay", type=float, default=None,
        help="Seconds between incidents (default: varies by count)",
    )
    parser.add_argument(
        "--api-url", default="http://localhost:8000",
        help="Dashboard API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    delay = args.delay if args.delay is not None else DEFAULT_DELAYS[args.count]

    try:
        run(args.count, delay, args.api_url)
    except KeyboardInterrupt:
        print("\n\nAborted by user.")
        sys.exit(1)


if __name__ == "__main__":
    main()
