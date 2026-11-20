# Herbarium Twin

A local Streamlit app for herbarium inventory, Gemini-assisted image assessments, QR labels, and 3-label print PDFs.

## Requirements

- Python 3.10–3.12 recommended
- Internet access for Gemini analysis
- Gemini API key (set locally; never commit it)

## Installation

Download or clone this repository, then open a terminal in its folder.

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
export GEMINI_API_KEY="your-api-key"
python -m streamlit run runnable.py --server.address 0.0.0.0
```

**Windows PowerShell:**

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GEMINI_API_KEY="your-api-key"
.\.venv\Scripts\python.exe -m streamlit run runnable.py --server.address 0.0.0.0
```

If `py` is unavailable, use `python` in its place. The Windows commands use the virtual environment's Python directly and do not require changing PowerShell execution policy.

Open the Local URL shown by Streamlit. For phone access, use the computer's network address and ensure the firewall permits the Streamlit port (default 8501). A hotspot/network change may invalidate previously generated QR URLs.

## Data and printing

The app creates `herbarium_database.db` automatically on first run if it is absent. The database, specimen images, QR codes, and JSON exports are intentionally ignored by Git to avoid publishing collection data. Keep a backup of these files before upgrading.

Labels are 15 × 8.8 cm at 300 DPI. Existing Collection can export up to three labels per US Letter sheet; print PDFs at **Actual Size / 100%**.

QR codes open records served by the running Streamlit app. For reliable permanent scanning, deploy the app at a stable reachable URL *before* generating labels.

## Notes

- The app uses standard-library `pathlib` for portable paths and Pillow for fonts/image handling. Font availability may change typography slightly between systems.
- Mobile camera capture is controlled by the phone browser and OS; cross-platform Python support does not guarantee Android camera upload behavior.
- This project has not been end-to-end tested on physical Windows, Linux, and macOS computers.
