from SmartApi import SmartConnect
import pyotp
from logzero import logger
from dotenv import load_dotenv
import pandas as pd
from smartmoneyconcepts import smc
import os
from datetime import datetime, timedelta
import json

#-- Editables - Data
symbol = "13528"
symbolName = "GMRA"

# ------------------ Load environment variables ------------------
load_dotenv()
api_key = os.getenv("API_KEY")
username = os.getenv("CLIENT_ID")
pwd = os.getenv("MPIN")
token = os.getenv("TOTP_SECRET")

smartApi = SmartConnect(api_key)

# ------------------ Generate TOTP ------------------
try:
    totp = pyotp.TOTP(token).now()
except Exception as e:
    logger.error("Invalid Token: The provided token is not valid.")
    raise e

# ------------------ Login ------------------
data = smartApi.generateSession(username, pwd, totp)
if not data["status"]:
    logger.error(data)
    raise SystemExit

authToken = data["data"]["jwtToken"]
refreshToken = data["data"]["refreshToken"]
feedToken = smartApi.getfeedToken()
smartApi.getProfile(refreshToken)
smartApi.generateToken(refreshToken)

# ------------------ Define intervals ------------------
timeframes = [
    {
        "name": "5m",
        "interval": "FIVE_MINUTE",
        "fromdate": "2025-08-13 09:15",
        "todate": "2025-08-18 15:30",
    },
    {
        "name": "1h",
        "interval": "ONE_HOUR",
        "fromdate": "2025-07-18 09:15",
        "todate": "2025-08-18 15:30",
    },
    {
        "name": "1d",
        "interval": "ONE_DAY",
        "fromdate": "2025-02-18 09:15",
        "todate": "2025-08-18 15:30",
    },
]

# ------------------ Final JSON container ------------------
final_result_json = {"symbol": "NIFTY", "timeframes": {}}


# ------------------ Helper function to process candles ------------------
def process_candles(candles, df_index):
    """Apply SMC functions and format results for JSON."""
    # FVG
    fvg = smc.fvg(df_index.reset_index(), join_consecutive=False)
    fvg_filtered = fvg[fvg["FVG"].notna()].copy()
    fvg_filtered["Timestamp"] = df_index.index[fvg_filtered.index]
    fvg_list = fvg_filtered.copy()
    fvg_list["Timestamp"] = fvg_list["Timestamp"].astype(str)
    fvg_list["MitigatedIndex"] = fvg_list["MitigatedIndex"].apply(
        lambda x: str(df_index.index[int(x)]) if pd.notna(x) and x is not None else None
    )
    fvg_list = fvg_list.to_dict(orient="records")

    # Swing highs/lows
    swing_highs_lows_df = smc.swing_highs_lows(df_index, swing_length=15)

    # BOS/CHOCH
    bos_choch = smc.bos_choch(df_index, swing_highs_lows_df, close_break=True)
    bos_choch = bos_choch[bos_choch["Level"].notna()].copy()
    bos_choch["Timestamp"] = df_index.index[bos_choch.index]
    bos_choch_list = bos_choch.copy()
    bos_choch_list["Timestamp"] = bos_choch_list["Timestamp"].astype(str)
    bos_choch_list["BrokenIndex"] = bos_choch_list["BrokenIndex"].apply(
        lambda x: str(df_index.index[int(x)]) if pd.notna(x) and x is not None else None
    )
    bos_choch_list = bos_choch_list.to_dict(orient="records")

    # Order blocks
    ob = smc.ob(df_index, swing_highs_lows_df, close_mitigation=False)
    ob = ob[ob["OB"].notna()].copy()
    ob["Timestamp"] = df_index.index[ob.index]
    ob_list = ob.copy()
    ob_list["Timestamp"] = ob_list["Timestamp"].astype(str)
    ob_list["MitigatedIndex"] = ob_list["MitigatedIndex"].apply(
        lambda x: str(df_index.index[int(x)]) if pd.notna(x) and x is not None else None
    )
    ob_list = ob_list.to_dict(orient="records")

    # Liquidity
    liquidity = smc.liquidity(df_index, swing_highs_lows_df, range_percent=0.05)
    liquidity_filtered = liquidity[liquidity["Liquidity"].notna()].copy()
    liquidity_levels = []
    for index, row in liquidity_filtered.iterrows():
        liquidity_levels.append(
            {
                "timestamp_detected": str(df_index.index[index]),
                "direction": int(row["Liquidity"]),
                "price": float(row["Level"]),
                "liquidity_hit_time": None,
                "status": "unhit",
                "End": float(row["End"]),
                "Swept": float(row["Swept"]),
            }
        )

    return {
        "fvg": fvg_list,
        "bos_choch": bos_choch_list,
        "ob": ob_list,
        "liquidity_levels": liquidity_levels,
    }


