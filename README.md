<p align="center">
  <img width="600" height="425" alt="Design sans titre (31)"
       src="https://github.com/user-attachments/assets/e5d30189-7d8d-4ea7-9689-11e9f80ea15d" />
</p>
# ScreenQnA

ScreenQnA is a tiny desktop utility that lets you *snap* any part of your screen and instantly receive an AI-generated answer to the question you highlighted.

## Features
* OCR the entire screen (or a selected region) using Tesseract.
* Detect sentences ending with a question mark.
* Query OpenAI ChatCompletion to get concise answers.
* Skip already-answered questions to avoid duplicate costs.

## Installation (A-Z)
1. **Install Python 3.10+**
   • Download from <https://python.org> and tick “Add Python to PATH” during setup.

2. **Install Tesseract-OCR 5.x**
   ```powershell
   winget install --id=UB-Mannheim.TesseractOCR --source winget  # easiest on Windows 10/11
   ```
   or grab the installer from the [UB Mannheim release page](https://github.com/UB-Mannheim/tesseract/wiki). The installer adds `tesseract.exe` to PATH by default.

   • To support Arabic OCR, download `ara.traineddata` (if not already included) and copy it to the Tesseract `tessdata` folder, e.g. `C:\Program Files\Tesseract-OCR\tessdata`.

   Test that it works:
   ```powershell
   tesseract --version
   ```

3. **Clone ScreenQnA**
   ```powershell
   git clone https://github.com/AlexGritli/ScreenQnA.git
   cd ScreenQnA
   ```

4. **Create & activate a virtual environment** (recommended):
   ```powershell
   python -m venv venv
   .\venv\Scripts\activate      # Windows PowerShell
   # or
   source venv/bin/activate      # macOS / Linux
   ```

5. **Install Python requirements**
   ```powershell
   pip install -r requirements.txt
   ```

6. **Configure OpenAI credentials** (never commit them!)

   Create a `.env` file in the project root – the app loads it automatically via `python-dotenv`:

   ```env
   # Normal user key (simplest)
   OPENAI_API_KEY=sk-...

   # --- OR ---
   # Service-account / project key
   OPENAI_API_KEY=sk-svcacct-...
   OPENAI_ORG_ID=org_...

   # OPTIONAL – only if you need to override the default project baked into the key
   # OPENAI_PROJECT_ID=proj_...
   ```

   Alternatively, export variables in the terminal (session-only):
   ```powershell
   $env:OPENAI_API_KEY="sk-..."
   $env:OPENAI_ORG_ID="org_..."   # only for svcacct keys
   ```

## Usage

ScreenQnA has **three ways** to run, depending on how you like to work.

### 1. Friendly GUI (recommended)
```powershell
python screen_qna_gui.py
```
Steps:
1. A window opens – click the **Select & Answer** button (or press **Ctrl + S**).
2. The screen dims; drag a rectangle around the question and *release* the mouse.
3. ScreenQnA does OCR ➜ queries OpenAI ➜ shows the answer:
   ```
   .....
   Answer: William Shakespeare
   ```
   The answer is also copied to your clipboard so you can paste it anywhere.
4. Click **Select & Answer** again for the next question.

### 2. One-shot “snip & quit” (no window)
```powershell
python screen_qna_snap.py [--lang ara] [--psm 6] [--model gpt-4o-mini]
```
The script dims the screen once, you draw a box, it prints only the answer, then offers:
```
(1) Retake screenshot  (2) Exit:
```
Choose **1** to capture another or **2** / Enter to quit.

Useful flags:
* `--lang ara` force Arabic OCR only (default `eng+ara`).
* `--psm 6`  Tesseract page-segmentation mode; try `3`, `6`, `11` for tricky cases.
* `--show-text` also print raw OCR text (debugging).

### 3. Continuous CLI watcher (hands-free)
```powershell
python screen_qna.py --interval 20            # every 20 s
python screen_qna.py --region 100 100 800 600  # watch just that box
python screen_qna.py --model gpt-4o-mini       # choose another model
```
The script scans automatically and prints Q ➜ A pairs until you press **Ctrl +C**.

---
Need help? Run any script with `-h` to see all options.


