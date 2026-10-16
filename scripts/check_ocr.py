"""Actual EasyOCR smoke test on a generated image; no database writes."""
import base64
import io
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
from PIL import Image, ImageDraw, ImageFont
from controllers.ai1_vision_ocr_controller import extract_game_data


def main():
    image = Image.new('RGB', (1000, 220), 'white')
    fonts = [Path('C:/Windows/Fonts/arialbd.ttf'),
             Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    font_path = next((p for p in fonts if p.exists()), None)
    font = ImageFont.truetype(str(font_path), 70) if font_path else ImageFont.load_default(size=70)
    ImageDraw.Draw(image).text((40, 60), 'Raz Muay Thai', fill='black', font=font)
    output = io.BytesIO()
    image.save(output, format='PNG')
    payload = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()
    result = extract_game_data(payload)
    if 'Raz Muay Thai' not in result['SkinHiem']:
        raise AssertionError('OCR text did not match: ' + result['ocr_text'])
    print('PASS: real EasyOCR detected Raz Muay Thai from generated PNG')
    print(result)


if __name__ == '__main__':
    main()
