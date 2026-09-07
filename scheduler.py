import asyncio
from datetime import datetime, time, timedelta

class PrecisionScheduler:
    @staticmethod
    def parse_target_time(target_str: str) -> datetime:
        """تبدیل رشته زمان HH:MM:SS.mmm به datetime مربوط به امروز"""
        now = datetime.now()
        parts = target_str.strip().split(".")
        time_parts = parts[0].split(":")
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2])
        microsecond = int(parts[1]) * 1000 if len(parts) > 1 else 0
        
        target = now.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)
        if target < now:
            # اگر زمان امروز گذشته باشد، برای فردا تنظیم می‌شود
            target += timedelta(days=1)
        return target

    @classmethod
    async def wait_until(cls, target_str: str):
        """انتظار با دقت بالا تا رسیدن به زمان هدف"""
        target_dt = cls.parse_target_time(target_str)
        print(f"[+] زمان‌بندی فعال شد. زمان هدف: {target_dt.strftime('%H:%M:%S.%f')[:-3]}")
        
        while True:
            now = datetime.now()
            diff = (target_dt - now).total_seconds()
            
            if diff <= 0:
                print(f"[!] زمان فرارسید! ساعت فعلی: {now.strftime('%H:%M:%S.%f')[:-3]}")
                break
            
            if diff > 1.0:
                await asyncio.sleep(diff - 0.5)
            elif diff > 0.05:
                await asyncio.sleep(0.01)
            else:
                # Busy wait در ۵۰ میلی‌ثانیه پایانی برای دستیابی به حداکثر دقت
                pass
