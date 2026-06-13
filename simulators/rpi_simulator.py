"""
Simulador del RPi — corre en Windows con tu webcam.
Envía frames al EC2 por MQTT y muestra los comandos que recibiría el Rapiro.
"""
import json
import time
from pathlib import Path

import cv2
import numpy as np
from awscrt import mqtt
from awsiot import mqtt_connection_builder

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ENDPOINT  = "a1ys5hknu5g0j7-ats.iot.us-east-1.amazonaws.com"
CLIENT_ID = "rapiro-monitor-thing"
CERT      = PROJECT_ROOT / "aws" / "terraform" / "certs" / "device.pem.crt"
KEY       = PROJECT_ROOT / "aws" / "terraform" / "certs" / "private.pem.key"
CA        = PROJECT_ROOT / "aws" / "terraform" / "certs" / "AmazonRootCA1.pem"

TOPIC_FRAMES   = "rapiro/frames"
TOPIC_COMMANDS = "rapiro/commands"
FRAME_INTERVAL = 0.5  # 2 fps

last_command = {"cmd": "#M0", "ts": 0.0}


def on_command(topic, payload, **kwargs):
    cmd = json.loads(payload).get("command", "?")
    last_command["cmd"] = cmd
    last_command["ts"] = time.time()
    action = "LEVANTA BRAZOS" if cmd == "#M1" else "BAJA BRAZOS"
    print(f"\n>>> COMANDO: {cmd} — {action}")


def main():
    print("[SIM] Conectando a IoT Core...")
    connection = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=str(CERT),
        pri_key_filepath=str(KEY),
        ca_filepath=str(CA),
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30,
    )
    connection.connect().result()
    print("[SIM] Conectado.")

    sub_future, _ = connection.subscribe(
        topic=TOPIC_COMMANDS,
        qos=mqtt.QoS.AT_LEAST_ONCE,
        callback=on_command,
    )
    sub_future.result()
    print(f"[SIM] Suscripto a {TOPIC_COMMANDS}.")

    cap = cv2.VideoCapture(0)
    has_cam = cap.isOpened()
    if has_cam:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        print("[SIM] Webcam detectada.")
    else:
        cap.release()
        print("[SIM] Sin webcam — usando frames de ruido aleatorio.")

    print("[SIM] Enviando frames. Presioná Q para salir.\n")

    frame_count = 0
    try:
        while True:
            if has_cam:
                ret, frame = cap.read()
                if not ret:
                    continue
                frame = cv2.resize(frame, (320, 240))
            else:
                frame = np.random.randint(0, 256, (240, 320, 3), dtype=np.uint8)

            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
            connection.publish(
                topic=TOPIC_FRAMES,
                payload=jpeg.tobytes(),
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )

            frame_count += 1
            cmd = last_command["cmd"]
            age = f"{time.time() - last_command['ts']:.1f}s ago" if last_command["ts"] else "esperando..."
            print(f"\r[SIM] Frame #{frame_count} | Último cmd: {cmd} ({age})    ", end="", flush=True)

            if has_cam:
                overlay = frame.copy()
                color = (0, 0, 255) if cmd == "#M1" else (0, 200, 0)
                cv2.putText(overlay, "BRAZOS ARRIBA" if cmd == "#M1" else "STANDBY",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
                cv2.imshow("RPi Simulator — Q para salir", overlay)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            time.sleep(FRAME_INTERVAL)

    finally:
        if has_cam:
            cap.release()
            cv2.destroyAllWindows()
        connection.disconnect()
        print("\n[SIM] Detenido.")


if __name__ == "__main__":
    main()
