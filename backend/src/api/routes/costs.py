"""Cost tracking API routes."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.dependencies import get_cost_tracking

router = APIRouter()


class CostLimitUpdate(BaseModel):
    """Cost limit update model."""
    cost_limit_nok: float


class CostStats(BaseModel):
    """Cost statistics model."""
    current_session_cost_nok: float
    current_session_cost_usd: float
    cost_limit_nok: float
    is_limit_reached: bool
    total_costs_7d: dict
    total_costs_30d: dict


@router.get("/current-session")
async def get_current_session_costs():
    """Get current session cost information."""
    cost_tracking = get_cost_tracking()
    
    if not cost_tracking:
        raise HTTPException(status_code=503, detail="Cost tracking not available")
    
    session = cost_tracking.get_current_session()
    
    if not session:
        return {
            "has_active_session": False,
            "message": "No active session",
        }
    
    return {
        "has_active_session": True,
        "session_id": session.session_id,
        "total_cost_nok": str(session.total_cost_nok),
        "total_cost_usd": str(session.total_cost_usd),
        "is_stopped": session.is_stopped,
        "stop_reason": session.stop_reason,
    }


@router.get("/stats", response_model=CostStats)
async def get_cost_stats():
    """Get overall cost statistics."""
    cost_tracking = get_cost_tracking()
    
    if not cost_tracking:
        raise HTTPException(status_code=503, detail="Cost tracking not available")
    
    session = cost_tracking.get_current_session()
    total_7d = cost_tracking.get_total_costs(days=7)
    total_30d = cost_tracking.get_total_costs(days=30)
    
    should_stop, _ = cost_tracking.check_limit()
    
    return CostStats(
        current_session_cost_nok=float(session.total_cost_nok) if session else 0.0,
        current_session_cost_usd=float(session.total_cost_usd) if session else 0.0,
        cost_limit_nok=cost_tracking.cost_limit_nok,
        is_limit_reached=should_stop,
        total_costs_7d={
            "nok": str(total_7d["nok"]),
            "usd": str(total_7d["usd"]),
        },
        total_costs_30d={
            "nok": str(total_30d["nok"]),
            "usd": str(total_30d["usd"]),
        },
    )


@router.get("/sessions")
async def list_sessions():
    """List all cost tracking sessions."""
    cost_tracking = get_cost_tracking()
    
    if not cost_tracking:
        raise HTTPException(status_code=503, detail="Cost tracking not available")
    
    return {"sessions": cost_tracking.list_sessions()}


@router.post("/limit")
async def update_cost_limit(update: CostLimitUpdate):
    """Update the cost limit."""
    cost_tracking = get_cost_tracking()
    
    if not cost_tracking:
        raise HTTPException(status_code=503, detail="Cost tracking not available")
    
    cost_tracking.cost_limit_nok = update.cost_limit_nok
    
    return {
        "success": True,
        "new_limit": update.cost_limit_nok,
    }