"""Android devices of Yume Companion: pairing (QR code), per-device tokens, and the command channel to the phone.

* A pairing code is created on the PC, shown as a QR code and valid for a few minutes, exactly once.
* The phone exchanges it for its own long-lived device token (stored hashed here, revocable per device).
* While a phone is connected over the WebSocket, tools can send commands to it (open apps, read the screen, ...).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import socket
import threading
import time
import uuid
from pathlib import Path
from urllib.parse import urlencode

logger = logging.getLogger("MobileDevices")

DEVICES_FILE = Path("app") / "configuration" / "android_devices.json"
PAIR_TTL_SECONDS = 180
BRIDGE = None            # the running WebBridge (set by web_server.WebBridge)
LAST_CONTACT = {"ip": "", "t": 0.0, "what": ""}   # last request of a phone (ping / pairing): helps to see whether the phone reaches the PC at all


def _hash(token: str) -> str:
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


class DeviceRegistry:
    def __init__(self, path: Path = DEVICES_FILE):
        self.path = path
        self._lock = threading.Lock()
        self._codes: dict[str, float] = {}
        self._data = {"devices": []}
        self._last_seen_write = 0.0
        self._load()

    # ------------------------------------------------------------------ storage
    def _load(self):
        try:
            if self.path.is_file():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("android_devices.json could not be read; starting empty", exc_info=True)
            self._data = {"devices": []}
        self._data.setdefault("devices", [])

    def _save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except Exception:
            logger.warning("android_devices.json could not be saved", exc_info=True)

    # ------------------------------------------------------------------ pairing
    def new_pair_code(self, ttl: int = PAIR_TTL_SECONDS) -> tuple[str, float]:
        with self._lock:
            now = time.time()
            self._codes = {c: e for c, e in self._codes.items() if e > now}
            code = secrets.token_hex(5).upper()          # 10 hex characters, single use
            self._codes[code] = now + ttl
            return code, now + ttl

    def consume_code(self, code: str) -> bool:
        code = (code or "").strip().upper()
        with self._lock:
            now = time.time()
            self._codes = {c: e for c, e in self._codes.items() if e > now}
            for known in list(self._codes):
                if secrets.compare_digest(known, code):
                    del self._codes[known]
                    return True
        return False

    def add_device(self, name: str, device_id: str | None = None) -> tuple[str, dict]:
        token = secrets.token_urlsafe(32)
        device = {
            "id": (device_id or uuid.uuid4().hex)[:64],
            "name": (name or "Android").strip()[:60] or "Android",
            "token_hash": _hash(token),
            "created": time.time(),
            "last_seen": time.time(),
        }
        with self._lock:
            self._data["devices"] = [d for d in self._data["devices"] if d["id"] != device["id"]] + [device]
            self._save()
        return token, {k: v for k, v in device.items() if k != "token_hash"}

    # ------------------------------------------------------------------ tokens
    def verify(self, token: str):
        if not token:
            return None
        digest = _hash(token)
        with self._lock:
            for d in self._data["devices"]:
                if secrets.compare_digest(d["token_hash"], digest):
                    now = time.time()
                    d["last_seen"] = now
                    if now - self._last_seen_write > 60:       # avoid rewriting the file on every request
                        self._last_seen_write = now
                        self._save()
                    return {k: v for k, v in d.items() if k != "token_hash"}
        return None

    def list_devices(self) -> list[dict]:
        with self._lock:
            return [{k: v for k, v in d.items() if k != "token_hash"} for d in self._data["devices"]]

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            before = len(self._data["devices"])
            self._data["devices"] = [d for d in self._data["devices"] if d["id"] != device_id]
            changed = len(self._data["devices"]) != before
            if changed:
                self._save()
        if changed and BRIDGE is not None:
            try:
                BRIDGE.drop_device_sockets(device_id)
            except Exception:
                logger.debug("could not drop sockets", exc_info=True)
        return changed


_registry: DeviceRegistry | None = None


def get_registry() -> DeviceRegistry:
    global _registry
    if _registry is None:
        _registry = DeviceRegistry()
    return _registry


# ---------------------------------------------------------------------- host identity + QR payload
def host_id(settings) -> str:
    value = settings.get_main_setting("android_host_id")
    if not value:
        value = uuid.uuid4().hex
        settings.update_main_setting("android_host_id", value)
    return str(value)


_VIRTUAL_ADAPTERS = ("vmware", "virtualbox", "vbox", "vethernet", "hyper-v", "nordlynx", "openvpn", "wireguard", "tailscale", "zerotier",
                     "tap-", "tun", "bluetooth", "loopback", "docker", "wsl", "hamachi", "radmin", "pseudo")


def lan_addresses() -> list[str]:
    """IPv4 addresses of real network adapters (no VPN / VMware / Hyper-V / link-local), best candidate first."""
    found: list[str] = []
    try:
        import psutil
        stats = psutil.net_if_stats()
        for name, addrs in psutil.net_if_addrs().items():
            low = name.lower()
            if any(v in low for v in _VIRTUAL_ADAPTERS) or not (stats.get(name) and stats[name].isup):
                continue
            for a in addrs:
                if a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.", "0.")):
                    found.append(a.address)
    except Exception:
        try:
            found = [i for i in socket.gethostbyname_ex(socket.gethostname())[2] if not i.startswith(("127.", "169.254."))]
        except Exception:
            found = []
    route = ""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        route = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    found.sort(key=lambda ip: (ip != route, not ip.startswith("192.168."), not ip.startswith(("10.", "172."))))
    if route and route not in found and not found and not route.startswith(("127.", "169.254.")):
        found.append(route)
    return found


def best_local_ip() -> str:
    ips = lan_addresses()
    return ips[0] if ips else "127.0.0.1"


def own_ip_addresses() -> set[str]:
    """Every IPv4 address of this PC (used to recognise an outdated stored local address)."""
    out = {"127.0.0.1"}
    try:
        import psutil
        for addrs in psutil.net_if_addrs().values():
            out.update(a.address for a in addrs if a.family == socket.AF_INET)
    except Exception:
        try:
            out.update(socket.gethostbyname_ex(socket.gethostname())[2])
        except Exception:
            pass
    return out


def fresh_local_url(stored: str, port: int) -> str:
    """The stored local URL, unless it points to an IP this PC does not have any more (e.g. a router address or an old DHCP lease)."""
    import ipaddress
    from urllib.parse import urlparse
    stored = (stored or "").strip().rstrip("/")
    if stored:
        host = urlparse(stored).hostname or ""
        try:
            ipaddress.ip_address(host)
            if host in own_ip_addresses():
                return stored
        except ValueError:
            return stored                       # a host name: the user knows better
    return f"http://{best_local_ip()}:{port}"


def host_name() -> str:
    try:
        return socket.gethostname()
    except OSError:
        return "Yume-PC"


def mac_addresses() -> list[str]:
    """MAC of the adapters that have an IPv4 address (for Wake-on-LAN from the phone)."""
    out: list[str] = []
    try:
        import psutil
        for name, addrs in psutil.net_if_addrs().items():
            low = name.lower()
            if any(x in low for x in ("vmware", "virtualbox", "vethernet", "loopback", "bluetooth", "wsl", "docker", "tailscale")):
                continue
            has_ip = any(a.family == socket.AF_INET and not a.address.startswith(("127.", "169.254.")) for a in addrs)
            for a in addrs:
                if a.family == getattr(psutil, "AF_LINK", -1) and has_ip:
                    mac = a.address.replace("-", ":").lower()
                    if len(mac) == 17 and mac not in out:
                        out.append(mac)
    except Exception:
        logger.debug("MAC detection failed", exc_info=True)
    return out


def build_pair_url(settings, local_url: str, remote_url: str) -> tuple[str, float, str]:
    """yume://pair?... for the QR code. Returns (url, expires_at, code)."""
    code, expires = get_registry().new_pair_code()
    params = {
        "v": "1", "h": host_id(settings), "n": host_name(), "c": code,
        "l": (local_url or "").rstrip("/"), "e": (remote_url or "").rstrip("/"),
    }
    macs = mac_addresses()
    if macs:
        params["m"] = ",".join(macs)
    return "yume://pair?" + urlencode(params), expires, code


# ---------------------------------------------------------------------- phone command channel
def phone_connected() -> bool:
    return BRIDGE is not None and BRIDGE.has_phone()
