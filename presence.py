"""Shared "who is home" check used by main.py and homenow.py.

- Everyone is checked in parallel, so total time is the slowest single check, not the sum.
- Each check stops at the first ping reply (a phone that is home costs ~10ms); only a
  phone that is away uses up all the attempts.
- Phones that sleep and ignore ping are still caught via the ARP/neighbour table if the
  person has an optional "mac" in config.json (e.g. "mac":"aa:bb:cc:dd:ee:ff").

Optional config.json keys: "ping_attempts" (default 3), "ping_timeout_seconds" (default 1).
"""
import platform
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor

IS_WINDOWS = platform.system() == "Windows"
MAC_RE = re.compile(r"^[0-9a-fA-F]{2}([:-][0-9a-fA-F]{2}){5}$")


def _run(cmd, timeout):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
        return (r.stdout or "")
    except Exception:
        return ""


def _norm_mac(mac):
    return re.sub(r"[^0-9a-f]", "", str(mac).lower())


def _ping_once(ip, timeout_s):
    if IS_WINDOWS:
        cmd = ["ping", "-n", "1", "-w", str(int(timeout_s * 1000)), ip]
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, int(timeout_s))), ip]
    out = _run(cmd, timeout_s + 3)
    # A TTL only appears on a genuine reply from the target; "Destination host unreachable"
    # replies from the router (which Windows exit codes can treat as success) have none.
    return "ttl=" in out.lower()


def _arp_lookup(ip):
    """Return the normalised MAC the OS currently holds for this IP, or None."""
    if IS_WINDOWS:
        for line in _run(["arp", "-a", ip], 5).splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == ip and MAC_RE.match(parts[1]):
                return _norm_mac(parts[1])
    else:
        parts = _run(["ip", "neigh", "show", ip], 5).split()
        # STALE/FAILED/INCOMPLETE mean "not recently confirmed" - don't trust them
        if "lladdr" in parts and parts[-1].upper() not in ("STALE", "FAILED", "INCOMPLETE"):
            return _norm_mac(parts[parts.index("lladdr") + 1])
    return None


def _flush_arp(ip):
    """Clear the cached entry so any entry we see later is fresh. Returns True only if the
    entry is verifiably gone (arp -d needs admin and exits 0 even when it fails)."""
    if IS_WINDOWS:
        _run(["arp", "-d", ip], 5)
    else:
        _run(["ip", "neigh", "del", ip], 5)
    return _arp_lookup(ip) is None


def _check_person(person, attempts, timeout_s):
    ip = person["ip"]
    mac = person.get("mac")

    # Windows can't report whether an ARP entry is fresh, so the fallback is only
    # trusted there if the flush worked. Linux ignores STALE entries, so it's always safe.
    arp_ok = False
    if mac:
        arp_ok = _flush_arp(ip) or not IS_WINDOWS

    for _ in range(attempts):
        if _ping_once(ip, timeout_s):
            return True, "ping"

    if arp_ok and _arp_lookup(ip) == _norm_mac(mac):
        return True, "arp"

    if mac and not arp_ok:
        return False, "none (arp skipped: cannot flush cache, run as admin/SYSTEM)"
    return False, "none"


def check_presence(config):
    """Returns (home, not_home, details) where details maps name -> 'ping'|'arp'|'none'."""
    people = config["people"]
    attempts = int(config.get("ping_attempts", 3))
    timeout_s = float(config.get("ping_timeout_seconds", 1))

    home, not_home, details = set(), set(), {}
    if not people:
        return home, not_home, details

    with ThreadPoolExecutor(max_workers=len(people)) as pool:
        futures = [(p["name"], pool.submit(_check_person, p, attempts, timeout_s)) for p in people]
        for name, fut in futures:
            try:
                is_home, how = fut.result()
            except Exception as e:
                is_home, how = False, "error: " + str(e)
            details[name] = how
            (home if is_home else not_home).add(name)

    return home, not_home, details
