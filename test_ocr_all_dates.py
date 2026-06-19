from mrtg_automation.report.excel import ExcelReportGenerator
from mrtg_automation.config import Config
from mrtg_automation.shared.paths import DATA_DIR, CONFIG_DIR, TEMPLATES_DIR, REPORTS_DIR
from mrtg_automation.shared.logging import setup_ocr_logger

setup_ocr_logger()

g = ExcelReportGenerator(Config())
template = TEMPLATES_DIR / 'MRTG-Monthly-Report-on-Internet-Bandwidth-Utilization-by-Telkom.xlsx'
output = REPORTS_DIR / 'MRTG-Monthly-Report-ocr-alldates.xlsx'  # Different output filename!
mapping = CONFIG_DIR / 'list_mrtg_data_position.txt'
target_list = CONFIG_DIR / 'list_mrtg_targets.csv'

summary = g.generate(
    'OCR_IMAGE',
    DATA_DIR,
    template,
    output,
    mapping,
    target_list,
    None  # No date filter = process all 5 dates
)

print(f"ALL DATES TEST DONE: OCR_OK={summary['ocr_ok']}, PARTIAL={summary['ocr_partial']}, FAIL={summary['ocr_fail']}, MISSING={summary['missing_screenshots']}")
print(ExcelReportGenerator.format_summary_table(summary))
