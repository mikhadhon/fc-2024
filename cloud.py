import time
import random
import json
import paho.mqtt.client as mqtt
import threading
import queue

from dataclasses import dataclass, field


# MQTT client setup
MQTT_BROKER = '0.0.0.0'
MQTT_PORT = 1883
MQTT_TOPIC = 'environment/telemetry'
MQTT_TOPIC_2 = 'environment/recommendation'
MQTT_TOPIC_3 = 'environment/connection'
SLEEP_DURATION = 10
client = mqtt.Client()

last_message = float("inf")

@dataclass(order=True)
class PrioritizedData:
    priority: float
    item: dict=field(compare=False)

data_queue = queue.PriorityQueue()
ketchup_queue = queue.Queue()


def on_connect(client, userdata, flags, rc):
    global last_message
    if rc == 0:
        print("Connected to MQTT Broker!")
        client.publish(MQTT_TOPIC_3, "online")
        while not ketchup_queue.empty():
            data = ketchup_queue.get()
            response = client.publish(MQTT_TOPIC_2, json.dumps(data))
            try:
                response.is_published()
            except RuntimeError as e:
                print(f"Failed to send data: {e}")
                ketchup_queue.put(data)
        last_message = float("inf")
    else:
        print("Failed to connect, return code %d\n", rc)


def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT Broker")


def on_publish(client, userdata, mid):
    print("Data published")


def on_message(client, userdata, msg):
    global last_message
    if msg.topic == MQTT_TOPIC_3:
        client.unsubscribe(MQTT_TOPIC_3)
        last_message = float("inf")
    else:
        data = json.loads(msg.payload)
        last_message = data["timestamp"]
        print(data)
        prioritized_data = PrioritizedData(-data["timestamp"], data)
        data_queue.put(prioritized_data)


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_message = on_message

client.user_data_set(queue.PriorityQueue())
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC)
client.loop_start()


def collect_and_send_data():
    while True:
        if not data_queue.empty():
            d_last_msg = time.time() - last_message
            print(f"delta: {d_last_msg}")
            data = {
                "cpu_offset_factor": calculate_recommendation("cpu_temp"),
                "gpu_offset_factor": calculate_recommendation("gpu_temp"),
                "timestamp": time.time()
            }
            if data == {}:
                time.sleep(SLEEP_DURATION)
                continue
            if client.is_connected() and d_last_msg < 2*SLEEP_DURATION:
                response = client.publish(MQTT_TOPIC_2, json.dumps(data))
                try:
                    response.is_published()
                except RuntimeError as e:
                    print(f"Failed to send data: {e}")
                    ketchup_queue.put(data)
            else:
                print("Offline")
                ketchup_queue.put(data)
                client.subscribe(MQTT_TOPIC_3)

            data = {}
            time.sleep(SLEEP_DURATION)

def calculate_mean(elements, key):
    return sum(item.item[key] for item in elements) / len(elements)
def calculate_recommendation(key):
    # if durchschnitt der letzten 3 temps höher als 80: reduce freq by 200
    # newest_three = list(data_queue.queue)[:3]
    if calculate_mean(list(data_queue.queue)[:3], key) > 70:
        return -0.05
    if calculate_mean(list(data_queue.queue)[:3], key) < 65:
        return 0.05
    else:
        return 0


data_thread = threading.Thread(target=collect_and_send_data)

data_thread.start()
