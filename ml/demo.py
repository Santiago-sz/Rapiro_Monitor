"""
Demo standalone — corre sin PostgreSQL ni AWS.
Muestra en pantalla: detección de movimiento (CNN), luz y caras en tiempo real.
El aprendizaje de patrones vive en memoria mientras dure la sesión.
"""
import time
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import cv2
import numpy as np
from tensorflow import keras

from cloud_processor.face_detector import FaceDetector
from cloud_processor.light_estimator import estimate_light

MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "modelo_movimiento.keras"
IMG_SIZE = 64
CNN_THRESHOLD = 0.5
# Mínimo de muestras por hora antes de calcular anomalías
MIN_SAMPLES = 2

# Patrones en memoria: hora -> {motion, light, count}
_patterns: dict = defaultdict(lambda: {"motion": 0.0, "light": 0.0, "count": 0})


def update_pattern(hour: int, motion: float, light: float) -> None:
    p = _patterns[hour]
    p["count"] += 1
    n = p["count"]
    p["motion"] += (motion - p["motion"]) / n
    p["light"] += (light - p["light"]) / n


def anomaly_level(hour: int, motion: float, light: float) -> tuple[float, str]:
    p = _patterns[hour]
    if p["count"] < MIN_SAMPLES:
        return 0.0, "aprendiendo..."

    motion_diff = abs(motion - p["motion"])
    light_diff = abs(light - p["light"])
    score = motion_diff * 5 + light_diff * 3

    if score < 1.0:
        return score, "NORMAL"
    elif score < 2.5:
        return score, "INFO"
    elif score < 4.0:
        return score, "ALERTA"
    else:
        return score, "CRITICO"


COLORS = {
    "aprendiendo...": (200, 200, 200),
    "NORMAL":  (0, 200, 0),
    "INFO":    (0, 200, 255),
    "ALERTA":  (0, 140, 255),
    "CRITICO": (0, 0, 255),
}


def main() -> None:
    print("[Demo] Cargando modelo CNN...")
    model = keras.models.load_model(MODEL_PATH)
    face_det = FaceDetector()
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("[Demo] ERROR: no se pudo abrir la cámara")
        return

    print("[Demo] Activo. Presioná Q para salir.")
    prev_gray = None

    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.05)
            continue

        hour = datetime.now().hour
        light = estimate_light(frame)
        face_detected, _ = face_det.detect(frame)

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.resize(gray, (IMG_SIZE, IMG_SIZE))

        motion_detected = False
        motion_conf = 0.0

        if prev_gray is not None:
            diff = cv2.absdiff(prev_gray, gray_r)
            inp = diff.astype("float32") / 255.0
            inp = inp.reshape(1, IMG_SIZE, IMG_SIZE, 1)
            motion_conf = float(model.predict(inp, verbose=0)[0][0])
            motion_detected = motion_conf > CNN_THRESHOLD

        prev_gray = gray_r

        motion_val = 1.0 if motion_detected else 0.0
        score, level = anomaly_level(hour, motion_val, light)
        update_pattern(hour, motion_val, light)

        col = COLORS.get(level, (255, 255, 255))
        h, w = frame.shape[:2]

        # Borde de color según nivel
        cv2.rectangle(frame, (0, 0), (w - 1, h - 1), col, 4)

        # Panel de info
        cv2.rectangle(frame, (0, 0), (w, 110), (0, 0, 0), -1)

        mov_col = (0, 60, 255) if motion_detected else (0, 200, 0)
        cv2.putText(frame,
                    f"MOVIMIENTO: {'SI' if motion_detected else 'NO'}  ({motion_conf:.2f})",
                    (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, mov_col, 2)
        cv2.putText(frame,
                    f"LUZ: {light:.2f}   HORA: {hour}h",
                    (10, 58), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 220, 0), 2)
        cv2.putText(frame,
                    f"CARA: {'SI' if face_detected else 'NO'}   "
                    f"PATRON: {level}  (score {score:.2f})",
                    (10, 88), cv2.FONT_HERSHEY_SIMPLEX, 0.65, col, 2)

        cv2.imshow("Rapiro Demo — Identificador de Patrones", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\n[Demo] Patrones aprendidos por hora:")
    for h, p in sorted(_patterns.items()):
        print(f"  Hora {h:02d}h — movimiento promedio: {p['motion']:.2f}  "
              f"luz promedio: {p['light']:.2f}  muestras: {p['count']}")


if __name__ == "__main__":
    main()
