import logging
from datetime import datetime
import os

class TradeLogger:
    def __init__(self):
        self.log_dir = "data/logs"
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.logger = logging.getLogger('trading_bot')
        self.logger.setLevel(logging.INFO)
        
        # File handler
        log_file = f"{self.log_dir}/{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        ))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    def log_trade(self, message, level="info"):
        getattr(self.logger, level)(message)