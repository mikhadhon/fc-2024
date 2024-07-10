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
    """
    A class for storing data with priority for the priority queue.

    Attributes:
        priority (float): The priority of the data.
        item (dict): The actual data.
    """
    priority: float
    item: dict = field(compare=False)


data_queue = queue.PriorityQueue()
ketchup_queue = queue.Queue()


def on_connect(client, userdata, flags, rc):
    """
    Callback function for when the client connects to the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        flags: Response flags sent by the broker.
        rc (int): The connection result.
    """
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
        client.subscribe(MQTT_TOPIC)
    else:
        print("Failed to connect, return code %d\n", rc)


def on_disconnect(client, userdata, rc):
    """
    Callback function for when the client disconnects from the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        rc (int): The disconnection result.
    """
    print("Disconnected from MQTT Broker")


def on_publish(client, userdata, mid):
    """
    Callback function for when a message is published.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        mid (int): The message ID.
    """
    print("Data published")


def on_message(client, userdata, msg):
    """
    Callback function for when a message is received from the MQTT broker.

    Parameters:
        client (Client): The MQTT client instance.
        userdata: The private user data.
        msg (MQTTMessage): The received message.
    """
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
    """
    Collects data from virtual sensors and sends back a recommendation to the MQTT broker.
    """
    global last_message
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
            if client.is_connected() and d_last_msg < 2 * SLEEP_DURATION:
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
    """
    Calculates the mean of a given key from a list of elements.

    Parameters:
        elements (list): The list of elements.
        key (str): The key for which the mean is calculated.

    Returns:
        float: The mean value.
    """
    return sum(item.item[key] for item in elements) / len(elements)


def calculate_recommendation(key):
    """
    Calculates the recommendation for adjusting the offset factor based on temperature readings.

    Parameters:
        key (str): The key for which the recommendation is calculated.

    Returns:
        float: The recommended offset adjustment.
    """
    # If the average of the last 3 temperatures is higher than 70, reduce the frequency by a factor of 0.05
    if calculate_mean(list(data_queue.queue)[:3], key) > 70:
        return -0.05
    # If the average of the last 3 temperatures is lower than 65, increase the frequency bya factor of 0.05
    if calculate_mean(list(data_queue.queue)[:3], key) < 65:
        return 0.05
    # Otherwise, no change
    else:
        return 0


# Start the data collection and sending thread
data_thread = threading.Thread(target=collect_and_send_data)
data_thread.start()
