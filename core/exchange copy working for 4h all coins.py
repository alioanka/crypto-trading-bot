import math
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union

class BinanceAPI:
    # Approved stablecoin pairs with USDT
    STABLE_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT',
        'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT',
        'MATICUSDT', 'LTCUSDT'
    ]

    def __init__(self, api_key: str, api_secret: str):
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False
        )
        self.retry_delay = 5

    def get_account_balance(self) -> Dict[str, float]:
        """Get all non-zero balances with retries"""
        for _ in range(3):
            try:
                account = self.client.get_account()
                return {
                    asset['asset']: float(asset['free'])
                    for asset in account['balances']
                    if float(asset['free']) > 0.0001
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
            if abs(price_change) > 15:
                print(f"⚠️ High volatility: {symbol} ({price_change}%)")
                return None
            return float(ticker['lastPrice'])
        except Exception as e:
            print(f"Price error: {e}")
            return None

    def get_klines(self, symbol: str, interval: str = '4h', limit: int = 100) -> Optional[List[Dict]]:
        """Get candle data with stability checks"""
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
        """Safe order execution with validation"""
        try:
            price = self.get_price(symbol)
            if not price or quantity <= 0:
                return None

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