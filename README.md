# firm_crd_advisorinfo_pdf

Headed Selenium automation to fetch Part 2 (ADV2A) PDFs from adviserinfo.sec.gov for a list of Firm CRDs.

- Reads Firm CRDs from `Manual Brochure Process.csv` (leftmost column)
- Navigates UI with anti-bot randomization
- Downloads PDFs and renames to `<CRD>.pdf` into `firm_pdfs/`
- Tracks processed CRDs in `processed_crds.txt`

Setup
- Python 3.11+
- `pip install -r requirements.txt`

Run
- `python main.py`
# firm_crd_advisorinfo_pdf
