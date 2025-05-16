import pandas as pd
import numpy as np
from utils.config import Config

class EMAStrategy:
    def __init__(self):
        self.ema_short = 9
        self.ema_long = 21
        self.min_volume = 100  # Minimum BTC volume (in USDT)
        
    def generate_signal(self, data):
        """
        Generates signals based on EMA crossover with volume confirmation
        Returns: 'BUY', 'SELL', or None
        """
        if len(data) < 22:  # Need at least 21 periods for EMA
            return None
            
        df = pd.DataFrame(data)
        df['ema9'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema21'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        # Current and previous values
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Volume check
        if current['volume'] < self.min_volume:
            return None
            
        # Bullish signal (EMA9 crosses above EMA21)
        if (previous['ema9'] <= previous['ema21']) and (current['ema9'] > current['ema21']):
            return 'BUY'
            
        # Bearish signal (EMA9 crosses below EMA21)
        elif (previous['ema9'] >= previous['ema21']) and (current['ema9'] < current['ema21']):
            return 'SELL'
            
        return None

class SmartTrendStrategy:
    def __init__(self):
        self.ema_short = 8
        self.ema_long = 20
        self.rsi_period = 14
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
    def generate_signal(self, data):
        """Advanced strategy combining EMA, RSI, and volume"""
        if len(data) < 21:  # Need enough data points
            return None
            
        df = pd.DataFrame(data)
        
        # Calculate EMAs
        df['ema8'] = df['close'].ewm(span=self.ema_short, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=self.ema_long, adjust=False).mean()
        
        # Calculate RSI
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=self.rsi_period).mean()
        avg_loss = loss.rolling(window=self.rsi_period).mean()
        rs = avg_gain / avg_loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        current = df.iloc[-1]
        previous = df.iloc[-2]
        
        # Bullish confirmation (EMA8 > EMA20 and RSI > 50)
        if (current['ema8'] > current['ema20'] and 
            current['rsi'] > 50 and 
            previous['rsi'] <= 50):
            return 'BUY'
            
        # Bearish confirmation (EMA8 < EMA20 and RSI < 50)
        elif (current['ema8'] < current['ema20'] and 
              current['rsi'] < 50 and 
              previous['rsi'] >= 50):
            return 'SELL'
            
        return None