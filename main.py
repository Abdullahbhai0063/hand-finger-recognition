"""
Real-Time Hand Finger Recognition & Voice Assistant
---------------------------------------------------
Detects your hand through the webcam, counts how many fingers are raised,
shows the number on screen and speaks it out loud (offline).

Press Q to quit.

Author : Muhammad Abdullah
Stack  : Python 3 + OpenCV + MediaPipe + pyttsx3
"""

import sys
import queue
import threading
import time
from collections import deque

import cv2
import mediapipe as mp

try:
    import pyttsx3
except ImportError:  # pyttsx3 missing -> app still runs, just without voice
    pyttsx3 = None


# ----------------------------------------------------------------------
# SETTINGS (change these if you want)
# ----------------------------------------------------------------------
CAMERA_INDEX = 0          # 0 = default laptop webcam, try 1 or 2 for USB cams
FRAME_WIDTH = 960
FRAME_HEIGHT = 540
STABLE_FRAMES = 3         # fewer frames = quicker voice response to finger changes
DETECTION_CONFIDENCE = 0.7
TRACKING_CONFIDENCE = 0.6
VOICE_RATE = 165          # speaking speed (words per minute)
VOICE_VOLUME = 1.0        # 0.0 to 1.0

NUMBER_WORDS = {
    0: "ZERO",
    1: "ONE",
    2: "TWO",
    3: "THREE",
    4: "FOUR",
    5: "FIVE",
    6: "SIX",
    7: "SEVEN",
    8: "EIGHT",
    9: "NINE",
    10: "TEN",
}

# MediaPipe landmark IDs
THUMB_TIP, THUMB_IP = 4, 3
FINGER_TIPS = [8, 12, 16, 20]   # index, middle, ring, pinky
FINGER_PIPS = [6, 10, 14, 18]   # the middle joint of each of those fingers
INDEX_MCP, PINKY_MCP = 5, 17    # knuckles, used to know which way the thumb points

# Colours (B, G, R)
COLOR_BG = (25, 25, 25)
COLOR_ACCENT = (0, 220, 120)
COLOR_WHITE = (245, 245, 245)
COLOR_GREY = (170, 170, 170)
COLOR_RED = (60, 60, 235)


# ----------------------------------------------------------------------
# VOICE ENGINE
# ----------------------------------------------------------------------
class VoiceEngine:
    """
    Runs pyttsx3 on a background thread.

    The engine is created once and kept alive. If it ever becomes unresponsive
    or fails during a speech call, we reset it so later detections can still
    trigger voice output without blocking the camera loop.
    """

    def __init__(self, rate=VOICE_RATE, volume=VOICE_VOLUME):
        self.available = False
        self.error_message = ""
        self._queue = queue.Queue()
        self._ready = threading.Event()
        self._engine = None
        self._rate = rate
        self._volume = volume
        self._lock = threading.Lock()

        if pyttsx3 is None:
            self.error_message = "pyttsx3 is not installed (pip install pyttsx3)."
            self._ready.set()
            return

        self._thread = threading.Thread(
            target=self._worker, daemon=True
        )
        self._thread.start()
        self._ready.wait(timeout=15)

    def _init_engine(self):
        try:
            import comtypes
            comtypes.CoInitialize()
        except Exception:
            pass

        try:
            engine = pyttsx3.init()
            voices = engine.getProperty("voices") or []
            preferred = [
                "Microsoft David Desktop - English (United States)",
                "Microsoft Zira Desktop - English (United States)",
                "Microsoft Hazel Desktop - English (Great Britain)",
            ]
            for voice_name in preferred:
                for candidate in voices:
                    if getattr(candidate, "name", "") == voice_name:
                        engine.setProperty("voice", candidate.id)
                        break
                else:
                    continue
                break

            engine.setProperty("rate", self._rate)
            engine.setProperty("volume", self._volume)
            self._engine = engine
            self.available = True
            self.error_message = ""
            return True
        except Exception as exc:
            self.error_message = f"Text-to-speech could not start: {exc}"
            self.available = False
            self._engine = None
            return False

    def _worker(self):
        startup_ok = self._init_engine()
        if startup_ok:
            try:
                if self._engine is not None:
                    self._engine.stop()
            except Exception:
                pass
            self._engine = None

        self._ready.set()

        while True:
            text = self._queue.get()
            if text is None:
                break

            try:
                # Windows SAPI can stop responding when one pyttsx3 engine is
                # reused for several runAndWait calls. Create and dispose of
                # one engine per word so every gesture gets a fresh voice.
                if not self._init_engine():
                    continue
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception as exc:
                print(f"[VOICE] Speech failed: {exc}")
                self.available = False
                try:
                    if self._engine is not None:
                        self._engine.stop()
                except Exception:
                    pass
                self._engine = None
            finally:
                try:
                    if self._engine is not None:
                        self._engine.stop()
                except Exception:
                    pass
                self._engine = None

        try:
            if self._engine is not None:
                self._engine.stop()
        except Exception:
            pass

    def say(self, text):
        """Queue a sentence for the thread that owns the speech engine."""
        if not text:
            return

        print(f"[VOICE] Queued: {text}")
        self._queue.put(text)

    def shutdown(self):
        if self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout=3)


