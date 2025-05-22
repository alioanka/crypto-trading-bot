import os
import logging
from dotenv import load_dotenv
from typing import List

load_dotenv()

logger = logging.getLogger(__name__)

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
    CANDLE_INTERVAL = os.getenv("CANDLE_INTERVAL", "5m")  # Changed default to 5m
    MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", 5))
    
    # Risk Management Parameters
    MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", 0.05))  # 5% max drawdown
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", 0.02))  # 1% per trade
    STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", 0.015))  # 1.5%
    TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", 0.03))  # 3%
    STRANDED_POSITION_TIMEOUT = 86400  # 24 hours in seconds
    STRANDED_POSITION_RETRY_INTERVAL = 3600  # 1 hour in seconds

    # Strategy Configuration
    STRATEGY = os.getenv("STRATEGY", "SmartTrend")  # SmartTrend or EMACross
    
    # SmartTrend Strategy Parameters
    SMARTTREND_EMA_SHORT = int(os.getenv("SMARTTREND_EMA_SHORT", 12))  # Widened
    SMARTTREND_EMA_LONG = int(os.getenv("SMARTTREND_EMA_LONG", 26))    # Widened
    SMARTTREND_RSI_PERIOD = int(os.getenv("SMARTTREND_RSI_PERIOD", 14))
    SMARTTREND_RSI_OVERBOUGHT = int(os.getenv("SMARTTREND_RSI_OVERBOUGHT", 65))
    SMARTTREND_RSI_OVERSOLD = int(os.getenv("SMARTTREND_RSI_OVERSOLD", 35))
    
    # EMA Cross Strategy Parameters
    EMA_SHORT_PERIOD = int(os.getenv("EMA_SHORT_PERIOD", 12))  # Widened
    EMA_LONG_PERIOD = int(os.getenv("EMA_LONG_PERIOD", 26))    # Widened

    # Market Filters
    # Market Filters
    MIN_VOLUME = float(os.getenv("MIN_VOLUME", 10))  # Changed from 1,000,000 to 100
    VOLUME_CHECK_MODE = os.getenv("VOLUME_CHECK_MODE", "relative")  # 'relative' or 'absolute'
    MIN_VOLUME_MULTIPLIER = float(os.getenv("MIN_VOLUME_MULTIPLIER", 0.3))  # 50% of average

    # Time Validation
    TIME_TOLERANCE_PCT = float(os.getenv("TIME_TOLERANCE_PCT", 50))  # 20% tolerance
    MAX_VOLATILITY = float(os.getenv("MAX_VOLATILITY", 15))  # 15% daily price change
    MIN_NOTIONAL = float(os.getenv("MIN_NOTIONAL", 15))  # $10 minimum order value

    # Debugging and Monitoring
    DEBUG_MODE = os.getenv("DEBUG_MODE", "False") == "True"
    HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", 3600))  # 1 hour
    DATA_QUALITY_CHECKS = os.getenv("DATA_QUALITY_CHECKS", "True") == "True"
    TELEGRAM_ALERTS = True

    # Logging Configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR
    LOG_RETENTION_DAYS = int(os.getenv("LOG_RETENTION_DAYS", 7))

    # System Configuration
    DATA_DIR = os.getenv("DATA_DIR", "data")
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", 3))
    REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", 10))

# Validate critical configuration
if not all([Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET]):
    logger.error("Missing Binance API credentials in configuration")
    raise ValueError("Binance API credentials not configured")

if not all([Config.TELEGRAM_TOKEN, Config.TELEGRAM_CHAT_ID]):
    logger.warning("Telegram alerts not fully configured - alerts will be logged only")