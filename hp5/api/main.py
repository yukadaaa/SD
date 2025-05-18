from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import time

from api.routes import camera, gps, logs, compass, telemetry
from api.utils.logger import logger

from api.utils.pixhawk_port_detector import find_pixhawk_port

app = FastAPI()

#разрешённые источники для CORS
origins = [
    "http://localhost:3000",
    "http://192.168.1.119:3000",
    "http://localhost:5173",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#глобальная переменная с портом Pixhawk
PIXHAWK_PORT = None

#событие старта приложения
@app.on_event("startup")
async def startup_event():
    global PIXHAWK_PORT
    try:
        PIXHAWK_PORT = find_pixhawk_port()
        print(f"✅ Pixhawk найден на порту: {PIXHAWK_PORT}")
    except Exception as e:
        print(f"❌ Ошибка при поиске Pixhawk: {e}")

#логирование запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    client_ip = request.client.host
    logger.info(
        f"{request.method} {request.url.path} from {client_ip} completed in {duration:.2f}s"
    )
    return response

#проверочный эндпоинт
@app.get("/")
def root():
    return {"status": "ok", "message": "Drone test API is alive"}

#подключение роутеров
app.include_router(camera.router)
app.include_router(gps.router, prefix="/gps", tags=["gps"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(compass.router)
app.include_router(telemetry.router)