# ----------------------------------------------------------------------
# FINGER LOGIC
# ----------------------------------------------------------------------
def count_fingers(landmarks):
    """
    Decide which fingers are raised and return (count, [t, i, m, r, p]).

    'landmarks' is the list of 21 points MediaPipe found on the hand.
    Each point has .x and .y between 0 and 1 (0,0 = top-left of the frame).

    Index / middle / ring / pinky:
        A finger is UP when its tip is HIGHER on the image than its middle
        joint. Higher on the image means a SMALLER y value.

    Thumb:
        The thumb bends sideways, not up and down, so we compare x instead.
        We first work out which side of the hand the thumb is on by looking
        at the knuckles, so it works for both the left and the right hand.
    """
    fingers = []

    # --- thumb ---
    thumb_on_right_side = landmarks[PINKY_MCP].x < landmarks[INDEX_MCP].x
    if thumb_on_right_side:
        thumb_open = landmarks[THUMB_TIP].x > landmarks[THUMB_IP].x
    else:
        thumb_open = landmarks[THUMB_TIP].x < landmarks[THUMB_IP].x
    fingers.append(1 if thumb_open else 0)

    # --- the other four fingers ---
    for tip_id, pip_id in zip(FINGER_TIPS, FINGER_PIPS):
        is_open = landmarks[tip_id].y < landmarks[pip_id].y
        fingers.append(1 if is_open else 0)

    return sum(fingers), fingers


def get_number_word(number):
    """Turn 4 into 'FOUR'. Returns '---' for anything unexpected."""
    return NUMBER_WORDS.get(number, "---")


def speak_number(voice, number):
    """Say the number out loud, e.g. 'Four'."""
    word = get_number_word(number)
    if word != "---":
        voice.say(word.capitalize())


