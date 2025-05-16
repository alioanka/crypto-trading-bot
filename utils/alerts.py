import requests
from datetime import datetime
from utils.config import Config

class TelegramAlerts:
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        
    def _send_message(self, text, alert_type="INFO"):
        icons = {
            "BUY": "🟢",
            "SELL": "🔴", 
            "STOP_LOSS": "🛑",
            "TAKE_PROFIT": "🎯",
            "WARNING": "⚠️",
            "INFO": "ℹ️"
        }
        
        payload = {
            "chat_id": Config.TELEGRAM_CHAT_ID,
            "text": f"{icons.get(alert_type)} {alert_type}\n{text}",
            "parse_mode": "HTML"
        }
        
        try:
            requests.post(self.base_url, json=payload, timeout=5)
        except Exception as e:
            print(f"Failed to send Telegram alert: {e}")

    def trade_alert(self, symbol, side, price, quantity):
        self._send_message(
            f"<b>{symbol}</b>\n"
            f"Action: {side.upper()}\n"
            f"Price: ${price:.2f}\n"
            f"Quantity: {quantity:.4f}",
            alert_type=side.upper()
        )
        
    def risk_alert(self, message):
        self._send_message(
            f"<b>RISK CONTROL ACTIVATED</b>\n{message}",
            alert_type="WARNING"
        )