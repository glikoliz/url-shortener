import logging

from fastapi import Request

from app.config import settings

logger = logging.getLogger(__name__)

_geoip_reader = None


def get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP, prioritizing X-Forwarded-For (from Proxy/Nginx)
    over the direct client host.
    """
    # 1. Check X-Forwarded-For (Standard for proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    # 2. Check X-Real-IP (Alternative)
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip

    return request.client.host if request.client else "unknown"


def get_client_country(request: Request) -> str | None:
    """
    Extracts the country code using a multi-layered approach:
    1. HTTP Headers (Standard for proxies/CDNs like Cloudflare)
    2. Local GeoIP database (Fallback: for portable deployments)
    """
    # 1. Header-based detection
    # Cloudflare
    cf_country = request.headers.get("cf-ipcountry")
    if cf_country:
        return cf_country

    # Generic/Nginx GeoIP module
    x_country = request.headers.get("x-country-code")
    if x_country:
        return x_country

    # 2. Local GeoIP Fallback
    if settings.geoip_path:
        return _get_country_from_geoip(get_client_ip(request))

    return None


def _get_country_from_geoip(ip: str) -> str | None:
    global _geoip_reader
    try:
        import geoip2.database

        if _geoip_reader is None:
            _geoip_reader = geoip2.database.Reader(settings.geoip_path)

        response = _geoip_reader.country(ip)
        return response.country.iso_code
    except ImportError:
        logger.debug("geoip2 library not installed. Skipping local GeoIP lookup.")
    except Exception as e:
        logger.debug(f"GeoIP lookup failed for IP {ip}: {e}")

    return None
