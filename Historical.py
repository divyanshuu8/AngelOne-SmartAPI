# package import statement
from SmartApi import SmartConnect  # or from SmartApi.smartConnect import SmartConnect
import pyotp
from logzero import logger
from dotenv import load_dotenv
import pandas as pd
from smartmoneyconcepts import smc
import mplfinance as mpf
import matplotlib.pyplot as plt
from datetime import datetime  # <-- this line is required
import os

# Load environment variables from .env
load_dotenv()

# Fetch credentials from .env
api_key = os.getenv("API_KEY")
username = os.getenv("CLIENT_ID")
pwd = os.getenv("MPIN")
token = os.getenv("TOTP_SECRET")

smartApi = SmartConnect(api_key)

try:
    totp = pyotp.TOTP(token).now()
except Exception as e:
    logger.error("Invalid Token: The provided token is not valid.")
    raise e

correlation_id = "abcde"
data = smartApi.generateSession(username, pwd, totp)

if data["status"] == False:
    logger.error(data)

else:
    # login api call
    # logger.info(f"You Credentials: {data}")
    authToken = data["data"]["jwtToken"]
    refreshToken = data["data"]["refreshToken"]
    # fetch the feedtoken
    feedToken = smartApi.getfeedToken()
    # fetch User Profile
    res = smartApi.getProfile(refreshToken)
    smartApi.generateToken(refreshToken)
    res = res["data"]["exchanges"]

    # Historic api
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": "3045",
            "interval": "FIVE_MINUTE",
            "fromdate": "2025-07-02 09:15",
            "todate": "2025-07-05 15:30",
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
        print(fvg_filtered)

        # Implement swing highs and lows
        swing_highs_lows_df = smc.swing_highs_lows(df, swing_length=15)

        # Detect BOS and CHoCH
        bos_choch = smc.bos_choch(df, swing_highs_lows_df, close_break=True)
        bos_choch = bos_choch[bos_choch["Level"].notna()].copy()
        bos_choch["Timestamp"] = df.index[bos_choch.index]
        print(bos_choch)

        # Detect Order Blocks
        ob = smc.ob(df, swing_highs_lows_df, close_mitigation=False)
        ob = ob[ob["OB"].notna()].copy()
        ob["Timestamp"] = df.index[ob.index]
        print(ob)

        # Detect Liquidity
        liquidity = smc.liquidity(df, swing_highs_lows_df, range_percent=0.05)
        liquidity = liquidity[liquidity["Liquidity"].notna()].copy()
        liquidity["Timestamp"] = df.index[liquidity.index]
        print(liquidity)

        # Assuming fvg is a list of dicts with 'start', 'end', 'low', 'high'
        # shapes = []
        # for gap in fvg:
        #     start_time = pd.to_datetime(gap["start"])
        #     end_time = pd.to_datetime(gap["end"])
        #     low_price = gap["low"]
        #     high_price = gap["high"]

        #     shapes.append(
        #         dict(
        #             type="rect",
        #             x0=start_time,
        #             x1=end_time,
        #             y0=low_price,
        #             y1=high_price,
        #             facecolor="yellow",
        #             alpha=0.3,
        #         )
        #     )

        # Plot candlestick chart
        # mpf.plot(
        #     df,
        #     type="candle",
        #     style="charles",
        #     title="Candlestick Chart with FVG",
        #     ylabel="Price",
        #     addplot=[],
        #     fill_between=shapes,
        # )

        # ---logger.info(f"Candle Data:\n{candles['data']}")
    except Exception as e:
        logger.exception(f"Historic Api failed: {e}")

    # fetch Holdings / Portfolio
    """
    try:
        portfolio = smartApi.holding()
        logger.info(f"Portfolio Data:\n{portfolio}")
    except Exception as e:
        logger.exception(f"Portfolio fetch failed: {e}")
    """

    # logout
    try:
        logout = smartApi.terminateSession(username)
        logger.info("Logout Successfull")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")
