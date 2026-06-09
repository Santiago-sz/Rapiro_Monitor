# Rapiro — Sistema Inteligente de Identificación de Patrones del Hogar

## ¿Qué es este sistema?

Rapiro es un robot que aprende el comportamiento normal de tu casa y genera alertas cuando detecta algo fuera de ese patrón. No es un simple detector de movimiento — es un identificador de patrones que entiende que a las 3am en tu casa normalmente no hay movimiento ni luz, y que si los hay, algo raro está pasando.

Todo el sistema corre dentro del robot Rapiro, en un Raspberry Pi. Los únicos datos que usa vienen de una cámara. No hay sensores físicos adicionales.

---

## ¿Por qué estas herramientas?

| Herramienta | Por qué |
|---|---|
| **Python** | Ecosistema de IA/ML más maduro, compatible con Raspberry Pi |
| **TensorFlow/Keras** | Framework de deep learning para entrenar y correr la CNN |
| **OpenCV** | Procesamiento de video en tiempo real, viene con Haar Cascade para caras |
| **PostgreSQL** | Base de datos relacional robusta, persiste los patrones entre reinicios |
| **MQTT + AWS IoT Core** | Protocolo liviano diseñado para dispositivos IoT con conexión limitada |
| **AWS Lambda** | Procesamiento serverless de eventos sin mantener un servidor |
| **AWS DynamoDB** | Historial de eventos en la nube con TTL automático |
| **AWS SNS** | Notificaciones push a email cuando hay alertas críticas |
| **AWS CloudWatch** | Monitoreo y alarmas sobre métricas del sistema |
| **Terraform** | Infraestructura como código — reproducible, versionable, auditable |

---

## Estructura del proyecto

```
motion_detector/
│
├── 1_collect_data.py      # Paso 1: recolectar imágenes para entrenar la CNN
├── 2_train.py             # Paso 2: entrenar la CNN con las imágenes recolectadas
├── 3_detect.py            # Paso 3: verificar que la CNN funciona (demo básico)
│
├── config.py              # Configuración central — lee el .env
├── setup_db.py            # Crea la base de datos y tablas automáticamente
├── db.py                  # Capa de datos — toda la comunicación con PostgreSQL
├── light_estimator.py     # Sensor de luz derivado de la cámara
├── face_detector.py       # Detección de caras en tiempo real
├── pattern_store.py       # Aprendizaje de patrones + detección de anomalías
├── mqtt_publisher.py      # Publicación de eventos a AWS IoT Core
├── rapiro_controller.py   # Control serial del robot (#M0 standby / #M6 alerta)
│
├── main.py                # Loop principal — integra todo el sistema
├── demo.py                # Demo sin base de datos ni AWS
│
├── requirements.txt       # Dependencias Python
├── setup_rpi.sh           # Instalación automática en Raspberry Pi
├── .env                   # Variables de entorno (NO subir al repo)
├── .gitignore             # Archivos excluidos del repositorio
│
├── modelo_movimiento.keras # Modelo CNN entrenado (se genera con 2_train.py)
│
└── terraform/
    ├── main.tf            # Provider AWS y configuración de Terraform
    ├── variables.tf       # Variables: región, nombre del proyecto, email
    ├── iot.tf             # AWS IoT Core: Thing, Certificado, Policy, Rule
    ├── dynamodb.tf        # Tabla de eventos en la nube
    ├── sns.tf             # Topic de notificaciones + suscripción email
    ├── lambda.tf          # Lambda + IAM + CloudWatch alarm
    ├── outputs.tf         # Exporta certificados y endpoints
    └── lambda_src/
        └── alert_handler.py  # Función Lambda: guarda en DynamoDB, notifica SNS
```

---

## Flujo 1 — Entrenamiento de la CNN (se hace una sola vez)

Este flujo prepara el cerebro de detección de movimiento.

