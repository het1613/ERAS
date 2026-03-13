"""
Shared pytest configuration and fixtures for benchmarks.

Sets up sys.path so optimizer and shared modules are importable,
and provides common fixtures for hospitals, ambulances, and incidents.
"""

import os
import sys

import numpy as np
import pytest

# Add project paths so we can import optimization.py and shared.*
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GEOSPATIAL_DIR = os.path.join(PROJECT_ROOT, "services", "geospatial-dispatch")
SHARED_DIR = os.path.join(PROJECT_ROOT, "shared")

for p in [PROJECT_ROOT, GEOSPATIAL_DIR, SHARED_DIR]:
    if p not in sys.path:
        sys.path.insert(0, p)

from generators import HOSPITALS, generate_ambulances, generate_incidents


@pytest.fixture
def hospitals():
    """Hospital coordinates as np.ndarray (4x2)."""
    return HOSPITALS.copy()


# Parametrized ambulance counts
@pytest.fixture(params=[5, 10, 20, 40], ids=lambda n: f"{n}amb")
def ambulance_count(request):
    return request.param


@pytest.fixture
def ambulances(ambulance_count):
    return generate_ambulances(ambulance_count)


# Parametrized incident counts
@pytest.fixture(params=[1, 5, 10, 20, 50, 100], ids=lambda n: f"{n}inc")
def incident_count(request):
    return request.param


@pytest.fixture
def incidents(incident_count):
    return generate_incidents(incident_count, priority_dist="realistic")
