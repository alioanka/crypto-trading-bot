import numpy as np
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self, max_drawdown=0.25, daily_loss_limit=0.1):
        self.max_drawdown = max_drawdown
        self.daily_loss_limit = daily_loss_limit
        self.today_loss = 0
        self.last_reset = datetime.now()
        
    def validate_trade(self, trade_size, portfolio_value):
        """Check if trade meets risk parameters"""
        # Reset daily loss counter if new day
        if datetime.now() - self.last_reset > timedelta(days=1):
            self.today_loss = 0
            self.last_reset = datetime.now()
            
        # Check max position size (5% of portfolio)
        if trade_size > portfolio_value * 0.05:
            return False
            
        # Check daily loss limit
        if self.today_loss >= portfolio_value * self.daily_loss_limit:
            return False
            
        return True
    
    def update_after_trade(self, pnl):
        """Update risk metrics after trade execution"""
        if pnl < 0:
            self.today_loss += abs(pnl)