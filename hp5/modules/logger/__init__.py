import logging
import os

from modules.logger.logger_copter import CopterLogger

global_logger = CopterLogger(
    name="CopterOdometry",
    level=logging.DEBUG,
    log_path=os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
    ),
)
