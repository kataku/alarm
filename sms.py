"""Send an SMS through a USB-connected Android phone using adb.

`adb shell` joins its arguments and hands them to the phone's shell, so the message has to
be quoted for that shell exactly once. We build the phone-side command with shlex.quote()
and run adb with an argument list (no local shell), so any message arrives intact.
"""
import re
import shlex
import subprocess

PHONE_RE = re.compile(r"\+?\d{5,15}")


def build_device_command(phone_number, message):
    """The command line the phone's shell will run (every argument safely quoted)."""
    parts = [
        "service", "call", "isms", "7",
        "i32", "1",
        "s16", "com.android.mms",
        "s16", str(phone_number),
        "s16", "null",
        "s16", str(message),
        "s16", "null",
        "s16", "null",
    ]
    return " ".join(shlex.quote(p) for p in parts)


def send_text(phone_number, message, log=print, timeout=30):
    """Returns True if adb ran and reported no error, False otherwise (and logs why)."""
    phone_number = str(phone_number)
    if not PHONE_RE.fullmatch(phone_number):
        log("text not sent: '" + phone_number + "' is not a valid phone number")
        return False

    cmd = ["adb", "shell", build_device_command(phone_number, message)]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        log("text send to " + phone_number + " failed: adb timed out after " + str(timeout) + "s")
        return False
    except FileNotFoundError:
        log("text send to " + phone_number + " failed: adb not found")
        return False
    except Exception as e:
        log("text send to " + phone_number + " failed: " + repr(e))
        return False

    output = ((result.stdout or "") + (result.stderr or "")).strip()

    if result.returncode != 0 or "exception" in output.lower():
        first_line = output.splitlines()[0] if output else "no output"
        log("text send to " + phone_number + " failed (adb exit " + str(result.returncode) + "): " + first_line[:200])
        return False

    return True
