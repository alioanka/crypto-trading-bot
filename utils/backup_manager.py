import pandas as pd
import os
import json
import gzip
from datetime import datetime
from typing import Dict, Any
from utils.config import Config

class BackupManager:
    def __init__(self):
        self.local_path = os.path.join(Config.DATA_DIR, "backups")
        self._ensure_directories()
        
    def _ensure_directories(self):
        os.makedirs(self.local_path, exist_ok=True)
        os.makedirs(os.path.join(self.local_path, "daily"), exist_ok=True)
        
    def save_trade(self, trade_data: Dict[str, Any]) -> None:
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
                
        except Exception as e:
            print(f"Backup failed: {e}")

    def get_recent_trades(self, days: int = 7) -> pd.DataFrame:
        try:
            csv_path = os.path.join(self.local_path, "trade_history.csv")
            if os.path.exists(csv_path):
                df = pd.read_csv(csv_path)
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                return df[df['timestamp'] > (datetime.now() - pd.Timedelta(days=days))]
            return pd.DataFrame()
        except Exception as e:
            print(f"Error loading trades: {e}")
            return pd.DataFrame()