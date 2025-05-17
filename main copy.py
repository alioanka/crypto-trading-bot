import os
import time
import math
from datetime import datetime
from core.strategies import SmartTrendStrategy
from core.risk_engine import RiskManager
from core.exchange import BinanceAPI
from utils.alerts import AlertSystem
from utils.backup_manager import BackupManager
from utils.logger import TradeLogger
from utils.config import Config

class TradingBot:
    def __init__(self):
        # Initialize directories
        os.makedirs("data/historical", exist_ok=True)
        os.makedirs("data/logs", exist_ok=True)

        # Core components
        self.strategy = SmartTrendStrategy()
        self.risk = RiskManager(max_drawdown=float(Config.MAX_DRAWDOWN))
        self.exchange = BinanceAPI()
        self.alerts = AlertSystem()
        self.backup = BackupManager()
        self.logger = TradeLogger()

        # Trading parameters
        self.symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.update_interval = 60  # seconds

        # System startup
        self.alerts.bot_started("2.0", self.symbols)
        self.logger.log_trade(f"Bot initialized for {', '.join(self.symbols)}")

    def get_account_balance(self):
        """Get available USDT balance"""
        try:
            balance = self.exchange.client.get_asset_balance(asset='USDT')
            return float(balance['free'])
        except Exception as e:
            self.logger.log_trade(f"Balance check failed: {e}", "warning")
            return 1000  # Fallback value

    def fetch_market_data(self, symbol):
        """Get candle data from exchange"""
        try:
            klines = self.exchange.client.get_klines(
                symbol=symbol,
                interval='1h',  # 1-hour candles
                limit=100       # Last 100 candles
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
            self.logger.log_trade(f"Data fetch failed for {symbol}: {str(e)}", "error")
            return None

    def calculate_position_size(self, symbol, price):
        """Calculate valid position size with precision"""
        try:
            balance = self.get_account_balance()
            risk_amount = balance * float(Config.RISK_PER_TRADE)
            raw_quantity = risk_amount / price
            
            rules = self.exchange._get_filters(symbol)
            if not rules:
                self.logger.log_trade(f"Could not get trading rules for {symbol}", "error")
                return 0
                
            precision = int(round(-math.log(rules['step_size'], 10)))
            quantity = round(raw_quantity, precision)
            
            # Validate against minimums
            if (quantity >= rules['min_qty'] and 
                quantity * price >= rules['min_notional']):
                return quantity
                
            self.logger.log_trade(
                f"Quantity {quantity} failed validation for {symbol} "
                f"(Min Qty: {rules['min_qty']}, Min Notional: {rules['min_notional']})",
                "warning"
            )
            return 0
        except Exception as e:
            self.logger.log_trade(f"Size calculation error: {e}", "error")
            return 0

    def execute_trade(self, symbol, signal):
        """Full trade execution pipeline"""
        try:
            # 1. Get current price
            price = self.exchange.get_price(symbol)
            if not price:
                return False

            # 2. Calculate position size
            quantity = self.calculate_position_size(symbol, price)
            if quantity <= 0:
                return False

            # 3. Execute order
            order = self.exchange.execute_order(symbol, signal, quantity)
            if not order:
                return False

            # 4. Record and notify
            self.alerts.trade_executed(symbol, signal, price, quantity)
            self.backup.save_trade({
                'symbol': symbol,
                'side': signal,
                'price': price,
                'quantity': quantity,
                'timestamp': datetime.now().isoformat()
            })
            return True

        except Exception as e:
            self.logger.log_trade(f"Trade failed for {symbol}: {str(e)}", "error")
            return False

    def run_strategy(self, symbol):
        """Run trading strategy for one symbol"""
        data = self.fetch_market_data(symbol)
        if not data:
            return

        signal = self.strategy.generate_signal(data)
        if signal:
            self.execute_trade(symbol, signal)

    def run(self):
        """Main trading loop"""
        try:
            while True:
                start_time = time.time()
                
                # Run strategies for all symbols
                for symbol in self.symbols:
                    self.run_strategy(symbol)

                # Sleep for remaining interval time
                elapsed = time.time() - start_time
                sleep_time = max(1, self.update_interval - elapsed)
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            self.alerts.bot_stopped("Manual shutdown")
            self.logger.log_trade("Bot stopped by user")
        except Exception as e:
            self.logger.log_trade(f"Fatal error: {str(e)}", "critical")
            raise

if __name__ == "__main__":
    # Verify environment
    if not all([Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET]):
        raise ValueError("Missing Binance API credentials in .env")

    # Start bot
    bot = TradingBot()
    bot.run()