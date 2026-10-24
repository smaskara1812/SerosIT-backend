"""The real client address of a request, safe behind a reverse proxy.

Behind a proxy every request arrives from the proxy's own address, and the client's address comes in the X-Forwarded-For header. That header is
only to be believed when the request really came from OUR proxy: anyone can send the header themselves. So set TRUSTED_PROXIES (environment
variable, comma-separated addresses or networks, for example "10.0.0.5,10.1.0.0/16") to the proxy's address(es). Then the address is the last one in
X-Forwarded-For that is not a trusted proxy. With TRUSTED_PROXIES empty the header is ignored and REMOTE_ADDR is used (correct without a proxy; behind
a proxy it would make every user look like one address, so set it)."""

import ipaddress
import os

_NETS = None


def _trusted():
    global _NETS
    if _NETS is None:
        nets = []
        for part in os.getenv("TRUSTED_PROXIES", "").split(","):
            part = part.strip()
            if part:
                try:
                    nets.append(ipaddress.ip_network(part, strict=False))
                except ValueError:
                    pass
        _NETS = nets
    return _NETS


def _is_trusted(addr):
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    return any(ip in n for n in _trusted())


def client_ip(request):
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    if remote and _is_trusted(remote):
        chain = [p.strip() for p in (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",") if p.strip()]
        for addr in reversed(chain):
            try:
                ipaddress.ip_address(addr)
            except ValueError:
                continue
            if not _is_trusted(addr):
                return addr[:45]
    return remote[:45] or "unknown"
