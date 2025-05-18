import serial

class GPSReader:
    def __init__(self, port):
        self.port = port
        self._stream = None

    def open(self):
        """Открываем подключение к GPS"""
        try:
            self._stream = serial.Serial(self.port, baudrate=9600, timeout=1)
            if self._stream.is_open:
                print(f"GPS подключен на {self.port}")
        except serial.SerialException as e:
            print(f"Ошибка подключения к GPS: {e}")
            self._stream = None

    def read_data(self):
        """Считываем данные с GPS"""
        if self._stream and self._stream.is_open:
            try:
                line = self._stream.readline().decode('ascii', errors='ignore').strip()
                return line
            except serial.SerialException as e:
                print(f"Ошибка чтения данных с GPS: {e}")
        return None

    def close(self):
        """Закрываем подключение к GPS"""
        if self._stream and self._stream.is_open:
            self._stream.close()
            print("GPS отключен")
