from datetime import datetime, timedelta
from typing import Dict
from utils.config import Config

class RiskManager:
    def __init__(self, max_drawdown: float = 0.05, max_daily_trades: int = 3):
        self.max_drawdown = max_drawdown
        self.max_daily_trades = max_daily_trades
        self.today_trades = 0
        self.daily_pnl = 0.0
        self.last_trade_time = None
        self.last_reset = datetime.now()
        self.cooldown_period = timedelta(minutes=30)

    def can_trade(self) -> bool:
        self._reset_daily_counter()
        
        if self.today_trades >= self.max_daily_trades:
            return False
            
        if self.daily_pnl <= -abs(self.max_drawdown):
            return False
            
        if self.last_trade_time and (datetime.now() - self.last_trade_time) < self.cooldown_period:
            return False
            
        return True

    def record_trade(self, pnl_change: float = 0) -> None:
        self.today_trades += 1
        self.daily_pnl += pnl_change
        self.last_trade_time = datetime.now()

    def get_risk_metrics(self) -> Dict[str, float]:
        return {
            'daily_trades': self.today_trades,
            'max_daily_trades': self.max_daily_trades,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'next_trade_time': (self.last_trade_time + self.cooldown_period).isoformat() 
                              if self.last_trade_time else None
        }

    def _reset_daily_counter(self) -> None:
        now = datetime.now()
        if now.date() != self.last_reset.date():
            self.today_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = now