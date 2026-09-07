import asyncio
import time
from datetime import datetime, timedelta
from typing import Optional, Union, Any
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
                tick_local_time = datetime.now()
                server_tick_dt = self.parse_hms(current_text)

                if server_tick_dt:
                    diff = (server_tick_dt - tick_local_time).total_seconds()
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

        # Fallback approximate calibration
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


class NetworkLatencyMeasurer:
    """
    Measures round-trip time (RTT / Ping) to EasyTrader server from the browser.
    """
    @staticmethod
    async def measure_ping(page: Page, samples: int = 5) -> float:
        """
        Send lightweight HEAD/GET requests with cache-busting to measure RTT.
        Returns median RTT in milliseconds.
        """
        rtts = []
        for _ in range(samples):
            try:
                rtt = await page.evaluate("""async () => {
                    const start = performance.now();
                    try {
                        await fetch(window.location.origin + '/manifest.json?_=' + Date.now(), { method: 'HEAD', cache: 'no-store' });
                    } catch(e) {
                        try {
                            await fetch(window.location.origin + '/?_=' + Date.now(), { method: 'HEAD', cache: 'no-store' });
                        } catch(err) {}
                    }
                    return performance.now() - start;
                }""")
                if rtt and rtt > 0:
                    rtts.append(rtt)
            except Exception:
                pass
            await asyncio.sleep(0.04)

        if not rtts:
            return 40.0  # Safe default if measurement fails

        rtts.sort()
        median_rtt = rtts[len(rtts) // 2]
        return median_rtt


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
    async def wait_until(cls, schedule_cfg: Any, page: Optional[Page] = None) -> datetime:
        """
        Wait with sub-millisecond precision until target time arrives,
        featuring EasyTrader clock sync and Dynamic Ping Compensation.
        """
        if isinstance(schedule_cfg, str):
            target_str = schedule_cfg
            dynamic_ping = True
            ping_lookback = 30
            ping_samples = 5
            manual_offset_ms = 0
        else:
            target_str = schedule_cfg.target_time
            dynamic_ping = getattr(schedule_cfg, "dynamic_ping_compensation", True)
            ping_lookback = getattr(schedule_cfg, "ping_lookback_seconds", 30)
            ping_samples = getattr(schedule_cfg, "ping_samples", 5)
            manual_offset_ms = getattr(schedule_cfg, "manual_offset_ms", 0)

        # 1. Clock synchronization with #easy-clock-id
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
        print(f"[+] Target Server Arrival Time: {target_str}")
        if dynamic_ping:
            print(f"[+] Dynamic Ping Compensation: ENABLED (Will calibrate in final {ping_lookback}s)")
        print("=" * 60)

        # 2. Main wait loop with dynamic ping calibration in final window
        ping_calibrated = False
        one_way_latency_ms = 0.0

        while True:
            now = clock_sync.get_current_server_time() if clock_sync else datetime.now()
            diff = (target_dt - now).total_seconds()

            # Trigger dynamic ping calibration when entering final lookback window (e.g. last 30 seconds)
            if dynamic_ping and page and not ping_calibrated and 0 < diff <= ping_lookback:
                print("\n" + "-" * 60)
                print(f"[*] Entering final {ping_lookback}s window. Measuring network RTT to EasyTrader...")
                median_rtt = await NetworkLatencyMeasurer.measure_ping(page, samples=ping_samples)
                one_way_latency_ms = (median_rtt / 2.0) + manual_offset_ms
                
                # Shift the trigger time earlier by one-way network latency
                old_target_str = target_dt.strftime('%H:%M:%S.%f')[:-3]
                target_dt = target_dt - timedelta(milliseconds=one_way_latency_ms)
                new_target_str = target_dt.strftime('%H:%M:%S.%f')[:-3]

                print(f"[⚡] Measured Server RTT (Ping): {median_rtt:.1f}ms")
                print(f"[⚡] Estimated One-Way Network Delay: {one_way_latency_ms:.1f}ms")
                print(f"[⚡] Dynamic Trigger Adjusted: {old_target_str} -> {new_target_str}")
                print("-" * 60 + "\n")
                ping_calibrated = True

            # Target reached
            if diff <= 0:
                print(f"\n[!] TARGET TIME REACHED! Firing at Server Time: {now.strftime('%H:%M:%S.%f')[:-3]}")
                if one_way_latency_ms > 0:
                    print(f"[*] (Compensated for {one_way_latency_ms:.1f}ms network transit time to hit server at {target_str})")
                return now

            # Adaptive precision sleep
            if diff > 1.0:
                await asyncio.sleep(min(diff - 0.5, 2.0))
            elif diff > 0.05:
                await asyncio.sleep(0.01)
            else:
                # Busy-wait during the last 50ms for sub-millisecond precision
                pass
