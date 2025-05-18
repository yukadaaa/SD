from fastapi import APIRouter, Response, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse
from modules.camera import Camera
import time
import cv2
import asyncio
import logging
import os
from api.utils.logger import logger
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect
import base64
from pydantic import BaseModel
import threading

router = APIRouter(prefix="/camera", tags=["Camera"])


#глобальные переменные для хранения состояния камеры
cap = None
streaming = False
stress_test_running = False

class CommandRequest(BaseModel):
    command: str
@router.post("/command")
async def handle_command(request: CommandRequest,background_tasks: BackgroundTasks):
    try:
        command = request.command.lower()
        
        #обработка команды для проверки статуса камеры
        if command == "status":
            return await camera_status()

        #обработка команды для получения кадра с камеры
        elif command == "frame":
            return await get_camera_frame()

        #обработка команды для запуска стрима
        elif command == "start_stream":
            width = 640
            height = 480
            return await camera_stream(request, width=width, height=height)

        #обработка команды для остановки стрима
        elif command == "stop_stream":
            return stop_stream()

        #обработка команды для сохранения кадра
        elif command == "save_frame":
            return await save_camera_frame()

        #обработка команды для получения трех кадров разного разрешения
        elif command == "combined-multi-capture":
            return get_real_combined_resolutions()

        #обработка команды для старта стресс теста
        elif command == "start_stress_test":
            return start_stress_test(background_tasks)

        #обработка команды для стопа стресс теста
        elif command == "stop_stress_test":
            return stop_stress_test()

        else:
            logger.warning(f"Неизвестная команда: {command}")
            return {"status": "fail", "message": "Unknown command"}

    except Exception as e:
        logger.error(f"Ошибка при обработке команды: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}


@router.get("/status")
def camera_status():
    try:
        cam = Camera()
        cap = cv2.VideoCapture(cam.id)

        #проверка открытия камеры
        if not cap.isOpened():
            logger.error(f"Камера {cam.id} не доступна")
            return {
                "status": "fail",
                "reason": "Камера не открывается"
            }

        #пытаемся захватить кадр с камеры
        ret, frame = cap.read()
        if not ret:
            logger.error(f"Не удалось получить кадр с камеры {cam.id}")
            return {
                "status": "fail",
                "reason": "Не удалось получить кадр"
            }

        #получаем параметры камеры
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        #получаем кодек
        codec = cap.get(cv2.CAP_PROP_FOURCC)

        #проверка на фокус
        try:
            focus = cap.get(cv2.CAP_PROP_FOCUS)
        except cv2.error:
            focus = "Не поддерживается"

        if codec != 0:
            codec_str = chr(int(codec) & 0xFF) + chr((int(codec) >> 8) & 0xFF) + chr((int(codec) >> 16) & 0xFF) + chr((int(codec) >> 24) & 0xFF)
        else:
            codec_str = "Не определен"

        available_modes = {
            "fps": fps,
            "resolution": f"{width}x{height}",
            "codec": codec_str,
            "focus": focus
        }

        cap.release()  #освобождаем камеру

        logger.info(f"Камера {cam.id} успешно инициализирована и прошла тест")

        return {
            "status": "ok",
            "message": "Камера успешно инициализирована и прошла тест",
            "camera_id": cam.id,
            "modes": available_modes
        }

    except Exception as e:
        logger.error(f"Ошибка при инициализации камеры: {str(e)}")
        return {
            "status": "error",
            "message": f"Ошибка: {str(e)}"
        }


@router.get("/frame")
def get_camera_frame():
    try:
        cam = Camera()
        cap = cv2.VideoCapture(cam.id)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            logger.error(f"Не удалось получить кадр с камеры {cam.id}")
            return {"status": "error", "message": "Не удалось получить кадр"}

        #кодируем изображение в JPEG
        ret, jpeg = cv2.imencode(".jpg", frame)
        if not ret:
            logger.error(f"Ошибка кодирования кадра с камеры {cam.id} в JPEG")
            return {"status": "error", "message": "Ошибка кодирования JPEG"}

        logger.info(f"Кадр с камеры {cam.id} успешно получен")
        return Response(content=jpeg.tobytes(), media_type="image/jpeg")

    except Exception as e:
        logger.error(f"Ошибка при получении кадра: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}


@router.get("/stream")
async def camera_stream(
    request: Request,
    width: int = Query(640, ge=160, le=1920),
    height: int = Query(480, ge=120, le=1080)
):
    global cap, streaming
    if streaming:
        logger.info("Стрим уже запущен")
        return {"message": "Stream already running"}

    #устанавливаем флаг стрима в True
    streaming = True
    logger.info("Запуск стрима")

    async def generate():
        global cap, streaming
        cam = Camera()
        cap = cv2.VideoCapture(cam.id)

        if not cap.isOpened():
            logger.error(f"Не удалось открыть камеру {cam.id}")
            yield (
                b"--frame\r\n"
                b"Content-Type: text/plain\r\n\r\n"
                b"error: Camera not available\r\n"
                b"\r\n"
            )
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        try:
            while streaming:
                if await request.is_disconnected():
                    logger.info("Клиент отключился от стрима")
                    break

                ret, frame = cap.read()
                if not ret:
                    logger.error(f"Не удалось получить кадр с камеры {cam.id}")
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: text/plain\r\n\r\n"
                        b"error: No frame received\r\n"
                        b"\r\n"
                    )
                    continue

                ret, jpeg = cv2.imencode(".jpg", frame)
                if not ret:
                    logger.error(f"Ошибка кодирования кадра с камеры {cam.id} в JPEG")
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: text/plain\r\n\r\n"
                        b"error: JPEG encoding failed\r\n"
                        b"\r\n"
                    )
                    continue

                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" +
                    jpeg.tobytes() +
                    b"\r\n"
                )

                logger.info(f"Кадр с камеры {cam.id} успешно передан")
                await asyncio.sleep(1 / cam.fps_cam)

        except Exception as e:
            logger.error(f"Ошибка при передаче фрейма: {str(e)}")
            yield (
                b"--frame\r\n"
                b"Content-Type: text/plain\r\n\r\n" +
                b"error: " + str(e).encode() + b"\r\n"
                b"\r\n"
            )

        finally:
            cap.release()
            cap = None
            streaming = False
            logger.info("Стрим остановлен")

    return StreamingResponse(generate(), media_type="multipart/x-mixed-replace; boundary=frame")


