import glob
from pymavlink import mavutil

CANDIDATE_PORTS = [
    "/dev/ttyUSB*",
    "/dev/ttyACM*",
    "/dev/ttyS*",
    "/dev/serial/by-id/*",
]

def find_pixhawk_port(baudrate=57600, timeout=3):
    for pattern in CANDIDATE_PORTS:
        for port in glob.glob(pattern):
            try:
                print(f"Пробуем подключиться к {port}...")
                master = mavutil.mavlink_connection(port, baud=baudrate)
                master.wait_heartbeat(timeout=timeout)
                print(f"✅ Найден Pixhawk на {port}")
                return port
            except Exception as e:
                print(f"❌ {port} не подходит: {e}")
    raise Exception("❗ Pixhawk не найден на доступных портах")
