import queue

from pymavlink import mavutil

from modules.logger import global_logger as logger


class PosData:
    def __init__(
        self, port="udp:127.0.0.1:14551", gps_baudrate=115200, gps_rate_ms=100
    ):
        # set connection with PixHawk
        self._master = mavutil.mavlink_connection(port)
        self._master.wait_heartbeat()
        logger.info(f"got heartbeat on {port}")

        # init data storage
        self.pdata = {}

    def _fetch_PX(self):
        while msg := self._master.recv_match(blocking=False):
            text = msg.to_dict()
            type = text["mavpackettype"]
            if "UNKNOWN" not in type:
                self.pdata[type] = text

    def run(self, stop_value, outque):
        logger.info("start polling pos data")

        while not stop_value.value:
            try:
                # finally poll pixhawk until empty packet
                try:
                    self._fetch_PX()
                except Exception as e:
                    logger.error(f"PixHawk read error {e}")

                # отправляем данные на инференс
                if "RAW_IMU" in self.pdata:
                    outque.put((self.pdata, self.pdata["RAW_IMU"]["time_usec"] / 1000))
                else:
                    outque.put((self.pdata, -1))
                if outque.full():
                    _ = outque.get(timeout=0.05)

            except KeyboardInterrupt:
                logger.warning("keybopard interrupt in posdata poll process")
                break
            except queue.Empty:
                continue

        logger.info("pixhawk, imu, altimeter polling stopped")
