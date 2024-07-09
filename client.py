import time
import random
import json
import paho.mqtt.client as mqtt
import threading
import queue

# Base frequencies for GPU and CPU
gpu_base_freq = 2750
cpu_base_freq = 4600

# Frequency offset factors for GPU and CPU
gpu_freq_offset_factor = 1
cpu_freq_offset_factor = 1

# Timestamp of the last received message
last_message = float("inf")


# Virtual sensors
def gpu_temp_sensor():
    """
    Simulates a GPU temperature sensor reading.

    Returns:
        float: Simulated GPU temperature multiplied by gpu_freq_offset_factor.
    """
    return round((((70.0 + random.uniform(-10, 20)) * gpu_freq_offset_factor)), 2)

def cpu_temp_sensor():
    """
    Simulates a CPU temperature sensor reading.

    Returns:
        float: Simulated CPU temperature multiplied by cpu_freq_offset_factor.
    """
    return round((((80.0 + random.uniform(-10, 20)) * cpu_freq_offset_factor)), 2)

def gpu_freq_sensor():
    """
    Simulates a GPU frequency sensor reading.

    Returns:
        float: Simulated GPU frequency multiplied by gpu_freq_offset_factor.
    """
    return round(gpu_base_freq * gpu_freq_offset_factor, 2)

def cpu_freq_sensor():
    """
    Simulates a CPU frequency sensor reading.

    Returns:
        float: Simulated CPU frequency multiplied by cpu_freq_offset_factor.
    """
    return round(cpu_base_freq * cpu_freq_offset_factor, 2)


# MQTT client setup
MQTT_BROKER = '34.38.244.15'
MQTT_PORT = 1883
MQTT_TOPIC = 'environment/telemetry'
MQTT_TOPIC_2 = 'environment/recommendation'
MQTT_TOPIC_3 = 'environment/connection'
SLEEP_DURATION = 10
client = mqtt.Client()

# Queues for data and unsent data (ketchup queue)
data_queue = queue.Queue()
ketchup_queue = queue.Queue()

def send_ketchup():
    """
    Sends all unsent data in the ketchup_queue to the MQTT broker.
    """
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
    """
    Callback when the client connects to the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        flags: Response flags sent by the broker.
        rc (int): The connection result.
    """
    global last_message
    if rc == 0:
        print("Connected to MQTT Broker!")
        send_ketchup()
        last_message = float("inf")
    else:
        print("Failed to connect, return code %d\n", rc)

def on_disconnect(client, userdata, rc):
    """
    Callback when the client disconnects from the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        rc (int): The disconnection result.
    """
    print("Disconnected from MQTT Broker")

def on_publish(client, userdata, mid):
    """
    Callback when a message is published.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        mid (int): The message ID.
    """
    print("Data published")

def on_message(client, userdata, msg):
    """
    Callback when a message is received from the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        msg (MQTTMessage): The received message.
    """
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

# Set MQTT client callbacks
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_message = on_message

# Connect to the MQTT broker and start the loop
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.subscribe(MQTT_TOPIC_2)
client.loop_start()

def collect_and_send_data():
    """
    Collects data from virtual sensors and sends it to the MQTT broker.
    """
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
        if client.is_connected() and d_last_msg < 2 * SLEEP_DURATION:
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

# Start the data collection and sending thread
data_thread = threading.Thread(target=collect_and_send_data)
data_thread.start()
