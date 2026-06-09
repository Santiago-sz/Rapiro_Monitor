import cv2
from pathlib import Path
from config import HAAR_CASCADE_PATH


class FaceDetector:
    def __init__(self) -> None:
        cascade_path = HAAR_CASCADE_PATH or str(
            Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        )
        self._cascade = cv2.CascadeClassifier(cascade_path)

    def detect(self, frame) -> tuple[bool, float]:
        """Return (face_detected, confidence) from a live BGR frame."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self._cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        if len(faces) == 0:
            return False, 0.0
        largest = max(w * h for _, _, w, h in faces)
        frame_area = frame.shape[0] * frame.shape[1]
        confidence = min(1.0, 0.5 + (largest / frame_area))
        return True, round(confidence, 2)
