
# Home Alarm System

## Description

This project is for one or more ESP32 with a 433Mhz radio reciever which publishes messages from sensors to an MQTT server
A python service then consumes messages and sends notifications when no-ones phone is on the network, i.e you're not home.

## Thingiverse

Cases for the ESP32(USB-C) and Reciever Board:

https://www.thingiverse.com/thing:6879482

https://www.thingiverse.com/thing:6879572

You wanna cable between pins

Reciever Data - ESP32 D27

Reciever +5V - ESP32 vin

Reciever GND - ESP32 gnd

## Prerequisites

Programming Language -

python 3.x

Python Modules -

paho-mqtt

## Getting started

```

pip install -r requirements.txt

fill out config_example.json and rename to config.json
fill out arduino_secrets_example.h and rename it arduino_secrets.h

Install alarm.service in /etc/systemd/system/
sudo systemctl enable alarm.service

if you change anything:
sudo systemctl stop alarm.service
sudo systemctl start alarm.service

Enable 2FA then go here to setup App Credentials: https://myaccount.google.com/apppasswords

```

## Presence detection

Two services run side by side: `alarm.service` (main.py, handles sensors and notifications) and `homenow.service` (homenow.py, publishes who is home to `alarm/homenow` every minute). Install both in /etc/systemd/system/. Both use `presence.py` to decide who is home.

How a phone is found:

1. Ping, up to `ping_attempts` times (default 3, `ping_timeout_seconds` default 1) - stops at the first reply. Everyone is checked in parallel.
2. If the person has a `"mac"` in config.json and ping fails, the ARP/neighbour table is checked. This catches phones that sleep and ignore ping but still answer ARP.

```
"people":[{"name":"John","ip":"192.168.1.20","mac":"aa:bb:cc:dd:ee:ff", ...}]
```

Notes:

- Use the phone's wifi MAC for your home network, and set the phone to use its device MAC (not a private/rotating one) for that network, otherwise the MAC will change.
- Linux needs the `ip` command (package `iproute2`). Check it works with `ip neigh show`.
- On Windows the ARP fallback only runs if the service is elevated (admin/SYSTEM), because the ARP cache has to be cleared to be sure an entry is fresh. If it can't, the fallback is skipped and `arp skipped` appears in the debug output; ping still works.
- `alarm/homenowdebug` publishes how each person was detected, e.g. `{'John': 'ping', 'Doe': 'arp'}` (`none` = not found).
- You get an "X is home" notification either when the exit sensor sees their phone, or - if the phone wasn't on wifi yet - a minute or two later when homenow sees it (`Late arrival detected via homenow` in the log).

## Watching the watcher

If `homenow` goes quiet the alarm can't arm itself when you leave, so there are two safeguards:

- `main.py` expects an `alarm/homenow` message every minute or so. If nothing arrives for `homenow_silent_seconds` (default 300) it emails/texts everyone once ("homenow silent"), and again when updates resume ("homenow is back").
- `homenow.service` is `Type=notify` with `WatchdogSec=180`: `homenow.py` tells systemd it's alive on every loop (see `sdnotify.py`) and systemd restarts it if it hangs. `homenow.py` also exits (so systemd restarts it) if it can't stay connected to the MQTT broker for about 5 minutes.

After changing a `.service` file, reinstall it:

```
sudo cp homenow.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl restart homenow
```

## Testing

```
python3 test_homenow.py          # unit tests, no network needed
python3 test_homenow.py --live   # run the real check against config.json
python3 test_send.py             # send a test email/text to the first person
```

## Usage

In beta test, more instructions one day. For now this repo is for my beta testers so if you can't make sense of it, yeah sorry, not ready yet.

