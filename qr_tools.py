"""Print-ready 15 x 8.8 cm Herbarium Twin labels at 300 DPI."""
import os
import re
from pathlib import Path
from urllib.parse import urlencode
import qrcode
from PIL import Image, ImageDraw, ImageFont

QR_FOLDER = Path(__file__).resolve().parent / 'qr_codes'
DPI = 300
WIDTH = round(15 / 2.54 * DPI)
HEIGHT = round(8.8 / 2.54 * DPI)


def create_qr_folder():
    QR_FOLDER.mkdir(parents=True, exist_ok=True)


def _font(size, bold=False):
    paths = ([
        '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
        'C:/Windows/Fonts/arialbd.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
    ] if bold else [
        '/System/Library/Fonts/Supplemental/Arial.ttf',
        'C:/Windows/Fonts/arial.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
    ])
    for path in paths:
        if Path(path).is_file():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _fit_single_line(draw, text, width, size, bold=False):
    for pt in range(size, 13, -1):
        font = _font(pt, bold)
        if draw.textbbox((0, 0), text, font=font)[2] <= width:
            return font, text
    font = _font(14, bold)
    while text and draw.textbbox((0, 0), text + '…', font=font)[2] > width:
        text = text[:-1]
    return font, text + ('…' if text else '')


def _wrap(draw, text, font, width):
    lines = []
    for paragraph in str(text).splitlines():
        if not paragraph.strip():
            lines.append('')
            continue
        current = ''
        for word in paragraph.split():
            candidate = f'{current} {word}'.strip()
            if draw.textbbox((0, 0), candidate, font=font)[2] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                    current = ''
                # Break an unusually long unspaced token to prevent overflow.
                for character in word:
                    if current and draw.textbbox((0, 0), current + character, font=font)[2] > width:
                        lines.append(current)
                        current = character
                    else:
                        current += character
        if current:
            lines.append(current)
    return lines


def generate_box_qr(box_title, location=None, base_url=None, barcode_identifier=None, short_ai_summary=''):
    """Generate a 15 x 8.8 cm landscape label with QR on left and summary on right.

    Subtitle is the barcode_identifier entered in Streamlit; no summary heading.

    Labels already on disk are not overwritten. The QR destination points to the
    live Streamlit box record; location is retained for API compatibility.
    """
    base_url = (base_url or os.getenv('HERBARIUM_APP_URL', '')).strip().rstrip('/')
    if not base_url.startswith(('http://', 'https://')):
        raise ValueError('Set an app URL starting with http:// or https://')

    title = str(box_title)
    subtitle = str(barcode_identifier or '').strip().upper()
    safe_id = re.sub(r'[^A-Za-z0-9_-]', '_', title)
    create_qr_folder()
    output = QR_FOLDER / f'{safe_id}_QR_15x8p8cm.jpg'
    if output.exists():
        return str(output)

    url = f"{base_url}/?{urlencode({'box_title': title})}"
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=12, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    code = qr.make_image(fill_color='black', back_color='white').convert('RGB')

    label = Image.new('RGB', (WIDTH, HEIGHT), 'white')
    draw = ImageDraw.Draw(label)
    margin = 55
    left_width = 735
    right_x = 835
    right_width = WIDTH - right_x - margin

    font, shown_title = _fit_single_line(draw, title, left_width - 30, 55, bold=True)
    bbox = draw.textbbox((0, 0), shown_title, font=font)
    draw.text((margin + (left_width - (bbox[2] - bbox[0])) / 2, 48), shown_title, font=font, fill='black')
    if subtitle:
        font, shown_subtitle = _fit_single_line(draw, subtitle, left_width - 30, 32)
        bbox = draw.textbbox((0, 0), shown_subtitle, font=font)
        draw.text((margin + (left_width - (bbox[2] - bbox[0])) / 2, 120), shown_subtitle, font=font, fill='black')

    qr_max = 685
    code = code.resize((qr_max, qr_max), Image.Resampling.NEAREST)
    label.paste(code, (margin + (left_width - qr_max) // 2, 215))

    summary = str(short_ai_summary or '').strip()
    available_height = HEIGHT - 70 - 65
    # Prefer a slightly larger summary font while still fitting the label.
    if summary:
        for size in range(43, 13, -1):
            font = _font(size)
            lines = _wrap(draw, summary, font, right_width)
            line_height = int(size * 1.38)
            if len(lines) * line_height <= available_height:
                break
        else:
            font = _font(14)
            lines = _wrap(draw, summary, font, right_width)
            line_height = 21
        max_lines = available_height // line_height
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while last and draw.textbbox((0, 0), last + '…', font=font)[2] > right_width:
                last = last[:-1]
            lines[-1] = last + '…'
        y = 70
        for line in lines:
            draw.text((right_x, y), line, font=font, fill='black')
            y += line_height
    else:
        draw.text((right_x, 70), '—', font=_font(34), fill='#777777')

    label.save(output, 'JPEG', quality=100, subsampling=0, dpi=(DPI, DPI))
    return str(output)
