import cv2
import numpy as np


def estimate_light(frame) -> float:
    """Ambient brightness 0.0–1.0 computed from mean grayscale pixel value."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return float(np.mean(gray)) / 255.0
