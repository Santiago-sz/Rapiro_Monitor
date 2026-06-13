import cv2
import numpy as np
from pathlib import Path
from tensorflow import keras

IMG_SIZE = 64
THRESHOLD = 0.5
MODEL_PATH = Path(__file__).resolve().parent / "artifacts" / "modelo_movimiento.keras"

model = keras.models.load_model(MODEL_PATH)
cap = cv2.VideoCapture(0)
prev_frame = None

print("Deteccion activa. Q para salir.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    gray_resized = cv2.resize(gray, (IMG_SIZE, IMG_SIZE))

    if prev_frame is not None:
        diff = cv2.absdiff(prev_frame, gray_resized)

        input_data = diff.astype('float32') / 255.0
        input_data = input_data.reshape(1, IMG_SIZE, IMG_SIZE, 1)

        prob = model.predict(input_data, verbose=0)[0][0]

        if prob > THRESHOLD:
            label = f"MOVIMIENTO ({prob:.2f})"
            color = (0, 0, 255)
        else:
            label = f"Sin movimiento ({prob:.2f})"
            color = (0, 255, 0)

        cv2.putText(frame, label, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.rectangle(frame, (5, 5), (frame.shape[1]-5, frame.shape[0]-5), color, 3)

    cv2.imshow('Sistema 1 - Deteccion de Movimiento', frame)
    prev_frame = gray_resized

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
