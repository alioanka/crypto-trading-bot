import requests
from datetime import datetime
from utils.config import Config

class AlertSystem:
    """
    Comprehensive alert system for all trading notifications
    Includes: Trade execution, risk triggers, system events
    """
    def __init__(self):
        self.base_url = f"https://api.telegram.org/bot{Config.TELEGRAM_TOKEN}/sendMessage"
        self.alert_types = {
            'BUY': {'icon': '🟢', 'color': '#00FF00'},
            'SELL': {'icon': '🔴', 'color': '#FF0000'},
            'STOP_LOSS': {'icon': '🛑', 'color': '#FF4500'},
            'TAKE_PROFIT': {'icon': '🎯', 'color': '#32CD32'},
            'RISK_ALERT': {'icon': '⚠️', 'color': '#FFA500'},
            'SYSTEM': {'icon': 'ℹ️', 'color': '#1E90FF'}
        }

    def _send_alert(self, message, alert_type):
        """Base alert sending method"""
        alert = self.alert_types.get(alert_type, {})
        formatted_msg = (
            f"{alert.get('icon', '')} <b>{alert_type.replace('_', ' ')}</b>\n"
            f"{message}"
        )
        
        try:
            requests.post(
                self.base_url,
                json={
                    "chat_id": Config.TELEGRAM_CHAT_ID,
                    "text": formatted_msg,
                    "parse_mode": "HTML"
                },
                timeout=5
            )
        except Exception as e:
            print(f"Alert failed: {e}")

    # TRADE ALERTS
    def trade_executed(self, symbol, side, price, quantity):
        self._send_alert(
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Price</b>: ${price:.2f}\n"
            f"<b>Quantity</b>: {quantity:.4f}",
            alert_type=side.upper()
        )

    def trade_closed(self, symbol, side, price, quantity, pnl):
        self._send_alert(
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Price</b>: ${price:.2f}\n"
            f"<b>Quantity</b>: {quantity:.4f}\n"
            f"<b>PnL</b>: ${pnl:.2f} ({'🔺' if pnl >=0 else '🔻'}{abs(pnl):.2f})",
            alert_type="TAKE_PROFIT" if pnl >=0 else "STOP_LOSS"
        )

    # RISK ALERTS
    def risk_triggered(self, trigger_type, details):
        self._send_alert(
            f"<b>Trigger</b>: {trigger_type}\n"
            f"<b>Details</b>: {details}",
            alert_type="RISK_ALERT"
        )

    def drawdown_alert(self, current_drawdown):
        self._send_alert(
            f"<b>Current Drawdown</b>: {current_drawdown*100:.2f}%\n"
            f"<b>Max Allowed</b>: {Config.MAX_DRAWDOWN*100:.0f}%",
            alert_type="RISK_ALERT"
        )

    # SYSTEM ALERTS
    def bot_started(self, version, pairs):
        self._send_alert(
            f"<b>Version</b>: {version}\n"
            f"<b>Trading pairs</b>: {', '.join(pairs)}",
            alert_type="SYSTEM"
        )

    def bot_stopped(self, reason):
        self._send_alert(
            f"<b>Shutdown reason</b>: {reason}",
            alert_type="SYSTEM"
        )

    def balance_update(self, current_balance, change):
        self._send_alert(
            f"<b>Account Balance</b>: ${current_balance:.2f}\n"
            f"<b>24h Change</b>: {'🔺+' if change >=0 else '🔻'}{change:.2f}",
            alert_type="SYSTEM"
        )