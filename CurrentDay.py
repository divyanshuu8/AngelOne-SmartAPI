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
# Example instrument info:
# {
#     "token": "458303",
#     "symbol": "GOLDPETAL30SEP25FUT",
#     "name": "GOLDPETAL",
#     "expiry": "30SEP2025",
#     "strike": "0.000000",
#     "lotsize": "1",
#     "instrumenttype": "FUTCOM",
#     "exch_seg": "MCX",
#     "tick_size": "100.000000"
# }

symbol = "4244"
exchange = "NSE"  # change to "MCX" if needed
symbolName = "hdfc"


# ------------------ Market hours switch ------------------
def get_market_hours(exchange, date: datetime):
    if exchange.upper() == "NSE":
        start = date.replace(hour=9, minute=15, second=0, microsecond=0)
        end = date.replace(hour=15, minute=30, second=0, microsecond=0)
    elif exchange.upper() == "MCX":
        start = date.replace(hour=9, minute=0, second=0, microsecond=0)
        end = date.replace(hour=23, minute=30, second=0, microsecond=0)
    else:
        # default NSE timings
        start = date.replace(hour=9, minute=15, second=0, microsecond=0)
        end = date.replace(hour=15, minute=30, second=0, microsecond=0)
    return start, end


today = datetime.now()
from_time, market_close = get_market_hours(exchange, today)
to_time = today if today < market_close else market_close

historicParam = {
    "exchange": exchange,
    "symboltoken": symbol,
    "interval": "FIVE_MINUTE",
    "fromdate": from_time.strftime("%Y-%m-%d %H:%M"),
    "todate": to_time.strftime("%Y-%m-%d %H:%M"),
}
print(f"  From: {historicParam['fromdate']}")
print(f"  To:   {historicParam['todate']}")
print("-" * 30)

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
