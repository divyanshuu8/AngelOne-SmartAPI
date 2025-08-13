from SmartApi import SmartConnect
import pyotp
from logzero import logger
from dotenv import load_dotenv
import pandas as pd
from smartmoneyconcepts import smc
import os
from datetime import datetime
import json

# Load environment variables
load_dotenv()
api_key = os.getenv("API_KEY")
username = os.getenv("CLIENT_ID")
pwd = os.getenv("MPIN")
token = os.getenv("TOTP_SECRET")

smartApi = SmartConnect(api_key)

# Generate TOTP
try:
    totp = pyotp.TOTP(token).now()
except Exception as e:
    logger.error("Invalid Token: The provided token is not valid.")
    raise e

# Login
data = smartApi.generateSession(username, pwd, totp)
if not data["status"]:
    logger.error(data)
    raise SystemExit

authToken = data["data"]["jwtToken"]
refreshToken = data["data"]["refreshToken"]
feedToken = smartApi.getfeedToken()
smartApi.getProfile(refreshToken)
smartApi.generateToken(refreshToken)

# --- Define intervals & custom dates ---
timeframes = [
    {
        "name": "5m",
        "interval": "FIVE_MINUTE",
        "fromdate": "2025-08-08 09:15",
        "todate": "2025-08-13 15:30",
    },
    {
        "name": "1h",
        "interval": "ONE_HOUR",
        "fromdate": "2025-07-13 09:15",
        "todate": "2025-08-13 15:30",
    },
    {
        "name": "1d",
        "interval": "ONE_DAY",
        "fromdate": "2025-02-13 09:15",
        "todate": "2025-08-13 15:30",
    },
]

# --- Final JSON container ---
final_result_json = {"symbol": "NIFTY", "timeframes": {}}

# --- Loop through timeframes ---
for tf in timeframes:
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": "2885",
            "interval": tf["interval"],
            "fromdate": tf["fromdate"],
            "todate": tf["todate"],
        }
        candles = smartApi.getCandleData(historicParam)

        # Format candle data
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

        # --- Apply SMC functions ---
        fvg = smc.fvg(df.reset_index(), join_consecutive=False)
        fvg_filtered = fvg[fvg["FVG"].notna()].copy()
        fvg_filtered["Timestamp"] = df.index[fvg_filtered.index]
        fvg_list = fvg_filtered.copy()
        fvg_list["Timestamp"] = fvg_list["Timestamp"].astype(str)
        fvg_list["MitigatedIndex"] = fvg_list["MitigatedIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        fvg_list = fvg_list.to_dict(orient="records")

        swing_highs_lows_df = smc.swing_highs_lows(df, swing_length=15)

        bos_choch = smc.bos_choch(df, swing_highs_lows_df, close_break=True)
        bos_choch = bos_choch[bos_choch["Level"].notna()].copy()
        bos_choch["Timestamp"] = df.index[bos_choch.index]
        bos_choch_list = bos_choch.copy()
        bos_choch_list["Timestamp"] = bos_choch_list["Timestamp"].astype(str)
        bos_choch_list["BrokenIndex"] = bos_choch_list["BrokenIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        bos_choch_list = bos_choch_list.to_dict(orient="records")

        ob = smc.ob(df, swing_highs_lows_df, close_mitigation=False)
        ob = ob[ob["OB"].notna()].copy()
        ob["Timestamp"] = df.index[ob.index]
        ob_list = ob.copy()
        ob_list["Timestamp"] = ob_list["Timestamp"].astype(str)
        ob_list["MitigatedIndex"] = ob_list["MitigatedIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        ob_list = ob_list.to_dict(orient="records")

        liquidity = smc.liquidity(df, swing_highs_lows_df, range_percent=0.05)
        liquidity_filtered = liquidity[liquidity["Liquidity"].notna()].copy()
        liquidity_levels = []
        for index, row in liquidity_filtered.iterrows():
            liquidity_levels.append(
                {
                    "timestamp_detected": str(df.index[index]),
                    "direction": int(row["Liquidity"]),
                    "price": float(row["Level"]),
                    "liquidity_hit_time": None,
                    "status": "unhit",
                    "End": float(row["End"]),
                    "Swept": float(row["Swept"]),
                }
            )

        # Add to final JSON
        final_result_json["timeframes"][tf["name"]] = {
            "stock": "Reliance",
            "from": tf["fromdate"],
            "to": tf["todate"],
            "fvg": fvg_list,
            "bos_choch": bos_choch_list,
            "ob": ob_list,
            "liquidity_levels": liquidity_levels,
        }

    except Exception as e:
        logger.exception(f"Failed processing timeframe {tf['name']}: {e}")

# Save to payload.json
with open("payload.json", "w") as f:
    json.dump(final_result_json, f, indent=2)
logger.info("✅ Saved payload.json")
# Logout
try:
    smartApi.terminateSession(username)
    logger.info("Logout Successful")
except Exception as e:
    logger.exception("Logout failed")

# Below is the Prompt-
"""
I will give you JSON data in the format:
json
{
  "symbol": "...",
  "timeframes": {
    "5m": { ... },
    "1h": { ... },
    "1d": { ... }
  }
}
Each timeframe contains OHLC candles plus SMC annotations (FVG, OB, BOS/CHOCH, liquidity levels).
Your task:
Analyze the 5-minute timeframe to generate at least two possible trade setups for the next candle after the last 5m bar.
Use the 1h and 1d timeframes only to determine higher-timeframe bias and important zones.
For each setup, include:

Direction: Buy or Sell
Confidence score: 0–10
Entry price range
Stop loss
Take profit(s) — can have multiple target levels

Reasoning: 5 bullet points max, showing how FVG, OB, BOS/CHOCH, liquidity, and HTF bias support this trade
Invalidation scenario: What would make this setup invalid and the alternate trade idea

Rules:
Favor fresh unmitigated OB/FVG near price.
If BOS is bullish in 5m and aligned with HTF structure, prioritize longs. If opposite, consider countertrend scalp.
If liquidity is nearby, explain how it may be targeted before reversal.
Clearly separate setups for long and short if both are viable.
Assume a short-term intraday scalp-to-swing style.
"""
