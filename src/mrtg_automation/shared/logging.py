import logging
from pathlib import Path

from .paths import LOGS_DIR


def setup_logging(logs_dir: Path | str | None = None, output_dir: Path | str | None = None):
    """
    Setup application-wide logging to file and minimal console output.
    """
    if logs_dir is not None:
        target_dir = Path(logs_dir).expanduser().resolve()
    elif output_dir is not None:
        target_dir = Path(output_dir).expanduser().resolve() / "logs"
    else:
        target_dir = LOGS_DIR

    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "app.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)8s] %(name)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter("[%(levelname)s] %(message)s")
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Suppress verbose loggers
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("webdriver_manager").setLevel(logging.WARNING)


def setup_ocr_logger(logs_dir: Path | str | None = None, output_dir: Path | str | None = None):
    """
    Setup isolated logger for OCR.
    """
    if logs_dir is not None:
        target_dir = Path(logs_dir).expanduser().resolve()
    elif output_dir is not None:
        target_dir = Path(output_dir).expanduser().resolve() / "logs"
    else:
        target_dir = LOGS_DIR

    target_dir.mkdir(parents=True, exist_ok=True)
    log_file = target_dir / "ocr_report.log"

    ocr_logger = logging.getLogger("mrtg_automation.ocr")
    ocr_logger.setLevel(logging.DEBUG)
    ocr_logger.propagate = False

    for handler in ocr_logger.handlers[:]:
        ocr_logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)8s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    ocr_logger.addHandler(file_handler)