# ------------------ Loop through timeframes ------------------
for tf in timeframes:
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": symbol,
            "interval": tf["interval"],
            "fromdate": tf["fromdate"],
            "todate": tf["todate"],
        }
        candles = smartApi.getCandleData(historicParam)

        formatted_data = []
        for d in candles["data"]:
            try:
                ts = pd.to_datetime(d[0])
                formatted_data.append(
                    {
                        "timestamp": ts,
                        "open": float(d[1]),
                        "high": float(d[2]),
                        "low": float(d[3]),
                        "close": float(d[4]),
                        "volume": int(d[5]),
                    }
                )
            except Exception as e:
                logger.warning(f"Skipping bad row {d}: {e}")

        df = pd.DataFrame(formatted_data)
        df.set_index("timestamp", inplace=True)

        smc_results = process_candles(candles, df)

        final_result_json["timeframes"][tf["name"]] = {
            "stock": symbolName,
            "from": tf["fromdate"],
            "to": tf["todate"],
            **smc_results,
        }

    except Exception as e:
        logger.exception(f"Failed processing timeframe {tf['name']}: {e}")

# ------------------ Previous day's 10m raw candles ------------------
prev_day = datetime.now() - timedelta(days=1)
while prev_day.weekday() >= 5:  # Skip weekends
    prev_day -= timedelta(days=1)
prev_day_str = prev_day.strftime("%Y-%m-%d")

historicParam_10m = {
    "exchange": "NSE",
    "symboltoken": symbol,
    "interval": "TEN_MINUTE",
    "fromdate": f"{prev_day_str} 09:30",
    "todate": f"{prev_day_str} 15:30",
}
candles_10m = smartApi.getCandleData(historicParam_10m)

formatted_10m = []
for d in candles_10m["data"]:
    try:
        ts = pd.to_datetime(d[0])
        formatted_10m.append(
            {
                "timestamp": ts.isoformat(),  # convert to string
                "open": float(d[1]),
                "high": float(d[2]),
                "low": float(d[3]),
                "close": float(d[4]),
                "volume": int(d[5]),
            }
        )
    except Exception as e:
        logger.warning(f"Skipping bad row {d}: {e}")

final_result_json["timeframes"]["10m_prev_day"] = {
    "stock": symbolName,
    "from": f"{prev_day_str} 09:30",
    "to": f"{prev_day_str} 15:30",
    "candles": formatted_10m,  # raw OHLCV data
}


# ------------------ Save to JSON (safe timestamp handling) ------------------
def json_serial(obj):
    if isinstance(obj, (pd.Timestamp, datetime)):
        return obj.isoformat()
    return str(obj)


with open("payload.json", "w") as f:
    json.dump(final_result_json, f, indent=2, default=json_serial)

logger.info("✅ Saved payload.json")

# ------------------ Logout ------------------
try:
    smartApi.terminateSession(username)
    logger.info("Logout Successful")
except Exception as e:
    logger.exception("Logout failed")

"""
You will receive JSON data in the format:
{
  "symbol": "...",
  "timeframes": {
    "5m": { ... },      // Current day intraday OHLC + SMC annotations (FVG, OB, BOS/CHOCH, liquidity)
    "1h": { ... },      // Higher timeframe OHLC + SMC annotations
    "1d": { ... },      // Daily OHLC + SMC annotations
    "10m_prev_day": { ... } // Previous day's 10-minute pure OHLCV candles (no annotations)
  }
}
Your task:
Analyze the 5-minute timeframe to generate at least two possible trade setups for the next candle after the latest 5m bar.
Use the 1h and 1d timeframes to determine higher-timeframe bias and important zones.
Use the previous day’s 10m OHLCV data to identify:
Key supply/demand zones from the previous day
Previous day’s high/low/midpoint and liquidity pools
Significant volume spikes or reaction levels that could act as intraday magnets

For each setup, include:
Direction: Buy or Sell
Confidence score: 0–10
Entry price range
Stop loss
Take profit(s): Can have multiple target levels
Reasoning: Up to 5 bullet points showing how FVG, OB, BOS/CHOCH, liquidity, HTF bias, and previous day’s levels support the trade
Invalidation scenario: What would make this setup invalid, plus the alternate trade idea

Rules:
Favor fresh unmitigated OB/FVG near price for high-probability entries.
If BOS is bullish in 5m and aligned with HTF structure → prioritize longs; if opposite → consider countertrend scalp.

Use previous day’s 10m OHLCV data to filter trades:
Avoid longs if price is rejecting previous day’s high with heavy selling
Avoid shorts if price is rejecting previous day’s low with heavy buying
If liquidity is nearby, explain how it may be targeted before reversal.
Clearly separate setups for long and short if both are viable.
Assume a short-term intraday scalp-to-swing style.
"""