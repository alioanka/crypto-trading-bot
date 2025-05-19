import logging
from datetime import datetime, timedelta
from typing import Dict
from utils.config import Config
from utils.alerts import AlertSystem

logger = logging.getLogger(__name__)
alerts = AlertSystem()

class RiskManager:
    def __init__(self, max_drawdown: float = 0.05, max_daily_trades: int = 3):
        self.max_drawdown = max_drawdown
        self.max_daily_trades = max_daily_trades
        self.today_trades = 0
        self.daily_pnl = 0.0
        self.last_trade_time = None
        self.last_reset = datetime.now()
        self.cooldown_period = timedelta(minutes=30)
        logger.info(f"RiskManager initialized - Max Drawdown: {max_drawdown*100}%, Max Daily Trades: {max_daily_trades}")

    def can_trade(self) -> bool:
        """Check if trading is allowed with detailed logging"""
        self._reset_daily_counter()
        
        if self.today_trades >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.today_trades}/{self.max_daily_trades}")
            alerts.error_alert("RISK_LIMIT", "Daily trade limit reached")
            return False
            
        if self.daily_pnl <= -abs(self.max_drawdown):
            logger.warning(f"Max drawdown reached: {self.daily_pnl*100:.2f}% <= -{self.max_drawdown*100:.0f}%")
            alerts.error_alert("RISK_LIMIT", "Max drawdown reached")
            return False
            
        if self.last_trade_time and (datetime.now() - self.last_trade_time) < self.cooldown_period:
            remaining = (self.last_trade_time + self.cooldown_period) - datetime.now()
            logger.warning(f"Cooldown active - {remaining.seconds//60}m {remaining.seconds%60}s remaining")
            return False
            
        logger.debug("Risk check passed - trading allowed")
        return True

    def record_trade(self, pnl_change: float = 0) -> None:
        """Record trade with logging"""
        self.today_trades += 1
        self.daily_pnl += pnl_change
        self.last_trade_time = datetime.now()
        logger.info(f"Trade recorded - Count: {self.today_trades}/{self.max_daily_trades}, PnL: {self.daily_pnl*100:.2f}%")

    def get_risk_metrics(self) -> Dict[str, float]:
        """Get current risk metrics"""
        metrics = {
            'daily_trades': self.today_trades,
            'max_daily_trades': self.max_daily_trades,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'next_trade_time': (self.last_trade_time + self.cooldown_period).isoformat() 
                              if self.last_trade_time else None
        }
        logger.debug(f"Risk metrics: {metrics}")
        return metrics

    def _reset_daily_counter(self) -> None:
        """Reset daily counters at midnight"""
        now = datetime.now()
        if now.date() != self.last_reset.date():
            logger.info("Resetting daily trade counters")
            self.today_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = now