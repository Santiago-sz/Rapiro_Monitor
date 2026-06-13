import json
import queue
import signal
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv()

# DB setup MUST happen before TensorFlow imports to avoid OpenSSL conflicts
from cloud_processor import db, setup_db
from cloud_processor.config import (
    ANOMALY_THRESHOLD,
    CNN_THRESHOLD,
    IMG_SIZE,
    MQTT_CLIENT_ID,
    MQTT_ENDPOINT,
)

setup_db.ensure_ready()

import cv2
import numpy as np
from awscrt import auth, io, mqtt
from awsiot import mqtt_connection_builder
from tensorflow import keras

from cloud_processor import light_estimator
from cloud_processor.face_detector import FaceDetector
from cloud_processor.pattern_store import compute_anomaly, update_pattern

WEIGHTS_PATH = PROJECT_ROOT / "ml" / "artifacts" / "pesos.weights.h5"
TOPIC_FRAMES = "rapiro/frames"
TOPIC_COMMANDS = "rapiro/commands"
TOPIC_EVENTS = "rapiro/events"
AWS_REGION = "us-east-1"

COMMAND_COOLDOWN_SEC = 3.0  # segundos entre #M1 consecutivos

def _build_model():
    m = keras.Sequential([
        keras.layers.Input(shape=(IMG_SIZE, IMG_SIZE, 1)),
        keras.layers.Conv2D(32, (3, 3), activation="relu", padding="same"),
        keras.layers.MaxPooling2D(2, 2),
        keras.layers.Conv2D(64, (3, 3), activation="relu", padding="same"),
        keras.layers.MaxPooling2D(2, 2),
        keras.layers.Conv2D(128, (3, 3), activation="relu", padding="same"),
        keras.layers.MaxPooling2D(2, 2),
        keras.layers.Flatten(),
        keras.layers.Dense(128, activation="relu"),
        keras.layers.Dropout(0.5),
        keras.layers.Dense(1, activation="sigmoid"),
    ])
    m.compile(optimizer="adam", loss="binary_crossentropy", metrics=["accuracy"])
    return m


_frame_queue: queue.Queue = queue.Queue(maxsize=5)
_running = True


def _on_frame(topic, payload, **kwargs):
    try:
        _frame_queue.put_nowait(bytes(payload))
    except queue.Full:
        pass


def _build_connection():
    elg = io.EventLoopGroup(1)
    resolver = io.DefaultHostResolver(elg)
    bootstrap = io.ClientBootstrap(elg, resolver)
    credentials = auth.AwsCredentialsProvider.new_default_chain(bootstrap)

    return mqtt_connection_builder.websockets_with_default_aws_signing(
        endpoint=MQTT_ENDPOINT,
        client_bootstrap=bootstrap,
        region=AWS_REGION,
        credentials_provider=credentials,
        client_id="rapiro-monitor-ec2",
        clean_session=False,
        keep_alive_secs=30,
    )


def main() -> None:
    global _running

    last_command_sent = "#M0"
    last_m1_time = 0.0

    print("[EC2] Iniciando servidor de procesamiento...")
    model = _build_model()
    model.load_weights(WEIGHTS_PATH)
    face_det = FaceDetector()

    connection = _build_connection()
    connection.connect().result()
    print("[EC2] Conectado a IoT Core.")

    sub_future, _ = connection.subscribe(
        topic=TOPIC_FRAMES,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=_on_frame,
    )
    sub_future.result()
    print(f"[EC2] Suscripto a {TOPIC_FRAMES}. Esperando frames del RPi...")

    def _shutdown(sig, frame):
        global _running
        _running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    prev_gray = None

    while _running:
        try:
            payload = _frame_queue.get(timeout=1.0)
        except queue.Empty:
            continue

        arr = np.frombuffer(payload, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            continue

        now = datetime.now()
        hour = now.hour

        light_pct = light_estimator.estimate_light(frame)
        face_detected, _ = face_det.detect(frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_resized = cv2.resize(gray, (IMG_SIZE, IMG_SIZE))

        motion_detected = False
        motion_conf = 0.0

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray_resized)
            inp = diff.astype("float32") / 255.0
            inp = inp.reshape(1, IMG_SIZE, IMG_SIZE, 1)
            motion_conf = float(model.predict(inp, verbose=0)[0][0])
            motion_detected = motion_conf > CNN_THRESHOLD

        prev_gray = gray_resized

        motion_val = 1.0 if motion_detected else 0.0
        anomaly_score, alert_level = compute_anomaly(hour, motion_val, light_pct)
        update_pattern(hour, motion_val, light_pct)

        # Debounce: #M1 una vez por evento, #M0 solo al volver a standby
        now_ts = time.time()
        command = None
        if motion_detected:
            if last_command_sent != "#M1" or (now_ts - last_m1_time) > COMMAND_COOLDOWN_SEC:
                command = "#M1"
                last_m1_time = now_ts
        else:
            if last_command_sent != "#M0":
                command = "#M0"

        if command:
            last_command_sent = command
            connection.publish(
                topic=TOPIC_COMMANDS,
                payload=json.dumps({"command": command}),
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )

        event_id = str(uuid.uuid4())
        event = {
            "event_id": event_id,
            "captured_at": now.isoformat(),
            "hour_of_day": hour,
            "motion_detected": motion_detected,
            "motion_confidence": motion_conf,
            "face_detected": face_detected,
            "light_percent": light_pct,
            "alert_level": alert_level,
            "anomaly_score": anomaly_score,
            "rapiro_command": command or last_command_sent,
        }

        # IoT Core → Lambda → DynamoDB
        connection.publish(
            topic=f"{TOPIC_EVENTS}/{event_id}",
            payload=json.dumps(event),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )

        row_id = db.save_event(event)
        if alert_level in ("warning", "critical"):
            db.mark_mqtt_published(row_id)

        print(
            f"[EC2] MOV:{motion_detected}({motion_conf:.2f}) "
            f"CARA:{face_detected} LUZ:{light_pct:.2f} "
            f"ANOMALIA:{anomaly_score:.2f} [{alert_level.upper()}] → {command}"
        )

    connection.disconnect()
    db.close_pool()
    print("[EC2] Servidor detenido.")


if __name__ == "__main__":
    main()