# ----------------------------------------------------------------------
# DRAWING
# ----------------------------------------------------------------------
def draw_panel(frame, x, y, w, h, alpha=0.55, color=COLOR_BG):
    """Draw a semi-transparent rectangle so text stays readable."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + w, y + h), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def draw_interface(frame, stable_count, hand_found, voice_ok):
    h, w = frame.shape[:2]

    # Title bar
    draw_panel(frame, 0, 0, w, 58, alpha=0.6)
    cv2.putText(frame, "REAL-TIME HAND FINGER RECOGNITION", (18, 38),
                cv2.FONT_HERSHEY_SIMPLEX, 0.85, COLOR_ACCENT, 2)

    # Result panel
    draw_panel(frame, 18, 78, 330, 150, alpha=0.55)
    if hand_found and stable_count is not None:
        cv2.putText(frame, f"Detected Fingers: {stable_count}", (34, 118),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLOR_WHITE, 2)
        cv2.putText(frame, get_number_word(stable_count), (34, 198),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, COLOR_ACCENT, 4)
    else:
        cv2.putText(frame, "No hand detected", (34, 118),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.75, COLOR_RED, 2)
        cv2.putText(frame, "---", (34, 198),
                    cv2.FONT_HERSHEY_SIMPLEX, 2.0, COLOR_GREY, 4)

    # Footer
    draw_panel(frame, 0, h - 42, w, 42, alpha=0.6)
    cv2.putText(frame, "Show your fingers to the camera  |  Press Q to quit",
                (18, h - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.62, COLOR_WHITE, 1)

    if not voice_ok:
        cv2.putText(frame, "Voice OFF", (w - 150, 38),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.62, COLOR_RED, 2)


# ----------------------------------------------------------------------
# CAMERA
# ----------------------------------------------------------------------
def open_camera(index=CAMERA_INDEX):
    """Open the webcam. On Windows DirectShow starts much faster."""
    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(index)

    if not cap.isOpened():                 # fall back to the default backend
        cap = cv2.VideoCapture(index)

    if cap.isOpened():
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    return cap


# ----------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------
def main():
    print("Starting Real-Time Hand Finger Recognition...")

    # 1. Voice
    voice = VoiceEngine()
    if not voice.available:
        print("[WARNING] " + (voice.error_message or "Voice unavailable."))
        print("[WARNING] The app will keep running WITHOUT sound.")
        print("[WARNING] Fix: pip install pyttsx3   (Windows also needs comtypes)")
    else:
        print("[OK] Text-to-speech ready.")

    # 2. Camera
    cap = open_camera()
    if not cap.isOpened():
        print("\n[ERROR] Could not open the webcam.")
        print("  - Is another app (Zoom / Teams / Camera) already using it?")
        print("  - Windows: Settings > Privacy > Camera > allow desktop apps.")
        print(f"  - Try changing CAMERA_INDEX = {CAMERA_INDEX} to 1 or 2 in main.py.")
        voice.shutdown()
        return
    print("[OK] Webcam opened.")

    # 3. MediaPipe
    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils
    mp_styles = mp.solutions.drawing_styles

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=2,
        min_detection_confidence=DETECTION_CONFIDENCE,
        min_tracking_confidence=TRACKING_CONFIDENCE,
    )
    print("[OK] MediaPipe ready. Press Q in the video window to quit.\n")

    # 4. State used for stability + repeated-voice control
    recent_counts = deque(maxlen=STABLE_FRAMES)  # last few raw readings
    stable_count = None                          # the number we trust
    last_spoken_number = None                    # last number that was spoken
    last_voice_time = 0.0                        # cooldown to avoid same-number spam
    window_name = "Hand Finger Recognition"

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("[ERROR] Lost the camera feed. Exiting.")
                break

            frame = cv2.flip(frame, 1)  # mirror, so moving right looks right
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            hand_found = bool(results.multi_hand_landmarks)

            if hand_found:
                raw_count = 0
                for hand_landmarks in results.multi_hand_landmarks:
                    mp_draw.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                        mp_styles.get_default_hand_landmarks_style(),
                        mp_styles.get_default_hand_connections_style(),
                    )
                    hand_count, _ = count_fingers(hand_landmarks.landmark)
                    raw_count += hand_count

                # If the hand count flips to a different value mid-stream,
                # discard the old stable window before we try to confirm a new
                # number. This prevents the previous 1-finger result from
                # masking later detections like 2, 3, 4, or 5.
                if stable_count is not None and raw_count != stable_count:
                    recent_counts.clear()
                    stable_count = None

                recent_counts.append(raw_count)

                # Only trust a number when the last STABLE_FRAMES readings agree
                if len(recent_counts) == recent_counts.maxlen and \
                        len(set(recent_counts)) == 1:
                    stable_count = recent_counts[0]

                    # Speak only when the confirmed count changed and the same
                    # number is not being repeated too quickly. Reset the stale
                    # history when we move to a fresh hand gesture.
                    now = time.monotonic()
                    if stable_count != last_spoken_number and (now - last_voice_time) >= 0.4:
                        speak_number(voice, stable_count)
                        last_spoken_number = stable_count
                        last_voice_time = now
                        print(f"Detected: {stable_count} -> {get_number_word(stable_count)}")
                    elif stable_count == last_spoken_number:
                        # Keep the history clean so the next valid count can be
                        # recognized promptly instead of staying stuck on the
                        # most recently spoken value.
                        recent_counts.clear()
            else:
                # Hand gone: clear everything so the next hand is announced again
                recent_counts.clear()
                stable_count = None
                last_spoken_number = None
                last_voice_time = 0.0

            draw_interface(frame, stable_count, hand_found, voice.available)
            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):  # Q or Esc
                break
            # Also quit if the user clicks the window's X button
            if cv2.getWindowProperty(window_name, cv2.WND_PROP_VISIBLE) < 1:
                break

    except KeyboardInterrupt:
        print("\nStopped with Ctrl+C.")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        hands.close()
        voice.shutdown()
        print("Closed cleanly. Goodbye!")


if __name__ == "__main__":
    main()
