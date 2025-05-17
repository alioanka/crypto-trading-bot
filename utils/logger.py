import os
import csv
from datetime import datetime
from typing import Optional, Dict, Any

class TradeLogger:
    def __init__(self, log_dir: str = "data/logs"):
        """Initialize logger with all required fields
        
        Args:
            log_dir: Directory to store log files
        """
        os.makedirs(log_dir, exist_ok=True)
        self.log_file = os.path.join(log_dir, "trades.csv")
        self._init_log_file()

    def _init_log_file(self):
        """Initialize CSV file with all possible headers"""
        fieldnames = [
            'timestamp',
            'event_type',  # STARTUP, TRADE, ERROR, etc.
            'symbol',      # BTCUSDT
            'side',        # BUY/SELL
            'quantity',
            'price',
            'interval',    # Trading interval (1h, 4h)
            'symbols',     # All traded pairs
            'details'      # Additional info
        ]
        
        # Only write headers if file doesn't exist
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()

    def log_trade(
        self,
        event_type: str,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        quantity: Optional[float] = None,
        price: Optional[float] = None,
        interval: Optional[str] = None,
        symbols: Optional[str] = None,
        details: Optional[str] = None
    ):
        """Universal logging method for all bot events
        
        Args:
            event_type: Type of event (STARTUP, TRADE, ERROR, etc.)
            symbol: Trading pair (for trade events)
            side: BUY/SELL (for trade events)
            quantity: Trade amount
            price: Execution price
            interval: Chart interval used
            symbols: All traded pairs (comma-separated)
            details: Additional information
        """
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'interval': interval,
            'symbols': symbols,
            'details': details
        }

        # Write to CSV
        with open(self.log_file, 'a', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'event_type', 'symbol', 
                'side', 'quantity', 'price',
                'interval', 'symbols', 'details'
            ])
            writer.writerow(entry)

    def get_recent_events(self, limit: int = 10) -> list:
        """Get last N log entries for debugging"""
        try:
            with open(self.log_file, 'r') as f:
                return list(csv.DictReader(f))[-limit:]
        except FileNotFoundError:
            return []