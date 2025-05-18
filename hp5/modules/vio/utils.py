import datetime

import numpy as np


def count_none_recursive(arr):
    count = 0
    for item in arr:
        if isinstance(item, list) or isinstance(item, np.ndarray):
            count += count_none_recursive(item)
        elif item is None:
            count += 1
    return count


def pt2h(abs_pressure, temperature, P0):
    return (1 - abs_pressure/P0) * 8.3144598 * (273.15 + temperature/100) / 9.80665 / 0.0289644


def calc_GPS_week_time():
    today = datetime.date.today()
    now = datetime.datetime.now()
    epoch = datetime.date(1980, 1, 6)

    epochMonday = epoch - datetime.timedelta(epoch.weekday())
    todayMonday = today - datetime.timedelta(today.weekday())
    GPS_week = int((todayMonday - epochMonday).days / 7)
    GPS_ms = (
        ((today - todayMonday).days * 24 + now.hour) * 3600000
        + now.minute * 60000
        + now.second * 1000
        + int(now.microsecond / 1000)
    )
    return GPS_week, GPS_ms


def fetch_angles(msg):
    angles = msg["ATTITUDE"]
    angles["yaw"] = -angles["yaw"]
    return angles


def extract_neighborhood(image, keypoint, size):
    x, y = keypoint
    half_size = size // 2

    x_start = x - half_size
    x_end = x + half_size
    y_start = y - half_size
    y_end = y + half_size
    # Reject keypoints too close to boundaries
    if x_start < 0 or x_end > image.shape[1] or y_start < 0 or y_end > image.shape[0]:
        return None

    nbh = image[y_start:y_end, x_start:x_end]
    # Reject keypoints  with mask pixels
    if np.any(nbh == 0):
        return None
    else:
        return nbh


def fisheye2rectilinear(focal, pp, rw, rh, fproj="equidistant"):
    # Create a grid for the rectilinear image
    rx, ry = np.meshgrid(np.arange(rw) - rw // 2, np.arange(rh) - rh // 2)
    r = np.sqrt(rx**2 + ry**2) / focal

    angle_n = np.arctan(r)
    if fproj == "equidistant":
        angle_n = angle_n
    elif fproj == "orthographic":
        angle_n = np.sin(angle_n)
    elif fproj == "stereographic":
        angle_n = 2 * np.tan(angle_n / 2)
    elif fproj == "equisolid":
        angle_n = 2 * np.sin(angle_n / 2)

    angle_t = np.arctan2(ry, rx)

    pt_x = focal * angle_n * np.cos(angle_t) + pp[0]
    pt_y = focal * angle_n * np.sin(angle_t) + pp[1]

    map_x = pt_x.astype(np.float32)
    map_y = pt_y.astype(np.float32)

    return map_x, map_y


def preprocess_frame(frame, mask):
    frame = np.where(mask, frame, 0)
    return frame
