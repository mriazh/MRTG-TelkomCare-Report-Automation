import os
os.environ['INSERT_IMAGES'] = 'False'
import logging
import time
from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.config import Config
from mrtg_automation.shared.paths import DATA_DIR, CONFIG_DIR, TEMPLATES_DIR, REPORTS_DIR, LOGS_DIR

logger = logging.getLogger('mrtg_automation')
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(LOGS_DIR / 'ocr_report_c.log', encoding='utf-8')
fh.setFormatter(logging.Formatter('[%(asctime)s] [%(levelname)8s] %(message)s', '%Y-%m-%d %H:%M:%S'))
logger.addHandler(fh)

g = ExcelReportGenerator(Config())
template = TEMPLATES_DIR / 'MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx'
output = REPORTS_DIR / 'MRTG-Monthly-Report-ocr-noimg.xlsx'
mapping = CONFIG_DIR / 'list_mrtg_data_position.txt'
target_list = CONFIG_DIR / 'list_mrtg_data.txt'

start = time.time()
summary = g.generate('OCR_IMAGE', DATA_DIR, template, output, mapping, target_list, '20260401')
end = time.time()

print(f"C DONE: OK={summary['ocr_ok']}, FAIL={summary['ocr_fail']}, IMAGES_INSERTED={summary['image_inserted']}")
print(f"TIME: {end - start:.2f}s")
