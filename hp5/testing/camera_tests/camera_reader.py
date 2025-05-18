import cv2

class CameraReader:
    def __init__(self):
        self._cap = None

    def open(self):
        """Открываем камеру"""
        self._cap = cv2.VideoCapture(0)  # Используем первую доступную камеру
        if not self._cap.isOpened():
            print("Не удалось открыть камеру.")
        else:
            print("Камера успешно открыта.")

    def capture_frame(self):
        """Захват кадра с камеры"""
        if self._cap and self._cap.isOpened():
            ret, frame = self._cap.read()
            if ret:
                # Возвращаем изображение в виде массива
                return frame
            else:
                print("Не удалось захватить кадр с камеры.")
        return None

    def close(self):
        """Закрываем камеру"""
        if self._cap:
            self._cap.release()
            print("Камера закрыта.")
