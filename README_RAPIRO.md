# Rapiro — Identificador de Patrones del Hogar

## Qué hace el sistema

El Rapiro usa la cámara para aprender el comportamiento normal de tu casa (movimiento, luz, presencia de personas) y genera alertas cuando detecta algo fuera de ese patrón.

Tres sensores, todos desde la cámara:
- **Movimiento** — CNN entrenada sobre diferencia entre frames
- **Luz** — brillo promedio del frame en escala de grises
- **Caras** — Haar Cascade de OpenCV

---

## Estructura del proyecto

```
motion_detector/
├── 1_collect_data.py      # Recolección de datos para entrenar la CNN
├── 2_train.py             # Entrenamiento de la CNN
├── 3_detect.py            # Demo básico de detección
├── demo.py                # Demo completa sin base de datos
├── main.py                # Sistema completo (usar en producción)
├── config.py              # Configuración vía variables de entorno
├── db.py                  # PostgreSQL — conexión y queries
├── setup_db.py            # Crea la BD y tablas automáticamente
├── light_estimator.py     # Sensor de luz desde cámara
├── face_detector.py       # Detección de caras en tiempo real
├── pattern_store.py       # Aprendizaje de patrones + anomalías
├── mqtt_publisher.py      # Publicación a AWS IoT Core
├── rapiro_controller.py   # Comandos seriales al robot (#M0/#M6)
├── setup_rpi.sh           # Instalación automática en Raspberry Pi
├── .env                   # Variables de entorno (NO subir al repo)
├── certs/                 # Certificados AWS IoT (NO subir al repo)
└── terraform/             # Infraestructura AWS
```

---

## Variables de entorno (.env)

```env
# PostgreSQL local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rapiro
DB_USER=rapiro
DB_PASSWORD=rapiro1234
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=1234

# Rapiro serial (activar solo en Raspberry Pi)
RAPIRO_ENABLED=true
RAPIRO_PORT=/dev/ttyUSB0
RAPIRO_BAUD=57600

# AWS IoT Core (activar cuando tengas los certificados)
MQTT_ENABLED=false
MQTT_ENDPOINT=xxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com
MQTT_CLIENT_ID=rapiro-001
MQTT_TOPIC=rapiro/events
MQTT_CERT_PATH=certs/device.pem.crt
MQTT_KEY_PATH=certs/private.pem.key
MQTT_CA_PATH=certs/AmazonRootCA1.pem

# Detección
ANOMALY_THRESHOLD=2.0
MIN_SAMPLES_TO_LEARN=10
LOOP_INTERVAL_SEC=1.0
```

---

## Primer arranque en Raspberry Pi

### 1. Copiar el proyecto desde Windows

```powershell
scp -r "C:\Users\santi\Desktop\motion_detector" pi@<IP_DEL_RPI>:~/
```

### 2. Conectarse al RPi

```bash
ssh pi@<IP_DEL_RPI>
cd motion_detector
```

### 3. Correr el setup automático

```bash
chmod +x setup_rpi.sh
./setup_rpi.sh
```

Esto instala: PostgreSQL, Python, todas las dependencias, habilita la cámara y registra el servicio systemd.

### 4. Configurar el .env

```bash
nano .env
```

Ajustá `DB_ADMIN_PASSWORD` y `DB_PASSWORD` con tus contraseñas.

### 5. Copiar el modelo entrenado

```powershell
# Desde Windows, si reentrenaste la CNN
scp "C:\Users\santi\Desktop\motion_detector\modelo_movimiento.keras" pi@<IP_DEL_RPI>:~/motion_detector/
```

### 6. Arrancar el sistema

```bash
sudo systemctl start rapiro
```

Para ver los logs en tiempo real:
```bash
sudo journalctl -u rapiro -f
```

El servicio arranca automáticamente cada vez que se enciende el RPi.

---

## Comandos útiles en el RPi

```bash
# Ver estado del servicio
sudo systemctl status rapiro

# Detener el sistema
sudo systemctl stop rapiro

# Reiniciar el sistema
sudo systemctl restart rapiro

# Ver logs
sudo journalctl -u rapiro -f

# Conectarse a PostgreSQL para ver datos
psql -U rapiro -d rapiro

# Consultas útiles en psql
SELECT COUNT(*) FROM events;
SELECT captured_at, motion_detected, light_percent, alert_level FROM events ORDER BY captured_at DESC LIMIT 10;
SELECT * FROM hourly_patterns ORDER BY hour_of_day;
```

---

## Comandos seriales del Rapiro

| Comando | Código | Cuándo |
|---|---|---|
| Standby | `#M0` | Sin anomalías |
| Alerta | `#M6` | Anomalía warning o critical |

---

## Integración AWS (cuando estés listo)

### 1. Instalar Terraform

```bash
# En Windows
winget install Hashicorp.Terraform
```

### 2. Configurar credenciales AWS

```bash
aws configure
```

### 3. Desplegar infraestructura

```bash
cd terraform
terraform init
terraform apply -var="alert_email=tu@email.com"
```

### 4. Copiar certificados al RPi

```bash
# Obtener el endpoint de IoT
aws iot describe-endpoint --endpoint-type iot:Data-ATS

# Guardar los outputs sensibles
terraform output -raw certificate_pem > ../certs/device.pem.crt
terraform output -raw private_key > ../certs/private.pem.key

# Descargar el certificado raíz de Amazon
curl -o ../certs/AmazonRootCA1.pem https://www.amazontrust.com/repository/AmazonRootCA1.pem

# Copiar certs al RPi
scp -r certs/ pi@<IP_DEL_RPI>:~/motion_detector/
```

### 5. Activar MQTT en el .env del RPi

```env
MQTT_ENABLED=true
MQTT_ENDPOINT=xxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com
```

---

## Tablas PostgreSQL

**events** — cada ciclo de detección
- `event_id` — UUID único
- `captured_at` — timestamp
- `hour_of_day` — hora (0-23)
- `motion_detected` — booleano
- `motion_confidence` — probabilidad CNN (0.0-1.0)
- `face_detected` — booleano
- `light_percent` — brillo (0.0-1.0)
- `alert_level` — none / info / warning / critical
- `anomaly_score` — puntaje de desviación del patrón
- `rapiro_command` — comando enviado al robot
- `mqtt_published` — si fue enviado a AWS

**hourly_patterns** — patrón aprendido por franja horaria
- `hour_of_day` — hora (0-23)
- `avg_motion_freq` — movimiento promedio aprendido
- `avg_light_percent` — luz promedio aprendida
- `motion_std` — variabilidad del movimiento
- `light_std` — variabilidad de la luz
- `sample_count` — muestras acumuladas
