import json
import ssl
import threading
from config import (
    MQTT_ENABLED, MQTT_ENDPOINT, MQTT_PORT, MQTT_CLIENT_ID,
    MQTT_TOPIC, MQTT_CERT_PATH, MQTT_KEY_PATH, MQTT_CA_PATH,
)

_client = None
_lock = threading.Lock()


def _get_client():
    global _client
    if _client is not None:
        return _client
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[MQTT] paho-mqtt no instalado")
        return None

    client = mqtt.Client(client_id=MQTT_CLIENT_ID, protocol=mqtt.MQTTv311)
    client.tls_set(
        ca_certs=MQTT_CA_PATH,
        certfile=MQTT_CERT_PATH,
        keyfile=MQTT_KEY_PATH,
        tls_version=ssl.PROTOCOL_TLSv1_2,
    )
    client.connect(MQTT_ENDPOINT, MQTT_PORT, keepalive=60)
    client.loop_start()
    _client = client
    return _client


def publish(payload: dict) -> bool:
    if not MQTT_ENABLED:
        return False
    with _lock:
        try:
            client = _get_client()
            if client is None:
                return False
            topic = f"{MQTT_TOPIC}/{payload.get('event_id', 'unknown')}"
            result = client.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1)
            return result.rc == 0
        except Exception as exc:
            print(f"[MQTT] Error publicando: {exc}")
            return False


def shutdown() -> None:
    global _client
    if _client:
        _client.loop_stop()
        _client.disconnect()
        _client = None
