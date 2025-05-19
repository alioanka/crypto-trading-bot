import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from utils.config import Config

try:
    import talib
    TA_LIB_AVAILABLE = True
except ImportError:
    TA_LIB_AVAILABLE = False
    print("TA-Lib not available, using fallback calculations")

class SmartTrendStrategy:
    def __init__(self):
        self.ema_short = Config.SMARTTREND_EMA_SHORT
        self.ema_long = Config.SMARTTREND_EMA_LONG
        self.rsi_period = Config.SMARTTREND_RSI_PERIOD
        self.rsi_overbought = Config.SMARTTREND_RSI_OVERBOUGHT
        self.rsi_oversold = Config.SMARTTREND_RSI_OVERSOLD
        self.min_volume = Config.MIN_VOLUME
        
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
            return None
            
        df = pd.DataFrame(data)
        closes = df['close'].values
        
        # Volume check
        if df['volume'].iloc[-1] < self.min_volume:
            return None
            
        # Calculate EMAs
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        # Calculate RSI
        df['rsi'] = self._calculate_rsi(closes)
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish conditions
        if (current['ema_short'] > current['ema_long'] and 
            current['rsi'] > 50 and 
            previous['rsi'] <= 50 and
            current['rsi'] < self.rsi_overbought):
            return 'BUY'
            
        # Bearish conditions
        elif (current['ema_short'] < current['ema_long'] and 
              current['rsi'] < 50 and 
              previous['rsi'] >= 50 and
              current['rsi'] > self.rsi_oversold):
            return 'SELL'
            
        return None

class EMACrossStrategy:
    def __init__(self):
        self.ema_short = Config.EMA_SHORT_PERIOD
        self.ema_long = Config.EMA_LONG_PERIOD
        self.min_volume = Config.MIN_VOLUME
        
    def generate_signal(self, data: List[Dict]) -> Optional[str]:
        """Simple EMA crossover strategy"""
        if len(data) < 22:
            return None
            
        df = pd.DataFrame(data)
        
        if df['volume'].iloc[-1] < self.min_volume:
            return None
            
        df['ema_short'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema_long'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        if (previous['ema_short'] <= previous['ema_long']) and (current['ema_short'] > current['ema_long']):
            return 'BUY'
        elif (previous['ema_short'] >= previous['ema_long']) and (current['ema_short'] < current['ema_long']):
            return 'SELL'
            
        return None