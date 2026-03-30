import json
import time
import sys
from pathlib import Path

BANNER_JSON = Path(__file__).parent / "banner.json"

ENTER_ALT = "\033[?1049h"
EXIT_ALT  = "\033[?1049l"
HIDE_CUR  = "\033[?25l"
SHOW_CUR  = "\033[?25h"
HOME      = "\033[H"
RESET     = "\033[0m"
CLEAR_LINE = "\033[0m\r"

TEXT    = "slap slap slaaap!"
PADDING = 4


def render_frames(raw_frames: list[str]) -> list[str]:
    n_lines      = raw_frames[0].count("\n") + 1
    center_index = n_lines // 2        # índice 0-based de la línea central
    text_gap     = " " * PADDING
    clear_gap    = " " * (PADDING + len(TEXT))  # borra el área del texto en otras líneas

    rendered = []
    for frame in raw_frames:
        lines  = frame.split("\n")
        result = []
        for i, line in enumerate(lines):
            if i == center_index:
                # Escribe el banner + gap + texto en secuencia, sin saltos de cursor
                result.append(CLEAR_LINE + line + RESET + text_gap + TEXT)
            else:
                # Limpia el área del texto para no dejar residuos
                result.append(CLEAR_LINE + line + RESET + clear_gap)
        rendered.append("\n".join(result))
    return rendered


def run():
    data       = json.loads(BANNER_JSON.read_text())
    raw_frames = data["frames"]
    delay      = data.get("delay", 0.1)
    frames = render_frames(raw_frames)

    sys.stdout.write(ENTER_ALT + HIDE_CUR)
    sys.stdout.flush()

    try:
        i = 0
        while True:
            sys.stdout.write(HOME + frames[i % len(frames)])
            sys.stdout.flush()
            time.sleep(delay)
            i += 1
    finally:
        sys.stdout.write(SHOW_CUR + EXIT_ALT)
        sys.stdout.flush()


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        pass