```
┌─────────────────────────────────────────────────────┐
│  1_collect_data.py                                  │
│                                                     │
│  Cámara → frame actual → escala de grises 64x64     │
│                │                                    │
│         absdiff(frame_actual, frame_anterior)        │
│                │                                    │
│         imagen de diferencia (lo que cambió)        │
│                │                                    │
│     M = guarda en data/movement/                    │
│     N = guarda en data/no_movement/                 │
│     Q = termina                                     │
└─────────────────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│  2_train.py                                         │
│                                                     │
│  data/movement/     → label 1 (hay movimiento)      │
│  data/no_movement/  → label 0 (sin movimiento)      │
│          │                                          │
│   normaliza: píxeles / 255.0                        │
│   divide: 80% entrenamiento / 20% validación        │
│          │                                          │
│   CNN:                                              │
│   Conv2D(32)  + MaxPool  → detecta bordes           │
│   Conv2D(64)  + MaxPool  → detecta texturas         │
│   Conv2D(128) + MaxPool  → detecta patrones         │
│   Dense(128)             → combina todo             │
│   Sigmoid                → probabilidad 0.0 a 1.0   │
│          │                                          │
│   20 épocas, batch 32                               │
│          │                                          │
│   Guarda: modelo_movimiento.keras                   │
│   Guarda: entrenamiento.png (gráfico accuracy/loss) │
└─────────────────────────────────────────────────────┘
```

**Por qué absdiff**: La CNN no analiza el frame completo sino la diferencia entre dos frames consecutivos. Lo que cambia entre un instante y el siguiente es exactamente el movimiento. Esto hace que la red sea invariante al fondo — no importa cómo sea tu casa, solo importa lo que se mueve.

**Por qué 64x64**: Balance entre detalle suficiente para detectar movimiento y velocidad de inferencia en el Raspberry Pi.

---

## Flujo 2 — Loop principal en tiempo real (main.py)

Este flujo corre indefinidamente una vez que el sistema está en producción.

```
                    INICIO
                      │
              setup_db.ensure_ready()
              ┌───────────────────┐
              │ ¿Existe usuario   │
              │ 'rapiro' en PG?   │──NO──→ lo crea
              └───────────────────┘
              ┌───────────────────┐
              │ ¿Existe base de   │
              │ datos 'rapiro'?   │──NO──→ la crea
              └───────────────────┘
              ┌───────────────────┐
              │ ¿Existen tablas?  │──NO──→ las crea
              └───────────────────┘
                      │
              Carga modelo CNN
              Inicializa FaceDetector
              Inicializa RapiroController
              Abre VideoCapture(0)
                      │
        ┌─────────────────────────────────────────┐
        │         CICLO (cada 1 segundo)           │
        │                                         │
        │  cap.read() → frame BGR                 │
        │        │                                │
        │        ├──→ light_estimator             │
        │        │    mean(gray)/255 → luz         │
        │        │                                │
        │        ├──→ face_detector               │
        │        │    Haar Cascade → cara SI/NO    │
        │        │                                │
        │        ├──→ CNN de movimiento            │
        │        │    absdiff → predict            │
        │        │    → prob 0.0-1.0               │
        │        │    > 0.5 = movimiento           │
        │        │                                │
        │        ├──→ compute_anomaly()            │
        │        │    z_mov = |mov-avg| / std      │
        │        │    z_luz = |luz-avg| / std      │
        │        │    score = (z_mov+z_luz) / 2   │
        │        │    < 2.0 → NORMAL              │
        │        │    < 3.0 → INFO                │
        │        │    < 5.0 → ALERTA              │
        │        │    ≥ 5.0 → CRITICO             │
        │        │                                │
        │        ├──→ update_pattern()             │
        │        │    aprende el nuevo valor       │
        │        │    actualiza media y std        │
        │        │                                │
        │        ├──→ rapiro_controller            │
        │        │    ALERTA/CRITICO → #M6        │
        │        │    NORMAL/INFO    → #M0        │
        │        │                                │
        │        ├──→ db.save_event()             │
        │        │    INSERT en PostgreSQL         │
        │        │                                │
        │        └──→ mqtt_publisher.publish()     │
        │             JSON → AWS IoT Core         │
        │             (si MQTT_ENABLED=true)       │
        └─────────────────────────────────────────┘
                      │
                   Q presionado
                      │
              Libera cámara
              Cierra conexiones
              Sistema detenido
```

---

## Flujo 3 — Aprendizaje de patrones (pattern_store.py)

Este flujo explica cómo Rapiro aprende qué es normal.

