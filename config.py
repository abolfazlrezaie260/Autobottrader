import os
import yaml
from dataclasses import dataclass
from typing import Optional

@dataclass
class AppConfig:
    url: str
    connection_mode: str
    user_data_dir: str
    cdp_endpoint: str
    headless: bool

@dataclass
class OrderConfig:
    symbol: str
    side: str
    quantity: int
    price: int
    use_ceiling_price: bool
    use_max_quantity: bool = True
    action_type: str = "send"  # "send" or "draft"

@dataclass
class ScheduleConfig:
    enabled: bool
    target_time: str
    max_attempts: int
    interval_ms: int
    dynamic_ping_compensation: bool = True
    ping_lookback_seconds: int = 30
    ping_samples: int = 5
    manual_offset_ms: int = 0

@dataclass
class AntiDetectionConfig:
    random_delay_min_ms: int
    random_delay_max_ms: int
    human_mouse_movement: bool

@dataclass
class StorageConfig:
    save_stocks_data: bool = True
    output_dir: str = "./stocks_data"

class Config:
    def __init__(self, config_path: str = "config.yaml"):
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            
        self.app = AppConfig(**data.get("app", {}))
        self.order = OrderConfig(**data.get("order", {}))
        self.schedule = ScheduleConfig(**data.get("schedule", {}))
        self.anti_detection = AntiDetectionConfig(**data.get("anti_detection", {}))
        self.storage = StorageConfig(**data.get("storage", {}))
