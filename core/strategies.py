import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional
from utils.config import Config
from utils.alerts import AlertSystem

logger = logging.getLogger(__name__)
alerts = AlertSystem()

try:
    import talib
    TA_LIB_AVAILABLE = True
    logger.info("TA-Lib available - using optimized indicators")
except ImportError:
    TA_LIB_AVAILABLE = False
    logger.warning("TA-Lib not available - using fallback calculations")

class SmartTrendStrategy:
    def __init__(self):
        self.ema_short = Config.SMARTTREND_EMA_SHORT
        self.ema_long = Config.SMARTTREND_EMA_LONG
        self.rsi_period = Config.SMARTTREND_RSI_PERIOD
        self.rsi_overbought = Config.SMARTTREND_RSI_OVERBOUGHT
        self.rsi_oversold = Config.SMARTTREND_RSI_OVERSOLD
        self.min_volume = Config.MIN_VOLUME
        logger.info(f"SmartTrendStrategy initialized: EMA({self.ema_short}/{self.ema_long}), "
                  f"RSI({self.rsi_period}), OB/OS({self.rsi_overbought}/{self.rsi_oversold})")
        
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

    def generate_signal(self, data: List[Dict]) -> Optional[str]:
        """Advanced strategy with TA-Lib fallback"""
        if len(data) < 50:
            logger.warning(f"Insufficient data points ({len(data)}), need at least 50")
            return None
            
        df = pd.DataFrame(data)
        closes = df['close'].values
        
        # Volume check
        current_volume = df['volume'].iloc[-1]
        if current_volume < self.min_volume:
            logger.debug(f"Volume too low: {current_volume} < {self.min_volume}")
            return None
            
        # Calculate EMAs
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        # Calculate RSI
        df['rsi'] = self._calculate_rsi(closes)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Log current indicators
        logger.debug(f"{df.index[-1]} - Price: {current['close']}, "
                    f"EMA({self.ema_short}): {current['ema_short']}, "
                    f"EMA({self.ema_long}): {current['ema_long']}, "
                    f"RSI: {current['rsi']}")
        
        # Bullish conditions
        ema_cross = current['ema_short'] > current['ema_long']
        rsi_above = current['rsi'] > 50
        rsi_cross = previous['rsi'] <= 50
        rsi_not_overbought = current['rsi'] < self.rsi_overbought
        
        if all([ema_cross, rsi_above, rsi_cross, rsi_not_overbought]):
            logger.info("✅ BUY signal generated")
            return 'BUY'
            
        # Bearish conditions
        ema_cross = current['ema_short'] < current['ema_long']
        rsi_below = current['rsi'] < 50
        rsi_cross = previous['rsi'] >= 50
        rsi_not_oversold = current['rsi'] > self.rsi_oversold
        
        if all([ema_cross, rsi_below, rsi_cross, rsi_not_oversold]):
            logger.info("✅ SELL signal generated")
            return 'SELL'
            
        return None

class EMACrossStrategy:
    def __init__(self):
        self.ema_short = Config.EMA_SHORT_PERIOD
        self.ema_long = Config.EMA_LONG_PERIOD
        self.min_volume = Config.MIN_VOLUME
        logger.info(f"EMACrossStrategy initialized: EMA({self.ema_short}/{self.ema_long})")
        
    def generate_signal(self, data: List[Dict]) -> Optional[str]:
        """Simple EMA crossover strategy"""
        if len(data) < 22:
            logger.warning(f"Insufficient data points ({len(data)}), need at least 22")
            return None
            
        df = pd.DataFrame(data)
        
        current_volume = df['volume'].iloc[-1]
        if current_volume < self.min_volume:
            logger.debug(f"Volume too low: {current_volume} < {self.min_volume}")
            return None
            
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Log current indicators
        logger.debug(f"{df.index[-1]} - Price: {current['close']}, "
                    f"EMA({self.ema_short}): {current['ema_short']}, "
                    f"EMA({self.ema_long}): {current['ema_long']}")
        
        if (previous['ema_short'] <= previous['ema_long']) and (current['ema_short'] > current['ema_long']):
            logger.info("✅ BUY signal generated")
            return 'BUY'
        elif (previous['ema_short'] >= previous['ema_long']) and (current['ema_short'] < current['ema_long']):
            logger.info("✅ SELL signal generated")
            return 'SELL'
            
        return None