```
Primer día — hora 14:00
  mov=0.1, luz=0.7 → guarda como base
  mov=0.0, luz=0.7 → actualiza media
  mov=0.2, luz=0.6 → actualiza media
  ... después de MIN_SAMPLES_TO_LEARN muestras ...
  avg_motion=0.1, avg_light=0.68, motion_std=0.05, light_std=0.04

Segundo día — hora 14:00
  Llega: mov=0.9, luz=0.9
  z_mov = |0.9 - 0.1| / 0.05 = 16.0  ← enorme
  z_luz = |0.9 - 0.68| / 0.04 = 5.5  ← enorme
  score = (16.0 + 5.5) / 2 = 10.75
  → CRITICO → #M6 → notificación SNS
```

**Por qué media incremental**: En el Raspberry Pi la memoria es limitada. Con la fórmula `media = media + (nuevo - media) / n` actualizás sin guardar el historial completo.

**Por qué z-score**: Mide qué tan lejos está un valor de lo normal en términos de su propia variabilidad. Un score de 2.0 significa que estás a 2 desviaciones estándar de la media — estadísticamente poco común.

---

## Flujo 4 — Publicación a AWS

```
main.py
  │
  └──→ mqtt_publisher.publish(evento)
              │
        Conecta con TLS (certificados X.509)
        a AWS IoT Core endpoint
              │
        Publica JSON en topic:
        rapiro/events/{event_id}
              │
              ▼
        AWS IoT Core
              │
        IoT Rule: SELECT * FROM 'rapiro/events/+'
              │
              ▼
        Lambda: alert_handler.py
              │
        ┌─────┴──────────┐
        │                │
        ▼                ▼
   DynamoDB         ¿alert_level
   PutItem()        warning/critical?
                         │
                       SI → SNS.publish()
                                │
                         Email a tu casilla
```

**Por qué MQTT y no HTTP**: MQTT fue diseñado para dispositivos IoT. Un mensaje ocupa ~50 bytes vs ~500 bytes de HTTP. Más confiable con conexión WiFi inestable.

**Por qué certificados X.509**: AWS IoT Core usa autenticación mutua TLS. Más seguro que contraseñas y no hay credenciales que rotar.

**Por qué Lambda**: No necesitás un servidor corriendo 24/7. Lambda escala a cero cuando no hay eventos. Solo pagás por lo que usás.

---

## Archivo por archivo

### `config.py`
Lee todas las variables del `.env` y las expone como constantes. Centraliza la configuración para que ningún módulo tenga valores hardcodeados. Cambiar el comportamiento del sistema es tan simple como editar el `.env`.

### `setup_db.py`
Se ejecuta automáticamente al arrancar `main.py`. Conecta a PostgreSQL como superusuario y crea el usuario de la aplicación y la base de datos si no existen. Usa `ISOLATION_LEVEL_AUTOCOMMIT` porque `CREATE DATABASE` no puede correr dentro de una transacción en PostgreSQL.

### `db.py`
Maneja toda la comunicación con PostgreSQL usando un pool de 1 a 5 conexiones reutilizables. Evita abrir y cerrar una conexión nueva en cada ciclo, lo que sería lento.

### `light_estimator.py`
Convierte el frame a escala de grises y calcula el promedio de todos los píxeles dividido 255. Una operación de numpy — extremadamente rápida.

### `face_detector.py`
Usa el modelo Haar Cascade incluido en OpenCV, entrenado por Viola & Jones. No necesitás entrenarlo. Detecta caras frontales y calcula la confianza según el tamaño de la cara relativo al frame.

### `pattern_store.py`
Implementa dos operaciones: `update_pattern()` actualiza media y std por hora sin guardar historial. `compute_anomaly()` calcula el z-score combinado y necesita `MIN_SAMPLES_TO_LEARN` muestras antes de generar scores, para evitar falsos positivos al inicio.

### `mqtt_publisher.py`
Mantiene una conexión MQTT persistente con AWS IoT Core usando TLS mutuo. La conexión se establece una vez y se reutiliza. Usa un thread separado para no bloquear el loop principal. Si `MQTT_ENABLED=false` no hace nada.

### `rapiro_controller.py`
Abre el puerto serial al microcontrolador del Rapiro y envía comandos ASCII. Si `RAPIRO_ENABLED=false` simula el envío sin abrir el puerto — útil para desarrollo en Windows.

