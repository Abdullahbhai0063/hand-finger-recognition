# Real-Time Hand Finger Recognition & Voice Assistant

A Python computer-vision app that watches your hand through the webcam, counts how many
fingers you are holding up (0–5), shows the number and the word on screen, and **speaks it
out loud — completely offline**.

---

## 1. Project Overview

Point your hand at the laptop camera. The program finds your hand, draws 21 skeleton points
on it, works out which fingers are raised, and announces the result.

| You show | Screen shows | Laptop says |
|---|---|---|
| Closed fist | `Detected Fingers: 0` / **ZERO** | "Zero" |
| 1 finger | `Detected Fingers: 1` / **ONE** | "One" |
| 2 fingers | `Detected Fingers: 2` / **TWO** | "Two" |
| 3 fingers | `Detected Fingers: 3` / **THREE** | "Three" |
| 4 fingers | `Detected Fingers: 4` / **FOUR** | "Four" |
| 5 fingers | `Detected Fingers: 5` / **FIVE** | "Five" |

No internet, no cloud API, no database, no training required.

---

## 2. Features

- Real-time hand detection from the laptop webcam
- 21 hand landmarks + connections drawn live on your hand
- Finger counting from 0 to 5, works with the left or the right hand
- Clean on-screen UI with title, result panel and instructions
- Offline voice output with `pyttsx3`
- **Anti-repeat voice** — says each number once, not on every frame
- **Stability / debouncing** — a number must hold for 5 frames before it is trusted
- `No hand detected` state, with no speech
- Graceful error handling: no camera, no voice engine, lost feed
- Voice runs on a background thread so the video never freezes

---

## 3. Technologies Used

**Python 3** — the language holding everything together (3.9 to 3.12 recommended, because
MediaPipe does not yet publish wheels for 3.13).

**OpenCV (`cv2`)** — talks to the webcam, grabs each frame, mirrors it, draws text and
rectangles, and shows the window. Everything you *see* is OpenCV.

**MediaPipe** — Google's ready-made hand-tracking model. It takes an image and returns 21
numbered points on the hand. This is the "AI" part, and it is already trained for us.

**pyttsx3** — offline text-to-speech. On Windows it uses the SAPI5 voices already installed
in your system, so it works with no internet.

---

## 4. How It Works

```
Webcam (OpenCV)
      ↓
Hand Detection (MediaPipe)
      ↓
21 Hand Landmarks (x, y for each joint)
      ↓
Finger Open/Closed Logic (compare tip vs joint)
      ↓
Finger Counting (add up the open ones)
      ↓
Stability Check (same number 5 frames in a row)
      ↓
Number Recognition (4 → "FOUR")
      ↓
Screen Output (OpenCV)  +  Voice Output (pyttsx3, only on change)
```

---

## 5. Installation (Windows)

Open the project folder in VS Code, then open a terminal (**Ctrl + `**) and run:

```bat
python -m venv venv
```

Activate it:

```bat
venv\Scripts\activate
```

> If PowerShell blocks the activation, either use **Command Prompt**, or run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Upgrade pip (avoids a lot of install errors):

```bat
python -m pip install --upgrade pip
```

Install the dependencies:

```bat
pip install -r requirements.txt
```

Run the app:

```bat
python main.py
```

Check your Python version first if anything fails:

```bat
python --version
```

It should say 3.9, 3.10, 3.11 or 3.12.

---

## 6. How to Use

1. Run `python main.py`.
2. Allow camera access if Windows asks.
3. A window titled **Hand Finger Recognition** opens with your camera feed.
4. Hold your hand up, palm facing the camera, about 40–70 cm away.
5. Change the number of raised fingers — the screen and the voice follow you.
6. Press **Q** (or **Esc**) to quit.

Tips for the best results: good lighting, a plain background behind your hand, fingers
clearly separated, and the whole hand inside the frame.

---

## 7. Example

```
1 finger  →  ONE    →  voice says "One"
2 fingers →  TWO    →  voice says "Two"
3 fingers →  THREE  →  voice says "Three"
4 fingers →  FOUR   →  voice says "Four"
5 fingers →  FIVE   →  voice says "Five"
0 fingers →  ZERO   →  voice says "Zero"
```

Holding FOUR for ten seconds still says "Four" **once**. Going 4 → 2 → 5 says
"Two" then "Five".

---

## 8. Testing Checklist

| # | Test | What you should see / hear |
|---|---|---|
| 1 | Run with no hand in frame | Red `No hand detected`, `---`, complete silence |
| 2 | Closed fist | `Detected Fingers: 0`, **ZERO**, says "Zero" |
| 3 | Index finger only | `1`, **ONE**, says "One" |
| 4 | Index + middle | `2`, **TWO**, says "Two" |
| 5 | Three fingers | `3`, **THREE**, says "Three" |
| 6 | Four fingers (thumb folded in) | `4`, **FOUR**, says "Four" |
| 7 | Open palm | `5`, **FIVE**, says "Five" |
| 8 | Switch quickly 2 → 5 → 1 | Each confirmed number spoken once, in order; brief wobbles are ignored |
| 9 | Hold the same gesture 10 seconds | Spoken **once only**, number stays steady on screen |
| 10 | Move the hand out of frame and back | Goes to `No hand detected`, then re-announces the number when you return |
| 11 | Press Q | Window closes, terminal prints `Closed cleanly. Goodbye!`, camera light turns off |
| 12 | Left hand instead of right | Same results — the thumb logic handles both |

---

## 9. Troubleshooting

**"Could not open the webcam"** — another app (Zoom, Teams, the Windows Camera app) is
holding the camera. Close it. Also check *Settings → Privacy & security → Camera → Let
desktop apps access your camera*. If you use an external webcam, change `CAMERA_INDEX = 0`
to `1` or `2` at the top of `main.py`.

**`pip install mediapipe` fails** — you are almost certainly on Python 3.13. Install Python
3.11 or 3.12 and rebuild the virtual environment.

**No sound / "Voice OFF" in the corner** — run `pip install pyttsx3 comtypes`, check your
volume, and make sure a Windows voice is installed (*Settings → Time & language → Speech*).
The finger detection keeps working regardless.

**Thumb is counted when it shouldn't be** — tuck the thumb firmly across the palm; a thumb
resting beside the hand still looks "open" to simple x-comparison logic.

**Numbers flicker** — improve the lighting, or raise `STABLE_FRAMES` from 5 to 7–8 for a
calmer (but slightly slower) response.

**Video feels slow** — lower `FRAME_WIDTH` / `FRAME_HEIGHT` to 640 × 360.

**Window will not close** — click the video window first so it has keyboard focus, then
press Q. Ctrl + C in the terminal also shuts it down cleanly.

---

## 10. Future Improvements (Version 2 ideas)

- Two-hand detection and counting up to 10
- Sign-language (A–Z) recognition
- Custom gesture registration ("save this gesture as "OK"")
- Gesture-controlled computer: volume, brightness, scrolling
- Gesture-controlled media player (play / pause / next)
- Voice commands back to the app (speech recognition)
- ML-based gesture classification instead of hand-written rules
- GUI application with Tkinter / PyQt / Streamlit
- FPS counter and performance stats overlay
- Gesture history log + session statistics
- Advanced hand-pose recognition (rotation, angle, depth)
- Export as a standalone `.exe` with PyInstaller

---

## Project Structure

```
hand-finger-recognition/
├── main.py            # the complete application
├── requirements.txt   # dependencies
├── README.md          # this file
└── .gitignore         # keeps venv and cache out of git
```
