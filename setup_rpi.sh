#!/bin/bash
set -e

echo "[RPi] Actualizando sistema..."
sudo apt update && sudo apt upgrade -y

echo "[RPi] Instalando dependencias del sistema..."
sudo apt install -y python3-pip python3-venv libpq-dev \
    postgresql postgresql-contrib \
    libatlas-base-dev libhdf5-dev \
    libopencv-dev python3-opencv \
    python3-serial

echo "[RPi] Habilitando cámara..."
sudo raspi-config nonint do_camera 0

echo "[RPi] Creando entorno virtual..."
python3 -m venv .venv

echo "[RPi] Instalando dependencias Python..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install tensorflow-aarch64 opencv-python psycopg2-binary \
    paho-mqtt pyserial python-dotenv

echo "[RPi] Iniciando PostgreSQL..."
sudo systemctl enable postgresql
sudo systemctl start postgresql

echo "[RPi] Instalando servicio systemd..."
WORK_DIR=$(pwd)
USER=$(whoami)

sudo tee /etc/systemd/system/rapiro.service > /dev/null <<EOF
[Unit]
Description=Rapiro Home Pattern Identifier
After=network.target postgresql.service
Requires=postgresql.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
ExecStart=$WORK_DIR/.venv/bin/python main.py
Restart=on-failure
RestartSec=5
EnvironmentFile=$WORK_DIR/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable rapiro

echo ""
echo "========================================="
echo " Setup completo."
echo " Editá el archivo .env con tus datos y"
echo " luego corré: sudo systemctl start rapiro"
echo "========================================="
