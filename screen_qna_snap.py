#!/usr/bin/env python
"""screen_qna_snap.py
Instant one-shot snipping-tool-like helper.
• Run the script – the screen darkens.
• Drag a rectangle around the question.
• It OCRs the region and prints the AI answer to stdout (and to a message box).
Then the program exits.
"""
from __future__ import annotations

import os
import sys
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Tuple

import openai
import pytesseract
from PIL import ImageGrab
import shutil

# Tesseract locate (same logic)
if os.name == "nt" and shutil.which("tesseract") is None:
    for base in (r"C:\\Program Files\\Tesseract-OCR", r"C:\\Program Files (x86)\\Tesseract-OCR"):
        exe = os.path.join(base, "tesseract.exe")
        if os.path.exists(exe):
            pytesseract.pytesseract.tesseract_cmd = exe
            break


# ----------------------------- region selector -----------------------------

def select_region() -> Optional[Tuple[int, int, int, int]]:
    root = tk.Tk()
    root.withdraw()  # hide root

    overlay = tk.Toplevel(root)
    overlay.overrideredirect(True)
    overlay.lift()  # bring to front
    overlay.attributes("-topmost", True)
    overlay.focus_force()
    overlay.attributes("-alpha", 0.3)
    overlay.configure(bg="black")

    w, h = root.winfo_screenwidth(), root.winfo_screenheight()
    overlay.geometry(f"{w}x{h}+0+0")

    canvas = tk.Canvas(overlay, bg="black", cursor="cross", highlightthickness=0)
    canvas.pack(fill=tk.BOTH, expand=True)

    sel: dict[str, int] = {}
    rect_id = None

    def on_press(e):
        nonlocal rect_id
        sel["x1"], sel["y1"] = e.x_root, e.y_root
        rect_id = canvas.create_rectangle(sel["x1"], sel["y1"], sel["x1"], sel["y1"], outline="red", width=2)

    def on_drag(e):
        if rect_id:
            canvas.coords(rect_id, sel["x1"], sel["y1"], e.x_root, e.y_root)

    def on_release(e):
        sel["x2"], sel["y2"] = e.x_root, e.y_root
        overlay.destroy()
        root.destroy()

    def on_escape(e):
        sel.clear()
        overlay.destroy()
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_press)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_release)
    canvas.bind("<Escape>", on_escape)
    overlay.bind("<Escape>", on_escape)

    overlay.mainloop()

    if {"x1", "y1", "x2", "y2"}.issubset(sel):
        return (
            min(sel["x1"], sel["x2"]),
            min(sel["y1"], sel["y2"]),
            max(sel["x1"], sel["x2"]),
            max(sel["y1"], sel["y2"]),
        )
    return None


# ---------------------------- OpenAI helper ----------------------------

def ask_ai(question: str, model: str = "gpt-3.5-turbo") -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY env var not set")
    try:
        client = openai.OpenAI(api_key=key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except AttributeError:
        openai.api_key = key
        resp = openai.ChatCompletion.create(model=model, messages=[{"role": "user", "content": question}], temperature=0.7)
        return resp.choices[0].message.content.strip()


# ------------------------------- main -----------------------------------


import argparse
from dotenv import load_dotenv

def main():
    parser = argparse.ArgumentParser(description="Snap a region and answer.")
    parser.add_argument("--lang", default="eng+ara", help="Tesseract language(s), e.g. ara or eng+ara")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="OpenAI model")
    parser.add_argument("--psm", default="6", help="Tesseract page segmentation mode")
    parser.add_argument("--show-text", action="store_true", help="Also print detected OCR text")
    parser.add_argument("--popup", action="store_true", help="Show answers in GUI pop-up")
    args = parser.parse_args()

    load_dotenv()

    while True:
        bbox = select_region()
        if bbox is None:
            print("Selection cancelled.")
            break

        img = ImageGrab.grab(bbox=bbox)
        config = f"--psm {args.psm}"
        text = pytesseract.image_to_string(img, lang=args.lang, config=config).strip()

        if not text:
            if args.popup:
                messagebox.showinfo("ScreenQnA", "No text detected in selection.")
            print("No text detected.")
        else:
            if args.show_text:
                print(text)
            try:
                answer = ask_ai(text, model=args.model)
                print(".....")
                print(answer)
                if args.popup:
                    messagebox.showinfo("AI Answer", answer)
            except Exception as e:
                if args.popup:
                    messagebox.showerror("ScreenQnA", str(e))
                print("Error:", e)

        choice = input("(1) Retake screenshot  (2) Exit: ").strip()
        if choice != "1":
            break


if __name__ == "__main__":
    main()
