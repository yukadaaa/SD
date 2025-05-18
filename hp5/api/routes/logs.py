from fastapi import APIRouter
from fastapi.responses import JSONResponse
import os

router = APIRouter()

LOG_FILE_PATH = "logs/app.log"

@router.get("/logs")
def get_logs(limit: int = 50):
    """
    Возвращает последние строки из лог-файла
    """
    if not os.path.exists(LOG_FILE_PATH):
        return JSONResponse(status_code=404, content={"detail": "Log file not found."})

    try:
        with open(LOG_FILE_PATH, "r") as f:
            lines = f.readlines()
            last_lines = lines[-limit:]
            return {"logs": last_lines[::-1]}  
    except Exception as e:
        return JSONResponse(status_code=500, content={"detail": str(e)})
