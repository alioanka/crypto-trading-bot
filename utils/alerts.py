import requests
import time
import logging
from datetime import datetime
from typing import List, Dict, Optional
from utils.config import Config

logger = logging.getLogger(__name__)

class AlertSystem:
    """
    Comprehensive alert system with advanced performance tracking
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
            'PORTFOLIO': {'icon': '📊', 'color': '#9370DB'},
            'PERFORMANCE': {'icon': '📈', 'color': '#20B2AA'}
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

    def trade_executed(self, symbol: str, side: str, price: float, quantity: float, 
                     stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> bool:
        logger.info(f"Sending trade alert for {symbol} {side}")
        message = (
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Type</b>: {side.upper()}\n"
            f"<b>Price</b>: ${price:.4f}\n"
            f"<b>Quantity</b>: {quantity:.6f}\n"
            f"<b>Value</b>: ${price * quantity:.2f}"
        )
        
        if stop_loss:
            sl_pct = (stop_loss - price)/price * 100 if side == 'BUY' else (price - stop_loss)/price * 100
            message += f"\n<b>Stop Loss</b>: ${stop_loss:.4f} (<code>{sl_pct:+.2f}%</code>)"
            
        if take_profit:
            tp_pct = (take_profit - price)/price * 100 if side == 'BUY' else (price - take_profit)/price * 100
            message += f"\n<b>Take Profit</b>: ${take_profit:.4f} (<code>{tp_pct:+.2f}%</code>)"
            
        return self._send_alert(message, alert_type=side.upper())

    def trade_closed(self, symbol: str, side: str, price: float, quantity: float, 
                   entry_price: float, pnl_usd: float, pnl_pct: float, duration: str,
                   win_streak: int, lose_streak: int) -> bool:
        """Enhanced trade closure alert with full metrics"""
        logger.info(f"Sending trade closure alert for {symbol}")
        return self._send_alert(
            f"<b>Pair</b>: {symbol}\n"
            f"<b>Type</b>: {side.upper()} CLOSED\n"
            f"<b>Entry</b>: ${entry_price:.4f}\n"
            f"<b>Exit</b>: ${price:.4f}\n"
            f"<b>Quantity</b>: {quantity:.6f}\n"
            f"<b>Duration</b>: {duration}\n"
            f"<b>PnL</b>: ${pnl_usd:.2f} (<code>{pnl_pct:+.2f}%</code>)\n"
            f"<b>Streak</b>: {'🔥' * win_streak if pnl_usd >=0 else '💧' * lose_streak}",
            alert_type="TAKE_PROFIT" if pnl_usd >=0 else "STOP_LOSS"
        )

    def position_update(self, positions: Dict, metrics: Dict) -> bool:
        """Detailed portfolio update with performance metrics"""
        if not positions:
            return False
            
        message = (
            f"📊 <b>PORTFOLIO UPDATE</b>\n"
            f"• Balance: <code>${metrics['balance']:.2f}</code>\n"
            f"• Today's PnL: <code>${metrics['daily_pnl']:.2f}</code> (<code>{metrics['daily_pnl_pct']:.2f}%</code>)\n"
            f"• Total PnL: <code>${metrics['total_pnl']:.2f}</code> (<code>{metrics['total_pnl_pct']:.2f}%</code>)\n"
            f"• Win Rate: <code>{metrics['win_rate']:.1f}%</code>\n"
            f"• Risk/Reward: <code>1:{metrics['risk_reward']:.2f}</code>\n\n"
            f"<b>POSITIONS</b> ({len(positions)}):"
        )
        
        for symbol, pos in positions.items():
            message += (
                f"\n\n<b>{symbol}</b>\n"
                f"• Side: {pos['side']}\n"
                f"• Size: {pos['quantity']:.4f} @ ${pos['entry_price']:.4f}\n"
                f"• Current: ${pos['current_price']:.4f}\n"
                f"• PnL: ${pos['pnl_usd']:.2f} (<code>{pos['pnl_pct']:+.2f}%</code>)\n"
                f"• Value: ${pos['value']:.2f}"
            )
        
        return self._send_alert(message, "PORTFOLIO")

    def performance_report(self, metrics: Dict) -> bool:
        """Detailed performance analytics report"""
        return self._send_alert(
            f"📈 <b>PERFORMANCE REPORT</b>\n"
            f"• Total Trades: <code>{metrics['total_trades']}</code>\n"
            f"• Win Rate: <code>{metrics['win_rate']:.1f}%</code>\n"
            f"• Avg Win: <code>{metrics['avg_win']:.2f}%</code>\n"
            f"• Avg Loss: <code>{metrics['avg_loss']:.2f}%</code>\n"
            f"• Risk/Reward: <code>1:{metrics['risk_reward']:.2f}</code>\n"
            f"• Profit Factor: <code>{metrics['profit_factor']:.2f}</code>\n"
            f"• Max Drawdown: <code>{metrics['max_drawdown']:.2f}%</code>\n"
            f"• Sharpe Ratio: <code>{metrics['sharpe_ratio']:.2f}</code>",
            "PERFORMANCE"
        )

    def _format_duration(self, seconds: float) -> str:
        """Convert seconds to human-readable duration"""
        minutes, sec = divmod(seconds, 60)
        hours, min = divmod(minutes, 60)
        days, hr = divmod(hours, 24)
        
        if days > 0:
            return f"{int(days)}d {int(hr)}h"
        elif hours > 0:
            return f"{int(hours)}h {int(min)}m"
        return f"{int(minutes)}m {int(sec)}s"

    # ... [keep existing system/error alerts]

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