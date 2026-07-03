"""Optional MQTT output for sensor payloads."""

import json


class MqttPublisher:
    def __init__(self, client, topic):
        self.client = client
        self.topic = topic

    @classmethod
    def from_connection(cls, host, topic, port=1883, client_id="icams-acquisition"):
        import paho.mqtt.client as mqtt

        client = mqtt.Client(client_id=client_id)
        client.connect(host, port)
        client.loop_start()
        return cls(client, topic)

    def publish(self, payload):
        self.client.publish(self.topic, json.dumps(payload))

    def close(self):
        self.client.loop_stop()
        self.client.disconnect()
