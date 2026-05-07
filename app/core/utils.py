from fastapi import Request


def get_client_ip(request: Request) -> str:
    """
    Extracts the real client IP, prioritizing X-Forwarded-For (from Vercel/Nginx)
    over the direct client host.
    """
    # X-Forwarded-For can contain multiple IPs, the first one is the real client
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


def get_client_country(request: Request) -> str | None:
    """
    Extracts the country code from Vercel's X-Vercel-IP-Country header.
    """
    return request.headers.get("x-vercel-ip-country")
