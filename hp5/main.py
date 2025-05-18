# main.py

import os
import time
import traceback
from multiprocessing import Process, Queue, Value
from multiprocessing.sharedctypes import Synchronized

from pymavlink import mavutil

import cfg
from modules import VIO, Camera, PosData
from modules.InfoOnDisplay import send_info_on_display
from modules.logger import global_logger as logger
from utils.data_utils import dump_data, setup_dumping
from utils.gps_utils import (
    change_altitude,
    check_mode,
    get_current_position,
    get_current_waypoint,
    get_mission_count,
    gps2pixhawk,
    set_mode,
    GPSData
)
from utils.image_utils import letterbox

# from nvio import NVIO  # should be after VIO


# Отправка rc значений на pixhawk       
def send_rc(master, channel, rc_value):
    # Для неиспользуемых каналов устанавливаем значения в 65535
    rc_channels = [65535] * 18
    
    # Отправляем значения на третий канал 
    rc_channels[channel] = rc_value
    master.mav.rc_channels_override_send(
        master.target_system,  # target_system
        master.target_component,  # target_component
        *rc_channels  # RC channel list, in microseconds.
    )
    
def get_rc(msg):
        if 'RC_CHANNELS' in msg:
            return msg['RC_CHANNELS']
        else:
            return None
        
        

def initialize_processes(
    stop: Synchronized, vcap: Camera, posque: Queue, vidque: Queue, posque_window: Queue, gpsque: Queue
) -> list:
    # Initialize position data process
    list_processes = []

    posdata = PosData()
    data_poll_process = Process(target=posdata.run, args=(stop, posque), daemon=True)
    data_poll_process.start()
    list_processes.append(data_poll_process)

    video_poll_process = Process(
        target=vcap.run,
        args=(
            stop,
            vidque,
        ),
        daemon=True,
    )
    video_poll_process.start()
    list_processes.append(video_poll_process)
    
    # Initialize GPS data process
    gps = GPSData()
    gps_process = Process(target=gps.run, args=(stop, gpsque))
    gps_process.start()
    
    list_processes.append(gps_process)

    if cfg.SHOW_DISPLAY:
        info_on_display_procecc = Process(
            target=send_info_on_display, args=(stop, posque_window), daemon=True
        )
        info_on_display_procecc.start()
        list_processes.append(info_on_display_procecc)

    return list_processes


