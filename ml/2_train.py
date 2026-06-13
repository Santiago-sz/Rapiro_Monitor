import numpy as np
import cv2
import os
from pathlib import Path
from tensorflow import keras
from tensorflow.keras import layers
import matplotlib.pyplot as plt

IMG_SIZE = 64
EPOCHS = 20
BATCH_SIZE = 32
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
ARTIFACTS_DIR.mkdir(exist_ok=True)

def load_data():
    X, y = [], []
    for label, cls in enumerate(['no_movement', 'movement']):
        class_dir = DATA_DIR / cls
        for img_file in os.listdir(class_dir):
            img = cv2.imread(str(class_dir / img_file), cv2.IMREAD_GRAYSCALE)
            if img is not None:
                img = cv2.resize(img, (IMG_SIZE, IMG_SIZE))
                X.append(img)
                y.append(label)
    X = np.array(X, dtype='float32') / 255.0
    X = X.reshape(-1, IMG_SIZE, IMG_SIZE, 1)
    return X, np.array(y)

print("Cargando datos...")
X, y = load_data()
print(f"Total: {len(X)} imagenes | Movimiento: {sum(y)} | Sin movimiento: {len(y) - sum(y)}")

idx = np.random.permutation(len(X))
X, y = X[idx], y[idx]

split = int(0.8 * len(X))
X_train, X_val = X[:split], X[split:]
y_train, y_val = y[:split], y[split:]

# Arquitectura CNN
model = keras.Sequential([
    # Capa de entrada: imagen 64x64 en escala de grises
    layers.Input(shape=(IMG_SIZE, IMG_SIZE, 1)),

    # Capas ocultas: detectan bordes, texturas y patrones de movimiento
    layers.Conv2D(32, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D(2, 2),

    layers.Conv2D(64, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D(2, 2),

    layers.Conv2D(128, (3, 3), activation='relu', padding='same'),
    layers.MaxPooling2D(2, 2),

    layers.Flatten(),
    layers.Dense(128, activation='relu'),
    layers.Dropout(0.5),

    # Capa de salida: 0 = sin movimiento, 1 = movimiento
    layers.Dense(1, activation='sigmoid')
])

model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
model.summary()

print("\nEntrenando...")
history = model.fit(
    X_train, y_train,
    epochs=EPOCHS,
    batch_size=BATCH_SIZE,
    validation_data=(X_val, y_val)
)

model.save(ARTIFACTS_DIR / 'modelo_movimiento.keras')
print(f"\nModelo guardado: {ARTIFACTS_DIR / 'modelo_movimiento.keras'}")

plt.figure(figsize=(12, 4))

plt.subplot(1, 2, 1)
plt.plot(history.history['accuracy'], label='Entrenamiento')
plt.plot(history.history['val_accuracy'], label='Validacion')
plt.title('Precision por epoca')
plt.xlabel('Epoca')
plt.ylabel('Precision')
plt.legend()

plt.subplot(1, 2, 2)
plt.plot(history.history['loss'], label='Entrenamiento')
plt.plot(history.history['val_loss'], label='Validacion')
plt.title('Loss por epoca')
plt.xlabel('Epoca')
plt.ylabel('Loss')
plt.legend()

plt.tight_layout()
plt.savefig(ARTIFACTS_DIR / 'entrenamiento.png')
plt.show()
