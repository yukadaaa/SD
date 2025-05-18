import logging
import logging.handlers
import os


def create_formatters() -> tuple[logging.Formatter, logging.Formatter]:
    """
    Create and return simple and detailed log formatters.

    Returns
    -------
    tuple[logging.Formatter, logging.Formatter]
        A tuple containing a simple formatter and a detailed formatter.
    """
    simple_formatter = logging.Formatter(fmt="%(levelname)s:\t  %(message)s")

    detailed_formatter = logging.Formatter(
        fmt="%(levelname)s:\t%(asctime)s >>> %(message)s",
        datefmt="%d %B %Y | %H:%M:%S (%Z)",
    )

    return simple_formatter, detailed_formatter


def create_handlers(
    simple_formatter: logging.Formatter,
    detailed_formatter: logging.Formatter,
    log_file: str,
) -> list[logging.Handler]:
    """
    Create and configure logging handlers.

    Parameters
    ----------
    simple_formatter : logging.Formatter
        Formatter for simple log output.
    detailed_formatter : logging.Formatter
        Formatter for detailed log output.
    log_file : str
        Path to the log file.

    Returns
    -------
    list[logging.Handler]
        A list of configured logging handlers.
    """
    handlers = []

    stderr_handler = logging.StreamHandler()
    stderr_handler.setLevel(logging.DEBUG)
    stderr_handler.setFormatter(simple_formatter)
    handlers.append(stderr_handler)

    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        os.mkdir(log_dir)
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file, maxBytes=10_000_000, backupCount=3
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(detailed_formatter)
    handlers.append(file_handler)

    return handlers


def global_logger_configure(log_file: str = f"logs/{__name__}.log") -> None:
    """
    Configure the global logger with default settings.

    Parameters
    ----------
    log_file : str, optional
        Path to the log file (default is "logs/<module_name>.log").
    """
    # Formatters
    simple_formatter, detailed_formatter = create_formatters()

    # Handlers
    handlers = create_handlers(
        simple_formatter=simple_formatter,
        detailed_formatter=detailed_formatter,
        log_file=log_file,
    )

    # Logger configuration
    logging.basicConfig(level=logging.DEBUG, handlers=handlers)
