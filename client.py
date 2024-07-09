import time
import random
import json
import paho.mqtt.client as mqtt
import threading
import queue

gpu_base_freq = 2750
cpu_base_freq = 4600

gpu_freq_offset_factor = 1
cpu_freq_offset_factor = 1

last_message = float("inf")


# Virtual sensors
def gpu_temp_sensor():
    return round((((70.0 + random.uniform(-10, 20)) * gpu_freq_offset_factor)), 2)
def cpu_temp_sensor():
    return round((((80.0 + random.uniform(-10, 20)) * cpu_freq_offset_factor)), 2)
def gpu_freq_sensor():
    return round(gpu_base_freq * gpu_freq_offset_factor, 2)
def cpu_freq_sensor():
    return round(cpu_base_freq * cpu_freq_offset_factor, 2)


# MQTT client setup
MQTT_BROKER = '127.0.0.1'
MQTT_PORT = 1883
MQTT_TOPIC = 'environment/telemetry'
MQTT_TOPIC_2 = 'environment/recommendation'
MQTT_TOPIC_3 = 'environment/connection'
SLEEP_DURATION = 10
client = mqtt.Client()

data_queue = queue.Queue()
ketchup_queue = queue.Queue()

def send_ketchup():
    print("Sending ketchup")
    while not ketchup_queue.empty():
        data = ketchup_queue.get()
        response = client.publish(MQTT_TOPIC, json.dumps(data))
        try:
            response.is_published()
        except RuntimeError as e:
            print(f"Failed to send data: {e}")
            ketchup_queue.put(data)

def on_connect(client, userdata, flags, rc):
    global last_message
    if rc == 0:
        print("Connected to MQTT Broker!")
        send_ketchup()
        last_message = float("inf")

    else:
        print("Failed to connect, return code %d\n", rc)


def on_disconnect(client, userdata, rc):
    print("Disconnected from MQTT Broker")


def on_publish(client, userdata, mid):
    print("Data published")


def on_message(client, userdata, msg):
    global gpu_freq_offset_factor, cpu_freq_offset_factor, last_message
    if msg.topic == MQTT_TOPIC_3:
        client.unsubscribe(MQTT_TOPIC_3)
        last_message = float("inf")
    else:
        if not ketchup_queue.empty():
            print("Cloud is back")
            send_ketchup()

        data = json.loads(msg.payload)
        gpu_freq_offset_factor += data["gpu_offset_factor"]
        cpu_freq_offset_factor += data["cpu_offset_factor"]
        last_message = data["timestamp"]


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_message = on_message

client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC_2)
client.loop_start()


def collect_and_send_data():
    while True:
        d_last_msg = time.time() - last_message
        print(f"delta: {d_last_msg}")
        data = {
            'gpu_temp': gpu_temp_sensor(),
            'cpu_temp': cpu_temp_sensor(),
            'gpu_freq': gpu_freq_sensor(),
            'cpu_freq': cpu_freq_sensor(),
            'timestamp': time.time()
        }
        print(data)
        if data == {}:
            time.sleep(SLEEP_DURATION)
            continue
        if client.is_connected() and d_last_msg < 2*SLEEP_DURATION:
            response = client.publish(MQTT_TOPIC, json.dumps(data))
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


data_thread = threading.Thread(target=collect_and_send_data)

data_thread.start()
