from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
import csv
import time
import random
import os
from pathlib import Path
import shutil


CSV_FILENAME = "Manual Brochure Process.csv"
BUTTON_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-investment-advisor-search/div/div[1]/investor-tools-finder/div[1]/ul/li[2]/div"
INPUT_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-investment-advisor-search/div/div[1]/investor-tools-finder/div[2]/form[2]/div/div[1]/input"
SEARCH_BUTTON_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-investment-advisor-search/div/div[1]/investor-tools-finder/div[2]/form[2]/div/button/span"
MORE_DETAILS_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-search-results-page/iapd-search-results/div/investor-tools-search-results-template/div[2]/div[2]/div/div[1]/iapd-firm-search-result-card/investor-tools-card/div/div[1]/investor-tools-firm-search-result-template/div/div[3]/button"
PART2_BROCHURES_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-firm-container-page/iapd-firm-detail-page/div/iapd-firm-summary/div/div[3]/a[2]"
ADV2A_LINK_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-firm-container-page/iapd-firm-brochure-page/div/iapd-firm-brochure/div/div/div[3]/div/table/tbody/tr[1]/td[1]/a"
# Header finder after first iteration
HEADER_INPUT_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-firm-container-page/iapd-header/div/investor-tools-finder/div[2]/form[2]/div/div[1]/input"
HEADER_SEARCH_BUTTON_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-firm-container-page/iapd-header/div/investor-tools-finder/div[2]/form[2]/div/button/span"

PDF_VIEWER_DOWNLOAD_XPATH = "/html/body/pdf-viewer//viewer-toolbar//div/div[3]/viewer-download-controls//cr-icon-button"

# --- Anti-bot helpers ---
USER_AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

BASE_DIR = Path(__file__).resolve().parent
FIRM_PDFS_DIR = BASE_DIR / "firm_pdfs"
TMP_DOWNLOADS_DIR = BASE_DIR / "downloads_tmp"
PROCESSED_FILE = BASE_DIR / "processed_crds.txt"


def random_delay(min_seconds: float = 0.15, max_seconds: float = 0.6) -> None:
	time.sleep(random.uniform(min_seconds, max_seconds))


def random_idle(min_seconds: float = 0.6, max_seconds: float = 1.8) -> None:
	time.sleep(random.uniform(min_seconds, max_seconds))


def random_scroll(driver: webdriver.Chrome) -> None:
	try:
		amount = random.randint(-120, 320)
		driver.execute_script("window.scrollBy(0, arguments[0]);", amount)
	except Exception:
		pass


def human_type(element, text: str) -> None:
	for ch in text:
		element.send_keys(ch)
		if random.random() < 0.08:
			random_delay(0.2, 0.5)
		else:
			random_delay(0.05, 0.22)


def get_all_crds(csv_path: str) -> list[str]:
	values: list[str] = []
	seen = set()
	with open(csv_path, newline="", encoding="utf-8-sig") as f:
		reader = csv.reader(f)
		next(reader, None)
		for row in reader:
			if not row:
				continue
			val = row[0].strip()
			if not val or val in seen:
				continue
			seen.add(val)
			values.append(val)
	return values


def load_processed() -> set[str]:
	if not PROCESSED_FILE.exists():
		return set()
	with open(PROCESSED_FILE, "r", encoding="utf-8") as f:
		return set(line.strip() for line in f if line.strip())


def append_processed(crd: str) -> None:
	with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
		f.write(crd + "\n")


def find_element_retry(driver: webdriver.Chrome, xpath: str):
	while True:
		try:
			return driver.find_element(By.XPATH, xpath)
		except Exception:
			random_delay(0.2, 0.5)
			random_scroll(driver)


def click_xpath_retry(driver: webdriver.Chrome, xpath: str) -> None:
	while True:
		el = find_element_retry(driver, xpath)
		try:
			el.click()
			return
		except Exception:
			try:
				driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
				driver.execute_script("arguments[0].click();", el)
				return
			except Exception:
				try:
					el.send_keys(Keys.ENTER)
					return
				except Exception:
					random_delay(0.25, 0.8)
					random_scroll(driver)