### `main.py`
El director de orquesta. Inicializa todos los módulos, abre la cámara y corre el loop. El bloque `finally` garantiza que la cámara siempre se libera aunque el programa falle.

### `demo.py`
Versión de `main.py` sin PostgreSQL ni AWS. Los patrones viven en memoria RAM y se pierden al cerrar. Sirve para mostrar el sistema sin infraestructura.

### `setup_rpi.sh`
Script bash que instala todo en el Raspberry Pi automáticamente: dependencias del sistema, PostgreSQL, entorno virtual Python, todas las librerías, habilita la cámara, y registra el servicio systemd para que el sistema arranque solo al encender el RPi.

### `terraform/iot.tf`
Crea la identidad del dispositivo en AWS (Thing), el certificado X.509, la política con permisos mínimos (solo publicar en `rapiro/events/*`), y la regla que reenvía mensajes a Lambda.

### `terraform/dynamodb.tf`
Tabla con clave compuesta `event_id + captured_at`. Modo PAY_PER_REQUEST. TTL de 30 días — los eventos viejos se borran solos sin costo adicional.

### `terraform/lambda.tf`
Función Lambda con permisos mínimos: solo puede escribir en DynamoDB y publicar en SNS. CloudWatch alarm dispara si hay más de 5 invocaciones en 5 minutos.

### `terraform/sns.tf`
Topic de notificaciones con suscripción a email. El primer email pedirá confirmar la suscripción — hay que aceptarlo antes de que funcionen las notificaciones.

### `terraform/lambda_src/alert_handler.py`
Siempre guarda en DynamoDB. Solo notifica por SNS si el `alert_level` es `warning` o `critical`. Los eventos normales quedan registrados sin molestar.

---

## Variables de entorno — .env completo

```env
# PostgreSQL local
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rapiro
DB_USER=rapiro
DB_PASSWORD=rapiro1234
DB_ADMIN_USER=postgres
DB_ADMIN_PASSWORD=1234

# Serial del Rapiro (activar en Raspberry Pi)
RAPIRO_ENABLED=false
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

# Detección y aprendizaje
CNN_THRESHOLD=0.5
ANOMALY_THRESHOLD=2.0
MIN_SAMPLES_TO_LEARN=10
LOOP_INTERVAL_SEC=1.0
CAMERA_INDEX=0
```

---

## Qué falta para tener el sistema 100% completo

### Hardware
- [ ] Raspberry Pi con Raspberry Pi OS instalado
- [ ] Cámara conectada al RPi (módulo oficial o webcam USB)
- [ ] Rapiro conectado al RPi por cable USB serial
- [ ] Correr `setup_rpi.sh` en el RPi
- [ ] Activar `RAPIRO_ENABLED=true` en el `.env` del RPi

### AWS
- [ ] Cuenta AWS con credenciales configuradas (`aws configure`)
- [ ] Instalar Terraform (`winget install Hashicorp.Terraform`)
- [ ] Correr `terraform init` y `terraform apply` en `terraform/`
- [ ] Copiar `certificate_pem` y `private_key` de los outputs a `certs/`
- [ ] Descargar certificado raíz: `certs/AmazonRootCA1.pem`
- [ ] Obtener endpoint IoT con `aws iot describe-endpoint --endpoint-type iot:Data-ATS`
- [ ] Actualizar `MQTT_ENDPOINT` en el `.env`
- [ ] Activar `MQTT_ENABLED=true`
- [ ] Confirmar la suscripción al email cuando llegue el primer correo de SNS

### CNN (opcional pero recomendado)
- [ ] Recolectar más datos con `1_collect_data.py` en distintas condiciones de luz
- [ ] Reentrenar con `2_train.py`
- [ ] Copiar el nuevo `modelo_movimiento.keras` al RPi

### Funciona ahora mismo
- [x] Detección de movimiento vía CNN
- [x] Estimación de luz desde cámara
- [x] Detección de caras en tiempo real
- [x] Aprendizaje de patrones por hora
- [x] Detección de anomalías con z-score
- [x] Persistencia en PostgreSQL
- [x] Setup automático de la base de datos
- [x] Infraestructura AWS lista para desplegar (Terraform)
- [x] Publisher MQTT listo (desactivado hasta tener los certs)
- [x] Control serial del Rapiro listo (desactivado hasta tener el RPi)
