import logging
from .paths import LOGS_DIR

def setup_logging():
    """
    Setup application-wide logging to file and minimal console output.
    """
    log_file = LOGS_DIR / "app.log"
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)8s] %(name)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.WARNING)
    console_formatter = logging.Formatter('[%(levelname)s] %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose loggers
    logging.getLogger('PIL').setLevel(logging.WARNING)

def setup_ocr_logger():
    """
    Setup isolated logger for OCR.
    """
    from .paths import LOGS_DIR
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / "ocr_report.log"
    
    ocr_logger = logging.getLogger('mrtg_automation.ocr')
    ocr_logger.setLevel(logging.DEBUG)
    ocr_logger.propagate = False
    
    for handler in ocr_logger.handlers[:]:
        ocr_logger.removeHandler(handler)
        
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('[%(asctime)s] [%(levelname)8s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_formatter)
    ocr_logger.addHandler(file_handler)
