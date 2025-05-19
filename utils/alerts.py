import requests
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
from utils.config import Config

logger = logging.getLogger(__name__)

class AlertSystem:
    """
    Comprehensive alert system for trading notifications with retry mechanism
    """
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        self.retry_delay = 5
        self.max_retries = 3
        self.alert_types = {
            'BUY': {'icon': '🟢', 'color': '#00FF00'},
            'SELL': {'icon': '🔴', 'color': '#FF0000'},
            'STOP_LOSS': {'icon': '🛑', 'color': '#FF4500'},
            'TAKE_PROFIT': {'icon': '🎯', 'color': '#32CD32'},
            'RISK_ALERT': {'icon': '⚠️', 'color': '#FFA500'},
            'SYSTEM': {'icon': 'ℹ️', 'color': '#1E90FF'},
            'ERROR': {'icon': '❌', 'color': '#FF0000'},
            'HEARTBEAT': {'icon': '💓', 'color': '#FF69B4'}
        }
        logger.info("AlertSystem initialized")

    def _send_alert(self, message: str, alert_type: str) -> bool:
        """Base alert sending method with retries"""
        alert = self.alert_types.get(alert_type, {})
        formatted_msg = (
            f"{alert.get('icon', '')} <b>{alert_type.replace('_', ' ')}</b>\n"
            f"{message}\n"
            f"<i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
        )
        
        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.base_url,
                    json={
                        "chat_id": Config.TELEGRAM_CHAT_ID,
                        "text": formatted_msg,
                        "parse_mode": "HTML"
                    },
                    timeout=Config.REQUEST_TIMEOUT
                )
                response.raise_for_status()
                logger.debug(f"Alert sent successfully: {alert_type}")
                return True
            except Exception as e:
                if attempt < self.max_retries - 1:
                    logger.warning(f"Alert failed (attempt {attempt+1}), retrying: {e}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Alert failed after {self.max_retries} attempts: {e}")
                    return False
        return False

    # TRADE ALERTS
    def trade_executed(self, symbol: str, side: str, price: float, quantity: float) -> bool:
        logger.info(f"Sending trade alert for {symbol} {side}")
        return self._send_alert(
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Type</b>: {side.upper()}\n"
            f"<b>Price</b>: ${price:.4f}\n"
            f"<b>Quantity</b>: {quantity:.6f}\n"
            f"<b>Value</b>: ${price * quantity:.2f}",
            alert_type=side.upper()
        )

    def trade_closed(self, symbol: str, side: str, price: float, quantity: float, pnl: float) -> bool:
        logger.info(f"Sending trade closure alert for {symbol} {side}")
        return self._send_alert(
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Type</b>: {side.upper()}\n"
            f"<b>Price</b>: ${price:.4f}\n"
            f"<b>Quantity</b>: {quantity:.6f}\n"
            f"<b>PnL</b>: ${abs(pnl):.2f} ({'🔺+' if pnl >=0 else '🔻'}{pnl:.2f})",
            alert_type="TAKE_PROFIT" if pnl >=0 else "STOP_LOSS"
        )

    # SYSTEM ALERTS
    def bot_started(self, version: str, pairs: List[str]) -> bool:
        logger.info("Sending bot startup alert")
        return self._send_alert(
            f"<b>Version</b>: {version}\n"
            f"<b>Interval</b>: {Config.CANDLE_INTERVAL}\n"
            f"<b>Pairs</b>: {', '.join(pairs)}",
            alert_type="SYSTEM"
        )

    def bot_stopped(self, reason: str) -> bool:
        logger.info(f"Sending bot shutdown alert: {reason}")
        return self._send_alert(
            f"<b>Reason</b>: {reason}",
            alert_type="SYSTEM"
        )

    def balance_update(self, current_balance: float, change: float) -> bool:
        logger.info("Sending balance update alert")
        return self._send_alert(
            f"<b>Balance</b>: ${current_balance:.2f}\n"
            f"<b>24h Change</b>: {'🔺+' if change >=0 else '🔻'}{change:.2f}",
            alert_type="SYSTEM"
        )

    # ERROR ALERTS
    def error_alert(self, error_type: str, details: str, symbol: Optional[str] = None) -> bool:
        logger.error(f"Sending error alert: {error_type} - {details}")
        message = f"<b>Error</b>: {error_type}\n<b>Details</b>: {details}"
        if symbol:
            message = f"<b>Pair</b>: {symbol}\n" + message
        return self._send_alert(message, alert_type="ERROR")

    # HEARTBEAT ALERT
    def heartbeat(self, message: str) -> bool:
        logger.debug("Sending heartbeat alert")
        return self._send_alert(message, alert_type="HEARTBEAT")