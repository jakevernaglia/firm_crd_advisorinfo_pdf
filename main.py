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
from datetime import datetime
from PyPDF2 import PdfReader
from selenium.common.exceptions import NoSuchWindowException
import requests


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
TABLE_XPATH = "/html/body/iapd-root/iapd-home/div/div[2]/div/iapd-firm-container-page/iapd-firm-brochure-page/div/iapd-firm-brochure/div/div/div[3]/div/table"

# --- Anti-bot helpers ---
USER_AGENTS = [
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

BASE_DIR = Path(__file__).resolve().parent
FIRM_PDFS_DIR = BASE_DIR / "Firm_PDFs"
TMP_DOWNLOADS_DIR = BASE_DIR / "downloads_tmp"
PROCESSED_FILE = BASE_DIR / "processed_crds.txt"


def log(message: str) -> None:
	ts = datetime.now().strftime("%H:%M:%S")
	try:
		print(f"[{ts}] {message}", flush=True)
	except Exception:
		pass


def describe_driver(driver: webdriver.Chrome) -> str:
	try:
		url = driver.current_url
	except Exception:
		url = "<no url>"
	try:
		handles = driver.window_handles
	except Exception:
		handles = []
	return f"url={url} handles={len(handles)}"


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
	log(f"mark processed: {crd}")
	with open(PROCESSED_FILE, "a", encoding="utf-8") as f:
		f.write(crd + "\n")


def find_element_retry(driver: webdriver.Chrome, xpath: str):
	while True:
		try:
			el = driver.find_element(By.XPATH, xpath)
			return el
		except Exception as e:
			log(f"wait element xpath={xpath[:80]}... {describe_driver(driver)}")
			random_delay(0.2, 0.5)
			random_scroll(driver)


def click_xpath_retry(driver: webdriver.Chrome, xpath: str) -> None:
	while True:
		el = find_element_retry(driver, xpath)
		try:
			el.click()
			log(f"clicked xpath={xpath[:80]}... {describe_driver(driver)}")
			return
		except Exception:
			try:
				driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
				driver.execute_script("arguments[0].click();", el)
				log(f"js clicked xpath={xpath[:80]}... {describe_driver(driver)}")
				return
			except Exception:
				try:
					el.send_keys(Keys.ENTER)
					log(f"enter fallback xpath={xpath[:80]}... {describe_driver(driver)}")
					return
				except Exception:
					random_delay(0.25, 0.8)
					random_scroll(driver)


def element_present(driver: webdriver.Chrome, xpath: str) -> bool:
	try:
		driver.find_element(By.XPATH, xpath)
		return True
	except Exception:
		return False

# --- ADV2A flexible detection ---

def try_find_adv2a_element(driver: webdriver.Chrome):
	# Best-effort search for an ADV 2A link/button (by visible text), prioritizing the brochures table
	X = "translate(normalize-space(.), 'abcdefghijklmnopqrstuvwxyz', 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')"
	candidates = [
		# Inside the brochures table only
		f"//table[contains(@class,'brochures-table')]//a[contains({X}, 'ADV2A') or contains({X}, 'ADV 2A') or contains({X}, 'PART 2A')]",
		f"//table[contains(@class,'brochures-table')]//*[self::a or self::button][contains({X}, 'ADV2A') or contains({X}, 'ADV 2A') or contains({X}, 'PART 2A')]",
		# Anywhere on the page as a fallback
		f"//a[contains({X}, 'ADV2A') or contains({X}, 'ADV 2A') or contains({X}, 'PART 2A')]",
		f"//*[self::a or self::button][contains({X}, 'ADV2A') or contains({X}, 'ADV 2A') or contains({X}, 'PART 2A')]",
	]
	for xp in candidates:
		els = driver.find_elements(By.XPATH, xp)
		if els:
			return els[0]
	# JS text scan across common clickable elements
	try:
		el = driver.execute_script(
			"""
			const rx = /(ADV\s*2A|PART\s*2A)/i;
			const nodes = Array.from(document.querySelectorAll('table.brochures-table a, a,button,div,span'));
			return nodes.find(n => rx.test((n.textContent||'').trim())) || null;
			"""
		)
		return el
	except Exception:
		return None


def find_adv2a_element(driver: webdriver.Chrome):
	# Blocking until found
	while True:
		el = try_find_adv2a_element(driver)
		if el:
			return el
		log("searching for ADV 2A element...")
		random_delay(0.2, 0.5)
		random_scroll(driver)


def wait_for_outcome_after_click(driver: webdriver.Chrome, existing_handles: list[str], since_time: float) -> str:
	# Returns one of: 'new_tab', 'viewer_same', 'download'
	last_seen_handles = existing_handles[:]
	while True:
		try:
			handles = driver.window_handles
		except Exception:
			handles = []
		# New tab appeared
		if len(handles) > len(last_seen_handles):
			new_handles = [h for h in handles if h not in last_seen_handles]
			if new_handles:
				try:
					driver.switch_to.window(new_handles[-1])
					log(f"switched to new tab: {describe_driver(driver)}")
					return 'new_tab'
				except NoSuchWindowException:
					# Tab closed quickly; check for a download and continue loop
					cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
					if cand and cand.stat().st_mtime >= since_time:
						log(f"new tab closed; detected direct download: {cand.name}")
						return 'download'
					# Else continue to wait
					pass
			last_seen_handles = handles
		# Same-tab viewer?
		try:
			if extract_pdf_embed_src(driver) or "crd_iapd_Brochure.aspx" in (driver.current_url or ""):
				log("detected same-tab PDF viewer")
				return 'viewer_same'
		except Exception:
			pass
		# Direct download?
		cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
		if cand and cand.stat().st_mtime >= since_time:
			log(f"detected direct download: {cand.name}")
			return 'download'
		random_delay(0.2, 0.6)


def click_pdf_download_button(driver: webdriver.Chrome) -> None:
	while True:
		clicked = False
		try:
			ok = driver.execute_script(
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
			clicked = bool(ok)
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
			log("clicked viewer download button")
			return
		log("retry viewer download click")
		random_delay(0.25, 0.8)


def extract_pdf_embed_src(driver: webdriver.Chrome) -> str | None:
	try:
		src = driver.execute_script(
			"var e=document.querySelector(\"embed[type='application/pdf']\"); return e? e.src : null;"
		)
		if src:
			log(f"found PDF <embed> src: {src}")
			return src
	except Exception as e:
		log(f"failed to read embed src: {e}")
	return None


def extract_iframe_src(driver: webdriver.Chrome) -> str | None:
	try:
		src = driver.execute_script(
			"var f=document.querySelector('iframe'); return f? (f.src||null) : null;"
		)
		if src and ('crd_iapd_Brochure.aspx' in src or '/IAPD/Content/Common/' in src):
			log(f"found <iframe> src: {src}")
			return src
	except Exception as e:
		log(f"failed to read iframe src: {e}")
	return None


def http_download_to_tmp(url: str, user_agent: str | None = None) -> Path:
	try:
		sess = requests.Session()
		headers = {"User-Agent": user_agent or USER_AGENTS[0]}
		resp = sess.get(url, headers=headers, stream=True, timeout=60)
		resp.raise_for_status()
		fname = f"download_{int(time.time()*1000)}.pdf"
		tmp_path = TMP_DOWNLOADS_DIR / fname
		with open(tmp_path, 'wb') as f:
			for chunk in resp.iter_content(chunk_size=65536):
				if chunk:
					f.write(chunk)
		log(f"http downloaded -> {tmp_path.name}")
		return tmp_path
	except Exception as e:
		log(f"http download failed: {e}")
		raise


def newest_file_in_directory(directory: Path) -> Path | None:
	candidates = list(directory.glob("*.pdf"))
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
			try:
				size = f.stat().st_size
			except Exception:
				size = -1
			if size == last_size and size > 0 and name.endswith('.pdf'):
				stable_count += 1
			else:
				stable_count = 0
			last_size = size
			if stable_count >= 2:
				log(f"download stable: {f.name} size={size}")
				return f
		random_delay(0.2, 0.6)


def move_to_dest(src_file: Path, dest_pdf_path: Path) -> None:
	while True:
		try:
			if dest_pdf_path.exists():
				dest_pdf_path.unlink()
			shutil.move(str(src_file), str(dest_pdf_path))
			log(f"moved file -> {dest_pdf_path}")
			return
		except Exception:
			random_delay(0.3, 0.8)


def finalize_download(crd: str, since_time: float) -> None:
	dest = FIRM_PDFS_DIR / f"{crd}.pdf"
	while not dest.exists():
		cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
		if cand and cand.stat().st_mtime >= since_time:
			log(f"finalize: moving {cand.name} to {dest.name}")
			move_to_dest(cand, dest)
			break
		random_delay(0.2, 0.6)


def process_first_iteration(driver: webdriver.Chrome, crd: str) -> None:
	log(f"process_first_iteration start crd={crd} {describe_driver(driver)}")
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
	open_part2_and_download(driver, crd)


def clear_and_type_header_input(driver: webdriver.Chrome, text: str) -> None:
	input_el = find_element_retry(driver, HEADER_INPUT_XPATH)
	input_el.click()
	for _ in range(3):
		try:
			input_el.clear()
		except Exception:
			pass
		input_el.send_keys(Keys.CONTROL, "a")
		input_el.send_keys(Keys.BACK_SPACE)
		for _ in range(5):
			input_el.send_keys(Keys.BACK_SPACE)
		random_delay(0.1, 0.2)
		val = input_el.get_attribute("value") or ""
		if val.strip() == "":
			break
	log("header input cleared")
	human_type(input_el, text)
	log(f"typed header input value={text}")


def process_subsequent_iteration(driver: webdriver.Chrome, crd: str) -> None:
	log(f"process_subsequent_iteration start crd={crd} {describe_driver(driver)}")
	clear_and_type_header_input(driver, crd)
	random_idle(0.3, 1.0)
	click_xpath_retry(driver, HEADER_SEARCH_BUTTON_XPATH)
	random_idle(1.0, 2.5)
	click_xpath_retry(driver, MORE_DETAILS_XPATH)
	random_idle(0.8, 2.0)
	open_part2_and_download(driver, crd)


def open_part2_and_download(driver: webdriver.Chrome, crd: str) -> None:
	log("opening Part 2 Brochures")
	existing = driver.window_handles
	start = time.time()
	click_xpath_retry(driver, PART2_BROCHURES_XPATH)
	new_tab = False
	while True:
		handles = driver.window_handles
		if len(handles) > len(existing):
			driver.switch_to.window([h for h in handles if h not in existing][-1])
			new_tab = True
			log(f"Part 2 opened in new tab: {describe_driver(driver)}")
			break
		el = try_find_adv2a_element(driver)
		if el:
			log("Part 2 brochures list detected (ADV2A element present)")
			break
		if extract_pdf_embed_src(driver) or "crd_iapd_Brochure.aspx" in (driver.current_url or ""):
			log("Direct brochure viewer detected")
			break
		cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
		if cand and cand.stat().st_mtime >= start:
			log("Direct download detected after Part 2 click")
			break
		random_delay(0.2, 0.6)

	el = try_find_adv2a_element(driver)
	if el:
		log("Proceeding to click ADV2A from list page")
		try:
			driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
		except Exception:
			pass
		random_delay(0.15, 0.4)
		href = None
		try:
			href = el.get_attribute("href")
		except Exception:
			href = None
		existing_handles = driver.window_handles
		if href:
			log("Opening ADV2A via href in new tab")
			driver.execute_script("window.open(arguments[0], '_blank');", href)
		else:
			log("Clicking ADV2A element without href")
			try:
				el.click()
			except Exception:
				driver.execute_script("arguments[0].click();", el)
		viewer_tab = wait_for_outcome_after_click(driver, existing_handles, time.time())
		if viewer_tab == 'new_tab':
			log("Viewer tab for ADV2A opened")
			pdf_src = extract_pdf_embed_src(driver)
			if pdf_src:
				log("Navigating to embedded PDF src to download")
				start_d = time.time()
				driver.get(pdf_src)
				f = wait_for_stable_download(start_d)
				move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
				move_finalize_verify(crd, start_d)
			else:
				click_pdf_download_button(driver)
				start2 = time.time()
				f = wait_for_stable_download(start2)
				move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
				move_finalize_verify(crd, start2)
			try:
				driver.close()
				log("closed ADV2A viewer tab")
			except Exception:
				pass
			remaining = driver.window_handles
			if remaining:
				driver.switch_to.window(remaining[0])
				wait_document_ready(driver)
				log(f"switched back to first handle {describe_driver(driver)}")
		elif viewer_tab == 'viewer_same':
			log("Same-tab PDF viewer detected for ADV2A")
			pdf_src = extract_pdf_embed_src(driver)
			if pdf_src:
				log("Navigating to embedded PDF src to download")
				driver.get(pdf_src)
				f = wait_for_stable_download(time.time())
				move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
				move_finalize_verify(crd, time.time())
			else:
				click_pdf_download_button(driver)
				start2 = time.time()
				f = wait_for_stable_download(start2)
				move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
				move_finalize_verify(crd, start2)
			try:
				driver.close()
				log("closed ADV2A viewer tab")
			except Exception:
				pass
			remaining = driver.window_handles
			if remaining:
				driver.switch_to.window(remaining[0])
				wait_document_ready(driver)
				log(f"switched back to first handle {describe_driver(driver)}")
		elif viewer_tab == 'download':
			log("Direct download detected for ADV2A")
			finalize_download(crd, start)
		return

	if extract_pdf_embed_src(driver) or "crd_iapd_Brochure.aspx" in (driver.current_url or ""):
		log("Downloading from viewer/direct PDF page")
		src = extract_pdf_embed_src(driver)
		if src:
			log("Navigating to embedded PDF src to download")
			driver.get(src)
			f = wait_for_stable_download(time.time())
			move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, time.time())
		else:
			click_pdf_download_button(driver)
			start2 = time.time()
			f = wait_for_stable_download(start2)
			move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, start2)
		if new_tab:
			try:
				driver.close()
				log("closed Part 2 viewer tab")
			except Exception:
				pass
			remaining = driver.window_handles
			if remaining:
				driver.switch_to.window(remaining[0])
				wait_document_ready(driver)
				log(f"switched back to first handle {describe_driver(driver)}")
		return

	log("Finalizing direct download after Part 2 click")
	finalize_download(crd, start)


