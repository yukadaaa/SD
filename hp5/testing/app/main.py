from fastapi import FastAPI
from app.routes import router

app = FastAPI()

# Подключаем маршруты
app.include_router(router)

# Запуск приложения:
# uvicorn app.main:app --reload
