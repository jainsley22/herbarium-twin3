"""Assemble existing Herbarium Twin JPEG labels into three-per-page print PDFs."""
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageDraw

DPI = 300
LETTER_WIDTH = round(8.5 * DPI)
LETTER_HEIGHT = round(11 * DPI)
LABEL_WIDTH = round(15 / 2.54 * DPI)
LABEL_HEIGHT = round(8.8 / 2.54 * DPI)


def make_print_pdf(label_paths):
    """Return PDF bytes; three centered, original-size labels per US Letter page.

    Uses the saved JPEG files only; no AI calls or label regeneration.
    """
    paths = [Path(path) for path in label_paths]
    if not paths:
        raise ValueError('Select at least one saved QR label.')
    pages = []
    for start in range(0, len(paths), 3):
        sheet = Image.new('RGB', (LETTER_WIDTH, LETTER_HEIGHT), 'white')
        # Three labels occupy 26.4 cm of a 27.94 cm page.
        top_margin = (LETTER_HEIGHT - 3 * LABEL_HEIGHT) // 2
        left_margin = (LETTER_WIDTH - LABEL_WIDTH) // 2
        for slot, path in enumerate(paths[start:start + 3]):
            with Image.open(path) as source:
                label = source.convert('RGB')
                if label.size != (LABEL_WIDTH, LABEL_HEIGHT):
                    raise ValueError(f'{path.name} is not a 15 x 8.8 cm label at 300 DPI.')
                sheet.paste(label, (left_margin, top_margin + slot * LABEL_HEIGHT))
        pages.append(sheet)
    output = BytesIO()
    pages[0].save(output, format='PDF', save_all=True, append_images=pages[1:], resolution=DPI)
    return output.getvalue()
