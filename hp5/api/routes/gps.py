from fastapi import APIRouter
from threading import Event, Thread
from queue import Queue, Empty
from utils import gps_utils
import time
import logging
from pydantic import BaseModel

router = APIRouter()

# Модель для получения параметров
class GPSRequest(BaseModel):
    command: str  # Например, "status", "test", "start_stream", etc.

@router.post("/gps_command")
async def handle_gps_command(request: GPSRequest):
    try:
        command = request.command.lower()

        # Обработка команды для статуса GPS
        if command == "status":
            return get_gps_status()

        # Обработка команды для теста GPS
        elif command == "test":
            return test_gps_connection()

        else:
            logger.warning(f"Unknown command: {command}")
            return {"status": "fail", "message": "Unknown command"}

    except Exception as e:
        logger.error(f"Error processing GPS command: {str(e)}")
        return {"status": "error", "message": f"Error: {str(e)}"}


# Настройки
DEVICE_PATH = "/dev/ttyS0"
RATE_MS = 100  # Частота опроса в миллисекундах
BAUDRATE = 115200

# Очередь и поток
stop_event = Event()
gps_queue = Queue(maxsize=1)

gps_reader = gps_utils.GPSData(device=DEVICE_PATH, rate_ms=RATE_MS, baudrate=BAUDRATE)

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def gps_worker():
    while not stop_event.is_set():
        try:
            gps_reader._stream.reset_input_buffer()
            _, parsed = gps_reader._ublox_m8n.read()
            
            if parsed:
                try:
                    gps_queue.put(parsed, timeout=1)
                    logger.info(f"GPS data received: {parsed}")
                except:
                    pass  # Игнорируем ошибку, если очередь заполнена
            else:
                logger.warning("No data received from GPS")

        except Exception as e:
            logger.error(f"Error while reading GPS data: {e}")
        
        # Задержка между запросами
        time.sleep(RATE_MS / 1000)

# Запуск фонового потока
Thread(target=gps_worker, daemon=True).start()

def extract_gps_data(parsed):
    """
    Извлекает данные из парсированного GPS объекта
    """
    def safe_get(attr):
        val = getattr(parsed, attr, None)
        return val() if callable(val) else val

    return {
        "identity": safe_get("identity"),
        "latitude": safe_get("lat"),
        "longitude": safe_get("lon"),
        "altitude": safe_get("alt"),
        "speed": safe_get("speed"),
        "satellites": safe_get("satellites"),
    }

@router.get("/status")
def get_gps_status():
    """
    Статус GPS: пытаемся получить данные из очереди
    """
    try:
        # Получаем данные из очереди
        parsed = gps_queue.get(timeout=2)  # Ждем данные до 2 секунд
    except Empty:
        logger.warning("No GPS data in the queue.")
        return {"status": "no_data", "detail": "No GPS data in the queue yet."}

    data = extract_gps_data(parsed)

    if data["latitude"] in [None, ""] or data["longitude"] in [None, ""]:
        return {
            "status": "no_fix",
            "identity": data["identity"],
            "detail": "GPS connected, but location not yet acquired.",
            "raw_data": str(parsed),
        }

    return {
        "status": "ok",
        "identity": data["identity"],
        "data": {
            "latitude": data["latitude"],
            "longitude": data["longitude"],
            "altitude": data["altitude"] or "unknown",
            "speed": data["speed"] or "unknown",
            "satellites": data["satellites"] or "unknown",
        },
    }

@router.get("/test")
def test_gps_connection():
    """
    Одноразовое ручное чтение, например, если нужно форсированно протестировать GPS.
    """
    try:
        # Создаем временный экземпляр GPS для одноразового чтения
        temp_reader = gps_utils.GPSData(device=DEVICE_PATH, rate_ms=RATE_MS, baudrate=BAUDRATE)
        temp_reader._stream.reset_input_buffer()
        _, parsed = temp_reader._ublox_m8n.read()

        if not parsed:
            logger.warning("No data received during test.")
            return {"status": "no_data", "detail": "Parsed object is empty."}

        data = extract_gps_data(parsed)

        if data["latitude"] in [None, ""] or data["longitude"] in [None, ""]:
            return {
                "status": "no_fix",
                "identity": data["identity"],
                "detail": "GPS connected, but location not yet acquired.",
                "raw_data": str(parsed),
            }

        return {
            "status": "success",
            "identity": data["identity"],
            "data": {
                "latitude": data["latitude"],
                "longitude": data["longitude"],
                "altitude": data["altitude"] or "unknown",
                "speed": data["speed"] or "unknown",
                "satellites": data["satellites"] or "unknown",
            },
        }

    except Exception as e:
        logger.error(f"Error during test GPS connection: {e}")
        return {"status": "error", "detail": str(e)}
