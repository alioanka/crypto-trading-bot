import os
import time
import math
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Union
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
        self.historical_data = {}  # Stores market data

        # System startup
        self.print_account_status()
        self.alerts.bot_started("2.2", self.symbols)
        self.logger.log_trade(f"Bot initialized for {', '.join(self.symbols)}")
        self.load_historical_data()  # Load initial data

    def load_historical_data(self):
        """Load or fetch historical data for all symbols"""
        for symbol in self.symbols:
            data_file = f"data/historical/{symbol}.csv"
            
            if os.path.exists(data_file):
                # Load existing data
                self.historical_data[symbol] = pd.read_csv(data_file)
                print(f"📊 Loaded historical data for {symbol} ({len(self.historical_data[symbol])} records)")
            else:
                # Fetch new data
                data = self.fetch_market_data(symbol)
                if data:
                    df = pd.DataFrame(data)
                    df.to_csv(data_file, index=False)
                    self.historical_data[symbol] = df
                    print(f"📊 Fetched new historical data for {symbol}")

    def print_account_status(self):
        """Print balances and open positions on startup"""
        print("\n=== ACCOUNT STATUS ===")
        
        # Print balances (only non-zero)
        balances = self.exchange.get_account_balance()
        print("\n💰 Balances:")
        for asset, amount in balances.items():
            if amount > 0:
                print(f"{asset}: {amount:.8f}")
        
        # Print open positions
        print("\n📊 Open Positions:")
        for symbol in self.symbols:
            orders = self.exchange.get_open_orders(symbol)
            if orders:
                for order in orders:
                    print(f"{order['symbol']} {order['side']} {order['origQty']} @ {order['price']}")
            else:
                print(f"{symbol}: No open positions")
        
        print("=====================\n")

    def get_account_balance(self) -> float:
        """Get available USDT balance"""
        try:
            balances = self.exchange.get_account_balance()
            return balances.get('USDT', 0.0)
        except Exception as e:
            self.logger.log_trade(f"Balance check failed: {e}", "warning")
            return 1000.0  # Fallback value

    def fetch_market_data(self, symbol: str) -> Optional[List[Dict]]:
        """Get candle data from exchange with logging"""
        try:
            print(f"\n🔍 Fetching market data for {symbol}...")
            klines = self.exchange.client.get_klines(
                symbol=symbol,
                interval='1h',
                limit=100
            )
            
            data = [{
                'timestamp': k[0],
                'open': float(k[1]),
                'high': float(k[2]),
                'low': float(k[3]),
                'close': float(k[4]),
                'volume': float(k[5])
            } for k in klines]
            
            print(f"✅ Successfully fetched {len(data)} candles for {symbol}")
            return data
            
        except Exception as e:
            self.logger.log_trade(f"Data fetch failed for {symbol}: {str(e)}", "error")
            return None

    def update_market_data(self):
        """Update historical data for all symbols"""
        for symbol in self.symbols:
            new_data = self.fetch_market_data(symbol)
            if new_data:
                # Append new data
                df = pd.DataFrame(new_data)
                data_file = f"data/historical/{symbol}.csv"
                
                if os.path.exists(data_file):
                    existing = pd.read_csv(data_file)
                    updated = pd.concat([existing, df]).drop_duplicates('timestamp')
                    updated.to_csv(data_file, index=False)
                else:
                    df.to_csv(data_file, index=False)
                
                self.historical_data[symbol] = df.tail(100)  # Keep last 100 candles

    def calculate_position_size(self, symbol: str, price: float) -> float:
        """Calculate valid position size with precision"""
        try:
            balance = self.get_account_balance()
            risk_amount = balance * float(Config.RISK_PER_TRADE)
            raw_quantity = risk_amount / price
            
            rules = self.exchange._get_filters(symbol)
            if not rules:
                self.logger.log_trade(f"Could not get trading rules for {symbol}", "error")
                return 0.0
                
            precision = int(round(-math.log(rules['step_size'], 10)))
            quantity = round(raw_quantity, precision)
            
            if (quantity >= rules['min_qty'] and 
                quantity * price >= rules['min_notional']):
                return quantity
                
            self.logger.log_trade(
                f"Quantity {quantity} failed validation for {symbol} "
                f"(Min Qty: {rules['min_qty']}, Min Notional: {rules['min_notional']})",
                "warning"
            )
            return 0.0
        except Exception as e:
            self.logger.log_trade(f"Size calculation error: {e}", "error")
            return 0.0

    def execute_trade(self, symbol: str, signal: str) -> bool:
        """Full trade execution pipeline with logging"""
        try:
            print(f"\n⚡ Checking {symbol} for {signal} opportunities...")
            price = self.exchange.get_price(symbol)
            if not price:
                print("⚠️ Could not get current price")
                return False

            quantity = self.calculate_position_size(symbol, price)
            if quantity <= 0:
                print("⚠️ Invalid position size")
                return False

            print(f"💡 Attempting {signal} order for {quantity} {symbol} at ~${price:.2f}")
            order = self.exchange.execute_order(symbol, signal, quantity)
            
            if not order:
                print("❌ Order failed")
                return False

            print(f"✅ Order executed: {order['side']} {order['executedQty']} {order['symbol']} @ ${order['fills'][0]['price']}")
            self.alerts.trade_executed(symbol, signal, price, quantity)
            
            trade_record = {
                'symbol': symbol,
                'side': signal,
                'price': price,
                'quantity': quantity,
                'timestamp': datetime.now().isoformat()
            }
            self.backup.save_trade(trade_record)
            return True

        except Exception as e:
            print(f"❌ Trade failed: {str(e)}")
            self.logger.log_trade(f"Trade failed for {symbol}: {str(e)}", "error")
            return False

    def run_strategy(self, symbol: str):
        """Run trading strategy for one symbol"""
        try:
            print(f"\n🔎 Analyzing {symbol}...")
            data = self.historical_data.get(symbol)
            if data is None or len(data) < 50:  # Minimum data points
                print(f"⚠️ Insufficient data for {symbol}")
                return

            signal = self.strategy.generate_signal(data.to_dict('records'))
            if signal:
                print(f"🎯 {symbol} {signal} signal detected!")
                self.execute_trade(symbol, signal)
            else:
                print(f"⏳ No trading signal for {symbol}")

        except Exception as e:
            print(f"❌ Strategy error for {symbol}: {str(e)}")
            self.logger.log_trade(f"Strategy error for {symbol}: {str(e)}", "error")

    def run(self):
        """Main trading loop with activity logging"""
        try:
            print("\n🚀 Starting trading loop...")
            while True:
                cycle_start = time.time()
                
                # 1. Update market data
                self.update_market_data()
                
                # 2. Run strategies
                for symbol in self.symbols:
                    self.run_strategy(symbol)
                
                # 3. Wait for next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(1, self.update_interval - elapsed)
                print(f"\n🔄 Cycle completed in {elapsed:.1f}s. Sleeping for {sleep_time:.1f}s...")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n🛑 Received shutdown signal...")
            self.alerts.bot_stopped("Manual shutdown")
            self.logger.log_trade("Bot stopped by user")
        except Exception as e:
            print(f"\n💥 Fatal error: {str(e)}")
            self.logger.log_trade(f"Fatal error: {str(e)}", "critical")
            raise

if __name__ == "__main__":
    if not all([Config.BINANCE_API_KEY, Config.BINANCE_API_SECRET]):
        raise ValueError("Missing Binance API credentials in .env")

    bot = TradingBot()
    bot.run()