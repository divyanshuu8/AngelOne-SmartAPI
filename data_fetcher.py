from SmartApi import SmartConnect
import pandas as pd
from logzero import logger
import os
from dotenv import load_dotenv
from smartmoneyconcepts import smc

# Load environment variables from .env
load_dotenv()

# Fetch credentials from .env
api_key = os.getenv("API_KEY")
username = os.getenv("CLIENT_ID")
pwd = os.getenv("MPIN")
token = os.getenv("TOTP_SECRET")

smartApi = SmartConnect(api_key)


def analyze_historical_data(symboltoken, interval, fromdate, todate):
    """
    Fetches and analyzes historical data for a given symbol token and interval.

    Args:
        symboltoken (str): The symbol token.
        interval (str): The interval (e.g., "FIVE_MINUTE").

    Returns:
        dict: A dictionary containing the analysis results, or None if an error occurs.
    """
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": fromdate,
            "todate": todate,
        }
        candles = smartApi.getCandleData(historicParam)

        formatted_data = []
        for d in candles["data"]:
            try:
                ts = pd.to_datetime(d[0])  # handles both ISO and "YYYY-MM-DD HH:MM:SS"
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
                print(f"Skipping bad row {d}: {e}")

        # Convert to DataFrame
        df = pd.DataFrame(
            formatted_data,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )

        # If timestamp is string, convert to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df.set_index("timestamp", inplace=True)

        # Detect FVG using your smc library
        fvg = smc.fvg(df.reset_index(), join_consecutive=False)
        fvg_filtered = fvg[fvg["FVG"].notna()].copy()
        fvg_filtered["Timestamp"] = df.index[fvg_filtered.index]

        # Implement swing highs and lows
        swing_highs_lows_df = smc.swing_highs_lows(df, swing_length=15)

        # Detect BOS and CHoCH
        bos_choch = smc.bos_choch(df, swing_highs_lows_df, close_break=True)
        bos_choch = bos_choch[bos_choch["Level"].notna()].copy()
        bos_choch["Timestamp"] = df.index[bos_choch.index]

        # Detect Order Blocks
        ob = smc.ob(df, swing_highs_lows_df, close_mitigation=False)
        ob = ob[ob["OB"].notna()].copy()
        ob["Timestamp"] = df.index[ob.index]

        # Detect Liquidity
        liquidity = smc.liquidity(df, swing_highs_lows_df, range_percent=0.05)
        liquidity_filtered = liquidity[liquidity["Liquidity"].notna()].copy()

        # Prepare data for JSON output
        fvg_list = fvg_filtered.copy()
        fvg_list["Timestamp"] = fvg_list["Timestamp"].astype(str)
        fvg_list["MitigatedIndex"] = fvg_list["MitigatedIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        fvg_list = fvg_list.to_dict(orient="records")

        bos_choch_list = bos_choch.copy()
        bos_choch_list["Timestamp"] = bos_choch_list["Timestamp"].astype(str)
        bos_choch_list["BrokenIndex"] = bos_choch_list["BrokenIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        bos_choch_list = bos_choch_list.to_dict(orient="records")

        ob_list = ob.copy()
        ob_list["Timestamp"] = ob_list["Timestamp"].astype(str)
        ob_list["MitigatedIndex"] = ob_list["MitigatedIndex"].apply(
            lambda x: str(df.index[int(x)]) if pd.notna(x) else None
        )
        ob_list = ob_list.to_dict(orient="records")

        liquidity_levels = []
        for index, row in liquidity_filtered.iterrows():
            liquidity_levels.append(
                {
                    "timestamp_detected": str(df.index[index]),
                    "direction": int(row["Liquidity"]),
                    "price": float(row["Level"]),
                    "liquidity_hit_time": None,  # You might need to calculate this
                    "status": "unhit",  # You might need to calculate this
                    "End": float(row["End"]),
                    "Swept": float(row["Swept"]),
                }
            )

        result = {
            "symbol": "NIFTY",
            "date": str(df.index[0].date()),
            "timeframe": "5m",
            "fvg": fvg_list,
            "bos_choch": bos_choch_list,
            "ob": ob_list,
            "liquidity_levels": liquidity_levels,
        }
        return result

    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        return None
