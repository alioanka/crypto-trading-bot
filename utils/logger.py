import os
import csv
import json
import gzip
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from utils.config import Config

class TradeLogger:
    def __init__(self, log_dir: str = os.path.join(Config.DATA_DIR, "logs")):
        """Enhanced logger with rotation and compression"""
        os.makedirs(log_dir, exist_ok=True)
        self.log_dir = log_dir
        self.current_log = os.path.join(log_dir, "trades.csv")
        self._init_log_file()
        self._cleanup_old_logs()

    def _init_log_file(self):
        """Initialize CSV file with headers if needed"""
        if not os.path.exists(self.current_log):
            with open(self.current_log, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
                writer.writeheader()

    def _get_fieldnames(self) -> List[str]:
        """Return all possible log fields"""
        return [
            'timestamp', 'event_type', 'symbol', 'side',
            'quantity', 'price', 'interval', 'symbols',
            'notional', 'details', 'error', 'stack_trace'
        ]

    def _cleanup_old_logs(self):
        """Remove logs older than retention period"""
        cutoff = datetime.now() - timedelta(days=Config.LOG_RETENTION_DAYS)
        for filename in os.listdir(self.log_dir):
            if filename.endswith('.csv') or filename.endswith('.gz'):
                filepath = os.path.join(self.log_dir, filename)
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff:
                    os.remove(filepath)

    def _rotate_logs(self):
        """Rotate and compress log file if it gets too large"""
        if os.path.getsize(self.current_log) > 5 * 1024 * 1024:  # 5MB
            rotated_name = f"trades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv.gz"
            rotated_path = os.path.join(self.log_dir, rotated_name)
            
            # Compress current log
            with open(self.current_log, 'rb') as f_in:
                with gzip.open(rotated_path, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Start new log file
            os.remove(self.current_log)
            self._init_log_file()

    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        notional: Optional[float] = None,
        details: Optional[str] = None
    ) -> None:
        """Log a completed trade"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': 'TRADE',
            'symbol': symbol,
            'side': side,
            'quantity': quantity,
            'price': price,
            'notional': notional,
            'interval': Config.CANDLE_INTERVAL,
            'details': details
        }
        self._write_entry(entry)

    def log_error(
        self,
        event_type: str,
        symbol: Optional[str] = None,
        side: Optional[str] = None,
        details: Optional[str] = None,
        error: Optional[str] = None,
        stack_trace: Optional[str] = None
    ) -> None:
        """Log an error event"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'symbol': symbol,
            'side': side,
            'details': details,
            'error': error,
            'stack_trace': stack_trace
        }
        self._write_entry(entry)

    def log_system(
        self,
        event_type: str,
        details: Dict[str, Any]
    ) -> None:
        """Log a system event"""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': json.dumps(details),
            'symbols': ','.join(details.get('symbols', [])) if 'symbols' in details else None
        }
        self._write_entry(entry)

    def _write_entry(self, entry: Dict[str, Any]) -> None:
        """Write entry to log file with rotation check"""
        try:
            self._rotate_logs()
            with open(self.current_log, 'a', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self._get_fieldnames())
                writer.writerow(entry)
        except Exception as e:
            print(f"Failed to write log entry: {e}")

    def get_recent_events(self, limit: int = 10) -> List[Dict]:
        """Get last N log entries for debugging"""
        try:
            with open(self.current_log, 'r') as f:
                return list(csv.DictReader(f))[-limit:]
        except FileNotFoundError:
            return []
        except Exception as e:
            print(f"Error reading log file: {e}")
            return []