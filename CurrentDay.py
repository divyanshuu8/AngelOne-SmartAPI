from SmartApi import SmartConnect
import pyotp
from logzero import logger
from dotenv import load_dotenv
import pandas as pd
import os
from datetime import datetime, timedelta
import json

# ------------------ Load environment variables ------------------
load_dotenv()
api_key = os.getenv("API_KEY")
username = os.getenv("CLIENT_ID")
pwd = os.getenv("MPIN")
token = os.getenv("TOTP_SECRET")

smartApi = SmartConnect(api_key)

# ------------------ Generate TOTP ------------------
totp = pyotp.TOTP(token).now()

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

# ------------------ Define today 5m interval ------------------
symbol = "2885"
symbolName = "Reliance"

today = datetime.now()
from_time = today.replace(hour=9, minute=15, second=0, microsecond=0)
to_time = today

historicParam = {
    "exchange": "NSE",
    "symboltoken": symbol,
    "interval": "FIVE_MINUTE",
    "fromdate": from_time.strftime("%Y-%m-%d %H:%M"),
    "todate": to_time.strftime("%Y-%m-%d %H:%M"),
}

# ------------------ Fetch candles ------------------
candles = smartApi.getCandleData(historicParam)

formatted_data = []
for d in candles["data"]:
    ts = pd.to_datetime(d[0])
    formatted_data.append(
        {
            "timestamp": ts.isoformat(),
            "open": float(d[1]),
            "high": float(d[2]),
            "low": float(d[3]),
            "close": float(d[4]),
            "volume": int(d[5]),
        }
    )

# ------------------ Save JSON ------------------
final_result_json = {
    "symbol": symbolName,
    "timeframe": "5m",
    "from": from_time.isoformat(),
    "to": to_time.isoformat(),
    "candles": formatted_data,
}

with open("today_5m.json", "w", encoding="utf-8") as f:
    json.dump(final_result_json, f, indent=2)

logger.info("✅ Saved today_5m.json")

# ------------------ Logout ------------------
try:
    smartApi.terminateSession(username)
    logger.info("Logout Successful")
except Exception as e:
    logger.exception("Logout failed")
