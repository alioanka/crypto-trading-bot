from binance.client import Client
from binance.exceptions import BinanceAPIException
from utils.config import Config
import time

class BinanceAPI:
    def __init__(self):
        self.client = Client(
            api_key=Config.BINANCE_API_KEY,
            api_secret=Config.BINANCE_API_SECRET
        )
        self.retry_delay = 5  # seconds
        
    def get_price(self, symbol):
        """Get current market price with retry logic"""
        for _ in range(3):
            try:
                return float(self.client.get_symbol_ticker(symbol=symbol)['price'])
            except BinanceAPIException as e:
                print(f"Price fetch error: {e}. Retrying...")
                time.sleep(self.retry_delay)
        return None
        
    def execute_order(self, symbol, side, quantity):
        """Place market order with error handling"""
        try:
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type=Client.ORDER_TYPE_MARKET,
                quantity=round(quantity, 6)
            )
            return order
        except BinanceAPIException as e:
            print(f"Order failed: {e}")
            return None