@router.get("/stop")
def stop_stream():
    global cap, streaming
    if cap and cap.isOpened():
        cap.release()
        cap = None
        streaming = False
        logger.info("Стрим остановлен и камера освобождена")
        return {"message": "Stream stopped and camera released"}
    else:
        logger.info("Нет активного стрима для остановки")
        return {"message": "No active stream to stop"}


@router.get("/save")
def save_camera_frame():
    try:
        cam = Camera()
        cap = cv2.VideoCapture(cam.id)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            logger.error(f"Не удалось получить кадр с камеры {cam.id}")
            return {"status": "error", "message": "Не удалось получить кадр"}

        #папка для сохранения снимков
        save_dir = os.path.join("logs", "captures")
        os.makedirs(save_dir, exist_ok=True)

        #имя файла с текущей датой и временем
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"capture_{timestamp}.jpg"
        filepath = os.path.join(save_dir, filename)

        #сохраняем кадр
        cv2.imwrite(filepath, frame)
        logger.info(f"Кадр с камеры {cam.id} сохранен как {filepath}")

        return {
            "status": "ok",
            "message": "Кадр успешно сохранен",
            "file": filepath
        }

    except Exception as e:
        logger.error(f"Ошибка при сохранении кадра: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}

#WebSocket для стрима с камеры
@router.websocket("/ws/stream")
async def camera_websocket_stream(websocket: WebSocket):
    await websocket.accept()
    cam = Camera()
    cap = cv2.VideoCapture(cam.id)

    if not cap.isOpened():
        await websocket.send_text("error: Camera not available")
        await websocket.close()
        return

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                await websocket.send_text("error: No frame received")
                continue

            ret, jpeg = cv2.imencode(".jpg", frame)
            if not ret:
                await websocket.send_text("error: JPEG encoding failed")
                continue

            frame_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
            await websocket.send_text(frame_base64)  

            await asyncio.sleep(0.1)  

    except WebSocketDisconnect:
        print("Client disconnected")

    finally:
        cap.release()
        cap = None
        print("WebSocket connection closed")


@router.get("/combined-multi-capture")
def get_real_combined_resolutions():
    try:
        cam = Camera()
        resolutions = [(1920, 1080), (1280, 720), (640, 480)]
        captured_frames = []

        for width, height in resolutions:
            cap = cv2.VideoCapture(cam.id)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

            time.sleep(0.1)

            ret, frame = cap.read()
            cap.release()

            if not ret:
                logger.warning(f"Не удалось получить кадр в разрешении {width}x{height}")
                continue

            # Кодируем каждый кадр отдельно
            ret, jpeg = cv2.imencode(".jpg", frame)
            if ret:
                jpeg_base64 = base64.b64encode(jpeg.tobytes()).decode('utf-8')
                captured_frames.append(jpeg_base64)

        if not captured_frames:
            return {"status": "error", "message": "Не удалось получить кадры ни в одном разрешении"}

        return {"imageData": captured_frames}

    except Exception as e:
        logger.error(f"Ошибка при получении кадров с разным разрешением: {str(e)}")
        return {"status": "error", "message": f"Ошибка: {str(e)}"}

@router.get("/stress_test/start")
def start_stress_test(background_tasks: BackgroundTasks):
    global stress_test_running
    if stress_test_running:
        return {"status": "already_running"}

    stress_test_running = True
    background_tasks.add_task(run_camera_stress_test)
    return {"status": "started"}

@router.get("/stress_test/stop")
def stop_stress_test():
    global stress_test_running
    stress_test_running = False
    return {"status": "stopping"}

def run_camera_stress_test():
    global stress_test_running
    cam = Camera()

    while stress_test_running:
        logger.info("Начинаем новый цикл стресс-теста камеры")

        try:
            cap = cv2.VideoCapture(cam.id)
            if not cap.isOpened():
                logger.error("Ошибка: камера не открылась")
                continue

            successful_reads = 0
            for i in range(10):
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Кадр {i+1}/10 не считался")
                else:
                    successful_reads += 1

                time.sleep(0.5)  

            cap.release()
            logger.info(f"Успешно считано {successful_reads}/10 кадров")

            if successful_reads < 10:
                logger.warning("Камера не стабильно работает, есть ошибки при считывании кадров")

        except Exception as e:
            logger.error(f"Ошибка в цикле стресс-теста: {str(e)}")

        time.sleep(10)  

    logger.info("Стресс-тест камеры остановлен")