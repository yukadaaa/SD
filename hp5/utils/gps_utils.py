import queue
from datetime import date, datetime, timedelta
from time import time, sleep

import numpy as np
from pymavlink import mavutil
from pyubx2 import NMEA_PROTOCOL, SET, UBXMessage, UBXReader
from serial import Serial


def datetime2text(gps_data: dict) -> dict:
    if "time" in gps_data.__dict__.keys():
        if (tic := gps_data.__dict__["time"]) != "":
            gps_data.__dict__["time"] = tic.strftime("%H:%M:%S.%f")
    if "date" in gps_data.__dict__.keys():
        if (dic := gps_data.__dict__["date"]) != "":
            gps_data.__dict__["date"] = dic.strftime("%d/%m/%Y")

    return gps_data


def calc_GPS_week_time(dic: str, tic: str) -> tuple[int, int]:
    today = datetime.strptime(dic, "%d/%m/%Y").date()
    now = datetime.strptime(tic, "%H:%M:%S.%f").time()
    epoch = date(1980, 1, 6)

    epochMonday = epoch - timedelta(epoch.weekday())
    todayMonday = today - timedelta(today.weekday())
    GPS_week = int((todayMonday - epochMonday).days / 7)
    GPS_ms = (
        ((today - todayMonday).days * 24 + now.hour) * 3600000
        + now.minute * 60000
        + now.second * 1000
        + int(now.microsecond / 1000)
    )
    return GPS_week, GPS_ms


def get_current_position(msg: dict) -> tuple[float | None, float | None, float | None]:
    lat, lon, alt = None, None, None
    if "GLOBAL_POSITION_INT" in msg:
        lat = msg["GLOBAL_POSITION_INT"]["lat"] / 1e7
        lon = msg["GLOBAL_POSITION_INT"]["lon"] / 1e7
        alt = msg["GLOBAL_POSITION_INT"]["relative_alt"] / 1000

    return lat, lon, alt


def change_altitude(lat: float, lon: float, alt: int, master):
    master.mav.set_position_target_global_int_send(
        0,  # time_boot_ms
        master.target_system,
        master.target_component,
        mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,  # Высота относительно земли
        0b0000111111111000,  # Игнорируем ненужные параметры (оставляем только alt)
        int(lat * 1e7),
        int(lon * 1e7),
        alt,  # Текущая широта, долгота, новая высота
        0,
        0,
        0,  # Скорости (не задаем)
        0,
        0,
        0,  # Ускорение
        0,  # Yaw (угол поворота)
        0,  # yaw_rate (скорость поворота)
    )


def check_msg(msg: dict) -> dict | None:
    msg_keys = msg.keys()
    if not (
        ("GNRMC" in msg_keys)
        and ("GNVTG" in msg_keys)
        and ("GNGGA" in msg_keys)
        and ("GNGSA" in msg_keys)
    ):
        return None
    elif msg["GNRMC"]["status"] == "V":
        return None

    return msg


def check_mode(target_mode: str, msg: dict) -> bool:
    if "HEARTBEAT" not in msg:
        return False
    mode_mapping = {3: "AUTO", 4: "GUIDED", 6: "RTL"}
    current_mode = mode_mapping.get(msg["HEARTBEAT"]["custom_mode"], "UNKNOWN")

    return current_mode == target_mode


def set_mode(mode: str, master):
    mode_mapping = {"AUTO": 3, "GUIDED": 4, "RTL": 6}
    if mode in mode_mapping:
        master.mav.set_mode_send(
            master.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_mapping[mode],
        )


def get_mission_count(msg: dict):
    if "MISSION_COUNT" not in msg:
        return 0

    return msg["MISSION_COUNT"]["count"]


def get_current_waypoint(msg: dict):
    if "MISSION_CURRENT" not in msg:
        return 0

    return msg["MISSION_CURRENT"]["seq"]


def calc_vels(msg: dict, flags: int) -> tuple[int, float, float, float]:
    cogt = msg["GNVTG"]["cogt"]
    sogk = msg["GNVTG"]["sogk"]
    if cogt == "" or sogk == "":
        flags = flags | mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_HORIZ
        veln = 0
        vele = 0
    else:
        cogt = float(cogt) / 180 * np.pi
        sogm = float(sogk) / 3.6
        veln = sogm * np.cos(cogt)
        vele = sogm * np.sin(cogt)
    veld = 0

    return flags, float(veln), float(vele), float(veld)