def wait_for_new_tab_or_download(driver: webdriver.Chrome, existing_handles: list[str], since_time: float) -> bool:
	# Returns True if a new tab was opened, False if a new download started instead
	while True:
		handles = driver.window_handles
		if len(handles) > len(existing_handles):
			new_handle = [h for h in handles if h not in existing_handles][-1]
			driver.switch_to.window(new_handle)
			return True
		cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
		if cand and cand.stat().st_mtime >= since_time:
			return False
		random_delay(0.2, 0.6)


def click_pdf_download_button(driver: webdriver.Chrome) -> None:
	while True:
		clicked = False
		try:
			driver.execute_script(
				"""
				const viewer = document.querySelector('pdf-viewer');
				if (!viewer) return false;
				const s1 = viewer.shadowRoot; if (!s1) return false;
				const toolbar = s1.querySelector('viewer-toolbar'); if (!toolbar) return false;
				const s2 = toolbar.shadowRoot; if (!s2) return false;
				const dlHost = s2.querySelector('viewer-download-controls'); if (!dlHost) return false;
				const s3 = dlHost.shadowRoot; if (!s3) return false;
				const btn = s3.querySelector('cr-icon-button, #download'); if (!btn) return false;
				btn.click();
				return true;
				"""
			)
			clicked = True
		except Exception:
			clicked = False
		if not clicked:
			try:
				el = driver.find_element(By.XPATH, PDF_VIEWER_DOWNLOAD_XPATH)
				driver.execute_script("arguments[0].click();", el)
				clicked = True
			except Exception:
				clicked = False
		if clicked:
			return
		random_delay(0.25, 0.8)


def newest_file_in_directory(directory: Path) -> Path | None:
	candidates = list(directory.glob("*"))
	if not candidates:
		return None
	return max(candidates, key=lambda p: p.stat().st_mtime)


def wait_for_stable_download(since_time: float) -> Path:
	last_size = -1
	stable_count = 0
	while True:
		f = newest_file_in_directory(TMP_DOWNLOADS_DIR)
		if f and f.stat().st_mtime >= since_time:
			name = f.name.lower()
			if name.endswith(".crdownload") or name.endswith(".tmp"):
				stable_count = 0
				random_delay(0.3, 0.8)
				continue
			try:
				size = f.stat().st_size
			except Exception:
				size = -1
			if size == last_size and size > 0:
				stable_count += 1
			else:
				stable_count = 0
			last_size = size
			if stable_count >= 2 and f.suffix.lower() == ".pdf":
				return f
		random_delay(0.2, 0.6)


def move_to_dest(src_file: Path, dest_pdf_path: Path) -> None:
	while True:
		try:
			if dest_pdf_path.exists():
				dest_pdf_path.unlink()
			shutil.move(str(src_file), str(dest_pdf_path))
			return
		except Exception:
			random_delay(0.3, 0.8)


def process_first_iteration(driver: webdriver.Chrome, crd: str) -> None:
	click_xpath_retry(driver, BUTTON_XPATH)
	random_idle(0.4, 1.2)
	input_el = find_element_retry(driver, INPUT_XPATH)
	try:
		input_el.clear()
	except Exception:
		pass
	input_el.click()
	random_delay(0.15, 0.4)
	human_type(input_el, crd)
	random_idle(0.3, 1.0)
	click_xpath_retry(driver, SEARCH_BUTTON_XPATH)
	random_idle(1.0, 2.5)
	click_xpath_retry(driver, MORE_DETAILS_XPATH)
	random_idle(0.8, 2.0)
	click_xpath_retry(driver, PART2_BROCHURES_XPATH)


