from fastapi import FastAPI, Query
from smartapi_utils import get_portfolio_data, get_historic_data
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow requests from your frontend (localhost:8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080"],  # or use ["*"] for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "SmartAPI + FastAPI backend running!"}

@app.get("/portfolio")
def portfolio():
    return get_portfolio_data()

@app.get("/historic")
def historic(
    symboltoken: str = Query(...),
    exchange: str = Query("NSE"),
    interval: str = Query("ONE_MINUTE"),
    fromdate: str = Query(..., description="Format: YYYY-MM-DD HH:MM"),
    todate: str = Query(..., description="Format: YYYY-MM-DD HH:MM")
):
    return get_historic_data(symboltoken, exchange, interval, fromdate, todate)
