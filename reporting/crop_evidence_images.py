from pathlib import Path
from PIL import Image

REPO = Path(__file__).resolve().parent.parent
SCREEN = REPO / "ebook" / "screenshots"
RAW = SCREEN / "raw"
TARGET = SCREEN / "06_PowerBI_predictive_actions.png"

def main():
    RAW.mkdir(exist_ok=True)
    if TARGET.exists() and not (RAW / TARGET.name).exists():
        TARGET.replace(RAW / TARGET.name)
    source = RAW / TARGET.name
    if not source.exists():
        raise SystemExit(f"missing source capture: {source}")
    im = Image.open(source).convert("RGB")
    if im.size != (1366, 768):
        raise SystemExit(f"unexpected screenshot size {im.size}; review crop before proceeding")
    cropped = im.crop((120, 140, 1030, 690))
    cropped.save(TARGET, format="PNG", optimize=True)
    print(f"wrote {TARGET} {cropped.size}; raw preserved at {source}")

if __name__ == "__main__":
    main()
