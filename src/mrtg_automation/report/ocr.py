import os
import sys
import re
import logging
import json
from pathlib import Path
import contextlib
from typing import Optional, Any
from mrtg_automation.config import Config
from mrtg_automation.report.gemini_ocr import GeminiLegendExtractor

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
        """Extract numerical values from an MRTG graph screenshot."""
        from mrtg_automation.config import Config
        return cls.extract_mrtg_values_with_metadata(image_path, Config(), progress_callback)["values"]

    @classmethod
    def extract_mrtg_values_with_metadata(cls, image_path: Path, config: Config, progress_callback=None) -> dict[str, Any]:
        """Extract numerical values from an MRTG graph screenshot using PaddleOCR + Gemini fallback."""

        # Safe default metadata
        result = {
            "values": {}, "engine_used": "Paddle (Fallback)", "decision_reason": "both_incomplete",
            "paddle_confidence": 0.0, "paddle_values": {}, "gemini_values": {},
            "gemini_model": "", "paddle_complete": False, "gemini_complete": False
        }

        # 1. PaddleOCR
        paddle_values = {}
        paddle_complete = False
        paddle_confidence = 0.0
        try:
            if progress_callback: progress_callback("start", image_path.name)
            ocr = cls._get_engine()

            # Use proved working predict OR ocr method
            res_iter = None
            if hasattr(ocr, 'predict'): res_iter = ocr.predict(str(image_path))
            elif hasattr(ocr, 'ocr'): res_iter = ocr.ocr(str(image_path))

            all_texts, all_confs = [], []
            if res_iter:
                # Handle v3 list lines and dict result structure
                for res in res_iter:
                    data = res.get('res', res) if isinstance(res, dict) else res
                    if isinstance(data, list):
                        for line in data:
                            if isinstance(line, list) and len(line) > 1:
                                all_texts.append(str(line[1][0]).strip())
                                all_confs.append(float(line[1][1]))
                    elif isinstance(data, dict):
                        texts = data.get('rec_texts', [])
                        all_texts.extend([str(t).strip() for t in texts])
                        # ADDED: Extract confidence from v3 dict result
                        scores = data.get('rec_scores', [])
                        all_confs.extend([float(s) for s in scores if isinstance(s, (int, float))])

            paddle_confidence = sum(all_confs) / len(all_confs) if all_confs else 0.0

            logger.debug(f"All texts: {all_texts}")
            # Proven section-aware fuzzy parser
            def find_values_in_section(section_keywords, texts):
                # find section start
                start_idx = -1
                for i, t in enumerate(texts):
                    if any(kw in t.lower() for kw in section_keywords):
                        start_idx = i
                        break
                if start_idx == -1: return {'Current': 'N/A', 'Average': 'N/A', 'Maximum': 'N/A'}

                # Search within a reasonable window for the section
                section_texts = texts[start_idx:start_idx+15]

                def extract(keyword):
                    for index, text in enumerate(section_texts):
                        if keyword not in text.lower():
                            continue
                        for value_index in range(index + 1, min(index + 5, len(section_texts))):
                            match = re.search(
                                r'(\d+(?:[\.,]\d+)?)\s*([MkGTmkgt]?[Bb]?p?s?)',
                                section_texts[value_index],
                            )
                            if not match:
                                continue
                            value = match.group(1).replace(',', '.')
                            unit = match.group(2).strip()
                            if not unit:
                                for unit_text in section_texts[value_index + 1:value_index + 3]:
                                    unit_match = re.fullmatch(
                                        r'([MkGTmkgt])(?:[Bb]?p?s?)?',
                                        unit_text.strip(),
                                    )
                                    if unit_match:
                                        unit = unit_match.group(1)
                                        break
                            return f"{value} {unit}".strip()
                    return "N/A"

                return {
                    'Current': extract('current'),
                    'Average': extract('average'),
                    'Maximum': extract('max')
                }

            inbound = find_values_in_section(['inbound', 'in'], all_texts)
            outbound = find_values_in_section(['outbound', 'out'], all_texts)

            paddle_values = {
                'Inbound_Current': inbound['Current'],
                'Inbound_Average': inbound['Average'],
                'Inbound_Maximum': inbound['Maximum'],
                'Outbound_Current': outbound['Current'],
                'Outbound_Average': outbound['Average'],
                'Outbound_Maximum': outbound['Maximum'],
            }
            paddle_complete = all(v != "N/A" for v in paddle_values.values())
        except Exception as e:
            logger.warning("PaddleOCR error: %s", str(e))

        # Decision Logic
        paddle_ok = paddle_complete and paddle_confidence >= config.ocr_confidence_threshold

        gemini_called = False
        gemini_res = {"values": {}, "model": "", "complete": False, "error_reason": None}

        # Call Gemini if needed based on policy
        if config.ocr_gemini_observe or not paddle_ok:
            gemini_called = True
            extracted_gemini = GeminiLegendExtractor(config).extract_legend(image_path)
            if isinstance(extracted_gemini, dict):
                gemini_res = {
                    "values": extracted_gemini.get("values", {}),
                    "model": extracted_gemini.get("model", ""),
                    "complete": bool(extracted_gemini.get("complete", False)),
                    "error_reason": extracted_gemini.get("error_reason"),
                }

        final_values = paddle_values
        engine_used, decision_reason = "Paddle", "paddle_confident" if paddle_ok else "paddle_incomplete"

        # Decide
        if paddle_ok and not config.ocr_gemini_observe:
            pass
        elif gemini_res["complete"]:
            engine_used = "Gemini"
            decision_reason = "paddle_error" if not paddle_values else ("paddle_incomplete" if not paddle_complete else "low_confidence")
            final_values = gemini_res["values"]
        elif paddle_complete:
            engine_used, decision_reason = "Paddle", "gemini_unavailable"
        else:
            decision_reason = "both_unknown"

        # Override if observing mismatch
        if config.ocr_gemini_observe and paddle_ok and gemini_res["complete"]:
            if paddle_values != gemini_res["values"]:
                engine_used, decision_reason, final_values = "Gemini", "mismatch_observed", gemini_res["values"]

        result.update({
            "values": final_values, "engine_used": engine_used, "decision_reason": decision_reason,
            "paddle_confidence": paddle_confidence, "paddle_values": paddle_values,
            "gemini_values": gemini_res["values"], "gemini_model": gemini_res["model"],
            "paddle_complete": paddle_complete, "gemini_complete": gemini_res["complete"],
            "gemini_called": gemini_called
        })
        return result
