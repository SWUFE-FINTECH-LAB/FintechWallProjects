"""Endpoints for data snapshots."""

from fastapi import APIRouter
from typing import Dict, Any

from ..services.data_manager import get_data_manager

router = APIRouter()


@router.get("/snapshot", summary="Current market snapshot")
async def snapshot() -> Dict[str, Any]:
    """Get complete market data snapshot."""
    data_manager = get_data_manager()
    return await data_manager.get_market_snapshot()


@router.get("/a-shares", summary="A-share indices snapshot")
async def a_share_indices() -> Dict[str, Any]:
    """Get A-share indices data for display."""
    data_manager = get_data_manager()
    indices = await data_manager.get_a_share_indices()
    return {
        "timestamp": indices.get("timestamp"),
        "indices": indices,
        "count": len(indices)
    }


@router.get("/latest", summary="Latest market data for display")
async def latest() -> Dict[str, Any]:
    """Get latest market data optimized for wallboard display."""
    data_manager = get_data_manager()
    snapshot = await data_manager.get_market_snapshot()

    # Format for wallboard display
    return {
        "timestamp": snapshot["timestamp"],
        "a_shares": await data_manager.get_a_share_indices(),
        "fx": snapshot.get("fx", {}),
        "commodities": snapshot.get("commodities", {}),
        "us_stocks": snapshot.get("us_stocks", {}),
        "summary": snapshot.get("summary", {}),
    }
