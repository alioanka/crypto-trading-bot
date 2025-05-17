import math
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union
from utils.config import Config

class BinanceAPI:
    # Approved stable pairs (update quarterly)
    STABLE_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'BNBUSDT',
        'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT',
        'MATICUSDT', 'LTCUSDT'
    ]

    def __init__(self):
        self.client = Client(
            api_key=Config.BINANCE_API_KEY,
            api_secret=Config.BINANCE_API_SECRET,
            testnet=False
        )
        self.retry_delay = 5

    def is_stable_pair(self, symbol: str) -> bool:
        """Check if symbol is in approved stable list"""
        return symbol in self.STABLE_PAIRS

    def get_account_balance(self) -> Dict[str, float]:
        """Get all non-zero balances"""
        for _ in range(3):
            try:
                account = self.client.get_account()
                return {
                    asset['asset']: float(asset['free'])
                    for asset in account['balances']
                    if float(asset['free']) > 0.0001  # Ignore dust
                }
            except BinanceAPIException as e:
                print(f"Balance error: {e}. Retrying...")
                time.sleep(self.retry_delay)
        return {}

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price with volatility check"""
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            price_change = float(ticker['priceChangePercent'])
            
            # Skip if >15% daily volatility
            if abs(price_change) > 15:
                print(f"⚠️ High volatility: {symbol} ({price_change}%)")
                return None
                
            return float(ticker['lastPrice'])
        except Exception as e:
            print(f"Price error: {e}")
            return None

    def get_klines(self, symbol: str, interval: str = '4h', limit: int = 100) -> Optional[List[Dict]]:
        """Get candle data with stability checks"""
        if not self.is_stable_pair(symbol):
            print(f"⚠️ Unapproved pair: {symbol}")
            return None

        try:
            klines = self.client.get_klines(
                symbol=symbol,
                interval=interval,
                limit=limit
            )
            return [{
                'time': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in klines]
        except Exception as e:
            print(f"Klines error: {e}")
            return None

    def execute_order(self, symbol: str, side: str, quantity: float) -> Union[Dict, None]:
        """Safe order execution with stability checks"""
        try:
            if not self.is_stable_pair(symbol):
                raise ValueError(f"Unapproved trading pair: {symbol}")

            # Get current price with volatility check
            price = self.get_price(symbol)
            if not price:
                return None

            # Validate quantity
            if quantity <= 0:
                raise ValueError("Invalid quantity")

            return self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=quantity
            )
        except BinanceAPIException as e:
            print(f"API Error: {e.status_code} {e.message}")
            return None
        except Exception as e:
            print(f"Order Error: {str(e)}")
            return None