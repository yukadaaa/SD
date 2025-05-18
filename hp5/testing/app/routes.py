from fastapi import APIRouter
from gps_tests.gps_reader import GPSReader
from camera_tests.camera_reader import CameraReader

router = APIRouter()

@router.get("/test/gps")
async def test_gps():
    gps_reader = GPSReader('/dev/ttyUSB0')
    gps_reader.open()
    data = gps_reader.read_data()
    gps_reader.close()
    return {"gps_data": data}

@router.get("/test/camera")
async def test_camera():
    camera_reader = CameraReader()
    camera_reader.open()
    frame = camera_reader.capture_frame()
    camera_reader.close()
    return {"frame": "captured"}  # Здесь можно отправить информацию о кадре
