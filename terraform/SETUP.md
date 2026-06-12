# Rapiro Monitor — Setup completo

## Paso 1: Desplegar la infraestructura AWS

```powershell
cd C:\Users\santi\Desktop\motion_detector\terraform
terraform apply
```

Cuando pida valores:
- `alert_email` → tu email (para alertas críticas)
- `ec2_key_name` → `rapiro-monitor-key`

Escribí `yes` para confirmar. Tarda ~2 minutos.

---

## Paso 2: Guardar los certificados del Rapiro

Después del apply, ejecutá estos comandos **en la carpeta terraform**:

```powershell
mkdir certs
terraform output -raw certificate_pem | Out-File -Encoding ascii certs\device.pem.crt
terraform output -raw private_key     | Out-File -Encoding ascii certs\private.pem.key
```

Descargá también el certificado raíz de Amazon:

```powershell
Invoke-WebRequest -Uri "https://www.amazontrust.com/repository/AmazonRootCA1.pem" -OutFile certs\AmazonRootCA1.pem
```

Al final debés tener:
```
terraform/certs/
  device.pem.crt     ← certificado del dispositivo
  private.pem.key    ← clave privada
  AmazonRootCA1.pem  ← CA raíz de Amazon
```

---

## Paso 3: Obtener el endpoint IoT Core

```powershell
aws iot describe-endpoint --endpoint-type iot:Data-ATS --query endpointAddress --output text
```

Copiá ese valor — lo vas a necesitar en el Paso 6. Tiene este formato:
```
xxxxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com
```

---

## Paso 4: Obtener la IP del EC2

```powershell
terraform output ec2_public_ip
```

---

## Paso 5: Conectarte al EC2 por SSH

```powershell
ssh -i $env:USERPROFILE\.ssh\rapiro-monitor-key.pem ubuntu@<IP-DEL-EC2>
```

Verificá que las dependencias se instalaron:

```bash
python3 -c "import cv2, tensorflow, psycopg2; print('OK')"
```

Si alguna falla, instalala manualmente:
```bash
pip3 install opencv-python-headless tensorflow-cpu psycopg2-binary awsiotsdk
```

---

## Paso 6: Configurar la Raspberry Pi

### 6.1 — Copiar los certificados a la RPi

Desde tu PC (reemplazá `<IP-RPi>` con la IP de tu Raspberry Pi):

```powershell
scp -r certs\ pi@<IP-RPi>:/home/pi/rapiro/certs/
```

### 6.2 — Instalar dependencias en la RPi

Conectate a la RPi por SSH y ejecutá:

```bash
pip3 install paho-mqtt opencv-python-headless pyserial
```

### 6.3 — Crear el script cliente en la RPi

Creá el archivo `/home/pi/rapiro/client.py`:

```python
import cv2
import time
import json
import serial
from awscrt import mqtt
from awsiot import mqtt_connection_builder

ENDPOINT   = "xxxxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com"  # reemplazar
CLIENT_ID  = "rapiro-monitor-thing"
CERT       = "/home/pi/rapiro/certs/device.pem.crt"
KEY        = "/home/pi/rapiro/certs/private.pem.key"
CA         = "/home/pi/rapiro/certs/AmazonRootCA1.pem"
TOPIC_FRAMES   = "rapiro/frames"
TOPIC_COMMANDS = "rapiro/commands"
SERIAL_PORT    = "/dev/ttyUSB0"   # ajustar si cambia
SERIAL_ENABLED = False            # True cuando el Rapiro esté conectado

def on_command(topic, payload, **kwargs):
    cmd = json.loads(payload)["command"]
    print(f"Comando recibido: {cmd}")
    if SERIAL_ENABLED:
        ser.write(f"{cmd}\r\n".encode())

connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT,
    pri_key_filepath=KEY,
    ca_filepath=CA,
    client_id=CLIENT_ID,
    clean_session=False,
    keep_alive_secs=30,
)

print("Conectando a IoT Core...")
connection.connect().result()
print("Conectado.")

connection.subscribe(
    topic=TOPIC_COMMANDS,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_command,
).result()

if SERIAL_ENABLED:
    ser = serial.Serial(SERIAL_PORT, 57600, timeout=1)

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

print("Enviando frames...")
while True:
    ret, frame = cap.read()
    if not ret:
        continue
    _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 40])
    connection.publish(
        topic=TOPIC_FRAMES,
        payload=jpeg.tobytes(),
        qos=mqtt.QoS.AT_LEAST_ONCE,
    )
    time.sleep(0.5)  # 2 frames por segundo
```

**Importante:** reemplazá `ENDPOINT` con el valor del Paso 3.

### 6.4 — Correr el cliente

```bash
python3 /home/pi/rapiro/client.py
```

Deberías ver:
```
Conectando a IoT Core...
Conectado.
Enviando frames...
```

---

## Paso 7: Primera prueba de conexión

Desde tu PC, verificá que los frames están llegando a IoT Core:

```powershell
aws iot-data subscribe --topic "rapiro/frames" --cli-binary-format raw-in-base64-out
```

Si ves datos fluyendo, la conexión RPi → AWS está funcionando.

---

## Paso 8: Apagar cuando no uses

Para no gastar dinero con el EC2 cuando no estés trabajando:

```powershell
# Apagar instancia (no destruye nada, solo detiene)
aws ec2 stop-instances --instance-ids $(terraform output -raw ec2_public_ip)

# O destruir todo cuando termines el TPI
terraform destroy
```

---

## Resumen del flujo completo

```
RPi (client.py)
  └─ captura frame USB cam (320x240 JPEG)
  └─ publica en rapiro/frames vía MQTT + certificados
      └─ AWS IoT Core
          └─ EC2 suscripto a rapiro/frames
              └─ CNN inference + pattern learning + PostgreSQL
              └─ publica comando en rapiro/commands
                  └─ RPi recibe comando
                      └─ pyserial → Rapiro se mueve
```
