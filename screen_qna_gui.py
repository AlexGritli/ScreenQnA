#!/usr/bin/env python
"""screen_qna_gui.py
A minimal GUI wrapper around the ScreenQnA functionality.

Workflow
--------
1. Click the "Select & Answer" button (or press the keyboard shortcut Ctrl+S).
2. The application hides and a transparent full-screen overlay appears.
3. Click-drag to draw a rectangle around the on-screen question text.
4. Release the mouse; the app captures that region, performs OCR, then sends
   the detected text to OpenAI and shows the answer.

Dependencies
------------
Same as `screen_qna.py` (openai, pytesseract, pillow). `tkinter` ships with the
standard CPython distribution on Windows, so no extra install is required.

Usage
-----
python screen_qna_gui.py
"""
from __future__ import annotations

import os
import argparse
import traceback
import re
from typing import Optional
import threading
import tkinter as tk
from dotenv import load_dotenv
from tkinter import messagebox, scrolledtext
from typing import Optional, Tuple

import openai
import pytesseract
from PIL import ImageGrab, ImageTk, Image  # noqa: F401
import shutil

# ---------------------------------------------------------------------------
# Tesseract auto-detection (same logic as in the CLI script)
# ---------------------------------------------------------------------------
if os.name == "nt" and shutil.which("tesseract") is None:
    for _base in (
        r"C:\\Program Files\\Tesseract-OCR",
        r"C:\\Program Files (x86)\\Tesseract-OCR",
    ):
        _candidate = os.path.join(_base, "tesseract.exe")
        if os.path.exists(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break

# ---------------------------------------------------------------------------
# OpenAI helper
# ---------------------------------------------------------------------------

def query_openai(prompt: str, model: str = "gpt-3.5-turbo") -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")

    try:
        org_id = os.getenv("OPENAI_ORG_ID")
        project_id = os.getenv("OPENAI_PROJECT_ID")
        client_kwargs = {"api_key": api_key}
        if org_id:
            client_kwargs["organization"] = org_id
        if project_id:
            client_kwargs["project"] = project_id
        client = openai.OpenAI(**client_kwargs)
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a factual question answering assistant. Answer ACCURATELY and CONCISELY with ONLY the direct answer phrase. If the question is Arabic respond in Arabic."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except openai.AuthenticationError as e:
        # Provide a clearer error when the API key is invalid or missing permissions
        raise RuntimeError("OpenAI authentication failed. Please verify that your OPENAI_API_KEY is correct and active.") from e
    except AttributeError:
        # openai<1.0 fallback
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

# ---------------------------------------------------------------------------
# Region selection overlay
# ---------------------------------------------------------------------------


def select_region(parent: tk.Tk) -> Optional[Tuple[int, int, int, int]]:
    """Interactive region selector similar to Windows Snipping Tool.

    Returns a (x1, y1, x2, y2) tuple in **absolute screen pixels**, or None if
    the user cancels (e.g., presses Esc).
    """
    sel: dict[str, int] = {}

    overlay = tk.Toplevel(parent)  # child of main window
    overlay.overrideredirect(True)  # remove window frame
    overlay.attributes("-topmost", True)
    overlay.attributes("-alpha", 0.3)  # 30% opaque black overlay
    overlay.configure(bg="black")

        # Cover the entire virtual desktop (handles multi-monitor)
    try:
        import pyautogui
        w, h = pyautogui.size()
    except Exception:
        w, h = parent.winfo_screenwidth(), parent.winfo_screenheight()
    overlay.geometry(f"{w}x{h}+0+0")

    canvas = tk.Canvas(overlay, bg="black", cursor="crosshair", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    # Instruction label
    lbl = tk.Label(canvas, text="Drag to select area, release mouse to capture, Esc to cancel", fg="white", bg="black")
    lbl.place(relx=0.5, rely=0.02, anchor="n")

    # Grab all events so release is detected even outside rectangle
    overlay.grab_set()

    rect_id = None

    def on_press(event):
        nonlocal rect_id
        sel["x1"], sel["y1"] = event.x_root, event.y_root
        rect_id = canvas.create_rectangle(sel["x1"], sel["y1"], sel["x1"], sel["y1"], outline="red", width=2)

    def on_drag(event):
        if rect_id:
            canvas.coords(rect_id, sel["x1"], sel["y1"], event.x_root, event.y_root)

    def on_release(event):
        sel["x2"], sel["y2"] = event.x_root, event.y_root
        overlay.grab_release()
        overlay.destroy()

    def on_escape(event):
        sel.clear()
        overlay.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Escape>", on_escape)
    overlay.bind("<Escape>", on_escape)  # allow Esc to cancel

    overlay.update()
    # Wait until the overlay is destroyed (user has finished selection)
    parent.wait_window(overlay)

    if {"x1", "y1", "x2", "y2"}.issubset(sel):
        return (
            min(sel["x1"], sel["x2"]),
            min(sel["y1"], sel["y2"]),
            max(sel["x1"], sel["x2"]),
            max(sel["y1"], sel["y2"]),
        )
    return None

# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------


def run_ocr_and_answer(root: tk.Tk, bbox: Tuple[int, int, int, int], ui_text: tk.Text, button: tk.Button):
    """Background worker; schedules UI updates via `after`."""
    def ui(func, *args, **kwargs):
        ui_text.after(0, func, *args, **kwargs)

    ui(lambda: button.config(state=tk.DISABLED))
    ui(ui_text.delete, "1.0", tk.END)
    ui(ui_text.insert, tk.END, "Running OCR...\n")

    try:
        img = ImageGrab.grab(bbox=bbox)
        text = pytesseract.image_to_string(img, lang="eng+ara")
        ui(ui_text.insert, tk.END, f"OCR result:\n{text}\n\nQuerying OpenAI...\n")
        def extract_question(txt: str) -> str:
            # Arabic question mark or Latin
            m_ar = re.search(r"[^؟]{2,}؟", txt)
            if m_ar:
                return m_ar.group().strip()
            m_en = re.search(r"[^?]{2,}\?", txt)
            if m_en:
                return m_en.group().strip()
            return txt.strip()

        question_only = extract_question(text)
        answer = query_openai(question_only)
        # build prefix depending on language
        is_arabic = any("\u0600" <= ch <= "\u06FF" for ch in text)
        prefix = "الإجابة: " if is_arabic else "Answer: "
        num_part = ""
        m = re.match(r"^([\d٠-٩]+[%٪]?)\s+(.*)", answer)
        if m:
            num_part, ans_main = m.groups()
        else:
            ans_main = answer
        formatted = f"{num_part} {prefix}{ans_main}".strip()
        ui(ui_text.delete, "1.0", tk.END)  # clear previous
        ui(ui_text.insert, tk.END, ".....\n" + formatted)
        ui_text.after(0, lambda: root.clipboard_clear())
        ui_text.after(0, lambda: root.clipboard_append(formatted))
        ui(messagebox.showinfo, "AI Answer", answer)
    except Exception as e:
        traceback.print_exc()
        ui(messagebox.showerror, "Error", str(e))
    finally:
        ui(lambda: button.config(state=tk.NORMAL))


def main():
    load_dotenv(override=True)
    root = tk.Tk()
    root.title("Screen QnA GUI")
    root.geometry("600x400")

    root.columnconfigure(0, weight=1)
    root.rowconfigure(0, weight=1)

    answer_box = scrolledtext.ScrolledText(root, wrap=tk.WORD)
    answer_box.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    def on_select_and_answer():
        # Temporarily hide the main window so it doesn't obstruct the overlay
        # Disable interaction with main window while selecting
        root.attributes('-disabled', True)
        bbox = select_region(root)
        root.attributes('-disabled', False)
        root.lift()
        root.focus_force()
        if not bbox:
            return
        threading.Thread(target=run_ocr_and_answer, args=(root, bbox, answer_box, action_btn), daemon=True).start()

    action_btn = tk.Button(root, text="Select & Answer (Ctrl+S)", command=on_select_and_answer)
    action_btn.grid(row=1, column=0, pady=5, sticky="ew")

    root.bind("<Control-s>", lambda _e: on_select_and_answer())

    root.mainloop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="screenqna-gui",
        description="ScreenQnA GUI – select a screen region and instantly get an AI answer.",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog="""Examples:
  python screen_qna_gui.py          # launch the GUI
  python screen_qna_gui.py -h       # show this help

Inside the window:
  1. Click 'Select & Answer' (or press Ctrl+S)
  2. Drag to select the question area and release
  3. The answer appears and is copied to your clipboard
""",
        add_help=True,
    )
    # We purposefully accept no additional flags; this
    # allows `-h/--help` to work while failing on unknown args.
    parser.parse_args()
    main()
