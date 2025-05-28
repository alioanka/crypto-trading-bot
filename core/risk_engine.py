import logging
import time
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
        """Enhanced trading permission check with dynamic risk controls"""
        self._check_daily_reset()
        
        # Time-based trading hours restriction
        current_time = datetime.now().time()
        if not (time(9, 0) <= current_time <= time(16, 0)):  # 9AM-4PM only
            logger.debug("Outside trading hours - no trading allowed")
            return False
        
        # Dynamic cooldown calculation
        base_cooldown = self.cooldown_period.total_seconds()
        
        # Increase cooldown after consecutive losses
        if self.consecutive_losses >= 2:
            cooldown_multiplier = 1 + (self.consecutive_losses * 0.5)  # 1.5x, 2x, 2.5x etc.
            base_cooldown *= cooldown_multiplier
            logger.warning(f"Extended cooldown due to {self.consecutive_losses} consecutive losses")
        
        # Check cooldown period
        if self.last_trade_time:
            elapsed = (datetime.now() - self.last_trade_time).total_seconds()
            if elapsed < base_cooldown:
                remaining = base_cooldown - elapsed
                logger.warning(
                    f"Cooldown active - {int(remaining//60)}m {int(remaining%60)}s remaining. "
                    f"Loss streak: {self.consecutive_losses}"
                )
                return False
        
        # Check daily trade limit
        if self.daily_trades >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.daily_trades}/{self.max_daily_trades}")
            alerts.error_alert("RISK_LIMIT", "Daily trade limit reached")
            return False
        
        # Check drawdown limit (convert max_drawdown to percentage)
        max_drawdown_pct = self.max_drawdown * 100
        if self.daily_pnl <= -abs(max_drawdown_pct):
            logger.warning(
                f"Max drawdown reached: {self.daily_pnl:.2f}% <= -{max_drawdown_pct:.2f}%"
            )
            alerts.error_alert("RISK_LIMIT", "Max drawdown reached")
            return False
        
        # Check weekday restrictions (no trading Monday mornings or Friday afternoons)
        weekday = datetime.now().weekday()
        if weekday == 0 or (weekday == 4 and current_time.hour >= 15):
            logger.warning("Avoiding Monday morning/Friday afternoon trading")
            return False
        
        logger.debug(
            f"Risk check passed - Trades: {self.daily_trades}/{self.max_daily_trades}, "
            f"PnL: {self.daily_pnl:.2f}%, Loss Streak: {self.consecutive_losses}"
        )
        return True

    def record_trade(self, symbol: str, side: str, quantity: float, 
                    price: float, entry_price: float, current_balance: float,
                    pnl_usd: float = None, pnl_pct: float = None) -> Dict:
        """Comprehensive trade recording with performance metrics
        
        Args:
            symbol: Trading pair symbol
            side: BUY or SELL
            quantity: Trade quantity
            price: Execution price
            entry_price: Original entry price (for PnL calculation)
            current_balance: Current account balance
            pnl_usd: Optional pre-calculated PnL in USD
            pnl_pct: Optional pre-calculated PnL percentage
        
        Returns:
            Dictionary with trade details and performance metrics
        """
        try:
            # Calculate PnL if not provided (only for SELL trades)
            if side == 'SELL':
                if pnl_usd is None:
                    pnl_usd = (price - entry_price) * quantity
                if pnl_pct is None:
                    pnl_pct = (price - entry_price) / entry_price * 100
                is_win = pnl_usd >= 0
            else:
                pnl_usd = 0
                pnl_pct = 0
                is_win = False

            # Update trade counters
            self.total_trades += 1
            self.daily_trades += 1
            
            # Update win/loss streaks
            if side == 'SELL':
                if is_win:
                    self.winning_trades += 1
                    self.consecutive_wins += 1
                    self.consecutive_losses = 0
                    if self.consecutive_wins > self.max_consecutive_wins:
                        self.max_consecutive_wins = self.consecutive_wins
                else:
                    self.losing_trades += 1
                    self.consecutive_losses += 1
                    self.consecutive_wins = 0
                    if self.consecutive_losses > self.max_consecutive_losses:
                        self.max_consecutive_losses = self.consecutive_losses

            # Update PnL tracking
            self.daily_pnl += pnl_pct if side == 'SELL' else 0
            self.total_pnl += pnl_usd if side == 'SELL' else 0
            
            # Update drawdown calculations
            self.peak_balance = max(self.peak_balance, current_balance)
            drawdown = (self.peak_balance - current_balance) / self.peak_balance * 100
            self.max_drawdown_pct = max(self.max_drawdown_pct, drawdown)
            
            self.last_trade_time = datetime.now()
            
            # Record trade in history
            trade_record = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'side': side,
                'quantity': quantity,
                'price': price,
                'entry_price': entry_price,
                'pnl_usd': pnl_usd,
                'pnl_pct': pnl_pct,
                'is_win': is_win,
                'balance': current_balance
            }
            self.trade_history.append(trade_record)
            
            logger.info(
                f"Trade recorded - {symbol} {side} | "
                f"Qty: {quantity:.4f} | "
                f"Price: {price:.4f} | "
                f"PnL: ${pnl_usd:.2f} ({pnl_pct:.2f}%) | "
                f"Balance: ${current_balance:.2f}"
            )
            
            return {
                'trade': trade_record,
                'metrics': self.get_performance_metrics(current_balance)
            }
                
        except Exception as e:
            logger.error(f"Error recording trade: {e}", exc_info=True)
            return {
                'error': str(e),
                'trade': None,
                'metrics': None
            }

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
        now = datetime.now()
        today = now.date()
        if today != self.last_reset:
            logger.info("Resetting daily trade counters")
            self.daily_trades = 0
            self.daily_pnl = 0.0
            self.last_reset = today
            # Also reset last trade time to avoid cooldown issues
            self.last_trade_time = None

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