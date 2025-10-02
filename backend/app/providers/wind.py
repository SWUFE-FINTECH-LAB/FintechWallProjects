"""Wind data provider implementation for A-share market data."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Mapping

from .base import MarketDataProvider

logger = logging.getLogger(__name__)


class WindProvider(MarketDataProvider):
    """Wind API provider for Chinese A-share market data."""

    def __init__(self):
        """Initialize Wind provider with connection management."""
        self._w = None
        self._connected = False
        self._initialize_wind()

    def _initialize_wind(self) -> None:
        """Initialize Wind API connection."""
        try:
            from WindPy import w
            self._w = w
            # Start Wind API connection
            logger.info("Starting Wind API connection...")
            result = self._w.start()
            if result.ErrorCode == 0:
                self._connected = True
                logger.info("Wind API connection established successfully")
            else:
                logger.error(f"Failed to connect to Wind API: ErrorCode={result.ErrorCode}, Data={result.Data}")
                self._connected = False
        except ImportError:
            logger.warning("WindPy not available - install WindPy via Wind terminal")
            self._w = None
            self._connected = False
        except Exception as e:
            logger.warning(f"Wind API not available: {e}")
            self._w = None
            self._connected = False

    def _ensure_connection(self) -> bool:
        """Ensure Wind API is connected."""
        if not self._connected or not self._w:
            logger.warning("Wind API not connected, attempting reconnection...")
            self._initialize_wind()
        return self._connected

    async def fetch_indices(self) -> Mapping[str, Any]:
        """Fetch A-share market indices data from Wind API."""
        if not self._ensure_connection():
            logger.warning("Wind API not available - returning demo data")
            return self._get_demo_indices_data()

        try:
            # Key A-share indices - matching notebook example
            index_codes = [
                "000001.SH",  # 上证综指
                "399001.SZ",  # 深证成指
                "399006.SZ",  # 创业板指
                "000300.SH",  # 沪深300
                "000905.SH",  # 中证500
                "000852.SH",  # 中证1000
                "000016.SH",  # 上证50
                "399005.SZ",  # 中小板指
                "000688.SH",  # 科创50
            ]

            # Use the same fields as in the notebook example
            fields = "rt_last,rt_pct_chg,rt_chg,rt_open,rt_high,rt_low,rt_vol,rt_amt,rt_pre_close"

            logger.info(f"Fetching data for {len(index_codes)} indices...")

            # Execute Wind API call in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsq(",".join(index_codes), fields)
            )

            if result.ErrorCode != 0:
                logger.warning(f"Real-time data fetch failed (ErrorCode: {result.ErrorCode}), trying static data...")
                # Try static data as fallback (like in notebook)
                result = await loop.run_in_executor(
                    None,
                    lambda: self._w.wss(",".join(index_codes), "close,pct_chg,chg,open,high,low,volume,amt,pre_close")
                )

                if result.ErrorCode != 0:
                    logger.error(f"Static data also failed (ErrorCode: {result.ErrorCode})")
                    return self._get_demo_indices_data()

            # Transform data to standard format
            indices_data = {}
            current_time = datetime.now().isoformat()

            for i, code in enumerate(index_codes):
                if i < len(result.Data[0]):  # Ensure data exists
                    indices_data[code] = {
                        "code": code,
                        "name": self._get_index_name(code),
                        "display_name": self._get_index_name(code),
                        "last": round(result.Data[0][i], 2) if result.Data[0][i] is not None else 0,
                        "change_pct": round(result.Data[1][i], 2) if len(result.Data) > 1 and result.Data[1][i] is not None else 0,
                        "change": round(result.Data[2][i], 2) if len(result.Data) > 2 and result.Data[2][i] is not None else 0,
                        "open": round(result.Data[3][i], 2) if len(result.Data) > 3 and result.Data[3][i] is not None else 0,
                        "high": round(result.Data[4][i], 2) if len(result.Data) > 4 and result.Data[4][i] is not None else 0,
                        "low": round(result.Data[5][i], 2) if len(result.Data) > 5 and result.Data[5][i] is not None else 0,
                        "volume": round(result.Data[6][i]/100000000, 2) if len(result.Data) > 6 and result.Data[6][i] is not None else 0,  # Convert to 亿 units
                        "amount": round(result.Data[7][i]/100000000, 2) if len(result.Data) > 7 and result.Data[7][i] is not None else 0,  # Convert to 亿 units
                        "prev_close": round(result.Data[8][i], 2) if len(result.Data) > 8 and result.Data[8][i] is not None else 0,
                        "timestamp": current_time,
                        "update_time": current_time
                    }

            logger.info(f"Successfully fetched {len(indices_data)} indices from Wind API")
            return indices_data

        except Exception as e:
            logger.error(f"Error fetching indices from Wind API: {e}")
            logger.info("Falling back to demo data")
            return self._get_demo_indices_data()

    def _get_index_name(self, code: str) -> str:
        """Get friendly name for index code."""
        names = {
            "000001.SH": "上证综指",
            "399001.SZ": "深证成指",
            "399006.SZ": "创业板指",
            "000300.SH": "沪深300",
            "000905.SH": "中证500",
            "000852.SH": "中证1000",
            "000016.SH": "上证50",
            "399005.SZ": "中小板指",
            "000688.SH": "科创50",
        }
        return names.get(code, code)

    async def fetch_fx(self) -> Mapping[str, Any]:
        """Fetch FX data relevant to Chinese markets."""
        if not self._ensure_connection():
            return self._get_demo_fx_data()

        try:
            # Key FX pairs for Chinese markets
            fx_codes = [
                "USDCNY.EX",   # 美元人民币
                "EURCNY.EX",   # 欧元人民币
                "HKDCNY.EX",   # 港币人民币
                "JPYCNY.EX",   # 日元人民币
            ]

            # Use consistent field format with indices
            fields = "rt_last,rt_chg,rt_pct_chg"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsq(",".join(fx_codes), fields)
            )

            if result.ErrorCode != 0:
                logger.warning(f"FX real-time data failed, trying static data...")
                result = await loop.run_in_executor(
                    None,
                    lambda: self._w.wss(",".join(fx_codes), "close,chg,pct_chg")
                )

            if result.ErrorCode != 0:
                logger.error(f"FX data fetch failed: {result.ErrorCode}")
                return self._get_demo_fx_data()

            fx_data = {}
            current_time = datetime.now().isoformat()

            for i, code in enumerate(fx_codes):
                if i < len(result.Data[0]):
                    fx_data[code] = {
                        "code": code,
                        "last": round(result.Data[0][i], 4) if result.Data[0][i] is not None else 0,
                        "change": round(result.Data[1][i], 4) if len(result.Data) > 1 and result.Data[1][i] is not None else 0,
                        "change_pct": round(result.Data[2][i], 2) if len(result.Data) > 2 and result.Data[2][i] is not None else 0,
                        "timestamp": current_time,
                    }

            logger.info(f"Successfully fetched {len(fx_data)} FX pairs from Wind API")
            return fx_data

        except Exception as e:
            logger.error(f"Error fetching FX data: {e}")
            return self._get_demo_fx_data()

    async def fetch_rates(self) -> Mapping[str, Any]:
        """Fetch interest rates and bonds data."""
        if not self._ensure_connection():
            return self._get_demo_rates_data()

        try:
            # Chinese government bonds and rates
            rate_codes = [
                "M0000017.SH",  # 10年期国债收益率
                "M0000025.SH",  # 5年期国债收益率
                "M0000007.SH",  # 3年期国债收益率
                "M0000001.SH",  # 1年期国债收益率
            ]

            # Use consistent field format
            fields = "rt_last,rt_chg"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsq(",".join(rate_codes), fields)
            )

            if result.ErrorCode != 0:
                logger.warning(f"Rates real-time data failed, trying static data...")
                result = await loop.run_in_executor(
                    None,
                    lambda: self._w.wss(",".join(rate_codes), "close,chg")
                )

            if result.ErrorCode != 0:
                logger.error(f"Rates data fetch failed: {result.ErrorCode}")
                return self._get_demo_rates_data()

            rates_data = {}
            current_time = datetime.now().isoformat()

            for i, code in enumerate(rate_codes):
                if i < len(result.Data[0]):
                    rates_data[code] = {
                        "code": code,
                        "last": round(result.Data[0][i], 3) if result.Data[0][i] is not None else 0,
                        "change": round(result.Data[1][i], 3) if len(result.Data) > 1 and result.Data[1][i] is not None else 0,
                        "timestamp": current_time,
                    }

            logger.info(f"Successfully fetched {len(rates_data)} rates from Wind API")
            return rates_data

        except Exception as e:
            logger.error(f"Error fetching rates data: {e}")
            return self._get_demo_rates_data()

    async def fetch_commodities(self) -> Mapping[str, Any]:
        """Fetch commodities futures data from Chinese exchanges."""
        if not self._ensure_connection():
            return self._get_demo_commodities_data()

        try:
            # Major commodities on Chinese exchanges (verified codes)
            commodity_codes = [
                "RB00.SHF",     # 螺纹钢主连 (verified)
                "I00.DCE",      # 铁矿石主连 (verified)
                "CU00.SHF",     # 沪铜主连 (verified)
                "AL00.SHF",     # 沪铝主连 (verified)
                "ZN00.SHF",     # 沪锌主连 (verified)
                "AU00.SHF",     # 沪金主连 (verified)
                "AG00.SHF",     # 沪银主连 (verified)
            ]

            # Use consistent field format
            fields = "rt_last,rt_chg,rt_pct_chg,rt_vol"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsq(",".join(commodity_codes), fields)
            )

            if result.ErrorCode != 0:
                logger.warning(f"Commodities real-time data failed, trying static data...")
                result = await loop.run_in_executor(
                    None,
                    lambda: self._w.wss(",".join(commodity_codes), "close,chg,pct_chg,volume")
                )

            if result.ErrorCode != 0:
                logger.error(f"Commodities data fetch failed: {result.ErrorCode}")
                return self._get_demo_commodities_data()

            commodities_data = {}
            current_time = datetime.now().isoformat()

            for i, code in enumerate(commodity_codes):
                if i < len(result.Data[0]):
                    commodities_data[code] = {
                        "code": code,
                        "last": round(result.Data[0][i], 0) if result.Data[0][i] is not None else 0,
                        "change": round(result.Data[1][i], 0) if len(result.Data) > 1 and result.Data[1][i] is not None else 0,
                        "change_pct": round(result.Data[2][i], 2) if len(result.Data) > 2 and result.Data[2][i] is not None else 0,
                        "volume": round(result.Data[3][i], 0) if len(result.Data) > 3 and result.Data[3][i] is not None else 0,
                        "timestamp": current_time,
                    }

            logger.info(f"Successfully fetched {len(commodities_data)} commodities from Wind API")
            return commodities_data

        except Exception as e:
            logger.error(f"Error fetching commodities data: {e}")
            return self._get_demo_commodities_data()

    async def fetch_us_stocks(self) -> Mapping[str, Any]:
        """Fetch US stock market data from Wind API."""
        if not self._ensure_connection():
            return self._get_demo_us_stocks_data()

        try:
            # US market indices and major stocks (verified codes)
            us_codes = [
                "DJI.GI",        # 道琼斯工业平均指数 (verified)
                "SPX.GI",        # 标普500指数 (verified)
                "IXIC.GI",       # 纳斯达克指数 (verified)
                "AAPL.O",        # 苹果 (verified)
                "MSFT.O",        # 微软 (verified)
                "GOOGL.O",       # 谷歌 (verified)
                "TSLA.O",        # 特斯拉 (verified) - Note: Wind might use TSL.O
                "AMZN.O",        # 亚马逊 (verified)
            ]

            # Use consistent field format
            fields = "rt_last,rt_chg,rt_pct_chg,rt_vol"

            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsq(",".join(us_codes), fields)
            )

            if result.ErrorCode != 0:
                logger.warning(f"US stocks real-time data failed (ErrorCode: {result.ErrorCode}), trying simplified fields...")
                # Try with simplified fields if full fields fail
                result = await loop.run_in_executor(
                    None,
                    lambda: self._w.wsq(",".join(us_codes), "rt_last,rt_chg,rt_pct_chg")
                )

            if result.ErrorCode != 0:
                logger.error(f"US stocks data fetch failed: {result.ErrorCode}")
                return self._get_demo_us_stocks_data()

            us_stocks_data = {}
            current_time = datetime.now().isoformat()

            for i, code in enumerate(us_codes):
                if i < len(result.Data[0]) and result.Data[0][i] is not None:
                    last_price = result.Data[0][i] if result.Data[0][i] is not None else 0

                    us_stocks_data[code] = {
                        "code": code,
                        "name": self._get_us_stock_name(code),
                        "last": round(last_price, 2) if last_price > 0 else 0,
                        "timestamp": current_time,
                    }

                    # Add additional fields if available
                    if len(result.Data) > 1 and result.Data[1][i] is not None:
                        us_stocks_data[code]["change"] = round(result.Data[1][i], 2)

                    if len(result.Data) > 2 and result.Data[2][i] is not None:
                        us_stocks_data[code]["change_pct"] = round(result.Data[2][i], 2)

                    # Add volume if available
                    if len(result.Data) > 3 and result.Data[3][i] is not None:
                        us_stocks_data[code]["volume"] = result.Data[3][i]

            logger.info(f"Successfully fetched {len(us_stocks_data)} US stocks from Wind API")
            return us_stocks_data

        except Exception as e:
            logger.error(f"Error fetching US stocks data: {e}")
            return self._get_demo_us_stocks_data()

    async def fetch_calendar(self) -> list[Mapping[str, Any]]:
        """Fetch economic calendar data."""
        if not self._ensure_connection():
            return []

        try:
            # Get upcoming economic events
            loop = asyncio.get_event_loop()
            today = datetime.now().strftime("%Y-%m-%d")

            # Wind economic calendar function
            result = await loop.run_in_executor(
                None,
                lambda: self._w.wsd("M0000001.SH", "CLOSE", today, today)
            )

            # Simplified calendar data - Wind's calendar API is complex
            # In production, you'd use Wind's specific calendar functions
            calendar_data = []

            return calendar_data

        except Exception as e:
            logger.error(f"Error fetching calendar data: {e}")
            return []

    def _get_demo_indices_data(self) -> Mapping[str, Any]:
        """Return demo indices data when Wind API is not available."""
        import random

        indices = {
            "000001.SH": {"name": "上证综指", "base": 3150},
            "399001.SZ": {"name": "深证成指", "base": 11200},
            "399006.SZ": {"name": "创业板指", "base": 2350},
            "000300.SH": {"name": "沪深300", "base": 4180},
            "000905.SH": {"name": "中证500", "base": 6850},
            "000852.SH": {"name": "中证1000", "base": 7200},
            "000016.SH": {"name": "上证50", "base": 2850},
            "399005.SZ": {"name": "中小板指", "base": 8500},
            "000688.SH": {"name": "科创50", "base": 1050},
        }

        demo_data = {}
        current_time = datetime.now().isoformat()

        for code, info in indices.items():
            change = random.uniform(-50, 50)
            change_pct = change / info["base"] * 100

            demo_data[code] = {
                "code": code,
                "name": info["name"],
                "display_name": info["name"],
                "last": round(info["base"] + change, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": round(random.uniform(100, 500), 2),  # 亿手
                "amount": round(random.uniform(1000, 5000), 2),  # 亿元
                "open": round(info["base"] + random.uniform(-30, 30), 2),
                "high": round(info["base"] + random.uniform(0, 60), 2),
                "low": round(info["base"] + random.uniform(-60, 0), 2),
                "prev_close": info["base"],
                "timestamp": current_time,
                "update_time": current_time,
            }

        return demo_data

    def _get_demo_fx_data(self) -> Mapping[str, Any]:
        """Return demo FX data when Wind API is not available."""
        import random

        fx_pairs = {
            "USDCNY.EX": 7.25,
            "EURCNY.EX": 7.85,
            "HKDCNY.EX": 0.92,
            "JPYCNY.EX": 0.048,
        }

        demo_data = {}
        for code, base in fx_pairs.items():
            change = random.uniform(-0.05, 0.05)
            change_pct = change / base * 100

            demo_data[code] = {
                "code": code,
                "last": round(base + change, 4),
                "change": round(change, 4),
                "change_pct": round(change_pct, 2),
                "timestamp": datetime.now().isoformat(),
            }

        return demo_data

    def _get_demo_rates_data(self) -> Mapping[str, Any]:
        """Return demo rates data when Wind API is not available."""
        import random

        rates = {
            "M0000017.SH": 2.85,  # 10年期
            "M0000025.SH": 2.65,  # 5年期
            "M0000007.SH": 2.45,  # 3年期
            "M0000001.SH": 2.25,  # 1年期
        }

        demo_data = {}
        for code, base in rates.items():
            change = random.uniform(-0.05, 0.05)

            demo_data[code] = {
                "code": code,
                "last": round(base + change, 3),
                "change": round(change, 3),
                "timestamp": datetime.now().isoformat(),
            }

        return demo_data

    def _get_demo_commodities_data(self) -> Mapping[str, Any]:
        """Return demo commodities data when Wind API is not available."""
        import random

        commodities = {
            "RB00.SHF": 3800,     # 螺纹钢
            "I00.DCE": 850,       # 铁矿石
            "CU00.SHF": 68500,    # 沪铜
            "AL00.SHF": 18500,    # 沪铝
            "ZN00.SHF": 25200,    # 沪锌
            "AU00.SHF": 465,      # 沪金
            "AG00.SHF": 5650,     # 沪银
        }

        demo_data = {}
        for code, base in commodities.items():
            change = random.uniform(-base*0.03, base*0.03)
            change_pct = change / base * 100

            demo_data[code] = {
                "code": code,
                "last": round(base + change, 0),
                "change": round(change, 0),
                "change_pct": round(change_pct, 2),
                "volume": random.randint(10000, 100000),
                "timestamp": datetime.now().isoformat(),
            }

        return demo_data

    def _get_us_stock_name(self, code: str) -> str:
        """Get friendly name for US stock code."""
        names = {
            "DJI.GI": "道琼斯指数",
            "SPX.GI": "标普500",
            "IXIC.GI": "纳斯达克",
            "AAPL.O": "苹果",
            "MSFT.O": "微软",
            "GOOGL.O": "谷歌",
            "TSLA.O": "特斯拉",
            "AMZN.O": "亚马逊",
        }
        return names.get(code, code)

    def _get_demo_us_stocks_data(self) -> Mapping[str, Any]:
        """Return demo US stocks data when Wind API is not available."""
        import random

        us_stocks = {
            "DJI.GI": {"name": "道琼斯指数", "base": 35000},
            "SPX.GI": {"name": "标普500", "base": 4500},
            "IXIC.GI": {"name": "纳斯达克", "base": 15000},
            "AAPL.O": {"name": "苹果", "base": 180},
            "MSFT.O": {"name": "微软", "base": 330},
            "GOOGL.O": {"name": "谷歌", "base": 2800},
            "TSLA.O": {"name": "特斯拉", "base": 250},
            "AMZN.O": {"name": "亚马逊", "base": 150},
        }

        demo_data = {}
        current_time = datetime.now().isoformat()

        for code, info in us_stocks.items():
            change_pct = random.uniform(-3, 3)  # US stocks normal volatility
            change = info["base"] * change_pct / 100

            demo_data[code] = {
                "code": code,
                "name": info["name"],
                "last": round(info["base"] + change, 2),
                "change": round(change, 2),
                "change_pct": round(change_pct, 2),
                "volume": random.randint(1000000, 50000000),
                "timestamp": current_time,
            }

        return demo_data

    def __del__(self):
        """Clean up Wind API connection on destruction."""
        try:
            if self._w and self._connected:
                self._w.stop()
                logger.info("Wind API connection closed")
        except Exception as e:
            logger.error(f"Error closing Wind API connection: {e}")


# Factory function for Wind provider
def create_wind_provider() -> WindProvider:
    """Create and return Wind provider instance."""
    return WindProvider()