
# Home Alarm System

## Description

This project is for one or more ESP32 with a 433Mhz radio reciever which publishes messages from sensors to an MQTT server
A python service then consumes messages and sends notifications when no-ones phone is on the network, i.e you're not home.

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

```

## Usage

In beta test, more instructions one day. For now this repo is for my beta testers so if you can't make sense of it, yeah sorry, not ready yet.

