import random
import time
import logging
from datetime import datetime
from main import TradingBot
from utils.logger import TradeLogger

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PaperTradingBot(TradingBot):
    def __init__(self):
        # Initialize with dummy values
        self.balance = 1000.0  # Starting balance
        self.positions = {}
        self.logger = TradeLogger()
        self.logger.log_trade("Paper trading initialized with $1000 balance")
        logger.info("Paper trading bot initialized")

    def simulate_market_data(self, symbol):
        """Generate realistic fake market data"""
        base_price = random.uniform(25000, 35000) if "BTC" in symbol else random.uniform(1000, 2000)
        return {
            'open': base_price,
            'high': base_price * 1.02,
            'low': base_price * 0.98,
            'close': base_price * (1 + random.uniform(-0.01, 0.01)),
            'volume': random.uniform(100, 1000),
            'timestamp': datetime.now().isoformat()
        }

    def execute_order(self, symbol, side, quantity):
        """Simulate order execution"""
        data = self.simulate_market_data(symbol)
        price = data['close']
        value = quantity * price

        if side == "BUY":
            self.balance -= value
            self.positions[symbol] = self.positions.get(symbol, 0) + quantity
        else:
            self.balance += value
            self.positions[symbol] = self.positions.get(symbol, 0) - quantity

        self.logger.log_trade(
            f"[PAPER] {side} {quantity:.4f} {symbol} at ${price:.2f} | "
            f"Balance: ${self.balance:.2f}"
        )
        logger.info(f"Paper trade executed: {side} {quantity} {symbol} @ {price}")
        return {'price': price, 'quantity': quantity}

    def run(self):
        """Run continuous paper trading simulation"""
        self.logger.log_trade("Starting paper trading session")
        logger.info("Starting paper trading simulation")
        
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        
        while True:
            try:
                # Randomly select a symbol and action
                symbol = random.choice(symbols)
                action = random.choice(["BUY", "SELL"])
                quantity = round(random.uniform(0.001, 0.1), 6)
                
                # Execute simulated trade
                self.execute_order(symbol, action, quantity)
                
                # Wait 5-15 seconds between trades
                time.sleep(random.uniform(5, 15))
                
            except KeyboardInterrupt:
                self.logger.log_trade("Paper trading session ended")
                logger.info("Paper trading session ended")
                break

if __name__ == "__main__":
    bot = PaperTradingBot()
    bot.run()