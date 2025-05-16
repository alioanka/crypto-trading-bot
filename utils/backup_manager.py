import pandas as pd
import os
import json
from datetime import datetime
from utils.config import Config

class BackupManager:
    def __init__(self):
        self.local_path = "backups/local"
        self._ensure_directories()
        
    def _ensure_directories(self):
        os.makedirs(self.local_path, exist_ok=True)
        
    def save_trade(self, trade_data):
        """Save trade to multiple backup formats"""
        # CSV backup (append)
        csv_path = f"{self.local_path}/trade_history.csv"
        df = pd.DataFrame([trade_data])
        
        if os.path.exists(csv_path):
            df.to_csv(csv_path, mode='a', header=False, index=False)
        else:
            df.to_csv(csv_path, index=False)
            
        # JSON backup (individual)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = f"{self.local_path}/{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(trade_data, f, indent=4)