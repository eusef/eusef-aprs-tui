"""mDNS service discovery for KISS TNC servers."""
from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SERVICE_TYPE = "_kiss-tnc._tcp.local."


@dataclass
class DiscoveredService:
    """A discovered KISS TNC service."""
    name: str
    host: str
    port: int
    reachable: bool = False


async def discover_kiss_servers(timeout: float = 3.0) -> list[DiscoveredService]:
    """Scan for KISS TNC servers via mDNS.

    Uses zeroconf AsyncServiceBrowser to find _kiss-tnc._tcp services.
    Each discovered service is TCP-tested before being returned.
    Returns empty list on any error (graceful fallback).

    Args:
        timeout: Browse duration in seconds (default 3.0)
    """
    try:
        from zeroconf import ServiceBrowser, Zeroconf
    except ImportError:
        logger.debug("zeroconf not installed, skipping mDNS discovery")
        return []

    services: list[DiscoveredService] = []
    found_names: list[tuple[str, str]] = []  # (service_type, name)

    class Listener:
        def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            found_names.append((type_, name))
        def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass
        def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
            pass

    zc = Zeroconf()
    listener = Listener()
    browser = ServiceBrowser(zc, SERVICE_TYPE, listener)

    try:
        await asyncio.sleep(timeout)

        for type_, name in found_names:
            info = zc.get_service_info(type_, name)
            if info and info.addresses:
                host = socket.inet_ntoa(info.addresses[0])
                port = info.port or 8001
                svc = DiscoveredService(
                    name=info.server or name,
                    host=host,
                    port=port,
                )
                # TCP test
                svc.reachable = await _test_tcp(host, port)
                services.append(svc)
    except Exception as e:
        logger.debug("mDNS discovery error: %s", e)
    finally:
        browser.cancel()
        zc.close()

    return services


async def _test_tcp(host: str, port: int, timeout: float = 2.0) -> bool:
    """Quick TCP connection test to verify a discovered service is reachable."""
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout)
        writer.close()
        await writer.wait_closed()
        return True
    except (ConnectionRefusedError, OSError, TimeoutError):
        return False
