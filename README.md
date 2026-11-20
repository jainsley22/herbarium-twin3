# Herbarium Twin 3 — Windows / macOS / Linux

This package preserves the uploaded Python application, AI assessment prompt, CSV/JSON exports, SQLite database, and QR label workflow.

This version of Herbarium Twin is version 3, which integrates the functionality of the first two versions with further prompt development, QR code & summary updates, database updates, and refinements to Streamlit interface. AI is functional with this version, thus this should be used as the primary version of Herbarium Twin. See herbarium-twin-human-friendly for manual backup version.

## Setup

Install Python 3.10+ (3.11 or 3.12 recommended). Open a terminal in this folder.

**To download herbarium-twin2 repository on local computer**:
```
git clone https://github.com/jainsley22/herbarium-twin3
```
**To open herbarium-twin2 in your terminal. This is the first step to every session, once downloaded.**
```
cd herbarium-twin3
```
**From here, it is system dependent**


**Windows PowerShell:**

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```
```
pip install -r requirements.txt
```
Go to Gemini API Key studio to create and copy-paste key here. Tip: open up text application (e.g. "Text Editor" on Linux or "TextEdit" on Mac) to copy-paste and format key with code easily.
```
$env:GEMINI_API_KEY = 'YOUR_API_KEY'
```
This runs the application. If you need to quit and restart, repeat this step.
```
streamlit run runnable.py --server.address 0.0.0.0
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```
```
pip install -r requirements.txt
```
Go to Gemini API Key studio to create and copy-paste key here. Tip: open up text application (e.g. "Text Editor" on Linux or "TextEdit" on Mac) to copy-paste and format key with code easily.
```
export GEMINI_API_KEY='YOUR_API_KEY'
```
This runs the application. If you need to quit and restart, repeat this step.
```
streamlit run runnable.py --server.address 0.0.0.0
```

# To connect mobile phone
1. Make sure that your phone is connected to Darwin.
2. Open the internet browser you use on your phone.
3. On your phone, type in the internet address listed at the top of the Streamlit application on your computer. This is listed underneath the section header "Access Herbarium Twin on mobile phone", in the field titled "Local Network URL".
4. Load the page and you are ready for use.

## Data, QR safety, frequent errors

The supplied herbarium_database.db is copied byte-for-byte. The application uses this file in its own folder. Do not run two independent copies of the app against different databases if you expect synchronized records. Back up the database before transferring it.

**In other words, samples are saved locally. This means that you must upload .json files, images, and/or QR codes to Google Drive folder titled "Herbarium Twin 2 Uploads" for sharing. Updates are NOT reflected across users.**

Existing QR JPGs and captured photos were not included in the uploads. Existing QR labels may encode a previous computer's IP address and will not automatically update when moved. New box labels are created on save; existing label files are not overwritten.
**QR codes link to full sample information.**

Do not share your Gemini API key in a ZIP or source code. Set GEMINI_API_KEY separately on each machine.
**Can access Gemini API key through simple search online. Be aware of Google Gemini updates, requirements, and model developments.**

The application was syntax-checked and the database integrity checked, but live Gemini API requests and Windows GUI operation were not tested in this environment.

**Frequent Errors**

To stop Streamlit running in the terminal, press ctrl-c. Try restarting the application for pretty much any error.
To get Streamlit running again:
```
streamlit run runnable.py --server.address 0.0.0.0
```

If you receive an error like:
```
AI failed: Gemini analysis failed: 503 UNAVAILABLE. {'error': {'code': 503, 'message': 'This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.', 'status': 'UNAVAILABLE'}}
```
**Wait 30 seconds-1 minute and try again.**
This error means that the Gemini model is overwhelmed. The code is perfectly fine, you just have to wait for the AI model to recover. 
If you get repeated messages for this error, refresh the entire webpage and try again.

Make sure that your Python version is up to date. This repository was built with version 3.13.9 and miniconda3.

**Check python version with this code**
```
python3 --version
```
**Check model of python (e.g. miniconda or anaconda)**
```
echo $CONDA_EXE
```
This is critical if you are running other projects and have other environments as you may run into errors. You can find other models and versions of python online.
