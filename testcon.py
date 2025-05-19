import time
import logging
from core.exchange import BinanceAPI
from utils.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_connection():
    print("Testing Binance API connection...")
    
    exchange = BinanceAPI(Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET)
    test_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT"]
    
    for symbol in test_symbols:
        print(f"\nTesting {symbol}:")
        
        # Test ticker
        try:
            ticker = exchange.get_ticker(symbol)
            print(f"  Price: {ticker['lastPrice']}")
            print(f"  24h Vol: ${float(ticker['quoteVolume'])/1e6:.2f}M")
        except Exception as e:
            print(f"  ❌ Ticker failed: {str(e)}")
        
        # Test market info
        try:
            market_info = exchange.get_market_info(symbol)
            print("  Market Info:")
            print(f"  - Min Qty: {market_info['minQty']}")
            print(f"  - Step Size: {market_info['stepSize']}")
            print(f"  - Min Notional: ${market_info['minNotional']:.2f}")
        except Exception as e:
            print(f"  ❌ Market info failed: {str(e)}")
        
        # Test klines
        try:
            klines = exchange.get_klines(symbol, "1m")
            print(f"  Got {len(klines)} candles")
        except Exception as e:
            print(f"  ❌ Klines failed: {str(e)}")
    
    print("\n✅ Test completed")

if __name__ == "__main__":
    try:
        test_connection()
    except Exception as e:
        logger.error(f"❌ Critical test failure: {e}")
    finally:
        time.sleep(1)