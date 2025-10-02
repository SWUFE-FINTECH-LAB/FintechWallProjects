"""Data management service for coordinating market data fetching and caching."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from ..core.cache import CacheManager
from ..core.settings import settings
from ..providers import MarketDataProvider, WindProvider, NullProvider

logger = logging.getLogger(__name__)


class DataManager:
    """Manages market data fetching, caching, and streaming."""

    def __init__(self, cache_manager: Optional[CacheManager] = None):
        """Initialize data manager with cache and provider."""
        self.cache_manager = cache_manager or CacheManager()
        self.provider = self._create_provider()
        self._last_fetch_times: Dict[str, datetime] = {}

    def _create_provider(self) -> MarketDataProvider:
        """Create appropriate provider based on settings."""
        if settings.data_mode == "wind":
            try:
                logger.info("Attempting to create Wind provider...")
                provider = WindProvider()
                logger.info("Wind provider created successfully")
                return provider
            except ImportError as e:
                logger.error(f"WindPy not available: {e}")
                logger.info("Falling back to null provider - install WindPy via Wind terminal")
                return NullProvider()
            except Exception as e:
                logger.error(f"Failed to create Wind provider: {e}")
                logger.info("Falling back to null provider")
                return NullProvider()
        else:
            # For now, use null provider for open mode
            # In production, you'd implement OpenProvider
            logger.info("Using null provider for open data mode")
            return NullProvider()

    async def get_market_snapshot(self) -> Dict[str, Any]:
        """Get complete market data snapshot."""
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "indices": await self._get_cached_or_fetch("indices"),
            "fx": await self._get_cached_or_fetch("fx"),
            "rates": await self._get_cached_or_fetch("rates"),
            "commodities": await self._get_cached_or_fetch("commodities"),
            "us_stocks": await self._get_cached_or_fetch("us_stocks"),
            "calendar": await self._get_cached_or_fetch("calendar"),
        }

        # Calculate market summary
        snapshot["summary"] = self._calculate_market_summary(snapshot)

        return snapshot

    async def _get_cached_or_fetch(self, data_type: str) -> Dict[str, Any]:
        """Get data from cache or fetch fresh if needed."""
        cache_key = f"market_data:{data_type}"

        # Try to get from cache first
        if self.cache_manager:
            cached_data = await self.cache_manager.get(cache_key)
            if cached_data:
                # Check if data is still fresh
                last_fetch = self._last_fetch_times.get(data_type)
                if last_fetch and datetime.now() - last_fetch < timedelta(seconds=settings.snapshot_cache_ttl):
                    return json.loads(cached_data)

        # Fetch fresh data
        try:
            if data_type == "indices":
                data = await self.provider.fetch_indices()
            elif data_type == "fx":
                data = await self.provider.fetch_fx()
            elif data_type == "rates":
                data = await self.provider.fetch_rates()
            elif data_type == "commodities":
                data = await self.provider.fetch_commodities()
            elif data_type == "us_stocks":
                data = await self.provider.fetch_us_stocks()
            elif data_type == "calendar":
                calendar_data = await self.provider.fetch_calendar()
                data = {"events": calendar_data}
            else:
                data = {}

            # Cache the data
            if self.cache_manager and data:
                await self.cache_manager.set(
                    cache_key,
                    json.dumps(data, default=str),
                    ttl=settings.snapshot_cache_ttl
                )

            # Update last fetch time
            self._last_fetch_times[data_type] = datetime.now()

            logger.info(f"Fetched fresh {data_type} data with {len(data)} items")
            return data

        except Exception as e:
            logger.error(f"Error fetching {data_type} data: {e}")
            return {}

    def _calculate_market_summary(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate market summary statistics."""
        summary = {
            "market_status": "open",  # Simplified - in production, check market hours
            "total_indices": len(snapshot.get("indices", {})),
            "advancing": 0,
            "declining": 0,
            "unchanged": 0,
        }

        # Count advancing/declining indices
        for index_data in snapshot.get("indices", {}).values():
            if isinstance(index_data, dict):
                change_pct = index_data.get("change_pct", 0)
                if change_pct > 0:
                    summary["advancing"] += 1
                elif change_pct < 0:
                    summary["declining"] += 1
                else:
                    summary["unchanged"] += 1

        return summary

    async def start_background_refresh(self) -> None:
        """Start background task to refresh data periodically."""
        logger.info("Starting background data refresh task")

        async def refresh_loop():
            while True:
                try:
                    await asyncio.sleep(settings.snapshot_cache_ttl)
                    logger.info("Running background data refresh")
                    await self.get_market_snapshot()
                except Exception as e:
                    logger.error(f"Error in background refresh: {e}")

        # Start the background task
        asyncio.create_task(refresh_loop())

    async def get_a_share_indices(self) -> Dict[str, Any]:
        """Get specifically A-share indices for display."""
        indices_data = await self._get_cached_or_fetch("indices")

        # Filter for A-share indices and add display formatting
        a_share_indices = {}
        for code, data in indices_data.items():
            if code in ["000001.SH", "399001.SZ", "399006.SZ", "000300.SH", "000905.SH", "000852.SH", "000016.SH"]:
                # Format for display
                formatted_data = data.copy()
                formatted_data["display_name"] = self._get_display_name(code)
                formatted_data["color"] = "green" if data.get("change_pct", 0) >= 0 else "red"
                formatted_data["formatted_last"] = f"{data.get('last', 0):.2f}"
                formatted_data["formatted_change"] = f"{data.get('change', 0):+.2f}"
                formatted_data["formatted_change_pct"] = f"{data.get('change_pct', 0):+.2f}%"

                a_share_indices[code] = formatted_data

        return a_share_indices

    def _get_display_name(self, code: str) -> str:
        """Get display name for index code."""
        names = {
            "000001.SH": "上证综指",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
            "000300.SH": "沪深300",
            "000905.SH": "中证500",
            "000852.SH": "中证1000",
            "000016.SH": "上证50",
        }
        return names.get(code, code)


# Global data manager instance
_data_manager: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    """Get global data manager instance."""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager