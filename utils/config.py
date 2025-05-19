import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Config:
    # Binance API Configuration
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    
    # Telegram Alerts Configuration
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # Backup Configuration
    BACKUP_TO_CLOUD = os.getenv("BACKUP_TO_CLOUD", "False") == "True"

    # Trading Parameters
    CANDLE_INTERVAL = os.getenv("CANDLE_INTERVAL", "1m")  # 1m, 5m, 15m, 30m, 1h, 4h, 1d
    MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", 3))
    
    # Risk Management Parameters
    MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", 0.05))  # 5% max drawdown
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 0.01))  # 1% per trade
    STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 0.015))  # 1.5%
    TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", 0.03))  # 3%

    # Strategy Configuration
    STRATEGY = os.getenv("STRATEGY", "SmartTrend")  # SmartTrend or EMACross
    
    # SmartTrend Strategy Parameters
    SMARTTREND_EMA_SHORT = int(os.getenv("SMARTTREND_EMA_SHORT", 8))
    SMARTTREND_EMA_LONG = int(os.getenv("SMARTTREND_EMA_LONG", 20))
    SMARTTREND_RSI_PERIOD = int(os.getenv("SMARTTREND_RSI_PERIOD", 14))
    SMARTTREND_RSI_OVERBOUGHT = int(os.getenv("SMARTTREND_RSI_OVERBOUGHT", 70))
    SMARTTREND_RSI_OVERSOLD = int(os.getenv("SMARTTREND_RSI_OVERSOLD", 30))
    
    # EMA Cross Strategy Parameters
    EMA_SHORT_PERIOD = int(os.getenv("EMA_SHORT_PERIOD", 9))
    EMA_LONG_PERIOD = int(os.getenv("EMA_LONG_PERIOD", 21))

    # Market Filters
    MIN_VOLUME = float(os.getenv("MIN_VOLUME", 10_000_000))  # $10M daily volume
    MAX_VOLATILITY = float(os.getenv("MAX_VOLATILITY", 15))  # 15% daily price change
    MIN_NOTIONAL = float(os.getenv("MIN_NOTIONAL", 10))  # $10 minimum order value

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))

    # System Configuration
    DATA_DIR = os.getenv("DATA_DIR", "data")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))