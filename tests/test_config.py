import os
import sys
import tempfile
import unittest
import yaml
from dataclasses import is_dataclass

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from config import Config, AppConfig, OrderConfig, ScheduleConfig, AntiDetectionConfig, StorageConfig

class TestConfig(unittest.TestCase):
    def setUp(self):
        self.valid_data = {
            "app": {
                "url": "https://d.easytrader.ir",
                "connection_mode": "persistent",
                "user_data_dir": "./test_profile",
                "cdp_endpoint": "http://127.0.0.1:9222",
                "headless": False
            },
            "order": {
                "symbol": "کرازی",
                "side": "buy",
                "quantity": 0,
                "price": 0,
                "use_ceiling_price": True,
                "use_max_quantity": True,
                "action_type": "draft"
            },
            "schedule": {
                "enabled": True,
                "target_time": "08:45:00.000",
                "max_attempts": 3,
                "interval_ms": 200,
                "dynamic_ping_compensation": True,
                "ping_lookback_seconds": 30,
                "ping_samples": 5,
                "manual_offset_ms": 0
            },
            "anti_detection": {
                "random_delay_min_ms": 60,
                "random_delay_max_ms": 180,
                "human_mouse_movement": True
            },
            "storage": {
                "save_stocks_data": True,
                "output_dir": "./stocks_data"
            }
        }

    def test_load_valid_config(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
            yaml.dump(self.valid_data, tf)
            tmp_path = tf.name

        try:
            cfg = Config(tmp_path)
            self.assertEqual(cfg.order.symbol, "کرازی")
            self.assertEqual(cfg.order.action_type, "draft")
            self.assertTrue(cfg.order.use_max_quantity)
            self.assertTrue(cfg.schedule.dynamic_ping_compensation)
            self.assertEqual(cfg.schedule.ping_lookback_seconds, 30)
            self.assertEqual(cfg.app.connection_mode, "persistent")
            self.assertTrue(cfg.storage.save_stocks_data)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_missing_config_file(self):
        with self.assertRaises(FileNotFoundError):
            Config("non_existent_path_to_config.yaml")

    def test_dataclasses_structure(self):
        self.assertTrue(is_dataclass(AppConfig))
        self.assertTrue(is_dataclass(OrderConfig))
        self.assertTrue(is_dataclass(ScheduleConfig))
        self.assertTrue(is_dataclass(AntiDetectionConfig))
        self.assertTrue(is_dataclass(StorageConfig))

if __name__ == "__main__":
    unittest.main()
