import time
import sys
import uuid
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
load_dotenv()

import cv2
import numpy as np
from tensorflow import keras

from cloud_processor import db, light_estimator, mqtt_publisher, setup_db
from cloud_processor.config import CAMERA_INDEX, IMG_SIZE, CNN_THRESHOLD, LOOP_INTERVAL_SEC
from cloud_processor.face_detector import FaceDetector
from cloud_processor.pattern_store import compute_anomaly, update_pattern
from edge_device.rapiro_controller import RapiroController

MODEL_PATH = PROJECT_ROOT / "ml" / "artifacts" / "modelo_movimiento.keras"

ALERT_COLOR = {
    "none": (0, 200, 0),
    "info": (0, 200, 255),
    "warning": (0, 140, 255),
    "critical": (0, 0, 255),
}


def main() -> None:
    print("[Rapiro] Iniciando sistema identificador de patrones...")
    setup_db.ensure_ready()

    model = keras.models.load_model(MODEL_PATH)
    face_det = FaceDetector()
    rapiro = RapiroController()

    cap = cv2.VideoCapture(CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError("No se pudo abrir la cámara")

    prev_gray = None
    print("[Rapiro] Sistema activo. Presioná Q para salir.")

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            now = datetime.now()
            hour = now.hour

            # Sensor de luz desde la cámara
            light_pct = light_estimator.estimate_light(frame)

            # Detección de rostros en el frame actual
            face_detected, face_conf = face_det.detect(frame)

            # Detección de movimiento vía CNN (diff entre frames)
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

            # Identificación de anomalía vs patrón aprendido
            motion_val = 1.0 if motion_detected else 0.0
            anomaly_score, alert_level = compute_anomaly(hour, motion_val, light_pct)
            update_pattern(hour, motion_val, light_pct)

            # Comando al robot según nivel de alerta
            command = "alert" if alert_level in ("warning", "critical") else "standby"
            rapiro_code = rapiro.send(command)

            # Overlay en pantalla
            alert_col = ALERT_COLOR.get(alert_level, (255, 255, 255))
            cv2.putText(frame,
                        f"MOV: {'SI' if motion_detected else 'NO'} ({motion_conf:.2f})",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                        (0, 0, 255) if motion_detected else (0, 200, 0), 2)
            cv2.putText(frame,
                        f"LUZ: {light_pct:.2f}  HORA: {hour}h",
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 220, 0), 2)
            cv2.putText(frame,
                        f"CARA: {'SI' if face_detected else 'NO'}  "
                        f"ANOMALIA: {anomaly_score:.2f}  [{alert_level.upper()}]",
                        (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.65, alert_col, 2)
            cv2.imshow("Rapiro — Identificador de Patrones del Hogar", frame)

            # Persistencia en PostgreSQL
            event = {
                "event_id": str(uuid.uuid4()),
                "captured_at": now.isoformat(),
                "hour_of_day": hour,
                "motion_detected": motion_detected,
                "motion_confidence": motion_conf,
                "face_detected": face_detected,
                "light_percent": light_pct,
                "alert_level": alert_level,
                "anomaly_score": anomaly_score,
                "rapiro_command": rapiro_code,
            }
            row_id = db.save_event(event)

            # Publicar a AWS IoT Core vía MQTT
            if mqtt_publisher.publish(event):
                db.mark_mqtt_published(row_id)

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

            time.sleep(LOOP_INTERVAL_SEC)

    finally:
        cap.release()
        cv2.destroyAllWindows()
        rapiro.close()
        mqtt_publisher.shutdown()
        db.close_pool()
        print("[Rapiro] Sistema detenido.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