def process_download_for_current_crd(driver: webdriver.Chrome, crd: str) -> None:
	adv_link = find_adv2a_element(driver)
	try:
		label = adv_link.text.strip()
		href = adv_link.get_attribute("href")
	except Exception:
		label = ""
		href = ""
	log(f"ADV link label='{label}' href='{href}' crd={crd}")

	existing_handles = driver.window_handles
	baseline_time = time.time()
	try:
		driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", adv_link)
	except Exception:
		pass
	random_delay(0.15, 0.4)
	try:
		if href:
			driver.execute_script("window.open(arguments[0], '_blank');", href)
		else:
			adv_link.click()
		log("opened ADV link (ADV2A)")
	except Exception:
		try:
			driver.execute_script("arguments[0].click();", adv_link)
			log("js click on ADV link")
		except Exception as e:
			log(f"failed to open ADV link: {e}")

	viewer_tab = wait_for_outcome_after_click(driver, existing_handles, baseline_time)
	if viewer_tab == 'new_tab':
		random_idle(0.6, 1.6)
		log(f"in brochure tab {describe_driver(driver)}")
		pdf_src = extract_pdf_embed_src(driver)
		if pdf_src:
			start = time.time()
			log("navigating directly to embedded PDF src to trigger download")
			driver.get(pdf_src)
			dl_file = wait_for_stable_download(start)
			move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, start)
		else:
			click_pdf_download_button(driver)
			start2 = time.time()
			dl_file = wait_for_stable_download(start2)
			move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, start2)
		try:
			driver.close()
			log("closed brochure tab")
		except Exception:
			log("failed closing brochure tab")
		remaining = driver.window_handles
		if remaining:
			driver.switch_to.window(remaining[0])
			wait_document_ready(driver)
			log(f"switched back to first handle {describe_driver(driver)}")
	elif viewer_tab == 'viewer_same':
		log("Same-tab PDF viewer detected for ADV2A")
		pdf_src = extract_pdf_embed_src(driver)
		if pdf_src:
			start = time.time()
			driver.get(pdf_src)
			dl_file = wait_for_stable_download(start)
			move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, start)
		else:
			click_pdf_download_button(driver)
			start2 = time.time()
			dl_file = wait_for_stable_download(start2)
			move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
			move_finalize_verify(crd, start2)
		try:
			driver.close()
			log("closed brochure tab")
		except Exception:
			log("failed closing brochure tab")
		remaining = driver.window_handles
		if remaining:
			driver.switch_to.window(remaining[0])
			wait_document_ready(driver)
			log(f"switched back to first handle {describe_driver(driver)}")
	elif viewer_tab == 'download':
		log("Direct download detected for ADV2A")
		dl_file = wait_for_stable_download(baseline_time)
		move_to_dest(dl_file, FIRM_PDFS_DIR / f"{crd}.pdf")
		move_finalize_verify(crd, baseline_time)

	set_verify_flag_from_text(label)


