import os
import sys
import re
import logging
from pathlib import Path
import contextlib

logger = logging.getLogger('mrtg_automation.ocr')

@contextlib.contextmanager
def _silence_paddlex_teardown():
    """Capture PaddleX post-init teardown noise (Creating model ... lines)."""
    devnull = open(os.devnull, 'w')
    try:
        with contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()

class OCRExtractor:
    _engine = None

    @classmethod
    def _get_engine(cls):
        """Singleton: initialization of PaddleOCR with strict silence."""
        if cls._engine is None:
            # Set environment variables BEFORE importing paddle
            os.environ['GLOG_minloglevel'] = '3'
            os.environ['FLAGS_minloglevel'] = '3'
            os.environ['PADDLE_LOG_LEVEL'] = 'ERROR'
            os.environ['PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK'] = 'True'
            os.environ['PADDLEX_DISABLE_PRINT'] = '1'
            os.environ['FLAGS_enable_pir_api'] = '0'
            os.environ['FLAGS_enable_new_executor'] = '0' 
            os.environ['FLAGS_use_onednn'] = '0' 
            os.environ['FLAGS_use_mkldnn'] = '0'
            os.environ['PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT'] = '0'
            os.environ['FLAGS_use_gpu'] = '0'
            os.environ['KMP_WARNINGS'] = '0'

            has_fd = False
            try:
                _stdout_fd = sys.stdout.fileno()
                _stderr_fd = sys.stderr.fileno()
                _save_stdout = os.dup(_stdout_fd)
                _save_stderr = os.dup(_stderr_fd)
                has_fd = True
            except Exception as e:
                logger.warning(f"Could not redirect stdout/stderr: {e}")

            try:
                import warnings
                warnings.filterwarnings("ignore")
                
                if has_fd:
                    fnull = open(os.devnull, 'w')
                    os.dup2(fnull.fileno(), _stdout_fd)
                    os.dup2(fnull.fileno(), _stderr_fd)
                    
                try:
                    import logging as py_logging
                    for _name in ("paddlex", "paddlex.inference", "paddlex.utils", "paddle", "ppocr"):
                        py_logging.getLogger(_name).setLevel(py_logging.ERROR)
                        py_logging.getLogger(_name).propagate = False

                    with _silence_paddlex_teardown():
                        import paddle
                        paddle.enable_static()
                        from paddleocr import PaddleOCR
                        
                        cls._engine = PaddleOCR(lang='en')
                except ImportError as e:
                    raise ImportError("OCR dependencies are not installed. Please run: pip install -e .[ocr]") from e
                except Exception as e:
                    raise Exception(f"OCR Engine failed to initialize: {e}") from e
            finally:
                if has_fd:
                    os.dup2(_save_stdout, _stdout_fd)
                    os.dup2(_save_stderr, _stderr_fd)
                    os.close(_save_stdout)
                    os.close(_save_stderr)
                    fnull.close()
                
            logger.debug("PaddleOCR engine initialized successfully.")
            
        return cls._engine

    @classmethod
    def extract_mrtg_values(cls, image_path: Path, progress_callback=None) -> dict:
        """
        Extract numerical values from an MRTG graph screenshot using PaddleOCR.
        """
        try:
            if progress_callback:
                progress_callback("start", image_path.name)
            
            ocr = cls._get_engine()
        except ImportError:
            # Re-raise to be handled gracefully
            raise

        logger.debug(f"--- START OCR [{image_path.name}] ---")
        try:
            # Predict
            result_iter = None
            if hasattr(ocr, 'predict'):
                result_iter = ocr.predict(str(image_path))
            elif hasattr(ocr, 'ocr'):
                result_iter = ocr.ocr(str(image_path))
            else:
                logger.error("OCR engine missing predict/ocr methods.")
                return None

            all_texts = []
            for res in result_iter:
                data = res.get('res', res) if isinstance(res, dict) else res
                if isinstance(data, list):
                    for line in data:
                        if isinstance(line, list) and len(line) > 1:
                            text = line[1][0] if isinstance(line[1], tuple) else str(line[1])
                            all_texts.append(str(text).strip())
                elif isinstance(data, dict):
                    texts = data.get('rec_texts', [])
                    all_texts.extend([str(t).strip() for t in texts])

            logger.debug(f"Raw Text Detected: {all_texts}")
            logger.debug(f"Raw OCR result count: {len(all_texts)}; first 5: {all_texts[:5]}")

            def find_value_after(keyword_list, texts, start_search_idx):
                for i in range(start_search_idx, len(texts)):
                    t = texts[i].lower()
                    if any(kw.lower() in t for kw in keyword_list):
                        for j in range(i, min(i + 6, len(texts))):
                            match = re.search(r'(\d+(?:[\.,]\d+)?)\s*([MkGTmkgt]?[Bb]?p?s?)', texts[j])
                            if match:
                                val = match.group(1).replace(',', '.')
                                unit_raw = match.group(2).strip()
                                unit = ""
                                u_low = unit_raw.lower()
                                if 't' in u_low: unit = "T"
                                elif 'g' in u_low: unit = "G"
                                elif 'm' in u_low: unit = "M"
                                elif 'k' in u_low: unit = "k"
                                
                                if not unit:
                                    for k in range(j + 1, min(j + 3, len(texts))):
                                        next_t = texts[k].strip().lower()
                                        if re.match(r'^[tmgkTMGK]$', next_t.strip()):
                                            if 't' in next_t: unit = "T"
                                            elif 'g' in next_t: unit = "G"
                                            elif 'm' in next_t: unit = "M"
                                            elif 'k' in next_t: unit = "k"
                                            break
                                        elif next_t in ['m', 'k', 'g', 't']:
                                            if next_t == 't': unit = "T"
                                            elif next_t == 'g': unit = "G"
                                            elif next_t == 'm': unit = "M"
                                            elif next_t == 'k': unit = "k"
                                            break
                                        elif any(kw in next_t for kw in ['current', 'average', 'maximum', 'inbound', 'outbound', 'cur rent']):
                                            break
                                            
                                if not unit:
                                    unit = "M"
                                return f"{val} {unit}".strip()
                            
                            if 'n/a' in texts[j].lower():
                                continue
                return "N/A"

            inbound_idx = -1
            outbound_idx = -1
            in_kws = ['inbound', 'in-bound', 'in bound', 'inhound', '1nbound', 'nbound', 'inb']
            out_kws = ['outbound', 'out-bound', 'out bound', 'oulbound', '0utbound', 'outb']

            for i, t in enumerate(all_texts):
                t_low = t.lower()
                if any(kw in t_low for kw in in_kws):
                    inbound_idx = i
                if any(kw in t_low for kw in out_kws):
                    outbound_idx = i

            if outbound_idx == -1 and inbound_idx != -1:
                for i in range(inbound_idx + 1, len(all_texts)):
                    if any(kw in all_texts[i].lower() for kw in ['current', 'cur rent', 'cur ren', 'curren']):
                        has_numbers_before = False
                        for j in range(inbound_idx + 1, i):
                            if re.search(r'\d', all_texts[j]):
                                has_numbers_before = True
                                break
                        if has_numbers_before:
                            outbound_idx = i - 1
                            break

            if inbound_idx != -1:
                search_limit = outbound_idx if outbound_idx > inbound_idx else len(all_texts)
                in_area = all_texts[inbound_idx:search_limit]
                in_vals = {
                    'Current': find_value_after(['Current', 'Curren', 'Cur rent', 'Cur ren', 'Cur'], in_area, 0),
                    'Average': find_value_after(['Average', 'Averaqe', 'Avera9e', 'Avera', 'Ave'], in_area, 0),
                    'Maximum': find_value_after(['Maximum', 'Maximu', 'Maxlmu', 'Max'], in_area, 0)
                }
            else:
                in_vals = {'Current': 'N/A', 'Average': 'N/A', 'Maximum': 'N/A'}

            if outbound_idx != -1:
                out_area = all_texts[outbound_idx:]
                out_vals = {
                    'Current': find_value_after(['Current', 'Curren', 'Cur rent', 'Cur ren', 'Cur'], out_area, 0),
                    'Average': find_value_after(['Average', 'Averaqe', 'Avera9e', 'Avera', 'Ave'], out_area, 0),
                    'Maximum': find_value_after(['Maximum', 'Maximu', 'Maxlmu', 'Max'], out_area, 0)
                }
            else:
                out_vals = {'Current': 'N/A', 'Average': 'N/A', 'Maximum': 'N/A'}

            result = {
                'Inbound_Current': in_vals['Current'],
                'Inbound_Average': in_vals['Average'],
                'Inbound_Maximum': in_vals['Maximum'],
                'Outbound_Current': out_vals['Current'],
                'Outbound_Average': out_vals['Average'],
                'Outbound_Maximum': out_vals['Maximum']
            }

            logger.debug(f"Extracted Values: {result}")
            logger.debug(f"--- END OCR [{image_path.name}] ---\n")

            if progress_callback:
                progress_callback("done", image_path.name, result)
                
            return result

        except Exception as e:
            logger.error(f"OCR Critical Error [{image_path.name}]: {e}")
            return None
