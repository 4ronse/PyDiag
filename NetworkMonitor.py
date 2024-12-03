import asyncio
import logging
import psutil

from threading import Lock
from enum import Enum

_LOGGER = logging.getLogger(__name__)

class NetworkMonitor:
    class Unit(Enum):
        Bytes = (1, "B/s")
        KiloBytes = (1_000, "kB/s")
        MegaBytes = (1_000_000, "MB/s")
        GigaBytes = (1_000_000_000, "GB/s")

        def __init__(self, factor, name):
            self.factor = factor
            self.unit_name = name

    def __init__(self, interface='eth0', sample_interval=1):
        self.interface = interface
        self.sample_interval = sample_interval
        self.throughput = {"tx": 0.0, "rx": 0.0}
        self.lock = Lock()

        _LOGGER.debug(f'NetworkMonitor for interface {interface} initiated')

    async def _calculate_throughput(self):
        while True:
            # Get initial stats
            initial_stats = psutil.net_io_counters(pernic=True).get(self.interface, None)
            if not initial_stats:
                raise ValueError(f"Interface '{self.interface}' not found.")

            initial_sent = initial_stats.bytes_sent
            initial_recv = initial_stats.bytes_recv

            # Wait asynchronously for the sample interval
            await asyncio.sleep(self.sample_interval)

            # Get stats again
            final_stats = psutil.net_io_counters(pernic=True).get(self.interface, None)
            if not final_stats:
                raise ValueError(f"Interface '{self.interface}' not found.")

            final_sent = final_stats.bytes_sent
            final_recv = final_stats.bytes_recv

            # Calculate throughput
            bytes_sent_per_second = (final_sent - initial_sent) / self.sample_interval
            bytes_received_per_second = (final_recv - initial_recv) / self.sample_interval

            # Update throughput in a thread-safe manner
            with self.lock:
                self.throughput["tx"] = bytes_sent_per_second
                self.throughput["rx"] = bytes_received_per_second
                _LOGGER.debug(self.throughput)

    async def start_monitoring(self):
        await self._calculate_throughput()

    def get_throughput(self, unit: Unit = Unit.KiloBytes):
        if unit not in self.Unit:
            raise ValueError(f"Invalid unit '{unit}'. Supported units: {list(self.Unit._member_names_)}")

        _LOGGER.debug(self.throughput)
        with self.lock:
            tx = self.throughput["tx"] / unit.factor
            rx = self.throughput["rx"] / unit.factor
            return {"tx": tx, "rx": rx}

