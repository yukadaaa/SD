import queue
import time

import cv2

from modules.logger import global_logger as logger


class Camera:
    def __init__(self, cap_id: str | None = None):
        self.id = cap_id
        if self.id is None:
            cap_id = self._check_available_ids()

        # Задаем целевое разрешение
        self.target_width = 640
        self.target_height = 480
        # FPS
        self.fps_cam = 30

    def _check_available_ids(self):
        for idx in range(4):
            cap = cv2.VideoCapture(idx)
            if cap.isOpened():
                cap.release()
                time.sleep(0.25)
                self.id = idx
                break
        if self.id is None:
            raise SystemError("No camera found")

    def run(self, stop, outque):
        cap = cv2.VideoCapture(self.id)

        # Устанавливаем формат MJPG для камеры
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        # Устанавливаем разрешение для камеры
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.target_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.target_height)
        # Устанавливаем желаемый FPS
        cap.set(cv2.CAP_PROP_FPS, self.fps_cam)

        assert cap.isOpened(), f"can not connect to camera with id {self.id}"

        logger.info("start polling frames")
        # Разрешение для inference
        while not stop.value:
            try:
                ret, frame = cap.read()
                timestemp = time.time()
                if not ret:
                    logger.error("Not frame!")
                    continue
                outque.put((frame, timestemp))
                if outque.full():
                    _ = outque.get(timeout=0.1)

            except KeyboardInterrupt:
                logger.warning("keybopard interrupt in camera process")
            except queue.Empty:
                continue
            except queue.Full:
                continue
        cap.release()
        logger.info(
            f"frames polling stopped   {not cap.isOpened()}",
        )
