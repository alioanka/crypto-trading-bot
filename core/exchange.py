import math
import time
from decimal import Decimal, getcontext
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union, Tuple
from utils.config import Config

class BinanceAPI:
    STABLE_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT',
        'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT',
        'MATICUSDT', 'LTCUSDT'
    ]

    # Default values for major pairs
    DEFAULT_VALUES = {
        'BTCUSDT': {'minQty': 0.00001, 'stepSize': 0.00001, 'minNotional': 10},
        'ETHUSDT': {'minQty': 0.001, 'stepSize': 0.001, 'minNotional': 10},
        'BNBUSDT': {'minQty': 0.01, 'stepSize': 0.01, 'minNotional': 10},
        'XRPUSDT': {'minQty': 1, 'stepSize': 1, 'minNotional': 10},
        'SOLUSDT': {'minQty': 0.01, 'stepSize': 0.01, 'minNotional': 10},
        'ADAUSDT': {'minQty': 1, 'stepSize': 1, 'minNotional': 10},
        'DOGEUSDT': {'minQty': 1, 'stepSize': 1, 'minNotional': 10},
        'DOTUSDT': {'minQty': 0.1, 'stepSize': 0.1, 'minNotional': 10},
        'MATICUSDT': {'minQty': 1, 'stepSize': 1, 'minNotional': 10},
        'LTCUSDT': {'minQty': 0.01, 'stepSize': 0.01, 'minNotional': 10}
    }

    def __init__(self, api_key: str, api_secret: str):
        getcontext().prec = 8
        self.client = Client(
            api_key=api_key,
            api_secret=api_secret,
            testnet=False
        )
        self.retry_delay = 5
        self.symbol_rules = {}
        self.market_info = {}

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Get ticker data with retries"""
        for _ in range(3):
            try:
                return self.client.get_ticker(symbol=symbol)
            except BinanceAPIException as e:
                print(f"Ticker error for {symbol}: {e}")
                time.sleep(self.retry_delay)
            except Exception as e:
                print(f"Unexpected ticker error: {e}")
                time.sleep(self.retry_delay)
        return None

    def get_market_info(self, symbol: str) -> Dict:
        """Get market information with ultimate fallback"""
        if symbol not in self.market_info:
            try:
                info = self.client.get_symbol_info(symbol)
                if info:
                    filters = {f['filterType']: f for f in info.get('filters', [])}
                    self.market_info[symbol] = {
                        'minQty': float(filters.get('LOT_SIZE', {}).get('minQty', 
                                   self.DEFAULT_VALUES.get(symbol, {}).get('minQty', 0.001))),
                        'stepSize': float(filters.get('LOT_SIZE', {}).get('stepSize', 
                                    self.DEFAULT_VALUES.get(symbol, {}).get('stepSize', 0.001))),
                        'minNotional': float(filters.get('MIN_NOTIONAL', {}).get('minNotional', 
                                       Config.MIN_NOTIONAL)),
                        'baseAsset': info.get('baseAsset', symbol.replace('USDT', '')),
                        'quoteAsset': info.get('quoteAsset', 'USDT')
                    }
                    return self.market_info[symbol]
            except Exception as e:
                print(f"API error for {symbol}, using defaults: {str(e)}")

            # Fallback to defaults
            self.market_info[symbol] = self.DEFAULT_VALUES.get(symbol, {
                'minQty': 0.001,
                'stepSize': 0.001,
                'minNotional': float(Config.MIN_NOTIONAL),
                'baseAsset': symbol.replace('USDT', ''),
                'quoteAsset': 'USDT'
            })

        return self.market_info[symbol]

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
            except Exception as e:
                print(f"Unexpected balance error: {e}")
                time.sleep(self.retry_delay)
        return {}

    def get_open_positions(self) -> Dict[str, Dict]:
        """Get current open positions with fallbacks"""
        positions = {}
        try:
            balances = self.get_account_balance()
            for symbol in self.STABLE_PAIRS:
                try:
                    market_info = self.get_market_info(symbol)
                    base_asset = market_info['baseAsset']
                    if base_asset in balances and balances[base_asset] > 0:
                        positions[symbol] = {
                            'quantity': balances[base_asset],
                            'entry_price': self.get_average_entry_price(symbol),
                            'side': 'BUY'
                        }
                except Exception as e:
                    print(f"Error processing {symbol} position: {e}")
        except Exception as e:
            print(f"Error getting positions: {e}")
        return positions

    def get_average_entry_price(self, symbol: str) -> float:
        """Calculate average entry price with error handling"""
        try:
            trades = self.client.get_my_trades(symbol=symbol, limit=10)
            buy_trades = [t for t in trades if t['isBuyer']]
            if not buy_trades:
                return 0.0
                
            total_cost = sum(float(t['quoteQty']) for t in buy_trades)
            total_amount = sum(float(t['qty']) for t in buy_trades)
            return total_cost / total_amount
        except Exception as e:
            print(f"Error calculating entry price: {e}")
            return 0.0

    def get_klines(self, symbol: str, interval: str = None) -> Optional[List[Dict]]:
        """Get candle data with interval validation"""
        valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        interval = interval or Config.CANDLE_INTERVAL
        
        if interval not in valid_intervals:
            print(f"⚠️ Invalid interval {interval}. Using 1h")
            interval = '1h'

        for _ in range(3):
            try:
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=100
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
                print(f"Klines error for {symbol}: {e}")
                time.sleep(self.retry_delay)
        return None

    def execute_order(self, symbol: str, side: str, quantity: float) -> Union[Dict, None]:
        """Safe order execution with full validation"""
        try:
            market_info = self.get_market_info(symbol)
            price = float(self.client.get_ticker(symbol=symbol)['lastPrice'])
            
            if not price or price <= 0:
                return None

            # Calculate precision
            step_size = Decimal(str(market_info['stepSize']))
            precision = abs(step_size.as_tuple().exponent)
            
            # Validate quantity
            quantity_dec = Decimal(str(quantity)).quantize(Decimal(10) ** -precision)
            valid_quantity = float(quantity_dec)
            notional = valid_quantity * price

            if valid_quantity < market_info['minQty']:
                print(f"❌ Quantity below minimum for {symbol}: {valid_quantity} < {market_info['minQty']}")
                return None
                
            if notional < market_info['minNotional']:
                print(f"❌ Notional below minimum for {symbol}: ${notional:.2f} < ${market_info['minNotional']:.2f}")
                return None

            return self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=valid_quantity
            )
        except BinanceAPIException as e:
            print(f"API Error: {e.status_code} {e.message}")
            return None
        except Exception as e:
            print(f"Order Error: {str(e)}")
            return None