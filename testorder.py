import time
import math
import logging
from datetime import datetime
from core.exchange import BinanceAPI
from utils.config import Config
from utils.alerts import AlertSystem
from utils.logger import TradeLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_order_placement():
    """Force test order placement regardless of market conditions"""
    print("\n=== ORDER TESTING MODE ===")
    print("WARNING: This will attempt real trades with your funds!")
    
    exchange = BinanceAPI(Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET)
    alerts = AlertSystem()
    trade_logger = TradeLogger()
    symbols = exchange.STABLE_PAIRS
    
    # Binance trading fee (0.1% for regular accounts)
    TRADING_FEE = 0.001
    
    while True:
        try:
            print("\nAvailable pairs:", ", ".join(symbols))
            symbol = input("Enter symbol to test (or 'quit'): ").upper()
            
            if symbol == 'QUIT':
                break
                
            if symbol not in symbols:
                print("Invalid symbol. Please choose from the list.")
                continue
                
            side = input("Enter side (BUY/SELL): ").upper()
            if side not in ['BUY', 'SELL']:
                print("Invalid side. Must be BUY or SELL.")
                continue
                
            # Get current price and market info
            price = exchange.get_price(symbol)
            if not price:
                print("Failed to get price. Try again.")
                continue
                
            market_info = exchange.get_market_info(symbol)
            min_qty = market_info['minQty']
            step_size = market_info['stepSize']
            base_asset = market_info['baseAsset']
            
            print(f"\nCurrent {symbol} price: {price}")
            
            if side == 'BUY':
                # Calculate reasonable test quantity for BUY
                test_qty = max(min_qty * 2, (10 / price))  # Enough to meet min notional
            else:
                # For SELL, get actual available balance
                balances = exchange.get_account_balance()
                available = balances.get(base_asset, 0.0)
                
                if available <= 0:
                    print(f"\n❌ No {base_asset} available to sell (balance: {available})")
                    continue
                    
                # Calculate maximum sellable quantity (accounting for fees)
                test_qty = available * (1 - TRADING_FEE)
                
                # Round DOWN to step size to ensure we don't exceed available balance
                precision = int(round(-math.log(step_size, 10)))
                test_qty = math.floor(test_qty * 10**precision) / 10**precision
                
                if test_qty < min_qty:
                    print(f"\n❌ Available quantity too small. Min: {min_qty}, Available: {test_qty}")
                    continue
                
                print(f"Available {base_asset} balance: {available}")
            
            print(f"Suggested test quantity: {test_qty}")
            custom_qty = input(f"Enter quantity (or press Enter for {test_qty}): ")
            
            quantity = float(custom_qty) if custom_qty else test_qty
            
            # Additional validation for manual quantity entry
            if side == 'SELL' and quantity > available:
                print(f"\n❌ Cannot sell more than available. Available: {available}, Attempted: {quantity}")
                continue
                
            # Round to step size again in case manual quantity was entered
            quantity = math.floor(quantity * 10**precision) / 10**precision
            
            # Final validation
            notional = quantity * price
            if quantity < min_qty:
                print(f"\n❌ Quantity below minimum. Min: {min_qty}, Attempted: {quantity}")
                continue
            if notional < market_info['minNotional']:
                print(f"\n❌ Notional value too small. Min: ${market_info['minNotional']:.2f}, Attempted: ${notional:.2f}")
                continue
            
            # Confirm order
            print(f"\n⚠️ WILL EXECUTE: {side} {quantity} {symbol} @ ~{price}")
            print(f"Estimated value: ${notional:.2f}")
            confirm = input("Confirm? (y/n): ").lower()
            
            if confirm != 'y':
                print("Order canceled")
                continue
                
            # Execute test order
            print("\nExecuting test order...")
            start_time = time.time()
            
            order = exchange.execute_order(symbol, side, quantity)
            
            if order:
                print(f"\n✅ Order successful!")
                print(f"ID: {order['orderId']}")
                print(f"Executed Qty: {order['executedQty']}")
                print(f"Avg Price: {order['fills'][0]['price']}")
                
                trade_logger.log_trade(
                    symbol=symbol,
                    side=side,
                    quantity=float(order['executedQty']),
                    price=float(order['fills'][0]['price']),
                    details="TEST ORDER"
                )
            else:
                print("\n❌ Order failed")
                
            print(f"Execution time: {time.time() - start_time:.2f}s")
            
        except ValueError as e:
            print(f"\n❌ Validation Error: {e}")
            trade_logger.log_error(
                event_type="TEST_ERROR",
                symbol=symbol,
                side=side,
                details=str(e)
            )
        except Exception as e:
            print(f"\n❌ Unexpected Error: {e}")
            trade_logger.log_error(
                event_type="TEST_ERROR",
                symbol=symbol,
                side=side,
                details=str(e)
            )
            continue
            
    print("\nTest mode exited")

if __name__ == "__main__":
    test_order_placement()