def pdf_contains_part2a(pdf_path: Path) -> bool:
	try:
		reader = PdfReader(str(pdf_path))
		text_chunks = []
		for page in reader.pages[:5]:
			try:
				text_chunks.append(page.extract_text() or "")
			except Exception:
				pass
		text = "\n".join(text_chunks).upper()
		return ("ADV 2A" in text) or ("ADV2A" in text) or ("PART 2A" in text)
	except Exception as e:
		log(f"pdf text read error: {e}")
		return False


def ensure_brochures_table(driver: webdriver.Chrome) -> bool:
	# Try to reach the brochures table page reliably
	for _ in range(5):
		try:
			if element_present(driver, TABLE_XPATH):
				return True
		except Exception:
			pass
		existing = driver.window_handles
		click_xpath_retry(driver, PART2_BROCHURES_XPATH)
		# Observe outcomes
		for _ in range(20):
			if element_present(driver, TABLE_XPATH):
				return True
			# If viewer tab opens, close and try again
			if len(driver.window_handles) > len(existing):
				driver.switch_to.window(driver.window_handles[-1])
				if extract_pdf_embed_src(driver) or "crd_iapd_Brochure.aspx" in (driver.current_url or ""):
					try:
						driver.close()
						log("closed viewer to reach table")
					except Exception:
						pass
					driver.switch_to.window(driver.window_handles[0])
			random_delay(0.2, 0.5)
	return element_present(driver, TABLE_XPATH)


