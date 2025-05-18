from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from api.utils.compass import (
    test_compass_rotation,
    find_pixhawk_port,
    get_compass_yaw
)
from pydantic import BaseModel
import logging
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
import asyncio
from pymavlink import mavutil

# Настройка логгера
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

router = APIRouter(prefix="/compass", tags=["compass"])

# Модель для POST-запроса
class CompassCommandRequest(BaseModel):
    command: str

def get_basic_compass_status():
    """
    Проверка подключения компаса с Pixhawk.
    """
    try:
        port = find_pixhawk_port()
        if not port:
            return {"connected": False, "error": "Pixhawk not found"}
        
        status_data = {
            "connected": True,
            "port": port,
            "last_update": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        }
        return status_data
    except Exception as e:
        logger.error(f"Ошибка при получении статуса компаса: {str(e)}")
        return {"connected": False, "error": str(e)}


@router.get("/status")
async def get_compass_status():
    """
    Проверка подключения компаса с базовыми данными.
    """
    try:
        status_data = await run_in_threadpool(get_basic_compass_status)
        
        if status_data["connected"]:
            return {
                "status": "ok",
                "port": status_data["port"],
                "message": f"Порт {status_data['port']} обнаружен"
            }
        else:
            return {
                "status": "error",
                "port": "",
                "message": status_data.get("error", "Неизвестная ошибка")
            }
    except Exception as e:
        logger.error(f"Compass status error: {str(e)}")
        return {
            "status": "error",
            "port": "",
            "message": str(e)
        }



@router.get("/test-rotation")
async def test_rotation():
    """
    Тест поворота компаса на 90° 4 раза.
    """
    try:
        success, results = await run_in_threadpool(test_compass_rotation)

        if success:
            return {
                "status": "ok",
                "angle": results.get("angle", 0),
                "message": "Тест успешно завершён"
            }
        else:
            return {
                "status": "error",
                "angle": 0,
                "message": "Ошибка при тестировании"
            }
    except Exception as e:
        logger.error(f"Compass test_rotation error: {str(e)}")
        return {
            "status": "error",
            "angle": 0,
            "message": str(e)
        }


@router.post("/command")
async def handle_compass_command(request: CompassCommandRequest):
    """
    Обработка команд для компаса:
    - status: получить статус устройства
    - test-rotation: запустить тест вращения
    - yaw: получить текущий угол поворота
    """
    command = request.command.lower()

    if command == "status":
        status_data = await run_in_threadpool(get_basic_compass_status)

        if status_data["connected"]:
            return {
                "status": "ok",
                "port": status_data["port"],
                "message": f"Порт {status_data['port']} обнаружен",
                "last_update": status_data["last_update"]
            }
        else:
            return {
                "status": "error",
                "port": "",
                "message": status_data.get("error", "Неизвестная ошибка")
            }

    elif command == "test-rotation":
        result, data = await run_in_threadpool(test_compass_rotation)
        
        if result:
            return {
                "status": "ok",
                "angle": data.get("angle", 0),
                "message": "Тест успешно завершён"
            }
        else:
            return {
                "status": "error",
                "angle": 0,
                "message": "Ошибка при тестировании"
            }

    elif command == "yaw":
        try:
            yaw_value = await run_in_threadpool(get_compass_yaw)
            return {
                "status": "ok",
                "yaw": yaw_value,
                "message": "Текущий угол поворота получен успешно"
            }
        except Exception as e:
            logger.error(f"Ошибка при получении yaw компаса: {str(e)}")
            return {
                "status": "error",
                "yaw": 0,
                "message": str(e)
            }
    
    else:
        logger.warning(f"Неизвестная команда: {command}")
        return {
            "status": "fail",
            "message": "Unknown command"
        }

@router.websocket("/live-test-rotation")
async def live_test_rotation(websocket: WebSocket):
    await websocket.accept()
    try:
        # сообщение клиенту, что подключение установлено
        await websocket.send_text("Подключение установлено, начинаем тестирование поворота компаса...")

        port = find_pixhawk_port()
        if not port:
            await websocket.send_text("Ошибка: не удалось найти порт для Pixhawk.")
            return
        connection = mavutil.mavlink_connection(port)
        connection.wait_heartbeat()

        # повороты на 90 (4 раза)
        for i in range(1, 5):
            await websocket.send_text(f"Поворот {i*90}° в процессе...")
            # отправляем команду на поворот
            connection.mav.command_long_send(
                connection.target_system, 
                connection.target_component,
                mavutil.mavlink.MAV_CMD_CONDITION_YAW,
                0,  # confirmation
                i*90,  # угол поворота
                0,  # направление (по часовой стрелке)
                0, 0, 0, 0, 0
            )

            # задержка для завершения поворота
            await asyncio.sleep(5) 

            # получаем текущий угол компаса
            current_yaw = connection.recv_match(type='ATTITUDE', blocking=True).yaw
            await websocket.send_text(f"Поворот {i*90}° завершен. Текущий угол компаса: {current_yaw * 180 / 3.14159:.2f}°")

        await websocket.send_text("Тестирование компаса завершено.")
    
    except Exception as e:
        await websocket.send_text(f"Ошибка: {str(e)}")
    finally:
        await websocket.close()
