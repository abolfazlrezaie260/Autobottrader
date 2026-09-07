import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional
from playwright.async_api import Page

class BrowserClockSync:
    """
    Synchronizes scheduling with EasyTrader's live server clock (#easy-clock-id)
    displayed in the browser, measuring exact millisecond offset.
    """
    def __init__(self, page: Page):
        self.page = page
        self.offset_seconds: float = 0.0
        self.is_synced: bool = False

    async def get_clock_text(self) -> Optional[str]:
        """Read the current clock string from EasyTrader DOM"""
        try:
            return await self.page.evaluate(
                "() => document.querySelector('#easy-clock-id')?.innerText.trim() || "
                "document.querySelector('[data-cy=\"order-list-clock\"] span')?.innerText.trim() || null"
            )
        except Exception:
            return None

    @staticmethod
    def parse_hms(hms_str: str) -> Optional[datetime]:
        """Parse HH:MM:SS to a datetime object for today"""
        try:
            parts = [int(p) for p in hms_str.strip().split(":")]
            now = datetime.now()
            return now.replace(hour=parts[0], minute=parts[1], second=parts[2], microsecond=0)
        except Exception:
            return None

    async def calibrate(self, max_wait_seconds: float = 3.0) -> bool:
        """
        Detect the exact moment #easy-clock-id transitions to the next second.
        At that tick transition, the server clock is precisely at .000 milliseconds.
        """
        initial_text = await self.get_clock_text()
        if not initial_text:
            print("[!] Warning: EasyTrader clock (#easy-clock-id) not found in DOM. Using system clock.")
            return False

        print(f"[*] Calibrating with EasyTrader clock (Current display: {initial_text})...")
        start_wait = time.time()
        last_text = initial_text

        # Poll rapidly for the second transition
        while time.time() - start_wait < max_wait_seconds:
            current_text = await self.get_clock_text()
            if current_text and current_text != last_text:
                # The clock just ticked to a new second!
                tick_local_time = datetime.now()
                server_tick_dt = self.parse_hms(current_text)

                if server_tick_dt:
                    diff = (server_tick_dt - tick_local_time).total_seconds()
                    # Handle timezone differences
                    if diff > 43200:
                        server_tick_dt -= timedelta(days=1)
                    elif diff < -43200:
                        server_tick_dt += timedelta(days=1)

                    self.offset_seconds = (server_tick_dt - tick_local_time).total_seconds()
                    self.is_synced = True

                    print(
                        f"[✓] Clock synchronized with EasyTrader: {current_text}.000 "
                        f"(System clock offset: {self.offset_seconds:+.3f}s)"
                    )
                    return True

            await asyncio.sleep(0.01)

        # Fallback if transition was not observed within timeout
        fallback_text = await self.get_clock_text()
        if fallback_text:
            server_dt = self.parse_hms(fallback_text)
            if server_dt:
                self.offset_seconds = (server_dt - datetime.now()).total_seconds()
                self.is_synced = True
                print(f"[✓] Clock calibrated approximately: {fallback_text} (Offset: {self.offset_seconds:+.3f}s)")
                return True

        return False

    def get_current_server_time(self) -> datetime:
        """Returns the current estimated server time based on calibrated offset"""
        if self.is_synced:
            return datetime.now() + timedelta(seconds=self.offset_seconds)
        return datetime.now()

class PrecisionScheduler:
    @staticmethod
    def parse_target_time(target_str: str, base_time: datetime) -> datetime:
        """Convert HH:MM:SS.mmm target time string to a datetime for base_time date"""
        parts = target_str.strip().split(".")
        time_parts = parts[0].split(":")
        
        hour = int(time_parts[0])
        minute = int(time_parts[1])
        second = int(time_parts[2])
        microsecond = int(parts[1]) * 1000 if len(parts) > 1 else 0
        
        target = base_time.replace(hour=hour, minute=minute, second=second, microsecond=microsecond)
        if target < base_time:
            target += timedelta(days=1)
        return target

    @classmethod
    async def wait_until(cls, target_str: str, page: Optional[Page] = None) -> datetime:
        """
        Wait with sub-millisecond precision until target time arrives,
        calibrated against the EasyTrader browser clock (#easy-clock-id).
        """
        clock_sync = None
        if page:
            clock_sync = BrowserClockSync(page)
            await clock_sync.calibrate()

        now_server = clock_sync.get_current_server_time() if clock_sync else datetime.now()
        target_dt = cls.parse_target_time(target_str, now_server)

        clock_source = (
            "EasyTrader Browser Clock (#easy-clock-id)" 
            if (clock_sync and clock_sync.is_synced) 
            else "Local System Clock"
        )
        print("=" * 60)
        print(f"[+] Precision Scheduler Armed")
        print(f"[+] Clock Source: {clock_source}")
        print(f"[+] Current Server Time: {now_server.strftime('%H:%M:%S.%f')[:-3]}")
        print(f"[+] Target Execution Time: {target_str}")
        print("=" * 60)

        while True:
            now = clock_sync.get_current_server_time() if clock_sync else datetime.now()
            diff = (target_dt - now).total_seconds()
            
            if diff <= 0:
                print(f"[!] TARGET TIME REACHED! Execution Server Time: {now.strftime('%H:%M:%S.%f')[:-3]}")
                return now
            
            if diff > 1.0:
                await asyncio.sleep(diff - 0.5)
            elif diff > 0.05:
                await asyncio.sleep(0.01)
            else:
                # Busy-wait during the last 50 milliseconds for sub-millisecond precision
                pass
