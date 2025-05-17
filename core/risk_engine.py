from datetime import datetime

class RiskManager:
    def __init__(self, max_drawdown: float = 0.05, max_daily_trades: int = 3):
        """
        Args:
            max_drawdown: Max allowed daily loss percentage (e.g., 0.05 for 5%)
            max_daily_trades: Maximum trades per 24h period
        """
        self.max_drawdown = max_drawdown
        self.max_daily_trades = max_daily_trades
        self.today_trades = 0
        self.last_reset = datetime.now()
        self.daily_pnl = 0.0

    def can_trade(self) -> bool:
        """Check if trading is allowed"""
        self._reset_daily_counter()
        return (self.today_trades < self.max_daily_trades and 
                self.daily_pnl > -abs(self.max_drawdown))

    def record_trade(self, pnl_change: float = 0):
        """Update trade counters"""
        self.today_trades += 1
        self.daily_pnl += pnl_change

    def _reset_daily_counter(self):
        """Reset counters at midnight"""
        if datetime.now().day != self.last_reset.day:
            self.today_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = datetime.now()