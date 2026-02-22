"""
Shared database helper for ERAS services.
"""

import os
import psycopg2
import psycopg2.extras


def get_connection():
    """Return a psycopg2 connection using DATABASE_URL env var."""
    database_url = os.getenv("DATABASE_URL", "postgresql://eras_user:eras_pass@localhost:5432/eras_db")
    return psycopg2.connect(database_url)