def clear_and_type_header_input(driver: webdriver.Chrome, text: str) -> None:
	input_el = find_element_retry(driver, HEADER_INPUT_XPATH)
	input_el.click()
	# Multi-strategy clear until empty
	for _ in range(3):
		try:
			input_el.clear()
		except Exception:
			pass
		input_el.send_keys(Keys.CONTROL, "a")
		input_el.send_keys(Keys.BACK_SPACE)
		# extra delete presses to remove auto-suggest leftovers
		for _ in range(5):
			input_el.send_keys(Keys.BACK_SPACE)
		random_delay(0.1, 0.2)
		val = input_el.get_attribute("value") or ""
		if val.strip() == "":
			break
	# Type new value human-like
	human_type(input_el, text)


def process_subsequent_iteration(driver: webdriver.Chrome, crd: str) -> None:
	clear_and_type_header_input(driver, crd)
	random_idle(0.3, 1.0)
	click_xpath_retry(driver, HEADER_SEARCH_BUTTON_XPATH)
	random_idle(1.0, 2.5)
	click_xpath_retry(driver, MORE_DETAILS_XPATH)
	random_idle(0.8, 2.0)
	click_xpath_retry(driver, PART2_BROCHURES_XPATH)


def process_download_for_current_crd(driver: webdriver.Chrome, crd: str) -> None:
	adv_link = find_element_retry(driver, ADV2A_LINK_XPATH)
	try:
		label = adv_link.text.strip()
		if label and "ADV2A" not in label.upper():
			pass
	except Exception:
		pass

	existing_handles = driver.window_handles
	baseline_time = time.time()
	try:
		driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", adv_link)
	except Exception:
		pass
	random_delay(0.15, 0.4)
	try:
		adv_link.click()
	except Exception:
		driver.execute_script("arguments[0].click();", adv_link)

	# Decide if viewer tab opened or direct download started
	viewer_tab = wait_for_new_tab_or_download(driver, existing_handles, baseline_time)
	if viewer_tab:
		random_idle(0.6, 1.6)
		click_pdf_download_button(driver)
		dl_file = wait_for_stable_download(time.time())
		move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
		try:
			driver.close()
		except Exception:
			pass
		remaining = driver.window_handles
		if remaining:
			driver.switch_to.window(remaining[-1])
	else:
		dl_file = wait_for_stable_download(baseline_time)
		move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")


def main() -> None:
	random.seed()
	FIRM_PDFS_DIR.mkdir(parents=True, exist_ok=True)
	TMP_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

	options = webdriver.ChromeOptions()
	options.add_argument("--auto-open-devtools-for-tabs")
	options.add_argument("--start-maximized")
	options.add_argument("--lang=en-US,en;q=0.9")
	options.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
	options.add_experimental_option("excludeSwitches", ["enable-automation"])
	options.add_experimental_option("useAutomationExtension", False)
	options.add_experimental_option("detach", True)
	prefs = {
		"download.default_directory": str(TMP_DOWNLOADS_DIR.resolve()),
		"download.prompt_for_download": False,
		"download.directory_upgrade": True,
		"safebrowsing.enabled": True,
	}
	options.add_experimental_option("prefs", prefs)

	driver = webdriver.Chrome(
		service=Service(ChromeDriverManager().install()),
		options=options,
	)
	try:
		driver.execute_cdp_cmd(
			"Page.addScriptToEvaluateOnNewDocument",
			{"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
		)
	except Exception:
		pass

	driver.get("https://adviserinfo.sec.gov/")
	random_idle(0.8, 2.0)
	random_scroll(driver)

	all_crds = get_all_crds(CSV_FILENAME)
	processed = load_processed()
	targets: list[str] = []
	for crd in all_crds:
		dest = FIRM_PDFS_DIR / f"{crd}.pdf"
		if crd in processed or dest.exists():
			continue
		targets.append(crd)
		if len(targets) >= 10:
			break

	first = True
	for crd in targets:
		if first:
			process_first_iteration(driver, crd)
			first = False
		else:
			process_subsequent_iteration(driver, crd)

		process_download_for_current_crd(driver, crd)
		append_processed(crd)
		random_idle(0.8, 1.8)

	while True:
		time.sleep(3600)


if __name__ == "__main__":
	main()
