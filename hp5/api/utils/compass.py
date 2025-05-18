from pymavlink import mavutil
import time
import glob
from time import sleep
from math import isclose
import logging

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Погрешность для теста
TOLERANCE = 5  # Допустимое отклонение в градусах

CANDIDATE_PORTS = [
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
    "/dev/ttyS*",
    "/dev/serial/by-id/*",
]

# Глобальная переменная для подключения
connection = None

def find_pixhawk_port(baudrate=57600, timeout=3):
    """
    Ищет порт Pixhawk
    """
    for pattern in CANDIDATE_PORTS:
        for port in glob.glob(pattern):
            try:
                logger.info(f"Пробуем подключиться к {port}...")
                global connection
                connection = mavutil.mavlink_connection(port, baud=baudrate)
                connection.wait_heartbeat(timeout=timeout)
                logger.info(f"✅ Найден Pixhawk на {port}")
                return port
            except Exception as e:
                logger.warning(f"❌ {port} не подходит: {e}")
    raise Exception("❗ Pixhawk не найден на доступных портах")


def get_compass_yaw():
    """
    Получает текущий угол компаса (yaw) от Pixhawk.
    """
    try:
        if connection is None:
            find_pixhawk_port()
        
        msg = connection.recv_match(type='VFR_HUD', blocking=True, timeout=2)
        if msg:
            logger.info(f"Получено значение yaw: {msg.heading}")
            return msg.heading
        else:
            logger.warning("Нет данных о yaw")
            return None
    except Exception as e:
        logger.error(f"Ошибка при получении yaw: {e}")
        return None


def test_compass_rotation():
    """
    Тестирование компаса с ручными поворотами на 90° 4 раза.
    """
    try:
        # Получаем начальное значение угла (yaw)
        initial_yaw = get_compass_yaw()
        if initial_yaw is None:
            raise ValueError("Не удалось получить начальное значение угла (yaw).")

        print(f"Начальный угол: {initial_yaw}")
        results = []

        for i in range(1, 5):
            expected_yaw = (initial_yaw + 90 * i) % 360
            print(f"\nПоверни дрон на 90° и нажми Enter для проверки... (Ожидается угол: {expected_yaw})")
            input("Нажми Enter, когда повернёшь дрон...")

            # Получаем текущий угол
            current_yaw = get_compass_yaw()
            if current_yaw is None:
                raise ValueError("Не удалось получить текущий угол (yaw).")

            print(f"Текущий угол: {current_yaw}")
            
            # Проверяем, что угол близок к ожидаемому значению
            if not isclose(current_yaw, expected_yaw, abs_tol=TOLERANCE):
                results.append({
                    "test": f"Test {i * 90}°",
                    "expected": expected_yaw,
                    "actual": current_yaw,
                    "status": "fail",
                    "error": f"Deviation is too high: {abs(current_yaw - expected_yaw)}°"
                })
            else:
                results.append({
                    "test": f"Test {i * 90}°",
                    "expected": expected_yaw,
                    "actual": current_yaw,
                    "status": "pass",
                    "error": None
                })

        # Проверка, был ли успешен тест
        success = all(result["status"] == "pass" for result in results)
        return success, results
    except Exception as e:
        logger.error(f"Compass rotation test failed: {str(e)}")
        return False, [{"test": "Rotation test", "status": "fail", "error": str(e)}]
