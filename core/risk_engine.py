import logging
from datetime import datetime, timedelta
from typing import Dict, List
from utils.config import Config
from utils.alerts import AlertSystem

logger = logging.getLogger(__name__)
alerts = AlertSystem()

class RiskManager:
    def __init__(self, max_drawdown: float = 0.05, max_daily_trades: int = 3):
        self.max_drawdown = max_drawdown
        self.max_daily_trades = max_daily_trades
        self.daily_trades = 0
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.max_consecutive_wins = 0
        self.max_consecutive_losses = 0
        self.peak_balance = 0.0
        self.max_drawdown_pct = 0.0
        self.trade_history = []
        self.last_trade_time = None
        self.last_reset = datetime.now().date()
        self.cooldown_period = timedelta(minutes=30)
        logger.info(f"RiskManager initialized - Max Drawdown: {max_drawdown*100}%, Max Daily Trades: {max_daily_trades}")

    def can_trade(self) -> bool:
        """Check if trading is allowed with automatic daily reset"""
        self._check_daily_reset()
        
            # Enhanced cooldown check
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            required_cooldown = self.cooldown_period.total_seconds()
            
            # Dynamic cooldown based on recent performance
            if self.consecutive_losses > 2:
                required_cooldown *= 2  # Double cooldown after losses
                
            if elapsed < required_cooldown:
                remaining = required_cooldown - elapsed
                logger.warning(
                    f"Cooldown active - {int(remaining//60)}m {int(remaining%60)}s remaining. "
                    f"Consecutive losses: {self.consecutive_losses}"
                )
                return False
        # Debug logging
        logger.debug(f"Trade check - Daily: {self.daily_trades}/{self.max_daily_trades}, "
                    f"Drawdown: {self.daily_pnl:.2f}%/{self.max_drawdown*100:.2f}%")
        
        if self.daily_trades >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.daily_trades}/{self.max_daily_trades}")
            alerts.error_alert("RISK_LIMIT", "Daily trade limit reached")
            return False
            
        if self.daily_pnl <= -abs(self.max_drawdown * 100):  # Convert to percentage
            logger.warning(f"Max drawdown reached: {self.daily_pnl:.2f}% <= -{self.max_drawdown*100:.2f}%")
            alerts.error_alert("RISK_LIMIT", "Max drawdown reached")
            return False
            
        if self.last_trade_time and (datetime.now() - self.last_trade_time) < self.cooldown_period:
            remaining = (self.last_trade_time + self.cooldown_period) - datetime.now()
            logger.warning(f"Cooldown active - {remaining.seconds//60}m {remaining.seconds%60}s remaining")
            return False
            
        logger.debug("Risk check passed - trading allowed")
        return True

    def record_trade(self, symbol: str, side: str, quantity: float, 
                    price: float, entry_price: float, current_balance: float,
                    pnl_usd: float = None, pnl_pct: float = None):
        """Record trade with comprehensive metrics"""
        try:
            # Calculate PnL if not provided
            if pnl_usd is None and side == 'SELL':
                pnl_usd = (price - entry_price) * quantity
                pnl_pct = (price - entry_price) / entry_price * 100
                
            is_win = pnl_usd >= 0 if pnl_usd is not None else False
            
            # Rest of the method...
            
            if side == 'SELL':
                pnl_usd = (price - entry_price) * quantity
                pnl_pct = (price - entry_price) / entry_price * 100
                is_win = pnl_usd >= 0
            
            # Update metrics
            self.total_trades += 1
            self.daily_trades += 1
            
            if is_win:
                self.winning_trades += 1
                self.consecutive_wins += 1
                self.consecutive_losses = 0
            else:
                self.losing_trades += 1
                self.consecutive_losses += 1
                self.consecutive_wins = 0
                
            # Update PnL tracking
            self.daily_pnl += pnl_pct
            self.total_pnl += pnl_usd
            
            # Update drawdown calculations
            self.peak_balance = max(self.peak_balance, current_balance)
            drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100
            self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown)
            
            self.last_trade_time = datetime.now()
            
            logger.info(
                f"Trade recorded - {symbol} {side} | "
                f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%) | "
                f"Daily: {self.daily_trades}/{self.max_daily_trades}"
            )
            
        except Exception as e:
            logger.error(f"Error recording trade: {e}")

    def get_performance_metrics(self, current_balance: float) -> Dict:
        """Calculate comprehensive performance metrics"""
        win_rate = (self.winning_trades / self.total_trades * 100) if self.total_trades > 0 else 0
        avg_win = self._calculate_avg('win') if self.winning_trades > 0 else 0
        avg_loss = self._calculate_avg('loss') if self.losing_trades > 0 else 0
        risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0
        profit_factor = (self.winning_trades * avg_win) / (self.losing_trades * abs(avg_loss)) if self.losing_trades > 0 else float('inf')
        
        return {
            'total_trades': self.total_trades,
            'winning_trades': self.winning_trades,
            'losing_trades': self.losing_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'risk_reward': risk_reward,
            'profit_factor': profit_factor,
            'max_consecutive_wins': self.max_consecutive_wins,
            'max_consecutive_losses': self.max_consecutive_losses,
            'current_win_streak': self.consecutive_wins,
            'current_loss_streak': self.consecutive_losses,
            'total_pnl': self.total_pnl,
            'total_pnl_pct': (self.total_pnl / current_balance) * 100 if current_balance > 0 else 0,
            'daily_pnl': self.daily_pnl,
            'daily_pnl_pct': self.daily_pnl,
            'max_drawdown': self.max_drawdown_pct,
            'sharpe_ratio': self._calculate_sharpe_ratio()
        }

    def _calculate_avg(self, trade_type: str) -> float:
        """Calculate average win/loss percentage"""
        relevant_trades = [t for t in self.trade_history if t['is_win'] == (trade_type == 'win')]
        return sum(t['pnl_pct'] for t in relevant_trades) / len(relevant_trades) if relevant_trades else 0

    def _calculate_sharpe_ratio(self, risk_free_rate: float = 0.0) -> float:
        """Calculate simplified Sharpe ratio"""
        if len(self.trade_history) < 2:
            return 0
            
        returns = [t['pnl_pct'] for t in self.trade_history]
        avg_return = sum(returns) / len(returns)
        std_dev = (sum((x - avg_return)**2 for x in returns) / len(returns))**0.5
        
        return (avg_return - risk_free_rate) / std_dev if std_dev != 0 else 0

    def _check_daily_reset(self):
        """Reset daily counters at midnight"""
        today = datetime.now().date()
        if today != self.last_reset:
            logger.info("Resetting daily trade counters")
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = today

    def get_risk_metrics(self) -> Dict:
        """Get current risk metrics"""
        return {
            'daily_trades': self.daily_trades,
            'max_daily_trades': self.max_daily_trades,
            'daily_pnl': self.daily_pnl,
            'max_drawdown': self.max_drawdown,
            'next_trade_time': (self.last_trade_time + self.cooldown_period).isoformat() 
                              if self.last_trade_time else None
        }