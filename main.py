from core import SmartTrendStrategy, RiskManager, BinanceAPI
from utils import TelegramAlerts, BackupManager, TradeLogger
from utils.config import Config
import time

class TradingBot:
    def __init__(self):
        self.strategy = SmartTrendStrategy()
        self.risk = RiskManager(max_drawdown=Config.MAX_DRAWDOWN)
        self.exchange = BinanceAPI()
        self.alerts = TelegramAlerts()
        self.backup = BackupManager()
        self.logger = TradeLogger()
        
    def run(self):
        self.logger.log_trade("Bot started successfully")
        
        while True:
            try:
                self.trading_cycle()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                self.logger.log_trade("Bot stopped by user")
                break
            except Exception as e:
                self.logger.log_trade(f"Error: {str(e)}", "error")
                time.sleep(300)  # Wait 5 minutes after error

    def trading_cycle(self):
        # Implement your trading logic here
        pass

if __name__ == "__main__":
    bot = TradingBot()
    bot.run()