def scan_table_click_newest_adv2a(driver: webdriver.Chrome) -> bool:
	if not ensure_brochures_table(driver):
		log("brochures table not found")
		return False
	try:
		table = driver.find_element(By.XPATH, TABLE_XPATH)
		rows = table.find_elements(By.XPATH, ".//tbody/tr") or table.find_elements(By.XPATH, ".//tr")
		extracted = []
		for r in rows:
			cells = r.find_elements(By.XPATH, ".//td")
			if len(cells) < 2:
				continue
			date_str = cells[1].text.strip()
			name_cell = cells[0]
			link_el = None
			try:
				link_el = name_cell.find_element(By.XPATH, ".//a|.//button|.//span|.//div")
			except Exception:
				continue
			try:
				link_text = (link_el.text or "").upper()
			except Exception:
				link_text = ""
			is_2a = ("ADV 2A" in link_text) or ("ADV2A" in link_text) or ("PART 2A" in link_text)
			extracted.append({
				"date": date_str,
				"cell": name_cell,
				"link": link_el,
				"text": link_text,
				"is_2a": is_2a,
			})
		def parse_date(s: str):
			try:
				return time.strptime(s, "%m/%d/%Y")
			except Exception:
				return time.gmtime(0)
		# Prefer only 2A rows; if none, fall back to all
		preferred = [e for e in extracted if e["is_2a"]]
		candidates = preferred if preferred else extracted
		candidates.sort(key=lambda e: parse_date(e["date"]), reverse=True)
		for e in candidates:
			link = e["link"]
			log(f"trying table link (preferred={e['is_2a']}): '{e['text']}' date={e['date']}")
			href = None
			try:
				href = link.get_attribute("href")
			except Exception:
				href = None
			start = time.time()
			if href:
				driver.execute_script("window.open(arguments[0], '_blank');", href)
			else:
				try:
					link.click()
				except Exception:
					driver.execute_script("arguments[0].click();", link)
			# Wait for viewer or download
			for _ in range(50):
				if len(driver.window_handles) > 1:
					driver.switch_to.window(driver.window_handles[-1])
					break
				cand = newest_file_in_directory(TMP_DOWNLOADS_DIR)
				if cand and cand.stat().st_mtime >= start:
					break
				random_delay(0.2, 0.5)
			src = extract_pdf_embed_src(driver)
			if src:
				log("navigating to embedded pdf from table")
				driver.get(src)
				wait_for_stable_download(time.time())
			else:
				click_pdf_download_button(driver)
				wait_for_stable_download(time.time())
			# close tab if opened
			if len(driver.window_handles) > 1:
				try:
					driver.close()
					driver.switch_to.window(driver.window_handles[0])
				except Exception:
					pass
			set_verify_flag_from_text(e['text'])
			return True
		return False
	except Exception as e:
		log(f"table scan error: {e}")
		return False


