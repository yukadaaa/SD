import websockets
import asyncio

async def test_rotation():
    uri = "ws://localhost:8000/compass/live-test-rotation"
    print(f" Подключение к {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ WebSocket подключен. Ожидание данных...\n")

            while True:
                message = await websocket.recv()
                print(f"📡 Получено сообщение: {message}")
    
    except websockets.ConnectionClosedError:
        print(" Соединение закрыто.")
    except Exception as e:
        print(f" Ошибка подключения: {str(e)}")

# Запуск клиента
if __name__ == "__main__":
    asyncio.run(test_rotation())
