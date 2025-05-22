import math
import time
import logging
from decimal import Decimal, getcontext, ROUND_DOWN
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, List, Union, Tuple
from utils.config import Config
from utils.alerts import AlertSystem

logger = logging.getLogger(__name__)
alerts = AlertSystem()

class BinanceAPI:
    STABLE_PAIRS = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT',
        'SOLUSDT', 'ADAUSDT', 'DOGEUSDT', 'DOTUSDT',
        'AVAXUSDT', 'LTCUSDT'
    ]

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
        logger.info("BinanceAPI initialized")

# In your exchange.py file, update get_price method:
    def get_price(self, symbol: str) -> Optional[float]:
        """Get current price with better error handling"""
        try:
            if symbol == 'MATICUSDT':  # Handle old symbol
                symbol = 'AVAXUSDT'  # Or whatever it was renamed to
            
            ticker = self.client.get_symbol_ticker(symbol=symbol)
            return float(ticker['price'])
        except Exception as e:
            logger.error(f"Price check failed for {symbol}: {str(e)}")
            # Try alternative endpoints if available
            try:
                klines = self.client.get_klines(symbol=symbol, interval='1m', limit=1)
                if klines:
                    return float(klines[0][4])  # Use close price
            except:
                pass
            return None

    def get_market_info(self, symbol: str) -> Dict:
        """Get market information with detailed logging"""
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
                    logger.info(f"Loaded market info for {symbol}: {self.market_info[symbol]}")
                    return self.market_info[symbol]
            except Exception as e:
                error_msg = f"API error for {symbol}, using defaults: {str(e)}"
                logger.warning(error_msg)
                alerts.error_alert("MARKET_INFO", error_msg, symbol)

            # Fallback to defaults
            self.market_info[symbol] = self.DEFAULT_VALUES.get(symbol, {
                'minQty': 0.001,
                'stepSize': 0.001,
                'minNotional': float(Config.MIN_NOTIONAL),
                'baseAsset': symbol.replace('USDT', ''),
                'quoteAsset': 'USDT'
            })
            logger.warning(f"Using fallback market info for {symbol}")

        return self.market_info[symbol]

    def get_account_balance(self) -> Dict[str, float]:
        """Get all non-zero balances with retries"""
        for attempt in range(3):
            try:
                account = self.client.get_account()
                balances = {
                    asset['asset']: float(asset['free'])
                    for asset in account['balances']
                    if float(asset['free']) > 0.0001
                }
                logger.debug(f"Account balances: {balances}")
                return balances
            except BinanceAPIException as e:
                error_msg = f"Balance error (attempt {attempt+1}): {e}"
                logger.error(error_msg)
                alerts.error_alert("BALANCE_FETCH", error_msg)
                time.sleep(self.retry_delay)
            except Exception as e:
                error_msg = f"Unexpected balance error: {e}"
                logger.error(error_msg)
                alerts.error_alert("BALANCE_FETCH", error_msg)
                time.sleep(self.retry_delay)
        return {}

    def get_open_positions(self) -> Dict[str, Dict]:
        """Get current open positions with fallbacks"""
        positions = {}
        try:
            # First check actual orders
            open_orders = self.client.get_open_orders()
            for order in open_orders:
                if order['side'] == 'BUY' and order['status'] == 'FILLED':
                    symbol = order['symbol']
                    positions[symbol] = {
                        'quantity': float(order['executedQty']),
                        'entry_price': float(order['price']),
                        'side': 'BUY'
                    }
            
            # Fallback to balance check if no orders found
            if not positions:
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
                        logger.error(f"Error processing {symbol} position: {e}")
            
            logger.info(f"Found {len(positions)} open positions")
            return positions
            
        except Exception as e:
            logger.error(f"Error getting positions: {e}")
            return {}

    def get_average_entry_price(self, symbol: str) -> float:
        """Calculate average entry price with error handling"""
        try:
            trades = self.client.get_my_trades(symbol=symbol, limit=10)
            buy_trades = [t for t in trades if t['isBuyer']]
            if not buy_trades:
                logger.warning(f"No buy trades found for {symbol}")
                return 0.0
                
            total_cost = sum(float(t['quoteQty']) for t in buy_trades)
            total_amount = sum(float(t['qty']) for t in buy_trades)
            avg_price = total_cost / total_amount
            logger.debug(f"Calculated avg entry price for {symbol}: {avg_price}")
            return avg_price
        except Exception as e:
            error_msg = f"Error calculating entry price: {e}"
            logger.error(error_msg)
            alerts.error_alert("PRICE_CALCULATION", error_msg, symbol)
            return 0.0

    def get_klines(self, symbol: str, interval: str = None) -> Optional[List[Dict]]:
        """Get candle data with interval validation"""
        valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        interval = interval or Config.CANDLE_INTERVAL
        
        if interval not in valid_intervals:
            error_msg = f"Invalid interval {interval}. Using 1h"
            logger.warning(error_msg)
            alerts.error_alert("CONFIG_ERROR", error_msg)
            interval = '1h'

        for attempt in range(3):
            try:
                klines = self.client.get_klines(
                    symbol=symbol,
                    interval=interval,
                    limit=100
                )
                formatted = [{
                    'time': k[0],
                    'open': float(k[1]),
                    'high': float(k[2]),
                    'low': float(k[3]),
                    'close': float(k[4]),
                    'volume': float(k[5])
                } for k in klines]
                logger.debug(f"Retrieved {len(formatted)} {interval} candles for {symbol}")
                return formatted
            except Exception as e:
                error_msg = f"Klines error for {symbol} (attempt {attempt+1}): {e}"
                logger.error(error_msg)
                if attempt == 2:
                    alerts.error_alert("KLINES_ERROR", error_msg, symbol)
                time.sleep(self.retry_delay)
        return None

    def execute_order(self, symbol: str, side: str, quantity: float) -> Union[Dict, None]:
        """Safe order execution with comprehensive logging"""
        try:
            market_info = self.get_market_info(symbol)
            price = self.get_price(symbol)
            
            if not price or price <= 0:
                error_msg = f"Invalid price for {symbol}: {price}"
                logger.error(error_msg)
                alerts.error_alert("ORDER_ERROR", error_msg, symbol)
                return None
            
                # Add precision adjustment for all quantities
            market_info = self.get_market_info(symbol)
            step_size = Decimal(str(market_info['stepSize']))
            precision = abs(step_size.as_tuple().exponent)
            quantity = float(Decimal(str(quantity)).quantize(
                Decimal(10) ** -precision, 
                rounding=ROUND_DOWN
                ))

            # Calculate precision
            step_size = Decimal(str(market_info['stepSize']))
            precision = abs(step_size.as_tuple().exponent)
            
            # Validate quantity
            quantity_dec = Decimal(str(quantity)).quantize(Decimal(10) ** -precision)
            valid_quantity = float(quantity_dec)
            notional = valid_quantity * price

            logger.debug(f"Order validation - Symbol: {symbol}, Side: {side}, "
                        f"Qty: {valid_quantity}, Price: {price}, Notional: {notional}")

            if valid_quantity < market_info['minQty']:
                error_msg = f"Quantity below minimum for {symbol}: {valid_quantity} < {market_info['minQty']}"
                logger.error(error_msg)
                alerts.error_alert("ORDER_ERROR", error_msg, symbol)
                return None
                
            if notional < market_info['minNotional']:
                error_msg = f"Notional below minimum for {symbol}: ${notional:.2f} < ${market_info['minNotional']:.2f}"
                logger.error(error_msg)
                alerts.error_alert("ORDER_ERROR", error_msg, symbol)
                return None

            logger.info(f"Attempting {side} order for {symbol}: {valid_quantity} @ ~{price}")
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=valid_quantity
            )
            
            logger.info(f"Order executed: {order}")
            alerts.trade_executed(symbol, side, price, valid_quantity)
            return order
            
        except BinanceAPIException as e:
            error_msg = f"API Error: {e.status_code} {e.message}"
            logger.error(error_msg)
            alerts.error_alert("API_ERROR", error_msg, symbol)
            return None
        except Exception as e:
            error_msg = f"Order Error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            alerts.error_alert("ORDER_ERROR", error_msg, symbol)
            return None