def main_loop(
    master,
    stop: Synchronized,
    posque: Queue,
    vidque: Queue,
    data_dir: str | None,
    pos_queue_window: Queue,
    gpsque: Queue
) -> None:
    vio_state = cfg.USE_VIO_FROM_START
    vis_odo = None
    wait_checkpoints = False
    mission_complete = False
    altitude_send = False
    
    
    part_1 = False
    part_2 = False
    
    land_30m = False
    altitude_send_3m =  False
    land_3m = False
    altitude_send_30m =  False
    target_30m = False

    # Init neural part of the odometry
    if cfg.USE_NVIO:
        yolo_model_path = os.path.join(
            os.path.dirname(__file__), "weights", "crossroads_yolov8n_030325.rknn"
        )
        efficient_model_path = os.path.join(
            os.path.dirname(__file__), "weights", "EfficientNet_v2_s_28.rknn"
        )
        nvio = NVIO(
            yolo_model_path, efficient_model_path, 256, 224, cfg.DRAW_YOLO_RESULTS
        )

    # Create variables for debugging
    if cfg.DEBUG:
        voltage = None
        init = True
        start_imu = 0
        start_frame = 0

    logger.info("main_loop")

    # Run neural part of the odometry
    if cfg.USE_NVIO:
        nvio.start()

    lat0 = cfg.DEFAULT_LAT
    lon0 = cfg.DEFAULT_LON
    alt0 = cfg.DEFAULT_ALT
    
    while True:
        try:
            if cfg.DEBUG:
                tic = time.monotonic()

            # Get frame and message from pixhawk
            frame, timestemp_frame = vidque.get()
            result_img = frame.copy()
            msg, timestemp_msg = posque.get()
            
            # Get GPS data from ublox_m8n
            if not gpsque.empty():
                gps = gpsque.get()
                if gps:
                    for key in gps.keys():
                        msg[key] = gps[key]

            # Get data for calculating delta time
            if cfg.DEBUG:
                if init and timestemp_msg != -1:
                    start_imu = timestemp_msg
                    start_frame = timestemp_frame
                    init = False

            # Waiting for turn on VIO
            if not vio_state and not land_30m:
                # Wait for start mission
                if check_mode("AUTO", msg) and not wait_checkpoints:
                    wait_checkpoints = True
                    waypoint_count = 0
                    current_wp = 0

                # Wait for mission's end
                if wait_checkpoints :
                    if not waypoint_count:
                        master.mav.mission_request_list_send(master.target_system, master.target_component)
                        waypoint_count = get_mission_count(msg)
                    if get_current_waypoint(msg) != current_wp:
                        current_wp = get_current_waypoint(msg)
                    mission_complete = (current_wp == (waypoint_count - 1))

                # Prepare for start VIO
                if mission_complete and not part_1:
                    if not check_mode("GUIDED", msg):
                        set_mode("GUIDED", master)
                    else:
                        lat, lon, alt = get_current_position(msg)
                        if lat is not None and lon is not None and not altitude_send:
                            lat0, lon0, alt0 = lat, lon, alt
                            for _ in range(5):
                                change_altitude(lat, lon, cfg.TARGET_ALTITUDE, master)
                            altitude_send = True
                        if abs(alt - cfg.TARGET_ALTITUDE) <= cfg.ALTITUDE_TOLERANCE:
                            vio_state = True
                            land_30m = True
                
            if land_30m and vio_state and not part_1:
                lat, lon, alt = get_current_position(msg)
                if lat is not None and lon is not None and alt is not None and not altitude_send_3m:
                        lat0, lon0, alt0 = lat, lon, alt
                        for _ in range(5):
                            change_altitude(lat, lon, 5, master)
                        altitude_send_3m = True
                if abs(alt - 5) <= cfg.ALTITUDE_TOLERANCE:
                    land_3m = True
                    
            if land_3m and not part_1:
                send_rc(master, 10, 981)
                rc_channels = get_rc(msg)
                if rc_channels:
                    if rc_channels['chan11_raw'] < 1200:
                        part_1 = True
            
            if part_1 and not part_2:
                lat, lon, alt = get_current_position(msg)
                if lat is not None and lon is not None and not altitude_send_30m:
                    lat0, lon0, alt0 = lat, lon, alt
                    change_altitude(lat, lon, cfg.TARGET_ALTITUDE, master)
                    altitude_send_30m = True
                if abs(alt - cfg.TARGET_ALTITUDE) <= cfg.ALTITUDE_TOLERANCE:
                    target_30m = True
                    vio_state = False
                    
            if target_30m and not part_2:
                if check_mode("RTL", msg):  
                    part_2 = True
                else:
                    set_mode("RTL", master)

            # Run VIO
            if vio_state:
                if vis_odo is None:
                    # Initialize Visual Inertial Odometry
                    vis_odo = VIO(lat0, lon0, alt0)
                    logger.info(f"Starting at coordinates: {lat0}, {lon0}, {alt0}")

                msg["VIO"] = vis_odo.add_trace_pt(frame, msg)

            if vio_state and cfg.USE_NVIO:
                nvio.send_frame(msg["VIO"]["crop"])
                results = nvio.get_data()
                if cfg.DRAW_YOLO_RESULTS:
                    result_img, results = results

            # Reshape vio crop to camera shape
            if vio_state and cfg.NADIR_DISPLAY:
                result_img, ratio, dwdh = letterbox(
                    msg["VIO"]["crop"], (480, 640), auto=False
                )

            # Display image
            if cfg.SHOW_DISPLAY:
                if not pos_queue_window.full():
                    pos_queue_window.put((result_img, msg))

            # Dump images and msg
            if cfg.DUMP and data_dir:
                dump_data(data_dir, frame, msg)

            # Send gps data
            gps_data_to_send = gps2pixhawk(msg)
            if gps_data_to_send is not None:
                master.mav.gps_input_send(*gps_data_to_send)

            if cfg.DEBUG:
                # Getting battery voltage
                if "SYS_STATUS" in msg.keys():
                    voltage = msg["SYS_STATUS"]["voltage_battery"]

                # Calculate and show debug information
                fps = 1 / (time.monotonic() - tic)
                if timestemp_msg != -1:
                    timestemp_frame = abs(timestemp_frame - start_frame) * 1000
                    timestemp_msg = abs(timestemp_msg - start_imu)
                    print(
                        f"FPS: {fps:.1f}, Voltage: {voltage if voltage else 'N/A'}, delta: {abs(timestemp_frame - timestemp_msg)}",
                        end="\r",
                    )

        except KeyboardInterrupt:
            # Handle keyboard interrupt
            # mode_id = master.mode_mapping()["LAND"]

            # master.mav.set_mode_send(
            #     master.target_system,
            #     mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            #     mode_id,
            # )
            stop.value = 1

        except Exception as e:
            logger.error(f"Main loop exception: {e} - {traceback.format_exc()}")

        if stop.value:
            logger.info("\nStopping all processes...")
            break

    # Ensure all processes are properly terminated
    stop.value = 1


if __name__ == "__main__":
    # Initialize Mavlink connection
    master = master = mavutil.mavlink_connection(cfg.PORT)
    master.wait_heartbeat()
    logger.info(f"Got heartbeat on {cfg.PORT}")

    # Initialize processes and queues
    stop_value = Value("i", 0)
    pos_queue = Queue(2)
    video_queue = Queue(2)
    gps_queue = Queue(2)

    # Queue for showing results on monitor
    pos_queue_window = Queue(2)

    # Initialize camera
    vcap = Camera()

    # Initialize processes
    processes = initialize_processes(
        stop_value, vcap, pos_queue, video_queue, pos_queue_window, gps_queue
    )

    # Setup data dumping if enabled
    data_directory = None
    if cfg.DUMP:
        data_directory = setup_dumping(cfg.DUMP_DIR, cfg.MIN_FREE_SPACE)
    try:
        # Run the main loop
        main_loop(
            master,
            stop_value,
            pos_queue,
            video_queue,
            data_directory,
            pos_queue_window,
            gps_queue
        )
    finally:
        # Ensure all processes are joined properly
        for process in processes:
            process.terminate()
            process.join()
