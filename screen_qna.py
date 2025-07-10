#!/usr/bin/env python
"""screen_qna.py
A small utility that captures your screen, extracts any visible question
(sentences that end with a question mark), and asks OpenAI's Chat
Completion endpoint for an answer.

Prerequisites:
1. Install the Python dependencies from requirements.txt
2. Install the Tesseract OCR engine (https://github.com/tesseract-ocr/tesseract)
   and ensure the `tesseract` command is in your system PATH.
3. Set the environment variable `OPENAI_API_KEY` with your OpenAI key.

Examples
--------
Capture the entire screen once and exit:
    python screen_qna.py --once

Continuously scan every 15 s only in a 1280×720 region starting at the top-left
corner and use GPT-4o:
    python screen_qna.py --interval 15 --region 0 0 1280 720 --model gpt-4o-mini
"""
from __future__ import annotations

import argparse
import os
import re
import time
from typing import List, Optional, Tuple

import openai
import platform
import shutil
import pyautogui
import pytesseract
from PIL import Image  # noqa: F401  # used implicitly by pyautogui / pytesseract

# ---------------------------------------------------------------------------
# Automatic Tesseract detection (Windows)
# ---------------------------------------------------------------------------
# If the user has Tesseract installed in the default location but didn't add it
# to the system PATH, configure pytesseract to use that executable so the
# script "just works" without manual PATH edits.
if os.name == "nt" and shutil.which("tesseract") is None:
    for _base in (
        r"C:\\Program Files\\Tesseract-OCR",
        r"C:\\Program Files (x86)\\Tesseract-OCR",
    ):
        _candidate = os.path.join(_base, "tesseract.exe")
        if os.path.exists(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break


# ----------------------------------------------------------------------------
# Core helpers
# ----------------------------------------------------------------------------

def capture_screen(region: Optional[Tuple[int, int, int, int]] = None) -> "Image.Image":
    """Grab a screenshot of the specified *region* or the full screen.

    Parameters
    ----------
    region : Tuple[int, int, int, int] | None
        Bounding box (x, y, width, height). If *None*, captures the full screen.

    Returns
    -------
    PIL.Image.Image
        The captured screenshot.
    """
    screenshot = pyautogui.screenshot(region=region)
    return screenshot


def extract_questions(text: str) -> List[str]:
    """Return a list of distinct question sentences inside *text*.

    A *question sentence* is any substring that ends in a question-mark.
    We keep it simple with a regex that captures a capitalised sentence of
    ≥ 4 characters ending with `?`.
    """
    pattern = r"([A-Z][^?]{3,}?\?)"
    questions = re.findall(pattern, text, re.MULTILINE | re.DOTALL)
    return list(dict.fromkeys(q.strip() for q in questions))  # dedupe while preserving order


def query_openai(question: str, model: str = "gpt-3.5-turbo") -> str:
    """Ask *question* to OpenAI and return the assistant's reply."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set.")

    # Use the v1+ client if available (openai>=1.0)
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()
    except AttributeError:
        # Fallback for older openai<1.0
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "user", "content": question}],
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Answer on-screen questions using AI.")
    parser.add_argument("--interval", type=int, default=10, help="Seconds between consecutive captures (ignored with --once).")
    parser.add_argument("--model", default="gpt-3.5-turbo", help="OpenAI model name (e.g., gpt-3.5-turbo, gpt-4o, etc.)")
    parser.add_argument("--once", action="store_true", help="Capture only once and exit.")
    parser.add_argument("--region", nargs=4, type=int, metavar=("X", "Y", "W", "H"), help="Screen region to capture instead of full screen.")
    args = parser.parse_args()

    region_box: Optional[Tuple[int, int, int, int]] = tuple(args.region) if args.region else None
    seen: set[str] = set()

    try:
        while True:
            img = capture_screen(region_box)
            text = pytesseract.image_to_string(img)
            for q in extract_questions(text):
                if q in seen:
                    continue
                print(f"\n[Q] Question detected: {q}\n")
                try:
                    answer = query_openai(q, args.model)
                    print("[A] Answer:\n" + answer + "\n")
                    seen.add(q)
                except Exception as e:
                    print(f"Error while querying OpenAI: {e}\n")
            if args.once:
                break
            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        print("\nExiting…")


if __name__ == "__main__":
    main()
