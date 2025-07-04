from SmartApi.smartConnect import SmartConnect
import pyotp
import os
from datetime import datetime
from dotenv import load_dotenv
from logzero import logger

def get_credentials():
    load_dotenv()
    return {
        "api_key": os.getenv("API_KEY"),
        "username": os.getenv("CLIENT_ID"),
        "pwd": os.getenv("MPIN"),
        "token": os.getenv("TOTP_SECRET")
    }

def get_portfolio_data():
    creds = get_credentials()
    smartApi = SmartConnect(creds["api_key"])

    try:
        totp = pyotp.TOTP(creds["token"]).now()
        session = smartApi.generateSession(creds["username"], creds["pwd"], totp)
        if not session["status"]:
            logger.error("Login Failed")
            return {"error": "Login failed", "details": session}

        refresh_token = session["data"]["refreshToken"]
        smartApi.generateToken(refresh_token)
        portfolio = smartApi.holding()
        smartApi.terminateSession(creds["username"])
        return portfolio

    except Exception as e:
        logger.exception("Portfolio fetch failed")
        return {"error": "Portfolio fetch failed", "details": str(e)}


def get_historic_data(symboltoken: str, exchange: str, interval: str, fromdate: str, todate: str):
    creds = get_credentials()
    smartApi = SmartConnect(creds["api_key"])

    try:
        totp = pyotp.TOTP(creds["token"]).now()
        session = smartApi.generateSession(creds["username"], creds["pwd"], totp)
        if not session["status"]:
            logger.error("Login Failed")
            return {"error": "Login failed", "details": session}
        
        refresh_token = session["data"]["refreshToken"]
        smartApi.generateToken(refresh_token)

        from_date_obj = datetime.strptime(fromdate, "%Y-%m-%d %H:%M")
        to_date_obj = datetime.strptime(todate, "%Y-%m-%d %H:%M")

        historic_param = {
            "exchange": exchange,
            "symboltoken": symboltoken,
            "interval": interval,
            "fromdate": from_date_obj.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date_obj.strftime("%Y-%m-%d %H:%M")
        }

        candles = smartApi.getCandleData(historic_param)
        smartApi.terminateSession(creds["username"])
        return candles

    except Exception as e:
        logger.exception("Historic API failed")
        return {"error": "Historic API failed", "details": str(e)}
