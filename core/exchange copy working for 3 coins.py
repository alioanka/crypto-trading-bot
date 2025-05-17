import math
import time
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, Union, List
from utils.config import Config


class BinanceAPI:
    def __init__(self):
        self.client = Client(
            api_key=Config.BINANCE_API_KEY,
            api_secret=Config.BINANCE_API_SECRET,
            testnet=False
        )
        self.retry_delay = 5

    def get_account_balance(self) -> Dict[str, float]:
        """Get all account balances with retries"""
        for _ in range(3):
            try:
                account = self.client.get_account()
                balances = {
                    asset['asset']: float(asset['free'])
                    for asset in account['balances']
                    if float(asset['free']) > 0
                }
                return balances
            except BinanceAPIException as e:
                print(f"Balance fetch error: {e}. Retrying...")
                time.sleep(self.retry_delay)
        return {}

    def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Get all open orders or for specific symbol"""
        try:
            if symbol:
                return self.client.get_open_orders(symbol=symbol)
            return self.client.get_open_orders()
        except BinanceAPIException as e:
            print(f"Open orders error: {e}")
            return []

    def get_price(self, symbol: str) -> Optional[float]:
        """Get current market price with retries"""
        for _ in range(3):
            try:
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                return float(ticker['price'])
            except (BinanceAPIException, KeyError, ValueError) as e:
                print(f"Price fetch error: {e}. Retrying...")
                time.sleep(self.retry_delay)
        return None

    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """Get trading rules for a symbol with retries"""
        for _ in range(3):
            try:
                return self.client.get_symbol_info(symbol)
            except BinanceAPIException as e:
                print(f"Symbol info error: {e}. Retrying...")
                time.sleep(self.retry_delay)
        return None

    def _get_default_filters(self, symbol: str) -> Dict[str, float]:
        """Fallback defaults for major symbols"""
        defaults = {
            'BTCUSDT': {'step_size': 0.000001, 'min_qty': 0.00001, 'min_notional': 10.0},
            'ETHUSDT': {'step_size': 0.0001, 'min_qty': 0.001, 'min_notional': 10.0},
            'SOLUSDT': {'step_size': 0.01, 'min_qty': 0.1, 'min_notional': 10.0}
        }
        return defaults.get(symbol, {'step_size': 0.0001, 'min_qty': 0.001, 'min_notional': 10.0})

    def _get_filters(self, symbol: str) -> Dict[str, float]:
        """Enhanced trading rule fetcher with fallback defaults"""
        try:
            info = self.get_symbol_info(symbol)
            if not info:
                print(f"⚠️ No symbol info for {symbol}. Using defaults.")
                return self._get_default_filters(symbol)

            filters = info.get('filters', [])
            if not filters:
                print(f"⚠️ No filters for {symbol}. Using defaults.")
                return self._get_default_filters(symbol)

            lot_size = next((f for f in filters if f.get('filterType') == 'LOT_SIZE'), None)
            min_notional = next((f for f in filters if f.get('filterType') == 'MIN_NOTIONAL'), None)

            if not lot_size or not min_notional:
                print(f"⚠️ Missing required filters for {symbol}. Using defaults.")
                return self._get_default_filters(symbol)

            return {
                'step_size': float(lot_size['stepSize']),
                'min_qty': float(lot_size['minQty']),
                'min_notional': float(min_notional['minNotional'])
            }
        except Exception as e:
            print(f"❌ Critical error processing filters for {symbol}: {str(e)}. Using defaults.")
            return self._get_default_filters(symbol)

    def execute_order(self, symbol: str, side: str, quantity: float) -> Union[Dict, None]:
        """Safe order execution with full validation"""
        try:
            rules = self._get_filters(symbol)
            precision = int(round(-math.log(rules['step_size'], 10)))
            valid_quantity = round(quantity, precision)
            
            if valid_quantity < rules['min_qty']:
                raise ValueError(f"Quantity too small. Min: {rules['min_qty']}, Got: {valid_quantity}")

            price = self.get_price(symbol)
            if not price:
                raise ValueError("Could not fetch current price")
                
            notional = valid_quantity * price
            if notional < rules['min_notional']:
                raise ValueError(f"Notional too small. Min: {rules['min_notional']}, Got: {notional:.2f}")

            return self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=valid_quantity
            )
            
        except BinanceAPIException as e:
            print(f"Binance API Error: {e.status_code} {e.message}")
            return None
        except Exception as e:
            print(f"Order Execution Error: {str(e)}")
            return None