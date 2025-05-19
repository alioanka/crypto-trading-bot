import os
import pandas as pd
import json
import gzip
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from utils.config import Config

logger = logging.getLogger(__name__)

class BackupManager:
    def __init__(self):
        self.local_path = os.path.join(Config.DATA_DIR, "backups")
        self._ensure_directories()
        logger.info(f"BackupManager initialized - storing backups in {self.local_path}")
        
    def _ensure_directories(self):
        """Create required directories if they don't exist"""
        os.makedirs(self.local_path, exist_ok=True)
        os.makedirs(os.path.join(self.local_path, "daily"), exist_ok=True)
        
    def save_trade(self, trade_data: Dict[str, Any]) -> None:
        """Save trade data to both CSV and compressed JSON"""
        try:
            # CSV backup (append)
            csv_path = os.path.join(self.local_path, "trade_history.csv")
            df = pd.DataFrame([trade_data])
            
            if os.path.exists(csv_path):
                df.to_csv(csv_path, mode='a', header=False, index=False)
            else:
                df.to_csv(csv_path, index=False)
                
            # JSON backup (compressed)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            json_path = os.path.join(self.local_path, "daily", f"{timestamp}.json.gz")
            
            with gzip.open(json_path, 'wt', encoding='UTF-8') as f:
                json.dump(trade_data, f, indent=4)
                
            logger.debug(f"Trade backup saved: {trade_data}")
                
        except Exception as e:
            logger.error(f"Backup failed: {e}")

    def get_recent_trades(self, days: int = 7) -> pd.DataFrame:
        """Get recent trades from backup"""
        try:
            csv_path = os.path.join(self.local_path, "trade_history.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df[df['timestamp'] > (datetime.now() - pd.Timedelta(days=days))]
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error loading trades: {e}")
            return pd.DataFrame()