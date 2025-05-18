# cfg.py

# Mavlink port configuration
PORT = 'udp:127.0.0.1:14550'

# Dump directory and settings
DUMP_DIR = '/home/orangepi/dumps'
MIN_FREE_SPACE = 2**31  # bytes

# Flags for dumping and sending data
DUMP = False

# Use VIO from program's start or at some moment at flight
USE_VIO_FROM_START = False

# Print debug info in terminal
DEBUG = True

# Info on display
SHOW_DISPLAY = True

# Display mode
NADIR_DISPLAY = True

# Draw centers of roofs, crossroads, roof_corners
DRAW_YOLO_RESULTS = False

# Is it necessary to use NVIO module
USE_NVIO = False

# Pin GPIO for VIO
PIN_STATUS_VIO = 15

# GPS mode configuration
GPS_MODE = 'vio'  # Options: 'gps', 'vio'

# Default GPS coordinates (used if GPS data is not available)
DEFAULT_LAT = 54.84309569281793
DEFAULT_LON = 83.09851770880381
DEFAULT_ALT = 204

# Altitude where to start VIO after mission
TARGET_ALTITUDE = 30
ALTITUDE_TOLERANCE = 3
