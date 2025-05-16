from main import TradingBot
from core.exchange import BinanceAPI
import random

class PaperTradingBot(TradingBot):
    def __init__(self):
        super().__init__()
        self.balance = 1000  # Starting balance
        self.positions = {}
        
    def simulate_market_data(self, symbol):
        """Generate fake market data for testing"""
        last_price = random.uniform(25000, 35000) if "BTC" in symbol else random.uniform(1000, 2000)
        return {
            'open': last_price,
            'high': last_price * 1.01,
            'low': last_price * 0.99,
            'close': last_price * (1 + random.uniform(-0.005, 0.005)),
            'volume': random.uniform(100, 1000)
        }
        
    def execute_order(self, symbol, side, quantity):
        price = self.simulate_market_data(symbol)['close']
        value = quantity * price
        
        if side == "BUY":
            self.balance -= value
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            self.balance += value
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity
            
        print(f"[PAPER] {side} {quantity:.4f} {symbol} at ${price:.2f}")
        return {'price': price, 'quantity': quantity}

if __name__ == "__main__":
    bot = PaperTradingBot()
    bot.run()