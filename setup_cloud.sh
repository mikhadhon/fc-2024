#!/bin/bash
sudo apt update -y
sudo apt upgrade -y
sudo apt-get install curl gnupg2 wget git apt-transport-https ca-certificates python3-pip mosquitto -y
# python dependency
pip install paho-mqtt
# Stop broker running as system service to start it manually
sudo systemctl stop mosquitto
# run broker
# mosquitto -c mosquitto.conf -v