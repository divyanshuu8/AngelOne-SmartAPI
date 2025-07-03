# package import statement
from SmartApi import SmartConnect  # or from SmartApi.smartConnect import SmartConnect
import pyotp
from logzero import logger
from dotenv import load_dotenv
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

if data['status'] == False:
    logger.error(data)

else:
    # login api call
    # logger.info(f"You Credentials: {data}")
    authToken = data['data']['jwtToken']
    refreshToken = data['data']['refreshToken']
    # fetch the feedtoken
    feedToken = smartApi.getfeedToken()
    # fetch User Profile
    res = smartApi.getProfile(refreshToken)
    smartApi.generateToken(refreshToken)
    res = res['data']['exchanges']

    # Historic api
    try:
        historicParam = {
            "exchange": "NSE",
            "symboltoken": "3045",
            "interval": "ONE_MINUTE",
            "fromdate": "2025-07-02 09:15",
            "todate": "2025-07-02 09:30"
        }
        candles = smartApi.getCandleData(historicParam)
        logger.info(f"Candle Data:\n{candles}")
    except Exception as e:
        logger.exception(f"Historic Api failed: {e}")
    
    # logout
    try:
        logout = smartApi.terminateSession(username)
        logger.info("Logout Successfull")
    except Exception as e:
        logger.exception(f"Logout failed: {e}")
