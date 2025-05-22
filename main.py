import os
import time
import math
from decimal import Decimal, getcontext, ROUND_DOWN
import logging
import traceback  # Add this import at the top of your main.py
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from core.exchange import BinanceAPI
from binance.exceptions import BinanceAPIException
from core.strategies import SmartTrendStrategy, EMACrossStrategy
from core.risk_engine import RiskManager
from utils.logger import TradeLogger
from utils.alerts import AlertSystem
from utils.backup_manager import BackupManager
from utils.config import Config

# Configure logging
logging.basicConfig(
    level=Config.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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
        self.start_time = datetime.now()
        self.trading_fee = 0.001  # 0.1% trading fee

        # Initialize
        self._print_configuration()
        self._load_all_historical_data()
        self._log_startup()
        self._validate_open_positions()  # Initial validation
            # Initial dust cleanup
        self._cleanup_dust_positions(initial_cleanup=True)
        self.last_dust_alert = {}  # symbol: timestamp
        self._last_full_validation = 0  # Tracks last full validation time

    def _validate_interval(self, interval: str) -> str:
        valid_intervals = ['1m', '5m', '15m', '30m', '1h', '4h', '1d']
        if interval not in valid_intervals:
            logger.warning(f"Invalid interval {interval}. Defaulting to 1h")
            return "1h"
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
        logger.info("\n" + "="*50)
        logger.info(f"⚙️ TRADING CONFIGURATION")
        logger.info("="*50)
        logger.info(f"• Strategy: {Config.STRATEGY}")
        logger.info(f"• Timeframe: {self.candle_interval} candles")
        logger.info(f"• Max Trades/Day: {Config.MAX_DAILY_TRADES}")
        logger.info(f"• Risk/Trade: {Config.RISK_PER_TRADE*100}%")
        logger.info(f"• Min Notional: ${Config.MIN_NOTIONAL}")
        logger.info(f"• Trading Pairs: {len(self.symbols)}")
        logger.info("="*50 + "\n")

    def _get_approved_symbols(self) -> List[str]:
        approved = []
        for symbol in self.exchange.STABLE_PAIRS:
            try:
                # Check if symbol is available by getting price
                price = self.exchange.get_price(symbol)
                if price is not None:
                    approved.append(symbol)
                    logger.info(f"✅ Approved: {symbol}")
                else:
                    logger.warning(f"⏭️ Skipped: {symbol} - Price check failed")
            except Exception as e:
                logger.error(f"Error checking {symbol}: {str(e)}")
                logger.warning(f"⏭️ Skipped: {symbol}")
        return approved

    def _load_all_historical_data(self):
        logger.info("\n🔄 Loading historical data...")
        for symbol in self.symbols:
            self._load_historical_data(symbol)

    def _load_historical_data(self, symbol: str):
        data_file = os.path.join(Config.DATA_DIR, "historical", f"{symbol}.csv")
        try:
            if os.path.exists(data_file):
                df = pd.read_csv(data_file)
                df = df.sort_values('time')
                self.historical_data[symbol] = df
                logger.info(f"📊 Loaded {len(df)} {self.candle_interval} candles for {symbol}")
            else:
                data = self.exchange.get_klines(symbol, self.candle_interval)
                if data:
                    df = pd.DataFrame(data)
                    df = df.sort_values('time')
                    df.to_csv(data_file, index=False)
                    self.historical_data[symbol] = df
                    logger.info(f"📊 Downloaded {len(df)} candles for {symbol}")
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
        logger.info(f"\n🚀 Trading Bot Active ({self.candle_interval} timeframe)")
        logger.info(f"📊 Monitoring {len(self.symbols)} pairs")
        logger.info(f"📈 Strategy: {Config.STRATEGY}")
        logger.info("⏳ Press Ctrl+C to stop\n")
        
        # Add heartbeat counter
        heartbeat_count = 0
        
        try:
            while True:
                cycle_start = time.time()
                self._validate_open_positions()
                heartbeat_count += 1
                
                # Send heartbeat every 12 cycles (approx hourly for 5m interval)
                if heartbeat_count % 12 == 0:
                    self._send_heartbeat()
                
                # Refresh account state
                self._update_account_state()
                self._cleanup_dust_positions()  # Add this line
                self._handle_stranded_positions()  # Add this line
                
                # Update market data
                self._update_market_data()
                
                # Execute strategies
                self._run_strategies()

           
                # Calculate sleep time with progress bar
                elapsed = time.time() - cycle_start
                sleep_time = max(5, self.update_interval - elapsed)

                # Display status with error handling
                try:
                    self._display_status(sleep_time)
                except Exception as e:
                    logger.error(f"Status display error: {e}")
                
                time.sleep(sleep_time)
                

                # Visual countdown
                logger.info(f"\n⏳ Next analysis in {sleep_time:.0f}s [{'#' * int(sleep_time)}]")
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("\n🛑 Received shutdown signal...")
            self._shutdown("Manual shutdown")
        except Exception as e:
            self._shutdown(f"Crash: {str(e)}", is_error=True)
            raise

    def _display_status(self, sleep_time: float):
        """Safe status display with filtered positions"""
        try:
            # Get non-dust positions
            valid_positions = {}
            for symbol, pos in self.open_positions.items():
                try:
                    current_price = self.exchange.get_price(symbol)
                    if current_price:
                        value = current_price * pos['quantity']
                        if value >= 1.0:  # Only show positions worth $1+
                            valid_positions[symbol] = {
                                **pos,
                                'current_price': current_price,
                                'value': value
                            }
                except Exception as e:
                    logger.error(f"Error evaluating {symbol} position: {e}")
            
            # Build status message
            status_msg = [
                f"\n⏳ Next analysis in {sleep_time:.0f}s [{'#' * int(sleep_time)}]",
                f"💵 Balance: ${self.account_balance:.2f}",
                f"📊 Positions: {len(valid_positions)}"
            ]
            
            if valid_positions:
                status_msg.append("🔍 Active Positions:")
                for symbol, pos in valid_positions.items():
                    status_msg.append(
                        f"• {symbol}: {pos['side']} {pos['quantity']:.6f} @ {pos['entry_price']:.6f} "
                        f"(Cur: {pos['current_price']:.6f}, Val: ${pos['value']:.2f})"
                    )
            
            logger.info("\n".join(status_msg))
            
        except Exception as e:
            logger.error(f"Failed to display status: {e}")
            # Fallback minimal status
            logger.info(f"\n⏳ Next analysis in {sleep_time:.0f}s")

    # ... [previous imports and code remain the same until _send_heartbeat method]
    def _check_position_limits(self, symbol: str) -> bool:
        """Check if position should be closed due to stop loss/take profit"""
        if symbol not in self.open_positions:
            return False
            
        position = self.open_positions[symbol]
        current_price = self.exchange.get_price(symbol)
        if not current_price:
            return False
            
        entry = position['entry_price']
        is_long = position['side'] == 'BUY'
        
        # Calculate current PnL
        if is_long:
            pnl_pct = (current_price - entry) / entry * 100
        else:
            pnl_pct = (entry - current_price) / entry * 100
        
        # Check stop loss (bypass min notional check)
        if pnl_pct <= -abs(Config.STOP_LOSS_PCT):
            logger.info(f"🛑 STOP LOSS triggered for {symbol} at {current_price} ({pnl_pct:.2f}%)")
            return self._execute_stop_loss(symbol, current_price)
                
        # Check take profit
        if pnl_pct >= abs(Config.TAKE_PROFIT_PCT):
            logger.info(f"🎯 TAKE PROFIT triggered for {symbol} at {current_price} ({pnl_pct:.2f}%)")
            self._execute_trade(symbol, 'SELL')
            return True
            
        return False

    def _send_heartbeat(self):
        """Send periodic status update"""
        status = {
            "uptime": str(datetime.now() - self.start_time),
            "symbols": self.symbols if isinstance(self.symbols, list) else [],
            "positions": len(self.open_positions),
            "balance": self.account_balance,
            "last_trades": list(self.last_trade_time.keys()) if isinstance(self.last_trade_time, dict) else [],
            "risk_metrics": self.risk.get_risk_metrics()
        }
        
        # Ensure symbols is always a list for joining
        symbols_list = status['symbols'] if isinstance(status['symbols'], list) else []
        
        message = (
            f"<b>💓 BOT HEARTBEAT</b>\n"
            f"• Uptime: {status['uptime']}\n"
            f"• Monitoring: {len(symbols_list)} pairs\n"
            f"• Positions: {status['positions']}\n"
            f"• Balance: ${status['balance']:.2f}\n"
            f"• Daily Trades: {status['risk_metrics']['daily_trades']}/{status['risk_metrics']['max_daily_trades']}"
        )
        
        self.alerts._send_alert(message, "SYSTEM")
        
        # Create a safe copy of status for logging
        log_status = status.copy()
        log_status['symbols'] = symbols_list  # Ensure this is a list
        self.logger.log_system("HEARTBEAT", log_status)

# ... [rest of the code remains the same]

    def _update_account_state(self):
        self.account_balance = self._get_usdt_balance()
        self.open_positions = self.exchange.get_open_positions()
        self._log_account_state()

    def _log_account_state(self):
        """Display open positions excluding dust"""
        if not self.open_positions:
            logger.info("\n📊 No open positions")
            return
            
        logger.info("\n📊 OPEN POSITIONS:")
        for symbol, position in self.open_positions.items():
            try:
                current_price = self.exchange.get_price(symbol)
                if not current_price:
                    continue
                    
                position_value = position['quantity'] * current_price
                market_info = self.exchange.get_market_info(symbol)
                min_notional = market_info['minNotional']
                
                # Only show positions worth at least $1 or 10% of min notional
                if position_value >= max(1.0, min_notional * 0.1):
                    logger.info(
                        f"• {symbol}: {position['side']} {position['quantity']} @ {position['entry_price']} "
                        f"(Cur: {current_price}, Val: ${position_value:.2f})"
                    )
                else:
                    # Mark as dust and don't display
                    position['dust'] = True
                    
            except Exception as e:
                logger.error(f"Error evaluating {symbol} position: {e}")
                continue

    def _validate_open_positions(self):
        """Verify tracked positions match actual balances"""
        try:
            actual_balances = self.exchange.get_account_balance()
            
            for symbol in list(self.open_positions.keys()):
                try:
                    base_asset = symbol.replace('USDT', '')
                    actual_qty = Decimal(str(actual_balances.get(base_asset, 0)))
                    
                    # If we're tracking a position that doesn't exist
                    if actual_qty <= Decimal('0'):
                        del self.open_positions[symbol]
                        logger.warning(f"Removed phantom position: {symbol}")
                        continue
                        
                    # Update quantity if different
                    tracked_qty = Decimal(str(self.open_positions[symbol]['quantity']))
                    if not math.isclose(float(tracked_qty), float(actual_qty), rel_tol=0.01):
                        logger.warning(
                            f"Quantity mismatch: {symbol} "
                            f"(Tracked: {tracked_qty}, Actual: {actual_qty})"
                        )
                        self.open_positions[symbol]['quantity'] = float(actual_qty)
                        
                except Exception as e:
                    logger.error(f"Error validating {symbol} position: {e}")
                    
        except Exception as e:
            logger.error(f"Position validation failed: {e}")

    def _get_usdt_balance(self) -> float:
        balances = self.exchange.get_account_balance()
        usdt = balances.get('USDT', 0.0)
        logger.info(f"\n💵 Account Balance: {usdt:.2f} USDT")
        return usdt

    def _update_market_data(self):
        logger.info("\n🔄 Updating market data...")
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
            logger.info(f"📈 Updated {symbol} data ({len(df)} candles)")
        except Exception as e:
            self.logger.log_error(
                event_type="DATA_UPDATE",
                symbol=symbol,
                details=str(e)
            )

    def _run_strategies(self):
        logger.info("\n🔍 Analyzing markets...")
        for symbol in self.symbols:
            try:
                # First check position limits
                if self._check_position_limits(symbol):
                    continue
                # Skip if traded recently
                if symbol in self.last_trade_time:
                    if time.time() - self.last_trade_time[symbol] < 86400:
                        logger.debug(f"Skipping {symbol} - traded recently")
                        continue

                # Get and validate data
                data = self.historical_data.get(symbol)
                if data is None or len(data) < 20:
                    logger.warning(f"Insufficient data for {symbol}")
                    continue

                # Generate signal
                signal = self.strategy.generate_signal(data.to_dict('records'))
                if signal:
                    logger.info(f"Signal generated for {symbol}: {signal}")
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
#update for PnL
    def _calculate_position_metrics(self) -> Dict:
        """Calculate all position metrics for alerts"""
        positions = {}
        total_pnl = 0.0
        total_value = 0.0
        
        for symbol, pos in self.open_positions.items():
            current_price = self.exchange.get_price(symbol)
            if current_price:
                entry = pos['entry_price']
                qty = pos['quantity']
                value = current_price * qty
                pnl_usd = (current_price - entry) * qty * (-1 if pos['side'] == 'SELL' else 1)
                pnl_pct = (current_price - entry) / entry * 100 * (-1 if pos['side'] == 'SELL' else 1)
                
                positions[symbol] = {
                    'side': pos['side'],
                    'quantity': qty,
                    'entry_price': entry,
                    'current_price': current_price,
                    'pnl_usd': pnl_usd,
                    'pnl_pct': pnl_pct,
                    'value': value,
                    'duration': time.time() - pos['entry_time']
                }
                total_pnl += pnl_usd
                total_value += value
        
        return {
            'positions': positions,
            'total_pnl': total_pnl,
            'total_value': total_value
        }

    def _send_performance_update(self):
        """Send comprehensive performance report"""
        position_metrics = self._calculate_position_metrics()
        risk_metrics = self.risk.get_performance_metrics(self.account_balance)
        
        # Prepare detailed message
        message_lines = [
            "📊 <b>PORTFOLIO PERFORMANCE</b>",
            f"• Balance: <code>${self.account_balance:.2f}</code>",
            f"• Positions: <code>{len(position_metrics['positions'])}</code>",
            f"• Total PnL: <code>${position_metrics['total_pnl']:+.2f}</code>",
            "",
            "<b>POSITIONS:</b>"
        ]
        
        # Add position details
        for symbol, pos in position_metrics['positions'].items():
            message_lines.append(
                f"• {symbol}: {pos['side']} {pos['quantity']:.4f} | "
                f"PnL: <code>{pos['pnl_pct']:+.2f}%</code> | "
                f"Value: <code>${pos['value']:.2f}</code>"
            )
        
        # Add risk metrics
        message_lines.extend([
            "",
            "<b>RISK METRICS:</b>",
            f"• Win Rate: <code>{risk_metrics['win_rate']:.1f}%</code>",
            f"• Avg Win: <code>{risk_metrics['avg_win']:.2f}%</code>",
            f"• Avg Loss: <code>{risk_metrics['avg_loss']:.2f}%</code>",
            f"• Profit Factor: <code>{risk_metrics['profit_factor']:.2f}</code>"
        ])
        
        # Send the alert
        self.alerts._send_alert("\n".join(message_lines), "PERFORMANCE")
        
        # Log full metrics
        metrics = {
            **risk_metrics,
            'balance': self.account_balance,
            'positions': position_metrics['positions'],
            'total_value': position_metrics['total_value']
        }
        self.logger.log_system("PERFORMANCE_REPORT", metrics)

    def _execute_trade(self, symbol: str, signal: str):
        """Enhanced trade execution with dust handling"""
        logger.info(f"\n⚡ Executing {signal} for {symbol}...")
        
        try:
            # Get current price and market info
            price = self.exchange.get_price(symbol)
            if not price or price <= 0:
                raise ValueError(f"Invalid price for {symbol}: {price}")

            market_info = self.exchange.get_market_info(symbol)
            min_qty = float(market_info['minQty'])
            step_size = float(market_info['stepSize'])
            min_notional = float(market_info['minNotional'])
            base_asset = market_info['baseAsset']
            precision = int(round(-math.log(step_size, 10)))

            # Calculate quantity based on signal type
            if signal == 'BUY':
                # Use 5% of balance or RISK_PER_TRADE, whichever is smaller
                risk_amount = min(self.account_balance * 0.05,
                                self.account_balance * Config.RISK_PER_TRADE)
                quantity = risk_amount / price
                
                # Round DOWN to step size
                quantity = math.floor(quantity * 10**precision) / 10**precision
                
                # Ensure minimum quantity and notional
                if quantity < min_qty:
                    quantity = min_qty
                    logger.info(f"Adjusting to minimum quantity: {min_qty}")
                
                if (quantity * price) < min_notional:
                    min_qty_needed = math.ceil((min_notional / price) * 10**precision) / 10**precision
                    quantity = max(min_qty_needed, min_qty)
                    logger.info(f"Adjusting to meet minimum notional: {quantity}")

# In the SELL section of _execute_trade():
            else:  # SELL
                # Get available balance
                balances = self.exchange.get_account_balance()
                base_asset = market_info['baseAsset']
                available = balances.get(base_asset, 0)
                
                if available <= 0:
                    raise ValueError(f"No {base_asset} available to sell")
                
                # Calculate precision
                step_size = Decimal(str(market_info['stepSize']))
                precision = abs(step_size.as_tuple().exponent)
                
                # Calculate max sellable quantity (accounting for fees)
                quantity = float((Decimal(str(available)) * Decimal(str(1 - self.trading_fee))).quantize(
                    Decimal(10)**-precision,
                    rounding=ROUND_DOWN
                ))
                
                # Special case for positions that dropped below min notional
                position_value = quantity * price
                min_notional = market_info['minNotional']
                
                if position_value < min_notional:
                    logger.warning(f"Position below min notional (${position_value:.2f} < ${min_notional:.2f}), "
                                f"attempting to sell anyway")
                    
                    # For very small positions, sell entire balance
                    if position_value < min_notional * 0.2:
                        quantity = float(available)
                        if quantity < market_info['minQty']:
                            logger.warning(f"Position below minimum quantity, attempting anyway: {quantity} < {market_info['minQty']}")
                # Final validation
                if quantity < min_qty:
                    raise ValueError(f"Quantity below minimum: {quantity} < {min_qty}")
                    
                if (quantity * price) < min_notional:
                    raise ValueError(f"Notional too small: ${quantity*price:.2f} < ${min_notional:.2f}")

            # Execute order
            order = self.exchange.execute_order(symbol, signal, quantity)
            if not order:
                raise ValueError("Order execution failed")

            # Get execution details
            executed_qty = float(order['executedQty'])
            executed_price = float(order['fills'][0]['price'])
            commission = float(order['fills'][0]['commission'])
            notional = executed_qty * executed_price

            # Handle position tracking
            if signal == 'SELL' and symbol in self.open_positions:
                position = self.open_positions[symbol]
                entry_price = position['entry_price']
                entry_time = position.get('entry_time', time.time())
                
                # Calculate PnL
                commission = sum(float(fill['commission']) for fill in order['fills'])
                pnl_usd = (executed_price - entry_price) * executed_qty - commission
                pnl_pct = (executed_price - entry_price) / entry_price * 100
                is_win = pnl_usd >= 0
                
                # Update risk manager
                self.risk.record_trade(
                    symbol=symbol,
                    side=signal,
                    quantity=executed_qty,
                    price=executed_price,
                    entry_price=entry_price,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    current_balance=self.account_balance
                )
                
                # Send closure alert
                self.alerts.trade_closure_alert(
                    symbol=symbol,
                    side=position['side'],
                    quantity=executed_qty,
                    price=executed_price,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    entry_price=entry_price,
                    entry_time=entry_time
                )
                
                # Check if position fully closed
                remaining_balance = self.exchange.get_account_balance().get(base_asset, 0)
                if remaining_balance <= Decimal(str(market_info['minQty'])) * 2:  # Tiny residual
                    del self.open_positions[symbol]
                    logger.info(f"Fully closed position for {symbol}")
                else:
                    # Update remaining position
                    remaining_qty = float(remaining_balance)
                    if remaining_qty * executed_price < min_notional * 0.5:
                        self.open_positions[symbol]['dust'] = True
                        logger.warning(f"Small residual position remains: {remaining_qty} {symbol}")
                    else:
                        self.open_positions[symbol]['quantity'] = remaining_qty
                
                # Update account balance estimate
                self.account_balance += pnl_usd
                
            elif signal == 'BUY':
                # Record new position
                self.open_positions[symbol] = {
                    'side': 'BUY',
                    'quantity': executed_qty,
                    'entry_price': executed_price,
                    'entry_time': time.time(),
                    'dust': False
                }
                
                # Record trade with 0 PnL
                self.risk.record_trade(
                    pnl_usd=0,
                    current_balance=self.account_balance,
                    is_win=False
                )
                
                # Update account balance estimate
                self.account_balance -= notional

            # Update trade history
            self.last_trade_time[symbol] = time.time()
            self._save_last_trade_times()
            
            # Log and alert
            logger.info(f"✅ Success: {executed_qty} {symbol} @ {executed_price} (${notional:.2f})")
            self.logger.log_trade(
                symbol=symbol,
                side=signal,
                quantity=executed_qty,
                price=executed_price,
                notional=notional,
                details=f"Commission: {commission} {market_info['quoteAsset']}"
            )
            
            # Send execution alert
            self.alerts.trade_executed(
                symbol=symbol,
                side=signal,
                price=executed_price,
                quantity=executed_qty,
                stop_loss=self._calculate_stop_loss(executed_price, signal == 'BUY'),
                take_profit=self._calculate_take_profit(executed_price, signal == 'BUY')
            )

        except ValueError as e:
            error_msg = f"Validation Error: {e}"
            logger.error(f"❌ {error_msg}")
            self.logger.log_error(
                event_type="TRADE_ERROR",
                symbol=symbol,
                side=signal,
                details=error_msg
            )
        except Exception as e:
            error_msg = f"Unexpected Error: {str(e)}"
            logger.error(f"❌ {error_msg}", exc_info=True)
            self.logger.log_error(
                event_type="TRADE_ERROR",
                symbol=symbol,
                side=signal,
                details=error_msg,
                stack_trace=traceback.format_exc()
            )
            self.alerts.error_alert(
                "TRADE_FAILURE",
                f"{symbol} {signal} failed: {str(e)}",
                symbol
            )

    def _execute_stop_loss(self, symbol: str, current_price: float):
        """Emergency sell procedure with comprehensive validation"""
        try:
            # First verify we actually have this position
            if symbol not in self.open_positions:
                logger.warning(f"No tracked position for {symbol} - nothing to sell")
                return False
                
            # Get REAL available balance from exchange
            balances = self.exchange.get_account_balance()
            base_asset = symbol.replace('USDT', '')
            available = Decimal(str(balances.get(base_asset, 0)))
            
            # If no balance available, clean up the ghost position
            if available <= Decimal('0'):
                del self.open_positions[symbol]
                logger.warning(f"No {base_asset} balance available - removed ghost position")
                return False
                
            # Get market precision
            market_info = self.exchange.get_market_info(symbol)
            step_size = Decimal(str(market_info['stepSize']))
            precision = abs(step_size.as_tuple().exponent)
            
            # Calculate quantity with proper rounding
            quantity = float(available.quantize(
                Decimal(10)**-precision,
                rounding=ROUND_DOWN
            ))
            
            # Final validation
            if quantity <= 0:
                del self.open_positions[symbol]
                logger.warning(f"Rounded quantity is zero for {symbol} - removed position")
                return False
                
            logger.warning(f"🚨 EMERGENCY STOP LOSS: Selling {quantity} {symbol} at ~{current_price}")
            
            # Execute market sell
            order = self.exchange.client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
            
            # Process execution
            executed_qty = float(order['executedQty'])
            fills = order.get('fills', [])
            executed_price = float(fills[0]['price']) if fills else current_price
            
            # Calculate PnL
            entry_price = self.open_positions[symbol]['entry_price']
            pnl_usd = (executed_price - entry_price) * executed_qty
            pnl_pct = (executed_price - entry_price) / entry_price * 100
            
            # Update tracking
            del self.open_positions[symbol]
            logger.info(f"✅ STOP LOSS executed: Sold {executed_qty} {symbol} at {executed_price}")
            
            # Record trade
            self.risk.record_trade(
                symbol=symbol,
                side='SELL',
                quantity=executed_qty,
                price=executed_price,
                entry_price=entry_price,
                current_balance=self.account_balance
            )
            
            # Send alert
            try:
                self.alerts.trade_closure_alert(
                    symbol=symbol,
                    side='SELL',
                    quantity=executed_qty,
                    price=executed_price,
                    pnl_usd=pnl_usd,
                    pnl_pct=pnl_pct,
                    entry_price=entry_price,
                    entry_time=self.open_positions[symbol].get('entry_time', time.time())
                )
            except Exception as e:
                logger.error(f"Failed to send closure alert: {e}")
                self.alerts._send_alert(
                    f"🛑 STOP LOSS EXECUTED\n{symbol} {executed_qty} @ {executed_price}",
                    "TRADE"
                )
            
            return True
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"🆘 STOP LOSS FAILED for {symbol}: {error_msg}")
            
            # Clean up if this is a dust position
            if symbol in self.open_positions:
                position_value = self.open_positions[symbol]['quantity'] * current_price
                if position_value < 1.0:  # $1 threshold
                    del self.open_positions[symbol]
                    logger.info(f"Auto-removed dust position: {symbol}")
            
            self.alerts.error_alert(
                "STOP_LOSS_FAILED",
                f"Failed to execute stop loss for {symbol}: {error_msg}",
                symbol
            )
            return False

    def _cleanup_dust_positions(self, initial_cleanup: bool = False):
        """Clean up residual dust positions with proper validation and alert cooldown"""
        dust_symbols = []
        dust_threshold = 1.0  # $1 threshold for dust
        
        for symbol, position in list(self.open_positions.items()):
            try:
                # Skip if not actually dust (unless initial cleanup)
                if not initial_cleanup and not position.get('dust', False):
                    continue
                    
                # Get current price and market info
                current_price = self.exchange.get_price(symbol)
                if not current_price:
                    continue
                    
                market_info = self.exchange.get_market_info(symbol)
                if not market_info:
                    continue
                    
                # Calculate position value
                position_value = position['quantity'] * current_price
                
                # Use the smaller of $1 or 20% of min notional
                threshold = min(dust_threshold, market_info['minNotional'] * 0.2)
                if position_value < threshold:
                    position['dust'] = True
                    dust_symbols.append((symbol, position_value))
                    logger.warning(f"Dust position detected: {symbol} (${position_value:.2f})")
                    
            except Exception as e:
                logger.error(f"Error evaluating {symbol} for dust: {e}")
                continue
        
        # Process dust positions
        for symbol, value in dust_symbols:
            try:
                # Remove from tracking first to prevent re-processing
                if symbol in self.open_positions:
                    del self.open_positions[symbol]
                    logger.info(f"Removed dust position: {symbol} (${value:.2f})")
                
                # Convert to USDT if during initial cleanup and value > $0.10
                if initial_cleanup and value > 0.10:
                    self._convert_dust_to_usdt(symbol, value)
                
                # Alert with cooldown (max once per 4 hours per symbol)
                last_alert = self.last_dust_alert.get(symbol, 0)
                if time.time() - last_alert > 14400:  # 4 hours
                    alert_sent = False
                    for attempt in range(3):
                        try:
                            self.alerts.error_alert(
                                "DUST_CLEANUP",
                                f"Removed dust position: {symbol} (${value:.2f})",
                                symbol
                            )
                            self.last_dust_alert[symbol] = time.time()
                            alert_sent = True
                            break
                        except Exception as e:
                            logger.warning(f"Alert attempt {attempt+1} failed: {e}")
                            time.sleep(1)
                    
                    if not alert_sent:
                        logger.error(f"Failed to send dust alert for {symbol}")
                
            except Exception as e:
                logger.error(f"Failed to process {symbol} dust: {e}")

    def _convert_dust_to_usdt(self, symbol: str, value: float):
        """Attempt to convert small balances to USDT"""
        try:
            if value <= 0:
                return
                
            base_asset = symbol.replace('USDT', '')
            balances = self.exchange.get_account_balance()
            available = Decimal(str(balances.get(base_asset, 0)))
            
            if available <= Decimal('0'):
                return
                
            market_info = self.exchange.get_market_info(symbol)
            step_size = Decimal(str(market_info['stepSize']))
            precision = abs(step_size.as_tuple().exponent)
            
            quantity = float(available.quantize(
                Decimal(10)**-precision,
                rounding=ROUND_DOWN
            ))
            
            if quantity <= 0:
                return
                
            logger.info(f"Converting dust: {quantity} {symbol} to USDT")
            order = self.exchange.client.create_order(
                symbol=symbol,
                side='SELL',
                type='MARKET',
                quantity=quantity
            )
            
            logger.info(f"Converted {quantity} {symbol} to USDT")
            return True
            
        except Exception as e:
            logger.error(f"Dust conversion failed for {symbol}: {e}")
            return False

    def _handle_stranded_positions(self):
        """Manage positions that can't be sold due to price drops"""
        stranded = []
        
        for symbol, position in self.open_positions.items():
            if position.get('stranded', False):
                try:
                    market_info = self.exchange.get_market_info(symbol)
                    current_price = self.exchange.get_price(symbol)
                    
                    if current_price:
                        current_value = position['quantity'] * current_price
                        
                        # Attempt recovery if price rebounds
                        if current_value >= market_info['minNotional'] * 0.8:  # 80% of min
                            logger.info(f"Price recovered for {symbol} - attempting close")
                            del self.open_positions[symbol]['stranded']
                            self._execute_trade(symbol, 'SELL')
                        else:
                            stranded.append(symbol)
                
                except Exception as e:
                    logger.error(f"Error handling stranded {symbol}: {e}")
        
        if stranded:
            logger.warning(f"Active stranded positions: {', '.join(stranded)}")

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
        logger.info("\n=== Trading Bot Stopped ===")

    # Add these methods to your TradingBot class in main.py

    def _send_enhanced_heartbeat(self):
        """Enhanced heartbeat with strategy diagnostics"""
        status = {
            "uptime": str(datetime.now() - self.start_time),
            "symbols": len(self.symbols),
            "positions": len(self.open_positions),
            "balance": self.account_balance,
            "daily_trades": f"{self.risk.daily_trades}/{Config.MAX_DAILY_TRADES}",
            "data_quality": self.strategy.get_data_quality_report(),
            "last_signals": list(self.last_trade_time.keys())[-5:]
        }
        
        # Prepare message with markdown formatting
        message = (
            f"<b>💓 ENHANCED HEARTBEAT</b>\n"
            f"• Uptime: <code>{status['uptime']}</code>\n"
            f"• Monitoring: <code>{status['symbols']}</code> pairs\n"
            f"• Positions: <code>{status['positions']}</code>\n"
            f"• Balance: <code>${status['balance']:.2f}</code>\n"
            f"• Trades Today: <code>{status['daily_trades']}</code>\n"
            f"• Data Issues: <code>{status['data_quality']['total_issues']}</code>\n"
            f"• Last Signals: <code>{', '.join(status['last_signals'])}</code>"
        )
        
        self.alerts._send_alert(message, "SYSTEM")
        self.logger.log_system("HEARTBEAT", status)

    def force_test_signal(self, symbol: str, signal: str):
        """Force a test signal for a specific symbol"""
        if not hasattr(self.strategy, 'force_test_signal'):
            logger.error("Current strategy doesn't support test signals")
            return
            
        if symbol not in self.symbols:
            logger.error(f"Symbol {symbol} not in monitored pairs")
            return
            
        self.strategy.force_test_signal(signal)
        logger.info(f"Test signal {signal} set for {symbol} - will trigger on next analysis")
        
        # Immediately process this symbol
        data = self.historical_data.get(symbol)
        if data is not None:
            signal = self.strategy.generate_signal(data.to_dict('records'))
            if signal:
                self._execute_trade(symbol, signal)
                
    def _run_strategies(self):
        logger.info("\n🔍 Analyzing markets...")
        for symbol in self.symbols:
            try:
                logger.debug(f"Checking {symbol}...")
                
                # First check position limits
                if self._check_position_limits(symbol):
                    continue
                    
                # Skip if traded recently
                if symbol in self.last_trade_time:
                    elapsed = time.time() - self.last_trade_time[symbol]
                    if elapsed < 86400:
                        logger.debug(f"Skipping {symbol} - traded {elapsed/3600:.1f} hours ago")
                        continue

                # Get and validate data
                data = self.historical_data.get(symbol)
                if data is None or len(data) < 20:
                    logger.warning(f"Insufficient data for {symbol}")
                    continue

                # Generate signal
                signal = self.strategy.generate_signal(data.to_dict('records'))
                if signal:
                    logger.info(f"Signal generated for {symbol}: {signal.action}")
                    if signal.action == 'BUY' and symbol not in self.open_positions:
                        if self.risk.can_trade():
                            logger.info(f"Attempting BUY for {symbol} (Risk check passed)")
                            self._execute_trade(symbol, signal.action)
                        else:
                            logger.warning(f"BUY signal for {symbol} blocked by risk manager")
                    elif signal.action == 'SELL' and symbol in self.open_positions:
                        logger.info(f"Attempting SELL for {symbol}")
                        self._execute_trade(symbol, signal.action)
            except Exception as e:
                logger.error(f"Error processing {symbol}: {e}")

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
    
    if os.getenv("ENABLE_TEST_SIGNAL", "False").lower() == "true":
        bot.force_test_signal("XRPUSDT", "BUY")  # Only runs when explicitly enabled
    
    try:
        bot.run()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise