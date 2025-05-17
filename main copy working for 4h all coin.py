import os
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from core.exchange import BinanceAPI
from core.strategies import SmartTrendStrategy
from core.risk_engine import RiskManager
from utils.logger import TradeLogger
from utils.alerts import AlertSystem
from utils.backup_manager import BackupManager
from utils.config import Config

class TradingBot:
    def __init__(self):
        """Initialize all components in correct order"""
        # Setup directories
        os.makedirs("data/historical", exist_ok=True)
        os.makedirs("data/logs", exist_ok=True)

        # Core components (MUST be in this order)
        self.logger = TradeLogger()
        self.exchange = BinanceAPI(
            api_key=Config.BINANCE_API_KEY,
            api_secret=Config.BINANCE_API_SECRET
        )
        self.strategy = SmartTrendStrategy()
        self.risk = RiskManager(
            max_drawdown=float(Config.MAX_DRAWDOWN),
            max_daily_trades=int(Config.MAX_DAILY_TRADES)
        )
        self.alerts = AlertSystem()
        self.backup = BackupManager()

        # Trading parameters
        self.symbols = self._get_approved_symbols()
        self.candle_interval = Config.CANDLE_INTERVAL
        self.update_interval = self._get_update_interval()
        
        # System state
        self.last_trade_time = {}
        self.historical_data = {}
        self.account_balance = 0.0

        # Initialize
        self._print_welcome()
        self._load_all_historical_data()
        self._log_startup()

    def _get_approved_symbols(self) -> List[str]:
        """Filter symbols based on stability criteria"""
        approved = []
        for symbol in self.exchange.STABLE_PAIRS:
            if self._is_symbol_tradable(symbol):
                approved.append(symbol)
                print(f"✅ Approved: {symbol}")
            else:
                print(f"⏭️ Skipped: {symbol} (fails filters)")
        return approved

    def _is_symbol_tradable(self, symbol: str) -> bool:
        """Check if symbol meets trading criteria"""
        try:
            ticker = self.exchange.client.get_ticker(symbol=symbol)
            return (
                float(ticker['quoteVolume']) > 10_000_000 and  # $10M daily volume
                abs(float(ticker['priceChangePercent'])) < 15   # <15% daily change
            )
        except Exception as e:
            self.logger.log_trade(
                event_type="ERROR",
                details=f"Symbol check failed for {symbol}: {str(e)}"
            )
            return False

    def _get_update_interval(self) -> int:
        """Convert candle interval to seconds"""
        interval_map = {
            '1m': 60,
            '5m': 300,
            '15m': 900,
            '1h': 3600,
            '4h': 14400,
            '1d': 86400
        }
        return interval_map.get(self.candle_interval, 3600)  # Default 1h

    def _print_welcome(self):
        """Display startup banner"""
        print("\n" + "="*50)
        print(f"CRYPTO BOT v3.2 (Set-and-Forget Mode)")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50 + "\n")

    def _load_all_historical_data(self):
        """Load or download data for all symbols"""
        print("🔄 Loading historical data...")
        for symbol in self.symbols:
            self._load_historical_data(symbol)

    def _load_historical_data(self, symbol: str):
        """Load or fetch historical data for one symbol"""
        data_file = f"data/historical/{symbol}.csv"
        
        try:
            if os.path.exists(data_file):
                self.historical_data[symbol] = pd.read_csv(data_file)
                print(f"📊 Loaded {len(self.historical_data[symbol])} {self.candle_interval} candles for {symbol}")
            else:
                data = self.exchange.get_klines(symbol, self.candle_interval)
                if data:
                    df = pd.DataFrame(data)
                    df.to_csv(data_file, index=False)
                    self.historical_data[symbol] = df
                    print(f"📊 Downloaded {len(df)} candles for {symbol}")
        except Exception as e:
            self.logger.log_trade(
                event_type="ERROR",
                details=f"Failed to load data for {symbol}: {str(e)}"
            )

    def _log_startup(self):
        """Fixed startup logging with all required fields"""
        self.logger.log_trade(
            event_type="STARTUP",
            symbols=",".join(self.symbols),
            interval=self.candle_interval,
            details=f"Initialized with {len(self.symbols)} pairs"
        )
        self.alerts.bot_started("3.2-STABLE", self.symbols)

    def run(self):
        """Main trading loop"""
        print("\n🚀 Starting trading engine (Ctrl+C to exit)")
        try:
            while True:
                cycle_start = time.time()
                
                # Refresh account balance
                self.account_balance = self._get_usdt_balance()
                
                # Update market data
                self._update_market_data()
                
                # Execute strategies
                self._run_strategies()
                
                # Sleep until next cycle
                elapsed = time.time() - cycle_start
                sleep_time = max(5, self.update_interval - elapsed)
                print(f"\n⏳ Next update in {sleep_time:.1f}s...")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            print("\n🛑 Received shutdown signal...")
            self.alerts.bot_stopped("Manual shutdown")
            self.logger.log_trade(
                event_type="SHUTDOWN",
                details="Manual shutdown"
            )
        except Exception as e:
            self.logger.log_trade(
                event_type="CRASH",
                details=f"Fatal error: {str(e)}"
            )
            self.alerts.bot_stopped(f"Crash: {str(e)}")
            raise

    def _get_usdt_balance(self) -> float:
        """Get current USDT balance"""
        balances = self.exchange.get_account_balance()
        usdt = balances.get('USDT', 0.0)
        print(f"\n💵 Account Balance: {usdt:.2f} USDT")
        return usdt

    def _update_market_data(self):
        """Refresh market data for all symbols"""
        print("\n🔄 Updating market data...")
        for symbol in self.symbols:
            new_data = self.exchange.get_klines(symbol, self.candle_interval)
            if new_data:
                self._process_new_data(symbol, new_data)

    def _process_new_data(self, symbol: str, new_data: List[Dict]):
        """Process and save new candle data"""
        df = pd.DataFrame(new_data)
        data_file = f"data/historical/{symbol}.csv"
        
        if os.path.exists(data_file):
            existing = pd.read_csv(data_file)
            updated = pd.concat([existing, df]).drop_duplicates('time')
            updated.to_csv(data_file, index=False)
        else:
            df.to_csv(data_file, index=False)
        
        self.historical_data[symbol] = df.tail(100)
        print(f"📈 Updated {symbol} data ({len(df)} candles)")

    def _run_strategies(self):
        """Execute trading strategies for all symbols"""
        print("\n🔍 Analyzing markets...")
        for symbol in self.symbols:
            # Skip if traded recently
            if symbol in self.last_trade_time:
                if time.time() - self.last_trade_time[symbol] < 86400:  # 24h cooldown
                    continue

            # Get and validate data
            data = self.historical_data.get(symbol)
            if data is None or len(data) < 20:
                continue

            # Generate signal
            signal = self.strategy.generate_signal(data.to_dict('records'))
            if signal and self.risk.can_trade():
                self._execute_trade(symbol, signal)

    def _execute_trade(self, symbol: str, signal: str):
        """Execute trade with full validation"""
        print(f"\n⚡ Attempting {signal} for {symbol}...")
        
        # Get current price
        price = self.exchange.get_price(symbol)
        if not price:
            print("⚠️ Price check failed")
            return

        # Calculate position size (1% risk)
        risk_amount = self.account_balance * 0.01
        quantity = risk_amount / price
        quantity = round(quantity, 6)  # Binance precision

        # Execute order
        order = self.exchange.execute_order(symbol, signal, quantity)
        if order:
            # Update state
            self.last_trade_time[symbol] = time.time()
            self.risk.record_trade()
            
            # Log results
            executed_qty = float(order['executedQty'])
            executed_price = float(order['fills'][0]['price'])
            print(f"✅ Success: {executed_qty} {symbol} @ {executed_price}")
            
            self.logger.log_trade(
                event_type="TRADE",
                symbol=symbol,
                side=signal,
                quantity=executed_qty,
                price=executed_price,
                details="Automated trade execution"
            )
            self.alerts.trade_executed(symbol, signal, executed_price, executed_qty)

if __name__ == "__main__":
    # Validate configuration
    required_config = [
        'BINANCE_API_KEY',
        'BINANCE_API_SECRET',
        'MAX_DRAWDOWN',
        'MAX_DAILY_TRADES',
        'CANDLE_INTERVAL'
    ]
    
    missing = [key for key in required_config if not hasattr(Config, key)]
    if missing:
        raise ValueError(f"Missing config values: {', '.join(missing)}")

    # Start bot
    bot = TradingBot()
    bot.run()