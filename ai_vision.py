
import json
import os
import mimetypes
import traceback

from google import genai
from google.genai import types


# --------------------------------------------------
# Gemini API configuration
# --------------------------------------------------

def get_gemini_client():
    """Create Gemini client with a validated API key."""

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY is missing. "
            "Check your environment variables."
        )

    # Remove accidental whitespace.
    api_key = api_key.strip()

    # Remove accidental surrounding quotation marks.
    api_key = api_key.strip("\"'\u201c\u201d")

    # API keys should contain ASCII characters only.
    try:
        api_key.encode("ascii")
    except UnicodeEncodeError:
        raise ValueError(
            "GEMINI_API_KEY contains non-ASCII characters. "
            "Copy the key again from Google AI Studio."
        )

    return genai.Client(api_key=api_key)


# --------------------------------------------------
# Image loading
# --------------------------------------------------

def load_image_bytes(image_path):
    """Read raw image bytes from disk."""

    with open(image_path, "rb") as image_file:
        return image_file.read()


# --------------------------------------------------
# AI image analysis
# --------------------------------------------------

def analyze_box_images(image_paths):
    """
    Analyze herbarium box images using Gemini.

    Returns:
        Dictionary of AI-generated metadata.
    """

    if not image_paths:
        raise ValueError(
            "No images were provided for analysis."
        )

    image_parts = []

    for path in image_paths:

        image_bytes = load_image_bytes(path)

        mime_type, _ = mimetypes.guess_type(path)

        if mime_type not in [
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/heic",
            "image/heif",
        ]:
            raise ValueError(
                f"Unsupported image type: {path}"
            )

        image_parts.append(
            types.Part.from_bytes(
                data=image_bytes,
                mime_type=mime_type,
            )
        )

    # --------------------------------------------------
    # Herbarium assessment prompt
    # --------------------------------------------------

    prompt = """
You are assisting researchers at a natural history museum with the rapid assessment of a herbarium backlog.
Analyze the provided photographs of a herbarium backlog unit and return ONLY valid JSON matching this exact structure:

{
  "backlog_unit": {
    "unit_type": "Single specimen/packet",
    "count_type": "Packets",
    "estimated_count": "1-9",
    "exact_count": ""
  },
  "packaging_condition": {
    "packaging": ["Brown paper bag"],
    "condition": ["Good"],
    "repacketing_needed": "No"
  },
  "labels_documentation": {
    "label_present": "Yes",
    "sample_barcode_present": "No",
    "data_located_on": ["Printed label"],
    "collector": "Present",
    "collector_number": "Present",
    "collection_date": "Complete",
    "other_documentation": []
  },
  "geographic_information": {
    "geographic_data": "Detailed",
    "coverage": "Single locality",
    "countries": [],
    "regions": []
  },
  "identification_curation": {
    "identification": "Species",
    "determination_details": [],
    "identifiers": "Neither",
    "type_material_present": "Maybe"
  },
  "short_ai_summary": "Concise summary including any legible collector name, geographic information, estimated specimen quantity, and taxonomic identifications.",
  "ai_confidence_notes": "All sections successfully parsed."
}

Rules:
- Fill in the JSON fields based on visible evidence in the images.
- For packaging_condition.packaging, select applicable packaging types including "Herbarium Sheet" or "Unpackaged" when visible. Use an array of labels; do not infer packaging not shown.
- For labels_documentation.sample_barcode_present, return exactly "Yes" or "No" based on whether a sample barcode is visible. Do not confuse this with the manually entered box Barcode Identifier.
- For identification_curation.type_material_present, return exactly "Yes", "No", or "Maybe". Use "Yes" only with clear evidence of type status, "No" only when clearly ruled out, and otherwise "Maybe".
- Write short_ai_summary as 1-3 concise, factual sentences, prioritizing these details in order: (1) collector name(s) transcribed from legible labels, (2) any available geographic information such as country, region, locality, or coordinates, (3) estimated quantity of specimens or packets, and (4) specimen identification, including species, genus, and family names when legible.
- Use the actual collector name and taxonomic names from labels, not just indicators such as "Present" or "Species". Preserve scientific spelling as shown; do not guess illegible names or infer a family from a genus.
- For quantity, use the visually supported approximate count or range; distinguish packets from specimens when possible, and do not imply that obscured material was counted exactly.
- Include all four categories when evidence is available. If one is not visible or legible, omit it from the summary rather than inventing it. Keep the text compact enough to print on a 15 cm × 8.8 cm QR label, and avoid repetitive packaging descriptions unless relevant.
- If information is not visible, use safe defaults like "Uncertain", "Absent", or empty lists [].
- Return ONLY raw JSON with no markdown block formatting if possible.
"""

    # --------------------------------------------------
    # Gemini request
    # --------------------------------------------------

    try:

        client = get_gemini_client()

        response = client.models.generate_content(
            model="gemini-3.5-flash-lite",
            contents=[prompt, *image_parts],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty response."
            )

        result_text = response.text.strip()

    except Exception as error:

        print(
            "Gemini analysis failed:",
            repr(error)
        )

        traceback.print_exc()

        raise RuntimeError(
            f"Gemini analysis failed: {error}"
        ) from error

    # --------------------------------------------------
    # Parse JSON response
    # --------------------------------------------------

    try:

        result = json.loads(result_text)

        if not isinstance(result, dict):
            raise ValueError(
                "Gemini returned JSON that is not an object."
            )

    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("AI response was not valid JSON. Please retry analysis.") from error

    expected = {
        "backlog_unit", "packaging_condition", "labels_documentation",
        "geographic_information", "identification_curation",
        "short_ai_summary", "ai_confidence_notes",
    }
    missing = expected - result.keys()
    if missing or any(not isinstance(result.get(k), dict) for k in expected - {"ai_confidence_notes", "short_ai_summary"}):
        raise ValueError(f"AI response does not match the requested assessment structure: {sorted(missing)}")

    return result
