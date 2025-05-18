import datetime
import logging

from modules.logger.utils import create_formatters, create_handlers


class CopterLogger(logging.Logger):
    def __init__(self, name: str, level: int = logging.DEBUG, log_path: str = "logs/"):
        super().__init__(name=name, level=level)

        # Formatters
        simple_formatter, detailed_formatter = create_formatters()

        # Handlers
        handlers = create_handlers(
            simple_formatter=simple_formatter,
            detailed_formatter=detailed_formatter,
            log_file=f"{log_path}/{name}_{datetime.datetime.now().strftime('%Y-%m-%d.%H-%M-%S.%f')[:-3]}.log",
        )

        # Logger configuration
        for handler in handlers:
            self.addHandler(handler)
