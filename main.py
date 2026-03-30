import sys
import signal
import time
import random
import queue
import threading
from pathlib import Path

import numpy as np
import sounddevice as sd

SOUNDS_DIR = Path(__file__).parent / "sounds"
SAMPLE_RATE = 44100
BLOCK_SIZE = 512       # ~11.6 ms — more stable energy estimate
COOLDOWN = 0.8         # seconds between slaps

# Onset ratio thresholds per sensitivity level.
# Compares current block energy vs slow background average.
# A physical slap spikes 20-100x above background; sustained noise stays ~1x.
THRESHOLDS = {"low": 200.0, "medium": 100.0, "high": 50.0}

# Minimum absolute RMS² — ignores ratio spikes in near-silence
MIN_ENERGY = 2e-3

IS_MACOS = sys.platform == "darwin"



class SlapDetector:
    def __init__(self, on_slap):
        self._on_slap = on_slap
        self._background = None
        self._alpha = 0.02
        self._last_slap = 0.0
        self.threshold = THRESHOLDS["medium"]
        self._stream = None

    def start(self):
        def callback(indata, _frames, _time, _status):
            energy = float(np.mean(indata ** 2))

            if self._background is None:
                self._background = max(energy, 1e-10)
                return

            bg = self._background
            ratio = energy / bg if bg > 1e-10 else 0.0

            if ratio < self.threshold:
                a = self._alpha
                self._background = (1 - a) * self._background + a * energy

            now = time.time()
            if (energy > MIN_ENERGY and ratio > self.threshold
                    and (now - self._last_slap) > COOLDOWN):
                self._last_slap = now
                self._on_slap(ratio)

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=BLOCK_SIZE,
            channels=1,
            dtype="float32",
            callback=callback,
        )
        self._stream.start()

    def stop(self):
        if self._stream:
            self._stream.stop()
            self._stream.close()


if IS_MACOS:
    import rumps
    from AppKit import NSSound

    class SlapApp(rumps.App):
        def __init__(self):
            super().__init__("🥵 0", quit_button="Quit")
            self.slap_menu_item = rumps.MenuItem("Slaps: 0", callback=None)
            self.menu = [
                self.slap_menu_item,
                rumps.separator,
                rumps.MenuItem("Sensitivity", callback=None),
                rumps.MenuItem("  Low",    callback=self.set_low),
                rumps.MenuItem("  Medium", callback=self.set_medium),
                rumps.MenuItem("  High",   callback=self.set_high),
                rumps.separator,
            ]
            self.slap_count = 0
            self._slap_queue = queue.Queue()
            self.sounds = self._load_sounds()
            self._last_sound = None

            self._detector = SlapDetector(on_slap=lambda r: self._slap_queue.put(r))
            self._detector.start()
            Path("/tmp/slap_ready").touch()

        def _load_sounds(self):
            if not SOUNDS_DIR.exists():
                return []
            files = list(SOUNDS_DIR.glob("*.wav")) + list(SOUNDS_DIR.glob("*.mp3"))
            return [str(f) for f in files]

        @rumps.timer(0.05)
        def _tick(self, _):
            try:
                ratio = self._slap_queue.get_nowait()
            except queue.Empty:
                return

            self.slap_count += 1
            self.title = f"🥵 {self.slap_count}"
            self.slap_menu_item.title = f"Slaps: {self.slap_count}"

            if self.sounds:
                volume = min(1.0, ratio / (self._detector.threshold * 3))
                choices = [s for s in self.sounds if s != self._last_sound] or self.sounds
                path = random.choice(choices)
                self._last_sound = path
                sound = NSSound.alloc().initWithContentsOfFile_byReference_(path, True)
                sound.setVolume_(volume)
                sound.play()

        def set_low(self, _):    self._detector.threshold = THRESHOLDS["low"]
        def set_medium(self, _): self._detector.threshold = THRESHOLDS["medium"]
        def set_high(self, _):   self._detector.threshold = THRESHOLDS["high"]

    def run():
        SlapApp().run()


else:
    import os
    os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
    import pygame
    import pystray
    from PIL import Image, ImageDraw

    def _make_icon(count: int) -> Image.Image:
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse([4, 4, 60, 60], fill=(220, 80, 60))
        draw.text((10, 18), str(count)[:3], fill="white")
        return img

    class SlapApp:
        def __init__(self):
            self.slap_count = 0
            self._slap_queue = queue.Queue()
            self.sounds = self._load_sounds()
            self._last_sound = None

            pygame.mixer.init()

            self._detector = SlapDetector(on_slap=lambda r: self._slap_queue.put(r))

            self._icon = pystray.Icon(
                "slap",
                _make_icon(0),
                "Slap - 0 slaps",
                menu=pystray.Menu(
                    pystray.MenuItem("Slaps: 0", None, enabled=False),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Sensitivity", pystray.Menu(
                        pystray.MenuItem("Low",    lambda _i, _it: self._set("low")),
                        pystray.MenuItem("Medium", lambda _i, _it: self._set("medium")),
                        pystray.MenuItem("High",   lambda _i, _it: self._set("high")),
                    )),
                    pystray.Menu.SEPARATOR,
                    pystray.MenuItem("Quit", lambda: self._quit()),
                ),
            )

        def _load_sounds(self):
            if not SOUNDS_DIR.exists():
                return []
            files = list(SOUNDS_DIR.glob("*.wav")) + list(SOUNDS_DIR.glob("*.mp3"))
            return [str(f) for f in files]

        def _set(self, level: str):
            self._detector.threshold = THRESHOLDS[level]

        def _quit(self):
            self._detector.stop()
            self._icon.stop()

        def _tick_loop(self):
            while True:
                try:
                    ratio = self._slap_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                self.slap_count += 1
                self._icon.icon = _make_icon(self.slap_count)
                self._icon.title = f"Slap - {self.slap_count} slaps"

                if self.sounds:
                    volume = min(1.0, ratio / (self._detector.threshold * 3))
                    choices = [s for s in self.sounds if s != self._last_sound] or self.sounds
                    path = random.choice(choices)
                    self._last_sound = path
                    sound = pygame.mixer.Sound(path)
                    sound.set_volume(volume)
                    sound.play()

        def run(self):
            self._detector.start()
            Path("/tmp/slap_ready").touch()
            tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
            tick_thread.start()

            def handle_signal(sig, frame):
                self._quit()

            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)

            self._icon.run()

    def run():
        SlapApp().run()


if __name__ == "__main__":
    run()
