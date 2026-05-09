"""Route packages — one module per business domain.

Each module exposes a `router: APIRouter` that `main.py` mounts.
"""
from . import auth_routes, healthkit_routes, onboarding_routes, worker_routes

__all__ = ["auth_routes", "healthkit_routes", "onboarding_routes", "worker_routes"]
