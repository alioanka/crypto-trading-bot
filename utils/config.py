import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Binance
    BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
    BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET")
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # Backup
    BACKUP_TO_CLOUD = os.getenv("BACKUP_TO_CLOUD", "False") == "True"

    # Risk Parameters
   # MAX_DRAWDOWN = float(os.getenv("MAX_DRAWDOWN", "0.25"))  # 25% max drawdown
    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.01"))  # 1% per trade

    # Trading Parameters
    CANDLE_INTERVAL = "1m"  # Options: 1m, 5m, 15m, 30m, 1h, 4h, 1d
    MAX_DAILY_TRADES = 3
    MAX_DRAWDOWN = 0.05  # 5%
    
    # Risk Profile (adjust these)
    RISK_PER_TRADE = 0.01  # 1% per trade
    MIN_VOLUME = 10_000_000  # $10M daily volume
    MAX_VOLATILITY = 15  # 15% daily price change