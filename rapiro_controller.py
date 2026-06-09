from config import RAPIRO_PORT, RAPIRO_BAUD, RAPIRO_ENABLED

COMMANDS = {
    "standby": "#M0",
    "wave": "#M1",
    "walk_forward": "#M2",
    "turn_left": "#M3",
    "turn_right": "#M4",
    "alert": "#M6",
}


class RapiroController:
    def __init__(self) -> None:
        self._serial = None
        if RAPIRO_ENABLED:
            try:
                import serial
                self._serial = serial.Serial(RAPIRO_PORT, RAPIRO_BAUD, timeout=1)
                print(f"[Rapiro] Serial conectado en {RAPIRO_PORT}")
            except Exception as exc:
                print(f"[Rapiro] Serial no disponible: {exc}")

    def send(self, command: str) -> str:
        code = COMMANDS.get(command, command)
        if self._serial:
            self._serial.write(f"{code}\n".encode("ascii"))
        return code

    def close(self) -> None:
        if self._serial:
            self._serial.close()
            self._serial = None
