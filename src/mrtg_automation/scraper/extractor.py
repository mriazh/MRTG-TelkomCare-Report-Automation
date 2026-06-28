"""
Graph Extractor for TelkomCare MRTG portal.
"""
import logging
import time
from pathlib import Path
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException, NoAlertPresentException

logger = logging.getLogger('mrtg_automation.scraper.extractor')

class GraphExtractor:
    def __init__(self, driver, mode='sid'):
        self.driver = driver
        self.mode = mode.lower()
        self.last_status = None
        self.last_error = None
        self.last_validation_error = None

    def dismiss_alert_if_present(self) -> bool:
        """Dismiss browser alert if present. Returns True if an alert was dismissed."""
        try:
            alert = self.driver.switch_to.alert
            text = alert.text
            logger.warning(f"Dismissing browser alert: {text}")
            alert.accept()
            time.sleep(1)
            return True
        except NoAlertPresentException:
            return False
        except Exception as e:
            logger.debug(f"Alert check failed: {e}")
            return False

    def navigate_to_graph_page(self) -> bool:
        try:
            wait = WebDriverWait(self.driver, 10)
            # Click top-level menu
            menu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-id='2']")))
            menu.click()
            time.sleep(1)

            # Click submenu based on mode
            if self.mode == 'sid':
                submenu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/mrtgnetcare2/graph/monitoring')]")))
            else:
                submenu = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[@data-id='1' and contains(@href, '/mrtgnetcare2/graph')]")))
            submenu.click()
            time.sleep(1)
            return True
        except Exception as e:
            logger.error(f"navigate_to_graph_page error: {e}")
            return False

    def input_target(self, target_id: str) -> bool:
        self.dismiss_alert_if_present()
        try:
            wait = WebDriverWait(self.driver, 10)
            input_name = 'sid' if self.mode == 'sid' else 'graphtitle'
            input_elem = wait.until(EC.element_to_be_clickable((By.NAME, input_name)))
            input_elem.clear()
            input_elem.send_keys(target_id)
            input_elem.send_keys(Keys.ENTER)
            time.sleep(2)

            btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.btn-graph")))
            self.driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(2)
            if not self.wait_for_detail_ready():
                logger.error(f"Detail page did not become ready for target {target_id}")
                return False
            return True
        except UnexpectedAlertPresentException as e:
            self.dismiss_alert_if_present()
            logger.warning(f"input_target alert dismissed for {target_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"input_target error: {e}")
            return False

    def set_date_filter(self, date_obj) -> bool:
        try:
            wait = WebDriverWait(self.driver, 10)
            start_str = date_obj.strftime("%d/%m/%Y 00:00")
            end_str = date_obj.strftime("%d/%m/%Y 23:55")

            if self.mode == 'sid':
                filter_btn = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(normalize-space(), 'Filter')]")))
                inputs = self.driver.find_elements(By.XPATH, "//button[contains(normalize-space(), 'Filter')]/preceding::input[not(@type='hidden')]")
                if len(inputs) >= 2:
                    start_input = inputs[-2]
                    end_input = inputs[-1]
                    self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));", start_input, start_str)
                    self.driver.execute_script("arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));", end_input, end_str)
                    self.driver.execute_script("arguments[0].click();", filter_btn)
                else:
                    logger.error("Could not find date inputs for SID mode")
                    return False
            else:
                start_input = wait.until(EC.presence_of_element_located((By.ID, "startdate")))
                end_input = wait.until(EC.presence_of_element_located((By.ID, "enddate")))
                btn = wait.until(EC.element_to_be_clickable((By.ID, "graphfilter")))

                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                    start_input,
                    start_str
                )
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; arguments[0].dispatchEvent(new Event('change'));",
                    end_input,
                    end_str
                )
                self.driver.execute_script("arguments[0].click();", btn)
            return True
        except Exception as e:
            logger.error(
                f"set_date_filter error for mode={self.mode}: {e}; "
                f"url={self.driver.current_url}; title={self.driver.title}"
            )
            return False

    def wait_for_loading_overlay(self, timeout=10):
        # Wait for any common loading overlays to disappear
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".blockUI, .loading, #loader, .spinner"))
            )
        except Exception:
            pass

    def mode_url(self) -> str:
        if self.mode == 'sid':
            return 'https://telkomcare.telkom.co.id/mrtgnetcare2/graph/monitoring'
        return 'https://telkomcare.telkom.co.id/mrtgnetcare2/graph'

    def wait_for_detail_ready(self, timeout: int = 15) -> bool:
        """Wait until target detail/filter controls are ready after Show Graph click."""
        try:
            wait = WebDriverWait(self.driver, timeout)
            if self.mode == 'sid':
                wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//button[contains(normalize-space(), 'Filter')]")
                ))
                return True

            wait.until(EC.presence_of_element_located((By.ID, "startdate")))
            wait.until(EC.presence_of_element_located((By.ID, "enddate")))
            wait.until(EC.presence_of_element_located((By.ID, "graphfilter")))
            return True
        except Exception as e:
            logger.error(
                f"Detail page not ready for mode={self.mode}: {e}; "
                f"url={self.driver.current_url}; title={self.driver.title}"
            )
            return False

    def recover_graph_page(self) -> bool:
        """Hard reset graph page and reopen the correct graph mode page."""
        try:
            self.dismiss_alert_if_present()
            target_url = self.mode_url()
            logger.warning(f"Recovering graph page with direct navigation: {target_url}")
            self.driver.get(target_url)
            time.sleep(5)
            self.dismiss_alert_if_present()
            self.wait_for_loading_overlay()
            return True
        except Exception as e:
            logger.error(f"recover_graph_page error: {e}")
            return False

    def wait_for_graph_render(self, timeout=15):
        for _ in range(timeout):
            try:
                imgs = self.driver.find_elements(By.XPATH, "//img[contains(@src, 'graph.php')]")
                for img in imgs:
                    width = self.driver.execute_script("return arguments[0].naturalWidth;", img)
                    if width and int(width) > 400:
                        return img
            except Exception:
                pass
            time.sleep(1)
        return None

    def isolate_image_for_capture(self, img_el):
        script = """
        window._hidden_elements = [];
        var target = arguments[0];
        var ancestors = [];
        var parent = target.parentNode;
        while(parent && parent.nodeName !== 'HTML') {
            ancestors.push(parent);
            parent = parent.parentNode;
        }
        var allElems = document.body.getElementsByTagName('*');
        for(var i=0; i<allElems.length; i++) {
            var el = allElems[i];
            if(el !== target && ancestors.indexOf(el) === -1 && el.nodeName !== 'SCRIPT' && el.nodeName !== 'STYLE') {
                if(window.getComputedStyle(el).display !== 'none') {
                    window._hidden_elements.push({el: el, display: el.style.display});
                    el.style.setProperty('display', 'none', 'important');
                }
            }
        }

        window._target_original_cssText = target.style.cssText;
        target.style.setProperty('position', 'fixed', 'important');
        target.style.setProperty('top', '0', 'important');
        target.style.setProperty('left', '0', 'important');
        target.style.setProperty('z-index', '99999999', 'important');

        var naturalWidth = target.naturalWidth || target.width || target.clientWidth;
        var naturalHeight = target.naturalHeight || target.height || target.clientHeight;
        target.style.setProperty('width', naturalWidth + 'px', 'important');
        target.style.setProperty('height', naturalHeight + 'px', 'important');
        target.style.setProperty('max-width', 'none', 'important');
        target.style.setProperty('max-height', 'none', 'important');
        target.style.setProperty('object-fit', 'fill', 'important');
        target.style.setProperty('transform', 'none', 'important');

        target.style.setProperty('margin', '0', 'important');
        target.style.setProperty('padding', '0', 'important');

        window._body_original_cssText = document.body.style.cssText;
        window._html_original_cssText = document.documentElement.style.cssText;
        document.body.style.setProperty('background', '#ffffff', 'important');
        document.body.style.setProperty('margin', '0', 'important');
        document.body.style.setProperty('padding', '0', 'important');
        document.body.style.setProperty('overflow', 'hidden', 'important');
        document.documentElement.style.setProperty('overflow', 'hidden', 'important');
        """
        self.driver.execute_script(script, img_el)

    def restore_ui_after_capture(self, img_el):
        script = """
        if(window._hidden_elements) {
            for(var i=0; i<window._hidden_elements.length; i++) {
                var item = window._hidden_elements[i];
                item.el.style.display = item.display;
            }
            window._hidden_elements = null;
        }
        var target = arguments[0];
        target.style.cssText = window._target_original_cssText || '';
        document.body.style.cssText = window._body_original_cssText || '';
        document.documentElement.style.cssText = window._html_original_cssText || '';
        """
        self.driver.execute_script(script, img_el)

    def validate_image(self, filepath: Path) -> bool:
        self.last_validation_error = None
        try:
            if not filepath.exists():
                self.last_validation_error = "invalid_image"
                logger.error(f"Image {filepath} does not exist")
                return False

            if filepath.stat().st_size < 1000:
                self.last_validation_error = "invalid_image"
                logger.error(f"Image {filepath} too small on disk: {filepath.stat().st_size} bytes")
                return False

            with Image.open(filepath) as img:
                w, h = img.size
                if w < 100 or h < 100:
                    self.last_validation_error = "invalid_image"
                    logger.error(f"Image {filepath} too small: {w}x{h}")
                    return False

                rgb = img.convert('RGB')
                extrema = rgb.getextrema()
                ranges = [hi - lo for lo, hi in extrema]

                gray = img.convert('L')
                gray_min, gray_max = gray.getextrema()
                luminance_range = gray_max - gray_min

                # Reject only near-solid placeholder/blank captures.
                if luminance_range < 10 and all(r < 10 for r in ranges):
                    self.last_validation_error = "blank"
                    logger.error(
                        f"Image {filepath} appears blank/solid "
                        f"(luminance_range={luminance_range}, rgb_ranges={ranges})"
                    )
                    return False

                pixels_l = list(gray.getdata())
                total = len(pixels_l)
                white_ratio = sum(1 for p in pixels_l if p > 230) / total
                dark_ratio = sum(1 for p in pixels_l if p < 100) / total

                pixels_rgb = list(rgb.getdata())
                colorful_ratio = (
                    sum(1 for r, g, b in pixels_rgb if max(r, g, b) - min(r, g, b) > 30) / total
                )

                if colorful_ratio < 0.002 and dark_ratio < 0.12 and white_ratio > 0.70:
                    self.last_validation_error = "no_graph"
                    logger.error(
                        f"Image {filepath} appears to be a no-graph placeholder "
                        f"(white_ratio={white_ratio:.3f}, dark_ratio={dark_ratio:.3f}, "
                        f"colorful_ratio={colorful_ratio:.5f})"
                    )
                    return False

            return True
        except Exception as e:
            self.last_validation_error = "invalid_image"
            logger.error(f"validate_image error on {filepath}: {e}")
            return False

    def capture_graph(self, target_id: str, date_obj) -> 'Path | None':
        self.last_status = None
        self.last_error = None
        for attempt in range(1, 4):
            self.dismiss_alert_if_present()
            img_el = None
            isolated = False
            try:
                if attempt > 1:
                    logger.warning(f"Retrying {target_id} (attempt {attempt}/3)")
                    time.sleep(2)

                if not self.input_target(target_id):
                    if attempt < 3:
                        logger.warning(f"input_target failed for {target_id}, retrying attempt {attempt + 1}/3")
                        continue
                    self.last_status = "error"
                    self.last_error = "input_target failed"
                    return None
                time.sleep(2)

                if not self.set_date_filter(date_obj):
                    if attempt < 3:
                        logger.warning(f"set_date_filter failed for {target_id}, retrying attempt {attempt + 1}/3")
                        continue
                    self.last_status = "error"
                    self.last_error = "set_date_filter failed"
                    return None
                time.sleep(3)

                self.wait_for_loading_overlay()

                img_el = self.wait_for_graph_render()
                if not img_el:
                    logger.error(f"Graph did not render for {target_id}")
                    if attempt < 3:
                        self.recover_graph_page()
                        time.sleep(2)
                        continue
                    self.last_status = "error"
                    self.last_error = "Graph did not render"
                    return None

                self.isolate_image_for_capture(img_el)
                isolated = True
                time.sleep(3)

                from mrtg_automation.shared.filenames import get_screenshot_path
                final_file = get_screenshot_path(target_id, date_obj)
                output_dir = final_file.parent
                output_dir.mkdir(parents=True, exist_ok=True)

                temp_file = output_dir / f"temp_{final_file.name}"

                img_el.screenshot(str(temp_file))

                if self.validate_image(temp_file):
                    temp_file.replace(final_file)
                    self.last_status = "ok"
                    self.last_error = None
                    return final_file

                temp_file.unlink(missing_ok=True)
                if attempt < 3:
                    logger.warning(
                        f"Invalid graph capture for {target_id}, recovering page and retrying "
                        f"attempt {attempt + 1}/3"
                    )
                    self.recover_graph_page()
                    time.sleep(2)
                    continue

                if self.last_validation_error == "no_graph":
                    self.last_status = "no_graph"
                    self.last_error = "TelkomCare returned No graph"
                else:
                    self.last_status = "error"
                    self.last_error = f"Invalid graph capture after 3 attempts ({self.last_validation_error})"

                logger.error(f"Invalid graph capture for {target_id} after 3 attempts")
                return None

            except StaleElementReferenceException as e:
                logger.warning(f"Stale graph element for {target_id} on attempt {attempt}/3: {e}")
                continue
            except UnexpectedAlertPresentException as e:
                self.dismiss_alert_if_present()
                logger.warning(f"Unexpected alert during capture for {target_id} on attempt {attempt}/3: {e}")
                continue
            except Exception as e:
                logger.error(f"capture_graph error for {target_id}: {e}")
                self.last_status = "error"
                self.last_error = f"capture_graph exception: {e}"
                return None
            finally:
                if isolated and img_el is not None:
                    try:
                        self.restore_ui_after_capture(img_el)
                    except Exception as e:
                        logger.debug(f"restore after capture failed for {target_id}: {e}")

        self.last_status = "error"
        self.last_error = "Capture failed after 3 stale retries"
        logger.error(f"capture_graph failed for {target_id} after 3 stale retries")
        return None
