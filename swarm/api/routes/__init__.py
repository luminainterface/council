"""
🔗 API Routes - Router registration for swarm API
Exposes all route modules to the main FastAPI application
"""

from fastapi import APIRouter
from . import feedback

# Main router that combines all sub-routes
main_router = APIRouter()

# Include feedback routes
main_router.include_router(feedback.router)

# Export for easy import
__all__ = ['main_router', 'feedback'] 