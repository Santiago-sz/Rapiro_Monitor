import os

# Camera
CAMERA_INDEX = int(os.getenv("CAMERA_INDEX", "0"))
IMG_SIZE = 64
CNN_THRESHOLD = 0.5
LOOP_INTERVAL_SEC = float(os.getenv("LOOP_INTERVAL_SEC", "1.0"))

# PostgreSQL — credenciales de la aplicación
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "rapiro")
DB_USER = os.getenv("DB_USER", "rapiro")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# PostgreSQL — credenciales del superusuario para setup inicial
DB_ADMIN_USER = os.getenv("DB_ADMIN_USER", "postgres")
DB_ADMIN_PASSWORD = os.getenv("DB_ADMIN_PASSWORD", "")

# Rapiro serial
RAPIRO_PORT = os.getenv("RAPIRO_PORT", "/dev/ttyUSB0")
RAPIRO_BAUD = int(os.getenv("RAPIRO_BAUD", "57600"))
RAPIRO_ENABLED = os.getenv("RAPIRO_ENABLED", "false").lower() == "true"

# MQTT / AWS IoT Core
MQTT_ENDPOINT = os.getenv("MQTT_ENDPOINT", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "8883"))
MQTT_CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "rapiro-001")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "rapiro/events")
MQTT_CERT_PATH = os.getenv("MQTT_CERT_PATH", "aws/terraform/certs/device.pem.crt")
MQTT_KEY_PATH = os.getenv("MQTT_KEY_PATH", "aws/terraform/certs/private.pem.key")
MQTT_CA_PATH = os.getenv("MQTT_CA_PATH", "aws/terraform/certs/AmazonRootCA1.pem")
MQTT_ENABLED = os.getenv("MQTT_ENABLED", "false").lower() == "true"

# Pattern learning / anomaly detection
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "2.0"))
MIN_SAMPLES_TO_LEARN = int(os.getenv("MIN_SAMPLES_TO_LEARN", "10"))

# Face detection (empty = use cv2 bundled cascade)
HAAR_CASCADE_PATH = os.getenv("HAAR_CASCADE_PATH", "")
