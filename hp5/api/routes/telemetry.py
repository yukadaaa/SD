from fastapi import APIRouter
from datetime import datetime
from pymavlink import mavutil
import logging
import threading
import time

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# Настройка логирования
logging.basicConfig(
    filename='logs/telemetry.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Глобальные переменные
connection = None
telemetry_data = {}
is_collecting = False
collect_thread = None


def find_pixhawk_port(baudrate=57600, timeout=3):
    """
    Ищет Pixhawk на доступных портах.
    """
    from glob import glob
    CANDIDATE_PORTS = [
        "/dev/ttyUSB*",
        "/dev/ttyACM*",
        "/dev/ttyS*",
        "/dev/serial/by-id/*",
    ]

    for pattern in CANDIDATE_PORTS:
        for port in glob(pattern):
            try:
                print(f"Пробуем подключиться к {port}...")
                connection = mavutil.mavlink_connection(port, baud=baudrate)
                connection.wait_heartbeat(timeout=timeout)
                print(f"✅ Найден Pixhawk на {port}")
                return connection
            except Exception as e:
                print(f"❌ {port} не подходит: {e}")
    raise Exception("❗ Pixhawk не найден на доступных портах")


def collect_telemetry():
    """
    Фоновая задача для сбора телеметрии.
    """
    global is_collecting, telemetry_data

    while is_collecting:
        msg = connection.recv_match(blocking=True)
        if not msg:
            continue

        if msg.get_type() == 'GLOBAL_POSITION_INT':
            telemetry_data["lat"] = msg.lat / 1e7
            telemetry_data["lon"] = msg.lon / 1e7
            telemetry_data["altitude"] = msg.relative_alt / 1000.0
        elif msg.get_type() == 'VFR_HUD':
            telemetry_data["groundspeed"] = msg.groundspeed
            telemetry_data["airspeed"] = msg.airspeed
        elif msg.get_type() == 'SYS_STATUS':
            telemetry_data["voltage_battery"] = msg.voltage_battery / 1000.0

        # Логирование данных в файл
        logging.info(f"Telemetry Data: {telemetry_data}")
        time.sleep(1)


@router.get("/start")
async def start_telemetry():
    """
    Запуск сбора телеметрии.
    """
    global connection, is_collecting, collect_thread

    if is_collecting:
        return {"status": "already_running"}

    try:
        connection = find_pixhawk_port()
        is_collecting = True
        collect_thread = threading.Thread(target=collect_telemetry)
        collect_thread.start()
        return {"status": "started"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


@router.get("/stop")
async def stop_telemetry():
    """
    Остановка сбора телеметрии.
    """
    global is_collecting, collect_thread

    if not is_collecting:
        return {"status": "not_running"}

    is_collecting = False
    collect_thread.join()
    return {"status": "stopped"}


@router.get("/status")
async def get_telemetry_status():
    """
    Получение текущих данных телеметрии.
    """
    if not is_collecting:
        return {"status": "not_running"}
    
    return {"status": "collecting", "data": telemetry_data}