def download_part2a_from_table_iterative(driver: webdriver.Chrome, crd: str) -> bool:
	if not ensure_brochures_table(driver):
		log("brochures table not found for iterative download")
		return False
	try:
		table = driver.find_element(By.XPATH, TABLE_XPATH)
		rows = table.find_elements(By.XPATH, ".//tbody/tr") or table.find_elements(By.XPATH, ".//tr")
		entries = []
		for r in rows:
			cells = r.find_elements(By.XPATH, ".//td")
			if len(cells) < 2:
				continue
			date_str = cells[1].text.strip()
			name_cell = cells[0]
			try:
				link = name_cell.find_element(By.XPATH, ".//a|.//button|.//span|.//div")
			except Exception:
				continue
			text = (link.text or "").upper()
			entries.append({"date": date_str, "link": link, "text": text})
		def parse_date(s: str):
			try:
				return time.strptime(s, "%m/%d/%Y")
			except Exception:
				return time.gmtime(0)
		# Sort newest first by date
		entries.sort(key=lambda e: parse_date(e["date"]), reverse=True)
		for e in entries:
			log(f"iterative table check: '{e['text']}' date={e['date']}")
			set_verify_flag_from_text(e["text"])  # will be True since titles lack 2A but generalized
			href = None
			try:
				href = e["link"].get_attribute("href")
			except Exception:
				href = None
			start = time.time()
			existing = driver.window_handles
			if href:
				driver.execute_script("window.open(arguments[0], '_blank');", href)
			else:
				try:
					e["link"].click()
				except Exception:
					driver.execute_script("arguments[0].click();", e["link"]) 
			outcome = wait_for_outcome_after_click(driver, existing, start)
			try:
				if outcome == 'new_tab':
					wait_document_ready(driver)
					src = extract_pdf_embed_src(driver)
					if src:
						driver.get(src)
						f = wait_for_stable_download(time.time())
						move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
						finalize_download(crd, time.time())
					else:
						click_pdf_download_button(driver)
						f = wait_for_stable_download(time.time())
						move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
						finalize_download(crd, time.time())
					# close the viewer tab and return to main if present
					if len(driver.window_handles) > 1:
						try:
							driver.close()
							driver.switch_to.window(driver.window_handles[0])
						except Exception:
							pass
				elif outcome == 'viewer_same':
					src = extract_pdf_embed_src(driver)
					if src:
						driver.get(src)
						f = wait_for_stable_download(time.time())
						move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
						finalize_download(crd, time.time())
					else:
						click_pdf_download_button(driver)
						f = wait_for_stable_download(time.time())
						move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
						finalize_download(crd, time.time())
				else:  # download
					f = wait_for_stable_download(start)
					move_to_dest(f, FIRM_PDFS_DIR / f"{crd}.pdf")
					finalize_download(crd, start)
			except NoSuchWindowException:
				log("window closed during table download; continuing")
				# try next entry
				pass
			# Verify content (since titles lacked 2A)
			dest = FIRM_PDFS_DIR / f"{crd}.pdf"
			if pdf_contains_part2a(dest):
				log("iterative table: found Part 2A; keeping file")
				return True
			else:
				log("iterative table: not Part 2A; removing and trying next")
				try:
					dest.unlink()
				except Exception:
					pass
		return False
	except Exception as e:
		log(f"iterative table error: {e}")
		return False


