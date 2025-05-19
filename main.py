import os
import time
import math
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from core.exchange import BinanceAPI
from core.strategies import SmartTrendStrategy, EMACrossStrategy
from core.risk_engine import RiskManager
from utils.logger import TradeLogger
from utils.alerts import AlertSystem
from utils.backup_manager import BackupManager
from utils.config import Config

class TradingBot:
    def __init__(self):
        # Initialize directories
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, "historical"), exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, "logs"), exist_ok=True)
        os.makedirs(os.path.join(Config.DATA_DIR, "state"), exist_ok=True)

        # Core components
        self.logger = TradeLogger()
        self.exchange = BinanceAPI(
            api_key=Config.BINANCE_API_KEY,
            api_secret=Config.BINANCE_API_SECRET
        )
        
        # Strategy selection
        if Config.STRATEGY == "SmartTrend":
            self.strategy = SmartTrendStrategy()
        elif Config.STRATEGY == "EMACross":
            self.strategy = EMACrossStrategy()
        else:
            raise ValueError(f"Unknown strategy: {Config.STRATEGY}")
            
        self.risk = RiskManager(
            max_drawdown=Config.MAX_DRAWDOWN,
            max_daily_trades=Config.MAX_DAILY_TRADES
        )
        self.alerts = AlertSystem()
        self.backup = BackupManager()

        # Trading parameters
        self.candle_interval = self._validate_interval(Config.CANDLE_INTERVAL)
        self.update_interval = self._get_update_interval()
        self.symbols = self._get_approved_symbols()
        
        # System state
        self.last_trade_time = {}
        self.historical_data = {}
        self.account_balance = 0.0
        self.open_positions = {}

        # Initialize
        self._print_configuration()
        self._load_all_historical_data()
        self._log_startup()

    def _validate_interval(self, interval: str) -> str:
        valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if interval not in valid_intervals:
            print(f"⚠️ Invalid interval. Defaulting to 4h")
            return "4h"
        return interval

    def _get_update_interval(self) -> int:
        interval_map = {
            '1m': 60 + 15,
            '5m': 300 + 30,
            '15m': 900 + 45,
            '30m': 1800 + 60,
            '1h': 3600 + 120,
            '4h': 14400 + 300,
            '1d': 86400 + 600
        }
        return interval_map.get(self.candle_interval, 3600)

    def _print_configuration(self):
        print("\n" + "="*50)
        print(f"⚙️ TRADING CONFIGURATION")
        print("="*50)
        print(f"• Strategy: {Config.STRATEGY}")
        print(f"• Timeframe: {self.candle_interval} candles")
        print(f"• Max Trades/Day: {Config.MAX_DAILY_TRADES}")
        print(f"• Risk/Trade: {Config.RISK_PER_TRADE*100}%")
        print(f"• Min Notional: ${Config.MIN_NOTIONAL}")
        print(f"• Trading Pairs: {len(self.symbols)}")
        print("="*50 + "\n")

    def _get_approved_symbols(self) -> List[str]:
        approved = []
        for symbol in self.exchange.STABLE_PAIRS:
            if self._is_symbol_tradable(symbol):
                approved.append(symbol)
                print(f"✅ Approved: {symbol}")
            else:
                print(f"⏭️ Skipped: {symbol}")
        return approved

    def _is_symbol_tradable(self, symbol: str) -> bool:
        """Simplified symbol check focusing on availability"""
        try:
            # Basic availability check
            ticker = self.exchange.get_ticker(symbol)
            if not ticker:
                return False
                
            # Check if we can get market info (uses fallbacks if API fails)
            market_info = self.exchange.get_market_info(symbol)
            if not market_info:
                return False
                
            return True
            
        except Exception as e:
            print(f"Error checking {symbol}: {str(e)}")
            return False

    def _load_all_historical_data(self):
        print("\n🔄 Loading historical data...")
        for symbol in self.symbols:
            self._load_historical_data(symbol)

    def _load_historical_data(self, symbol: str):
        data_file = os.path.join(Config.DATA_DIR, "historical", f"{symbol}.csv")
        try:
            if os.path.exists(data_file):
                df = pd.read_csv(data_file)
                df = df.sort_values('time')
                self.historical_data[symbol] = df
                print(f"📊 Loaded {len(df)} {self.candle_interval} candles for {symbol}")
            else:
                data = self.exchange.get_klines(symbol, self.candle_interval)
                if data:
                    df = pd.DataFrame(data)
                    df = df.sort_values('time')
                    df.to_csv(data_file, index=False)
                    self.historical_data[symbol] = df
                    print(f"📊 Downloaded {len(df)} candles for {symbol}")
        except Exception as e:
            self.logger.log_error(
                event_type="DATA_LOAD",
                symbol=symbol,
                details=str(e)
            )

    def _log_startup(self):
        self.logger.log_system(
            event_type="STARTUP",
            details={
                "strategy": Config.STRATEGY,
                "symbols": self.symbols,
                "interval": self.candle_interval,
                "pair_count": len(self.symbols)
            }
        )
        self.alerts.bot_started("3.5", self.symbols)

    def run(self):
        print(f"\n🚀 Trading Bot Active ({self.candle_interval} timeframe)")
        print(f"📊 Monitoring {len(self.symbols)} pairs")
        print(f"📈 Strategy: {Config.STRATEGY}")
        print("⏳ Press Ctrl+C to stop\n")
        
        try:
            while True:
                cycle_start = time.time()
                
                # Refresh account state
                self._update_account_state()
                
                # Update market data
                self._update_market_data()
                
                # Execute strategies
                self._run_strategies()
                
                # Calculate sleep time with progress bar
                elapsed = time.time() - cycle_start
                sleep_time = max(5, self.update_interval - elapsed)
                
                # Visual countdown
                print(f"\n⏳ Next analysis in {sleep_time:.0f}s [", end="", flush=True)
                for _ in range(int(sleep_time)):
                    print("#", end="", flush=True)
                    time.sleep(1)
                print("]")

        except KeyboardInterrupt:
            print("\n🛑 Received shutdown signal...")
            self._shutdown("Manual shutdown")
        except Exception as e:
            self._shutdown(f"Crash: {str(e)}", is_error=True)
            raise

    def _update_account_state(self):
        self.account_balance = self._get_usdt_balance()
        self.open_positions = self.exchange.get_open_positions()
        self._log_account_state()

    def _log_account_state(self):
        if self.open_positions:
            print("\n📊 OPEN POSITIONS:")
            for symbol, position in self.open_positions.items():
                print(f"• {symbol}: {position['side']} {position['quantity']} @ {position['entry_price']}")
        else:
            print("\n📊 No open positions")

    def _get_usdt_balance(self) -> float:
        balances = self.exchange.get_account_balance()
        usdt = balances.get('USDT', 0.0)
        print(f"\n💵 Account Balance: {usdt:.2f} USDT")
        return usdt

    def _update_market_data(self):
        print("\n🔄 Updating market data...")
        for symbol in self.symbols:
            new_data = self.exchange.get_klines(symbol, self.candle_interval)
            if new_data:
                self._process_new_data(symbol, new_data)

    def _process_new_data(self, symbol: str, new_data: List[Dict]):
        try:
            df = pd.DataFrame(new_data)
            data_file = os.path.join(Config.DATA_DIR, "historical", f"{symbol}.csv")
            
            if os.path.exists(data_file):
                existing = pd.read_csv(data_file)
                updated = pd.concat([existing, df]).drop_duplicates('time', keep='last')
                updated = updated.sort_values('time')
                updated.to_csv(data_file, index=False)
            else:
                df = df.sort_values('time')
                df.to_csv(data_file, index=False)
            
            self.historical_data[symbol] = df.tail(100)
            print(f"📈 Updated {symbol} data ({len(df)} candles)")
        except Exception as e:
            self.logger.log_error(
                event_type="DATA_UPDATE",
                symbol=symbol,
                details=str(e)
            )

    def _run_strategies(self):
        print("\n🔍 Analyzing markets...")
        for symbol in self.symbols:
            try:
                # Skip if traded recently
                if symbol in self.last_trade_time:
                    if time.time() - self.last_trade_time[symbol] < 86400:
                        continue

                # Get and validate data
                data = self.historical_data.get(symbol)
                if data is None or len(data) < 20:
                    continue

                # Generate signal
                signal = self.strategy.generate_signal(data.to_dict('records'))
                if signal:
                    if signal == 'BUY' and symbol not in self.open_positions:
                        if self.risk.can_trade():
                            self._execute_trade(symbol, signal)
                    elif signal == 'SELL' and symbol in self.open_positions:
                        self._execute_trade(symbol, signal)
            except Exception as e:
                self.logger.log_error(
                    event_type="STRATEGY_ERROR",
                    symbol=symbol,
                    details=str(e)
                )

    def _execute_trade(self, symbol: str, signal: str):
        print(f"\n⚡ Attempting {signal} for {symbol}...")
        
        try:
            # Get current price and market info
            price = self.exchange.get_price(symbol)
            if not price:
                raise ValueError("Price check failed")
                
            market_info = self.exchange.get_market_info(symbol)
            min_qty = market_info['minQty']
            step_size = market_info['stepSize']
            min_notional = market_info['minNotional']

            # Calculate quantity with precision
            if signal == 'BUY':
                risk_amount = self.account_balance * Config.RISK_PER_TRADE
                quantity = risk_amount / price
            else:  # SELL
                quantity = self.open_positions[symbol]['quantity']

            # Round to step size
            precision = int(round(-math.log(step_size, 10)))
            quantity = round(quantity, precision)
            notional = quantity * price

            # Validate against exchange requirements
            if quantity < min_qty:
                raise ValueError(f"Quantity too small. Min: {min_qty}, Attempted: {quantity}")
            if notional < min_notional:
                raise ValueError(f"Notional too small. Min: {min_notional}, Attempted: {notional:.2f}")

            # Execute order
            order = self.exchange.execute_order(symbol, signal, quantity)
            if not order:
                raise ValueError("Order execution failed")

            # Update state
            self.last_trade_time[symbol] = time.time()
            self._save_last_trade_times()
            
            if signal == 'BUY':
                self.risk.record_trade()
                self.open_positions[symbol] = {
                    'side': 'BUY',
                    'quantity': quantity,
                    'entry_price': price,
                    'time': time.time()
                }
            else:  # SELL
                if symbol in self.open_positions:
                    del self.open_positions[symbol]

            # Log results
            executed_qty = float(order['executedQty'])
            executed_price = float(order['fills'][0]['price'])
            notional = executed_qty * executed_price
            
            print(f"✅ Success: {executed_qty} {symbol} @ {executed_price} (${notional:.2f})")
            
            self.logger.log_trade(
                symbol=symbol,
                side=signal,
                quantity=executed_qty,
                price=executed_price,
                notional=notional
            )
            self.alerts.trade_executed(symbol, signal, executed_price, executed_qty)

        except Exception as e:
            error_msg = f"{symbol} {signal} failed: {str(e)}"
            print(f"❌ {error_msg}")
            self.logger.log_error(
                event_type="TRADE_ERROR",
                symbol=symbol,
                side=signal,
                details=str(e)
            )

    def _save_last_trade_times(self):
        state_file = os.path.join(Config.DATA_DIR, "state", "last_trades.json")
        with open(state_file, 'w') as f:
            import json
            json.dump(self.last_trade_time, f)

    def _shutdown(self, reason: str, is_error: bool = False):
        self.alerts.bot_stopped(reason)
        self.logger.log_system(
            event_type="SHUTDOWN",
            details={"reason": reason, "is_error": is_error}
        )
        self._save_last_trade_times()
        print("\n=== Trading Bot Stopped ===")

if __name__ == "__main__":
    # Validate configuration
    required_config = [
        'BINANCE_API_KEY', 'BINANCE_API_SECRET',
        'CANDLE_INTERVAL', 'MAX_DAILY_TRADES',
        'MAX_DRAWDOWN', 'RISK_PER_TRADE',
        'MIN_VOLUME', 'MAX_VOLATILITY',
        'MIN_NOTIONAL', 'STRATEGY'
    ]
    
    missing = [key for key in required_config if not hasattr(Config, key)]
    if missing:
        raise ValueError(f"Missing config values: {', '.join(missing)}")

    # Start bot
    bot = TradingBot()
    bot.run()