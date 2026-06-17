"""
Graph Extractor for TelkomCare MRTG portal.
"""
import logging
import time
import re
from pathlib import Path
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException

logger = logging.getLogger('mrtg_automation.scraper.extractor')

class GraphExtractor:
    def __init__(self, driver, mode='sid'):
        self.driver = driver
        self.mode = mode.lower()

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
            return True
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
                self.driver.execute_script("document.getElementById('startdate').value = arguments[0]; document.getElementById('startdate').dispatchEvent(new Event('change'));", start_str)
                self.driver.execute_script("document.getElementById('enddate').value = arguments[0]; document.getElementById('enddate').dispatchEvent(new Event('change'));", end_str)
                btn = self.driver.find_element(By.ID, 'graphfilter')
                self.driver.execute_script("arguments[0].click();", btn)
            return True
        except Exception as e:
            logger.error(f"set_date_filter error: {e}")
            return False

    def wait_for_loading_overlay(self, timeout=10):
        # Wait for any common loading overlays to disappear
        try:
            WebDriverWait(self.driver, timeout).until_not(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".blockUI, .loading, #loader, .spinner"))
            )
        except Exception:
            pass

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
        try:
            with Image.open(filepath) as img:
                w, h = img.size
                if w < 100 or h < 100:
                    logger.error(f"Image {filepath} too small: {w}x{h}")
                    return False
                ycbcr = img.convert('YCbCr')
                extrema = ycbcr.getextrema()
                if len(extrema) == 3:
                    y, cb, cr = extrema
                    if (cb[1] - cb[0]) < 15 and (cr[1] - cr[0]) < 15:
                        logger.error(f"Image {filepath} lacks color variation (grayscale/blank)")
                        return False
            return True
        except Exception as e:
            logger.error(f"validate_image error on {filepath}: {e}")
            return False

    def capture_graph(self, target_id: str, date_obj) -> 'Path | None':
        for attempt in range(1, 4):
            img_el = None
            isolated = False
            try:
                if attempt > 1:
                    logger.warning(f"Retrying {target_id} after stale element (attempt {attempt}/3)")
                    time.sleep(2)

                if not self.input_target(target_id):
                    return None
                time.sleep(2)

                if not self.set_date_filter(date_obj):
                    return None
                time.sleep(3)

                self.wait_for_loading_overlay()

                img_el = self.wait_for_graph_render()
                if not img_el:
                    logger.error(f"Graph did not render for {target_id}")
                    return None

                self.isolate_image_for_capture(img_el)
                isolated = True
                time.sleep(3)

                date_str = date_obj.strftime('%Y%m%d')
                output_dir = Path('data/MRTG-Data') / date_str
                output_dir.mkdir(parents=True, exist_ok=True)

                safe_target = re.sub(r'[\\/*?:"<>|]', '_', target_id)
                temp_file = output_dir / f"temp_{safe_target}_{date_str}.png"
                final_file = output_dir / f"MRTG_{safe_target}_{date_str}.png"

                img_el.screenshot(str(temp_file))

                if self.validate_image(temp_file):
                    temp_file.replace(final_file)
                    return final_file
                else:
                    temp_file.unlink(missing_ok=True)
                    return None

            except StaleElementReferenceException as e:
                logger.warning(f"Stale graph element for {target_id} on attempt {attempt}/3: {e}")
                continue
            except Exception as e:
                logger.error(f"capture_graph error for {target_id}: {e}")
                return None
            finally:
                if isolated and img_el is not None:
                    try:
                        self.restore_ui_after_capture(img_el)
                    except Exception as e:
                        logger.debug(f"restore after capture failed for {target_id}: {e}")

        logger.error(f"capture_graph failed for {target_id} after 3 stale retries")
        return None
