"""Route packages.

The new sync-pipeline backend has a single business-domain router
(`input_routes`). Auth, onboarding, healthkit upload, and worker queue
endpoints from the previous design were removed — this service now
runs the full Cox + Gemma pipeline synchronously inside POST /input.
"""
from . import input_routes

__all__ = ["input_routes"]