def verify_or_fallback(driver: webdriver.Chrome, crd: str, since_time: float) -> bool:
	dest = FIRM_PDFS_DIR / f"{crd}.pdf"
	# First, if we already have a file, verify it
	if dest.exists():
		if pdf_contains_part2a(dest):
			log("verified Part 2A in downloaded PDF")
			return True
		else:
			log("downloaded PDF does not contain Part 2A; trying table iterative fallback")
			try:
				dest.unlink()
			except Exception:
				pass
	# New approach: iterate table rows newest-first until a Part 2A is found
	return download_part2a_from_table_iterative(driver, crd)

# In download flows, after moving/finalize, call verify_or_fallback

# Since we cannot contextually replace with precision here, define a small wrapper to centralize move+verify usage

def move_finalize_verify(crd: str, start_time: float) -> None:
	dest = FIRM_PDFS_DIR / f"{crd}.pdf"
	finalize_download(crd, start_time)
	if verify_needed_ref[0]:
		ok = verify_or_fallback(driver_ref[0], crd, start_time)
		if not ok:
			log("WARNING: Could not verify Part 2A after fallback attempts")
	else:
		log("verification skipped due to link text including 2A")

# Helper to decide whether to verify PDF content based on link text

def set_verify_flag_from_text(text: str | None) -> None:
	try:
		upper = (text or "").upper()
	except Exception:
		upper = ""
	# If link text clearly indicates 2A, skip content verification
	verify_needed_ref[0] = not ("ADV 2A" in upper or "ADV2A" in upper or "PART 2A" in upper)
	if verify_needed_ref[0]:
		log("will verify PDF content (link text did not include 2A)")
	else:
		log("skipping PDF text verification (link text includes 2A)")

