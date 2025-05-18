import datetime
import json
import os
import shutil
import time

import cv2
import numpy as np

from modules.logger import global_logger as logger


def serialize(data):
    if isinstance(data, dict):
        return {key: serialize(value) for key, value in data.items()}
    elif isinstance(data, (list, tuple)):
        return [serialize(element) for element in data]
    elif isinstance(data, (bool, int, float, str)):
        return data
    else:
        return ""


def get_drive_space(folder_path: str) -> tuple[int, int, int]:
    total, used, free = shutil.disk_usage(folder_path)
    return total, used, free


def get_folder_size(folder_path: str) -> int:
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            # Skip if the file is a symbolic link
            if not os.path.islink(filepath):
                total_size += os.path.getsize(filepath)
    return total_size


def setup_dumping(dump_dir: str, min_free_space: int) -> str:
    ipynb_dir = os.path.join(dump_dir, ".ipynb_checkpoints")
    if os.path.isdir(ipynb_dir):
        shutil.rmtree(ipynb_dir)

    total, used, free = get_drive_space(dump_dir)
    dump_size = get_folder_size(dump_dir)
    logger.info(f"Size of dump folder is {dump_size}, space left is {free}")
    assert free > min_free_space, f"Empty log dir {dump_dir} to have enough disk space"

    ct = datetime.datetime.now()
    count_files = len(os.listdir(dump_dir)) + 1
    timestr = f"{ct.year}_{ct.month}_{ct.day}_{ct.hour}_{ct.minute}_{ct.second}_num_{count_files}"
    data_dir = os.path.join(dump_dir, timestr)
    os.makedirs(data_dir)
    return data_dir


def dump_data(data_dir: str, frame: np.ndarray, msg: dict):
    name = str(int(time.monotonic() * 1000))
    msg_path = os.path.join(data_dir, f"{name}.json")
    img_path = os.path.join(data_dir, f"{name}.jpg")
    cv2.imwrite(img_path, frame)
    with open(msg_path, "w") as f:
        json.dump(serialize(msg), f)
