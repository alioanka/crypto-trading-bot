import pandas as pd
import numpy as np
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
from collections import deque
from utils.config import Config
from utils.alerts import AlertSystem
from dataclasses import dataclass

logger = logging.getLogger(__name__)
alerts = AlertSystem()

try:
    import talib
    TA_LIB_AVAILABLE = True
    logger.info("TA-Lib available - using optimized indicators")
except ImportError:
    TA_LIB_AVAILABLE = False
    logger.warning("TA-Lib not available - using fallback calculations")

@dataclass
class TradeSignal:
    action: str  # "BUY", "SELL", or "HOLD"
    price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    confidence: Optional[float] = None

class BaseStrategy:
    def __init__(self):
        self.debug_mode = Config.DEBUG_MODE
        self.test_signal = None
        self.data_quality_issues = deque(maxlen=100)
        self.last_candle_time = None
        
        if self.debug_mode:
            logger.info("Debug mode enabled - verbose logging active")

    def _is_good_trading_time(self) -> bool:
        """Check if current time is within optimal trading hours"""
        current_time = datetime.now().time()
        weekday = datetime.now().weekday()
        
        # Trading hours (9AM-4PM)
        if not (time(9, 0) <= current_time <= time(16, 0)):
            if self.debug_mode:
                logger.debug("Outside optimal trading hours (9AM-4PM)")
            return False
        
        # Avoid Monday morning and Friday afternoon
        if weekday == 0 or (weekday == 4 and current_time.hour >= 15):
            if self.debug_mode:
                logger.debug("Avoiding Monday morning/Friday afternoon trading")
            return False
            
        return True

    def calculate_stop_loss(self, entry_price: float, is_long: bool = True) -> float:
        """Calculate stop loss price based on configured percentage"""
        if is_long:
            return entry_price * (1 - abs(Config.STOP_LOSS_PCT)/100)
        return entry_price * (1 + abs(Config.STOP_LOSS_PCT)/100)

    def calculate_take_profit(self, entry_price: float, is_long: bool = True) -> float:
        """Calculate take profit price based on configured percentage"""
        if is_long:
            return entry_price * (1 + abs(Config.TAKE_PROFIT_PCT)/100)
        return entry_price * (1 - abs(Config.TAKE_PROFIT_PCT)/100)

    def check_data_quality(self, data: List[Dict]) -> bool:
        """Enhanced data quality validation"""
        if not Config.DATA_QUALITY_CHECKS:
            return True
            
        if not data or len(data) < 1:
            self._log_data_issue("Empty data received")
            return False
            
        last_candle = data[-1]
        issues = []
        
        required_fields = ['open', 'high', 'low', 'close', 'volume', 'time']
        for field in required_fields:
            if field not in last_candle:
                issues.append(f"Missing field: {field}")
                return False
                
        if last_candle['close'] <= 0:
            issues.append(f"Invalid close price: {last_candle['close']}")
            return False
            
        if Config.CANDLE_INTERVAL != '1m' and last_candle['volume'] < Config.MIN_VOLUME:
            issues.append(f"Low volume: {last_candle['volume']} < {Config.MIN_VOLUME}")
        
        current_time = pd.to_datetime(last_candle['time'])
        if self.last_candle_time is not None:
            interval_map = {'1m': 60, '5m': 300, '15m': 900, '30m': 1800, '1h': 3600, '4h': 14400, '1d': 86400}
            expected_interval = interval_map.get(Config.CANDLE_INTERVAL, 60)
            time_diff = (current_time - self.last_candle_time).total_seconds()
            
            if abs(time_diff - expected_interval) > (expected_interval * 2):
                issues.append(f"Large time irregularity: {time_diff:.2f}s vs expected {expected_interval}s")
        
        self.last_candle_time = current_time
        
        if issues:
            self._log_data_issue(issues)
            
        return True

    def _log_data_issue(self, issues):
        """Log data quality issues"""
        issue_str = ", ".join(issues) if isinstance(issues, list) else str(issues)
        self.data_quality_issues.append({
            'time': pd.Timestamp.now().isoformat(),
            'issue': issue_str
        })
        logger.debug(f"Data quality note: {issue_str}")

    def force_test_signal(self, signal: str):
        """Force a specific signal for testing"""
        if signal.upper() not in ['BUY', 'SELL']:
            logger.error(f"Invalid test signal: {signal}")
            return
            
        self.test_signal = signal.upper()
        logger.info(f"Test signal set to: {self.test_signal}")

    def get_data_quality_report(self) -> Dict:
        """Generate data quality metrics"""
        return {
            'total_issues': len(self.data_quality_issues),
            'recent_issues': list(self.data_quality_issues)[-5:],
            'last_candle_time': self.last_candle_time
        }

class EMACrossStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.ema_short = Config.EMA_SHORT_PERIOD
        self.ema_long = Config.EMA_LONG_PERIOD
        logger.info(f"EMACrossStrategy initialized: EMA({self.ema_short}/{self.ema_long})")
        
    def generate_signal(self, data: List[Dict]) -> Optional[TradeSignal]:
        # Time filter check
        if not self._is_good_trading_time():
            return None
            
        if hasattr(self, 'test_signal') and self.test_signal:
            signal = TradeSignal(
                action=self.test_signal,
                price=data[-1]['close'],
                stop_loss=self.calculate_stop_loss(data[-1]['close']),
                take_profit=self.calculate_take_profit(data[-1]['close'])
            )
            self.test_signal = None
            logger.info(f"TEST MODE: Returning forced signal: {signal}")
            return signal
            
        if not super().check_data_quality(data):
            logger.debug("Data quality check failed")
            return None
            
        if len(data) < 22:
            logger.warning(f"Insufficient data points ({len(data)}), need at least 22")
            return None
            
        df = pd.DataFrame(data)
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        if self.debug_mode:
            logger.debug(f"Current indicators - Price: {current['close']}, "
                        f"EMA{self.ema_short}: {current['ema_short']:.4f}, "
                        f"EMA{self.ema_long}: {current['ema_long']:.4f}")
        
        # Volume filter - only trade if volume is above average
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        if current['volume'] < avg_volume * 1.2:
            logger.debug("Volume below threshold - no signal generated")
            return None
        
        if (previous['ema_short'] <= previous['ema_long']) and (current['ema_short'] > current['ema_long']):
            logger.info("✅ BUY signal generated")
            return TradeSignal(
                action='BUY',
                price=current['close'],
                stop_loss=self.calculate_stop_loss(current['close']),
                take_profit=self.calculate_take_profit(current['close'])
            )
        elif (previous['ema_short'] >= previous['ema_long']) and (current['ema_short'] < current['ema_long']):
            logger.info("✅ SELL signal generated")
            return TradeSignal(
                action='SELL',
                price=current['close'],
                stop_loss=self.calculate_stop_loss(current['close'], is_long=False),
                take_profit=self.calculate_take_profit(current['close'], is_long=False)
            )
        return None

class SmartTrendStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()
        self.ema_short = Config.SMARTTREND_EMA_SHORT
        self.ema_long = Config.SMARTTREND_EMA_LONG 
        self.rsi_period = Config.SMARTTREND_RSI_PERIOD
        self.rsi_overbought = Config.SMARTTREND_RSI_OVERBOUGHT
        self.rsi_oversold = Config.SMARTTREND_RSI_OVERSOLD
        self.adx_threshold = 25  # ADX trend strength threshold
        self.volume_multiplier = 1.5  # Minimum volume multiplier
        logger.info(f"Enhanced SmartTrendStrategy initialized")
        
    def _calculate_rsi(self, prices: List[float]) -> List[float]:
        """Calculate RSI with or without TA-Lib"""
        if TA_LIB_AVAILABLE:
            return talib.RSI(prices, timeperiod=self.rsi_period)
        
        # Fallback RSI calculation
        deltas = np.diff(prices)
        seed = deltas[:self.rsi_period+1]
        up = seed[seed >= 0].sum()/self.rsi_period
        down = -seed[seed < 0].sum()/self.rsi_period
        rs = up/down
        rsi = np.zeros_like(prices)
        rsi[:self.rsi_period] = 100. - 100./(1.+rs)

        for i in range(self.rsi_period, len(prices)):
            delta = deltas[i-1]
            if delta > 0:
                upval = delta
                downval = 0.
            else:
                upval = 0.
                downval = -delta

            up = (up*(self.rsi_period-1) + upval)/self.rsi_period
            down = (down*(self.rsi_period-1) + downval)/self.rsi_period
            rs = up/down
            rsi[i] = 100. - 100./(1.+rs)

        return rsi

    def generate_signal(self, data: List[Dict]) -> Optional[TradeSignal]:
        # Time filter check
        if not self._is_good_trading_time():
            return None
            
        if self.test_signal:
            signal = TradeSignal(
                action=self.test_signal,
                price=data[-1]['close'],
                stop_loss=self.calculate_stop_loss(data[-1]['close']),
                take_profit=self.calculate_take_profit(data[-1]['close'])
            )
            self.test_signal = None
            logger.info(f"TEST MODE: Returning forced signal: {signal}")
            return signal
            
        if not super().check_data_quality(data):
            logger.debug("Data quality check failed")
            return None
            
        if len(data) < 50:
            logger.warning(f"Insufficient data points ({len(data)}), need at least 50")
            return None
            
        df = pd.DataFrame(data)
        closes = df['close'].values
        volumes = df['volume'].values
        
        # Calculate all indicators
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        df['rsi'] = self._calculate_rsi(closes)
        
        if TA_LIB_AVAILABLE:
            df['adx'] = talib.ADX(df['high'], df['low'], df['close'], timeperiod=14)
            df['obv'] = talib.OBV(df['close'], df['volume'])
        else:
            df['adx'] = 25  # Fallback if TA-Lib not available
            df['obv'] = (df['volume'] * (2*(df['close'].diff() > 0)-1).cumsum())
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Enhanced Bullish Conditions:
        ema_cross = current['ema_short'] > current['ema_long']
        rsi_above = current['rsi'] > 50
        rsi_cross = previous['rsi'] <= 50
        rsi_not_overbought = current['rsi'] < self.rsi_overbought
        adx_strong = current['adx'] > self.adx_threshold
        volume_ok = current['volume'] > volumes[:-1].mean() * self.volume_multiplier
        
        if all([ema_cross, rsi_above, rsi_cross, rsi_not_overbought, adx_strong, volume_ok]):
            confidence = min(1.0, (current['rsi'] - 50)/50 + (current['adx']/100))
            return TradeSignal(
                action='BUY',
                price=current['close'],
                stop_loss=self.calculate_stop_loss(current['close']),
                take_profit=self.calculate_take_profit(current['close']),
                confidence=confidence
            )
            
        # Enhanced Bearish Conditions:
        ema_cross = current['ema_short'] < current['ema_long']
        rsi_below = current['rsi'] < 50
        rsi_cross = previous['rsi'] >= 50
        rsi_not_oversold = current['rsi'] > self.rsi_oversold
        adx_strong = current['adx'] > self.adx_threshold
        volume_ok = current['volume'] > volumes[:-1].mean() * self.volume_multiplier
        
        if all([ema_cross, rsi_below, rsi_cross, rsi_not_oversold, adx_strong, volume_ok]):
            confidence = min(1.0, (50 - current['rsi'])/50 + (current['adx']/100))
            return TradeSignal(
                action='SELL',
                price=current['close'],
                stop_loss=self.calculate_stop_loss(current['close'], is_long=False),
                take_profit=self.calculate_take_profit(current['close'], is_long=False),
                confidence=confidence
            )
            
        return None