# Keep a driver reference holder and verification flag
driver_ref = [None]
verify_needed_ref = [True]


def wait_document_ready(driver: webdriver.Chrome) -> None:
	# Poll until document.readyState is 'complete' or a short sequence of successes
	ok_count = 0
	for _ in range(50):
		try:
			state = driver.execute_script("return document.readyState || 'complete'")
			if state == 'complete':
				ok_count += 1
				if ok_count >= 2:
					return
			random_delay(0.1, 0.2)
		except Exception:
			random_delay(0.2, 0.4)


def safe_switch_to_valid_window(driver: webdriver.Chrome) -> None:
	for attempt in range(3):
		try:
			handles = driver.window_handles
			if not handles:
				random_delay(0.2, 0.4)
				continue
			driver.switch_to.window(handles[-1])
			_ = driver.current_url  # access to validate
			return
		except Exception:
			random_delay(0.2, 0.4)


def init_driver() -> webdriver.Chrome:
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
		"plugins.always_open_pdf_externally": True,
	}
	options.add_experimental_option("prefs", prefs)
	drv = webdriver.Chrome(
		service=Service(ChromeDriverManager().install()),
		options=options,
	)
	driver_ref[0] = drv
	try:
		drv.execute_cdp_cmd(
			"Page.addScriptToEvaluateOnNewDocument",
			{"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
		)
	except Exception:
		pass
	return drv


def main() -> None:
	random.seed()
	FIRM_PDFS_DIR.mkdir(parents=True, exist_ok=True)
	TMP_DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

	driver = init_driver()
	log("navigating to adviserinfo.sec.gov")
	driver.get("https://adviserinfo.sec.gov/")
	random_idle(0.8, 2.0)
	random_scroll(driver)
	log(f"landed {describe_driver(driver)}")

	all_crds = get_all_crds(CSV_FILENAME)
	processed = load_processed()
	log(f"loaded {len(all_crds)} CRDs, {len(processed)} already processed")
	targets: list[str] = []
	for crd in all_crds:
		dest = FIRM_PDFS_DIR / f"{crd}.pdf"
		if crd in processed or dest.exists():
			continue
		targets.append(crd)
		if len(targets) >= 10:
			break
	log(f"processing next {len(targets)} CRDs: {targets}")

	first = True
	for crd in targets:
		log(f"=== START CRD {crd} ===")
		try:
			if first:
				process_first_iteration(driver, crd)
				first = False
			else:
				process_subsequent_iteration(driver, crd)
			append_processed(crd)
			log(f"=== DONE CRD {crd} ===")
			random_idle(0.8, 1.8)
		except Exception as e:
			log(f"CRD {crd} failed with error: {e}; restarting driver and continuing")
			try:
				driver.quit()
			except Exception:
				pass
			driver = init_driver()
			log("reloaded driver; navigating home")
			driver.get("https://adviserinfo.sec.gov/")
			random_idle(0.8, 2.0)
			random_scroll(driver)
			first = True  # ensure we reset flow on fresh session

	log("idle forever")
	while True:
		time.sleep(3600)


if __name__ == "__main__":
	main()
