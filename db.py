"""Herbarium Twin database: one column per Streamlit/prompt assessment field."""
import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_NAME = str(Path(__file__).resolve().parent / "herbarium_database.db")

ASSESSMENT_FIELDS = {
    "backlog_unit": ["unit_type", "count_type", "estimated_count", "exact_count"],
    "packaging_condition": ["packaging", "condition", "repacketing_needed"],
    "labels_documentation": ["label_present", "sample_barcode_present", "data_located_on", "collector", "collector_number", "collection_date", "other_documentation"],
    "geographic_information": ["geographic_data", "coverage", "countries", "regions"],
    "identification_curation": ["identification", "determination_details", "identifiers", "type_material_present"],
}
ASSESSMENT_COLUMNS = [f"{section}__{field}" for section, fields in ASSESSMENT_FIELDS.items() for field in fields]


INVENTORY_COLUMNS = [
    "box_title", "inventory_date", "current_location", "inventoried_by",
    "barcode_identifier", "image_paths", "human_notes",
]
SUMMARY_COLUMNS = ["short_ai_summary", "ai_confidence_notes"]
ALL_COLUMNS = INVENTORY_COLUMNS + ASSESSMENT_COLUMNS + SUMMARY_COLUMNS

def export_filename_stem(box_title, barcode_identifier):
    """Cross-platform-safe title + barcode filename, without path separators."""
    import re
    def clean(value):
        value = re.sub(r'[^\w -]', '_', str(value or '').strip(), flags=re.UNICODE)
        return re.sub(r'\s+', '_', value).strip(' ._')[:80]
    title = clean(box_title) or 'Untitled'
    barcode = clean(barcode_identifier) or 'NoBarcode'
    return f"{title}_{barcode}"


def get_connection():
    """
    Create a database connection.
    """
    return sqlite3.connect(DB_NAME)


def db_init():
    """Initialize a clean schema; fail rather than silently retain stale columns."""
    with get_connection() as conn:
        cols = ',\n            '.join(
            f'"{name}" TEXT' + (' PRIMARY KEY' if name == 'box_title' else '')
            for name in ALL_COLUMNS
        )
        conn.execute(f"CREATE TABLE IF NOT EXISTS boxes ({cols})")
        existing = [r[1] for r in conn.execute("PRAGMA table_info(boxes)")]
        if existing != ALL_COLUMNS:
            raise RuntimeError(
                "Database schema does not match the current assessment. "
                "Back up and replace herbarium_database.db with the supplied clean database. "
                f"Expected {len(ALL_COLUMNS)} columns; found {len(existing)}."
            )


def get_next_box_title():
    """
    Generates the next box title.
    Example:
    HB001
    HB002
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT box_title 
        FROM boxes
        ORDER BY box_title DESC
        LIMIT 1
    """)

    result = cursor.fetchone()

    conn.close()

    if result is None:
        return "HB001"

    last_id = result[0]

    try:
        number = int(last_id.replace("HB", ""))
        return f"HB{number + 1:03d}"

    except:
        return "HB001"



def box_title_exists(box_title):
    """
    Check whether a box already exists.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT 1 
        FROM boxes 
        WHERE box_title = ?
        """,
        (box_title,)
    )

    exists = cursor.fetchone() is not None

    conn.close()

    return exists



def save_box(data):
    """Store each edited prompt response once in its matching column."""
    assessment = data.get("assessment", {})
    values = {column: data.get(column, "") for column in INVENTORY_COLUMNS + SUMMARY_COLUMNS}
    selected_date = values.get("inventory_date")
    values["inventory_date"] = (
        selected_date.isoformat() if hasattr(selected_date, "isoformat")
        else str(selected_date) if selected_date else datetime.now().date().isoformat()
    )
    for section, fields in ASSESSMENT_FIELDS.items():
        section_values = assessment.get(section, {})
        for field in fields:
            value = section_values.get(field, "")
            values[f"{section}__{field}"] = (
                json.dumps(value, ensure_ascii=False) if isinstance(value, list)
                else str(value) if value is not None else ""
            )
    quoted = ", ".join(f'"{column}"' for column in ALL_COLUMNS)
    placeholders = ", ".join("?" for _ in ALL_COLUMNS)
    with get_connection() as conn:
        conn.execute(
            f"INSERT INTO boxes ({quoted}) VALUES ({placeholders})",
            [values[column] for column in ALL_COLUMNS],
        )


def get_box_dict(box_title):
    """Return a named record including the new assessment columns."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM boxes WHERE box_title = ?", (box_title,))
        row = cursor.fetchone()
        return dict(zip([c[0] for c in cursor.description], row)) if row else None


def get_all_boxes():
    """
    Retrieve all inventory records.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM boxes
        ORDER BY inventory_date DESC, box_title DESC
    """)

    rows = cursor.fetchall()

    conn.close()

    return rows



def get_box(box_title):
    """
    Retrieve one box.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM boxes
        WHERE box_title = ?
    """, (box_title,))

    row = cursor.fetchone()

    conn.close()

    return row

def export_box_json(box_title):
    """Export a complete saved herbarium box record to JSON."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM boxes WHERE box_title = ?", (box_title,))
        row = cursor.fetchone()
        columns = [description[0] for description in cursor.description]
    finally:
        conn.close()

    if row is None:
        return None

    box_data = dict(zip(columns, row))
    box_data["exported_at"] = datetime.now().isoformat(timespec="seconds")

    export_folder = Path(__file__).resolve().parent / "json_exports"
    export_folder.mkdir(parents=True, exist_ok=True)
    # Prevent path traversal if an arbitrary box title was entered.
    export_stem = export_filename_stem(box_data["box_title"], box_data.get("barcode_identifier"))
    export_path = export_folder / f"{export_stem}.json"
    with open(export_path, "w", encoding="utf-8") as file:
        json.dump(box_data, file, indent=4, ensure_ascii=False)
    return export_path