def gps2pixhawk(msg: dict) -> list | None:
    if "VIO" in msg:
        viom = msg["VIO"]
        timestamp = int(viom["timestamp"] * 10**6)
        flags = (
            mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_VERT
            | mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VERTICAL_ACCURACY
            | mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_HORIZONTAL_ACCURACY
        )
        gps_ms = viom["GPS_ms"]
        gps_week = viom["GPS_week"]
        lat = int(viom["lat"] * 10**7)
        lon = int(viom["lon"] * 10**7)
        alt = viom["alt"]
        hdop = 1.0
        vdop = 1.0
        veln = viom["veln"]
        vele = viom["vele"]
        veld = viom["veld"]
        sat_num = 10
    else:
        msg = check_msg(msg)
        if msg is None:
            return None

        timestamp = int(time() * 10**6)
        flags = mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_VERT
        gps_week, gps_ms = calc_GPS_week_time(
            msg["GNRMC"]["date"], msg["GNRMC"]["time"]
        )
        lat = int(msg["GNRMC"]["lat"] * 10**7)
        lon = int(msg["GNRMC"]["lon"] * 10**7)
        alt = 0
        hdop = msg["GNGSA"]["HDOP"]
        vdop = msg["GNGSA"]["VDOP"]
        flags, veln, vele, veld = calc_vels(msg, flags)
        sat_num = msg["GNGGA"]["numSV"]

    return [
        timestamp,  # Timestamp (micros since boot or Unix epoch)
        0,  # GPS sensor id in th, e case of multiple GPS
        flags,  # flags to ignore 8, 16, 32 etc
        # (mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_HORIZ |
        # mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VEL_VERT |
        # mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_SPEED_ACCURACY) |
        # mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_HORIZONTAL_ACCURACY |
        # mavutil.mavlink.GPS_INPUT_IGNORE_FLAG_VERTICAL_ACCURACY,
        gps_ms,  # GPS time (milliseconds from start of GPS week)
        gps_week,  # GPS week number
        3,  # 0-1: no fix, 2: 2D fix, 3: 3D fix. 4: 3D with DGPS. 5: 3D with RTK
        lat,  # Latitude (WGS84), in degrees * 1E7
        lon,  # Longitude (WGS84), in degrees * 1E7
        alt,  # data['GNGGA']['alt'], # Altitude (AMSL, not WGS84), in m (positive for up)
        hdop,  # GPS HDOP horizontal dilution of precision in m
        vdop,  # GPS VDOP vertical dilution of precision in m
        veln,  # GPS velocity in m/s in NORTH direction in earth-fixed NED frame
        vele,  # GPS velocity in m/s in EAST direction in earth-fixed NED frame
        veld,  # GPS velocity in m/s in DOWN direction in earth-fixed NED frame
        0.6,  # GPS speed accuracy in m/s
        5.0,  # GPS horizontal accuracy in m
        3.0,  # GPS vertical accuracy in m
        sat_num,  # Number of satellites visible,
    ]


def config_ublox(port: str, rate_ms: int, baudrate: int) -> None:
    baudrate_arr = (9600, 19200, 38400, 57600, 115200, 230400)

    for baud in baudrate_arr:
        with Serial(port, baud, timeout=1) as stream:
            
            # Установка частоты 5 Гц (сообщения каждые 200 мс)
            ubx_rate_5hz = bytes.fromhex('B5 62 06 08 06 00 C8 00 C8 00 00 00 DE 6A')
            # Отправить команду изменения частоты
            stream.write(ubx_rate_5hz)
            sleep(0.5)
            
            # Настраиваем частоту сообщений (мс)
            msg_rate = UBXMessage(
                "CFG",
                "CFG-RATE",
                SET,
                measRate=rate_ms,
                navRate=1,
                timeRef=1,
            )
            stream.write(msg_rate.serialize())  # updating...

            # Настраиваем скорость UART1
            uart1set = UBXMessage(
                "CFG",
                "CFG-PRT",
                SET,
                portID=1,
                enable=0,
                pol=0,
                pin=0,
                thres=0,
                charLen=3,
                parity=4,
                nStopBits=0,
                baudRate=baudrate,
                inUBX=1,
                inNMEA=1,
                outUBX=0,
                outNMEA=1,
                extendedTxTimeout=0,
            )
            stream.write(uart1set.serialize())  # updating...

    # Сохраняем конфигурацию в энергонезависимой памяти
    with Serial(port, baudrate, timeout=1) as stream:
        # send command CFG-CFG
        msg_cfg = UBXMessage(
            "CFG",
            "CFG-CFG",
            SET,
            saveMask=b"\x1f\x1f\x00\x00",
            devBBR=1,
            devFlash=1,
            devEEPROM=1,
        )
        stream.write(msg_cfg.serialize())


class GPSData:
    def __init__(
        self,
        device: str = "/dev/ttyS0",
        rate_ms: int = 100,
        baudrate: int = 115200,
        timeout: float = 3,
    ) -> None:
        config_ublox(device, rate_ms=rate_ms, baudrate=baudrate)

        self._stream = Serial(device, baudrate=baudrate, timeout=timeout)
        self._ublox_m8n = UBXReader(self._stream, protfilter=NMEA_PROTOCOL)

        self.data = {}

    def run(self, stop_event, outque):
        print("start polling GPS sensor")
        while not stop_event.value:
            try:
                # read GPS
                for jj in range(12):
                    _, parsed_data = self._ublox_m8n.read()
                    if parsed_data is not None:
                        # convert to string to comply with json dump
                        gps_data_id = parsed_data.identity
                        self.data[gps_data_id] = datetime2text(parsed_data).__dict__
                    else:
                        self.data = None
                        break
                outque.put(self.data)
                if outque.full():
                    _ = outque.get(timeout=1)

            except Exception as e:
                print(f"GPS sensor error {e}")
            except queue.Empty:
                continue
            except KeyboardInterrupt:
                break

        self._stream.close()
        print("stop polling GPS sensor")


if __name__ == "__main__":
    rate_ms = 100
    baudrate = 115200
    device = "/dev/ttyS0"
    
    config_ublox(device, rate_ms=rate_ms, baudrate=baudrate)

    stream = Serial(device, baudrate=baudrate, timeout=1)
    ublox_m8n = UBXReader(stream, protfilter=NMEA_PROTOCOL)
    data = {}
    while True:
        try:
            # read GPS
            for jj in range(12):
                _, parsed_data = ublox_m8n.read()
                if parsed_data is not None:
                    # convert to string to comply with json dump
                    gps_data_id = parsed_data.identity
                    data[gps_data_id] = datetime2text(parsed_data).__dict__
                else:
                    data = None
                    break
            print(data)
        except Exception as e:
                print(f"GPS sensor error {e}")