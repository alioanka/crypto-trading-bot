# Makes core directory a Python package
from .strategies import EMAStrategy, SmartTrendStrategy
from .risk_engine import RiskManager
from .exchange import BinanceAPI

__all__ = ['EMAStrategy', 'SmartTrendStrategy', 'RiskManager', 'BinanceAPI']