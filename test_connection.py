from core.exchange import BinanceAPI
from utils.config import Config

print("Testing Binance connection...")
api = BinanceAPI()
price = api.get_price("BTCUSDT")
print(f"Current BTC price: {price}")