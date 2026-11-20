import ai_vision
import streamlit as st
import os
import json
import csv
import io
import hashlib
import socket
import re
from collections import defaultdict
from datetime import datetime, date
from PIL import Image, ImageOps
from pathlib import Path

import db
import qr_tools
import print_labels


# -----------------------------
# CSV export helpers
# -----------------------------

def records_to_csv(record_ids):
    """One box per row, one dedicated column per inventory/assessment field."""
    records = []
    for record_id in record_ids:
        saved_record = db.get_box_dict(record_id)
        if saved_record:
            records.append(saved_record)

    if not records:
        return b""

    assessment_columns = [
        f"{section}__{field}"
        for section, fields in db.ASSESSMENT_FIELDS.items()
        for field in fields
    ]
    fieldnames = db.INVENTORY_COLUMNS + assessment_columns + db.SUMMARY_COLUMNS

    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for record in records:
        row = {}
        for field in fieldnames:
            value = record.get(field)
            if isinstance(value, list):
                value = "; ".join(str(item) for item in value)
            elif isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            elif isinstance(value, str) and field in assessment_columns:
                # SQLite stores list responses as JSON strings.
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        value = "; ".join(str(item) for item in parsed)
                except (TypeError, ValueError):
                    pass
            row[field] = "" if value is None else value
        writer.writerow(row)
    return output.getvalue().encode("utf-8-sig")


# -----------------------------
# Initialization
# -----------------------------

db.db_init()

st.set_page_config(
    page_title="Herbarium Twin",
    layout="wide",
)

def display_saved_field(value):
    """Show every assessment field, including empty and missing values."""
    if value is None or value == "" or value == []:
        return "—"
    if isinstance(value, list):
        return ", ".join(map(str, value)) or "—"
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
            if isinstance(decoded, list):
                return ", ".join(map(str, decoded)) or "—"
        except (ValueError, TypeError):
            pass
    return value


# A QR scan opens the live record page on the same Streamlit server.
def show_record(box_title):
    saved = db.get_box_dict(box_title)
    if not saved:
        st.error("Box record not found.")
        return
    st.title(f"Herbarium Box {box_title}")
    st.write("Location:", saved.get("current_location", ""))
    st.write("Barcode Identifier:", saved.get("barcode_identifier") or "Not recorded")
    st.subheader("Saved assessment fields")
    for section, fields in db.ASSESSMENT_FIELDS.items():
        st.markdown(f"**{section.replace('_', ' ').title()}**")
        for field in fields:
            value = saved.get(f"{section}__{field}")
            st.write(f"{field.replace('_', ' ').title()}:", display_saved_field(value))
    st.write("Short AI Summary:", saved.get("short_ai_summary") or "")
    st.write("AI Confidence Notes:", saved.get("ai_confidence_notes") or "")
    st.write("Human Notes:", saved.get("human_notes") or "")
    image_paths = saved.get("image_paths") or ""
    for item in image_paths.split(","):
        if not item.strip():
            continue
        image_file = Path(__file__).resolve().parent / "captured_images" / Path(item.strip().replace("\\", "/")).name
        if image_file.is_file():
            with Image.open(image_file) as im:
                st.image(ImageOps.exif_transpose(im), use_container_width=True)
    export_path = db.export_box_json(box_title)
    if export_path:
        st.download_button("Download JSON", export_path.read_bytes(),
                           file_name=export_path.name, mime="application/json")

scanned_box_title = st.query_params.get("box_title") or st.query_params.get("box")
if scanned_box_title:
    show_record(scanned_box_title)
    st.stop()

st.title("Herbarium Twin")
st.write("AI-assisted herbarium inventory system")

def detect_network_url():
    """Best-effort local-network address on Windows, macOS, and Linux."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))  # No packet is sent.
            ip = sock.getsockname()[0]
        if ip and not ip.startswith("127."):
            return f"http://{ip}:8501"
    except OSError:
        pass
    return ""


# Local-network link for opening this application on an iPhone.
st.subheader("Access Herbarium Twin on mobile phone")
app_url = st.text_input(
    "Local Network URL",
    value=os.getenv("HERBARIUM_APP_URL", "") or detect_network_url(),
    placeholder="http://192.168.1.42:8501",
    help="Use the Network URL shown in the Streamlit terminal on your computer.",
)
app_url = app_url.strip()
if not app_url.startswith(("http://", "https://")):
    st.caption("Enter your computer's Streamlit Network URL to access the app on your phone.")
st.caption("Your phone must be able to reach the computer running Streamlit on the same network or hotspot.")


# -----------------------------
# Tabs
# -----------------------------

tab1, tab2 = st.tabs(
    [
        ":package: New Inventory",
        ":mag_right: Existing Collection",
    ]
)


# ==================================================
# TAB 1: NEW INVENTORY
# ==================================================

with tab1:
    st.header("Create Herbarium Box Record")

    # -----------------------------
    # Basic information
    # -----------------------------

    entry_version = st.session_state.get("new_entry_version", 0)
    if "next_box_title_value" not in st.session_state:
        st.session_state["next_box_title_value"] = db.get_next_box_title()
    box_title = st.text_input(
        "Box Title",
        value=st.session_state["next_box_title_value"],
        key=f"box_title_{entry_version}",
    )

    inventory_date_value = st.date_input(
        "Inventory Date",
        value=date.today(),
        key=f"inventory_date_input_{entry_version}",
    )

    location = st.text_input(
        "Current Location *",
        placeholder="Example: Room 204 Shelf B",
        key=f"current_location_{entry_version}",
    )

    inventor = st.text_input("Inventoried By", key=f"inventor_{entry_version}")

    # -----------------------------
    # Barcode Identification
    # -----------------------------
    st.subheader("Barcode Identification")
    barcode_identifier = st.text_input(
        "Barcode Identifier",
        key=f"barcode_identification_{entry_version}",
        placeholder="Example: C2110528F",
        help="Enter the barcode identifier printed beneath the barcode.",
    ).strip().upper()

    # -----------------------------
    # Image upload
    # -----------------------------

    st.subheader("Upload Images")

    uploaded_files = st.file_uploader(
        "Upload herbarium box photos",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"uploaded_files_{entry_version}",
    )

    image_paths = []
    if uploaded_files:
        image_dir = Path(__file__).resolve().parent / "captured_images"
        image_dir.mkdir(parents=True, exist_ok=True)
        for i, file in enumerate(uploaded_files):
            with Image.open(file) as source:
                img = ImageOps.exif_transpose(source).convert("RGB")
                export_stem = db.export_filename_stem(box_title, barcode_identifier)
                temp_path = image_dir / f"{export_stem}_{i + 1}.jpg"
                img.save(temp_path)
            image_paths.append(str(temp_path))
            st.image(img, caption=file.name, width=250)

    # Re-analyze when the box title or uploaded image contents change.
    upload_signature = (
        box_title,
        tuple((f.name, hashlib.sha256(f.getvalue()).hexdigest()) for f in uploaded_files or []),
    )
    if st.session_state.get("ai_upload_signature") != upload_signature:
        st.session_state.ai_upload_signature = upload_signature
        st.session_state.ai_results = {}
        st.session_state.ai_edit_version = st.session_state.get("ai_edit_version", 0) + 1

    if image_paths and st.button("Analyze images with AI", type="primary"):
        with st.spinner("AI analyzing herbarium images..."):
            try:
                result = ai_vision.analyze_box_images(image_paths)
                st.session_state.ai_results = result
                st.session_state.ai_edit_version += 1
            except Exception as error:
                st.error(f"AI failed: {error}")

    st.subheader("AI-generated assessment (editable)")
    st.caption("Review and correct the AI's responses before saving. One field per prompt response; list fields accept one entry per line.")

    # Use the exact database/prompt field map; no duplicated schema in Streamlit.
    assessment_schema = db.ASSESSMENT_FIELDS
    list_fields = {
        "packaging_condition": {"packaging", "condition"},
        "labels_documentation": {"data_located_on", "other_documentation"},
        "geographic_information": {"countries", "regions"},
        "identification_curation": {"determination_details"},
    }
    ai = st.session_state.get("ai_results", {})
    version = st.session_state.get("ai_edit_version", 0)
    edited_assessment = {}
    for section, fields in assessment_schema.items():
        with st.expander(section.replace("_", " ").title(), expanded=True):
            section_values = ai.get(section, {})
            if not isinstance(section_values, dict):
                section_values = {}
            edited_assessment[section] = {}
            for field in fields:
                is_list = field in list_fields.get(section, set())
                initial = section_values.get(field, [] if is_list else "")
                if is_list:
                    if not isinstance(initial, list):
                        initial = [str(initial)] if initial else []
                    initial_text = "\n".join(str(v) for v in initial)
                else:
                    initial_text = str(initial) if initial is not None else ""
                # All assessment fields are editable text areas, including
                # packaging and fields previously shown as dropdowns.
                if section == "packaging_condition" and field == "packaging":
                    field_label = "Packaging"
                    field_help = (
                        "Enter packaging types, one per line. Options include "
                        "Herbarium sheet and Unpackaged, alongside existing types."
                    )
                else:
                    field_label = field.replace("_", " ").title()
                    field_help = None
                edited_text = st.text_area(
                    field_label,
                    value=initial_text,
                    key=f"assessment_{version}_{section}_{field}",
                    height=75,
                    help=field_help,
                )
                edited_assessment[section][field] = (
                    [line.strip() for line in edited_text.splitlines() if line.strip()]
                    if is_list else edited_text.strip()
                )

    short_ai_summary = st.text_area(
        "Short AI Summary",
        value=str(ai.get("short_ai_summary", "")),
        key=f"assessment_{version}_short_summary",
        height=100,
    )

    confidence = st.text_area(
        "AI Confidence Notes",
        value=str(ai.get("ai_confidence_notes", "")),
        key=f"assessment_{version}_confidence",
    )
    human_notes = st.text_area("Human Notes", key=f"human_notes_{entry_version}_{box_title}")

    # -----------------------------
    # Save
    # -----------------------------

    if st.button(":floppy_disk: Save Herbarium Box"):
        if not location.strip():
            st.error("Current location is required.")
        elif db.box_title_exists(box_title):
            st.error("Box Title already exists.")
        else:
            record = {
                "box_title": box_title,
                "barcode_identifier": barcode_identifier,
                "inventory_date": inventory_date_value.isoformat(),
                "current_location": location,
                "inventoried_by": inventor,
                "image_paths": ",".join(image_paths),
                "human_notes": human_notes,
                "short_ai_summary": short_ai_summary,
                "ai_confidence_notes": confidence,
                "assessment": edited_assessment,
            }

            try:
                db.save_box(record)
                if not db.box_title_exists(box_title):
                    raise RuntimeError("The saved box could not be found in the database.")
            except Exception as error:
                st.error(f"Database save failed: {error}")
                st.stop()
            st.success(f"Saved {box_title} to the database. Your assessment is preserved above.")
            try:
                json_path = db.export_box_json(box_title)
            except Exception as error:
                json_path = None
                st.warning(f"Box saved, but JSON export failed: {error}")
            # Create exactly one saved QR label when the box is first saved.
            # Existing Collection only reads this file; it never regenerates it.
            qr_url = app_url if app_url.startswith(("http://", "https://")) else "http://localhost:8501"
            try:
                qr_path = Path(qr_tools.generate_box_qr(box_title, location, base_url=qr_url, barcode_identifier=barcode_identifier, short_ai_summary=short_ai_summary))
                st.image(str(qr_path), caption=f"Saved QR label — {box_title}", width=150)
                st.download_button(
                    "Download Box QR Code (.jpg)",
                    data=qr_path.read_bytes(),
                    file_name=qr_path.name,
                    mime="image/jpeg",
                    key=f"new_qr_{box_title}",
                )
                if qr_url == "http://localhost:8501":
                    st.warning("QR created, but its link uses localhost and will not open on another device. Enter this computer's Network URL at the top before saving future boxes.")
            except Exception as error:
                st.error(f"Box saved, but QR label generation failed: {error}")
            if json_path is not None:
                st.download_button(
                    "Download Box JSON",
                    data=json_path.read_bytes(),
                    file_name=json_path.name,
                    mime="application/json",
                    key=f"new_json_{box_title}",
                )


# ==================================================
# TAB 2: EXISTING COLLECTION
# ==================================================

with tab2:
    st.header("Inventory Database")

    boxes = db.get_all_boxes()

    # Print existing saved labels three per US Letter page, without regenerating QR codes.
    label_dir = Path(__file__).resolve().parent / "qr_codes"
    available_labels = {}
    for box in boxes:
        title = str(box[0])
        safe_title = re.sub(r"[^A-Za-z0-9_-]", "_", title)
        label_file = label_dir / f"{safe_title}_QR_15x8p8cm.jpg"
        if label_file.is_file():
            available_labels[title] = label_file

    if available_labels:
        st.subheader("Print QR Labels — 3 per page")
        st.caption("Choose saved labels to print on US Letter paper. Three 15 × 8.8 cm labels fit per sheet. Print at Actual Size / 100%.")
        selected_labels = st.multiselect(
            "Select boxes for printing",
            options=list(available_labels),
            key="print_label_selection",
        )
        if selected_labels:
            try:
                print_pdf = print_labels.make_print_pdf(
                    [available_labels[title] for title in selected_labels]
                )
                st.download_button(
                    "🖨️ Print QR Labels (PDF)",
                    data=print_pdf,
                    file_name="herbarium_qr_labels_3_per_page.pdf",
                    mime="application/pdf",
                    key="print_three_labels_pdf",
                )
                st.caption(f"{len(selected_labels)} label(s) · {(len(selected_labels) + 2) // 3} sheet(s). Open the downloaded PDF and choose Print.")
            except (OSError, ValueError) as error:
                st.error(f"Unable to prepare printable labels: {error}")
    elif boxes:
        st.caption("No saved 15 × 8.8 cm QR labels are available for printing yet.")

    if boxes:
        st.download_button(
            label="Download Entire Collection (.csv)",
            data=records_to_csv([box[0] for box in boxes]),
            file_name="herbarium_twin_collection.csv",
            mime="text/csv",
            key="download_collection_csv",
        )
        st.caption("One row per box, with individual saved assessment fields as columns.")

    if not boxes:
        st.info("No boxes inventoried yet.")
    else:
        # Group by the date recorded when each inventory entry was created.
        # Do not substitute today's date for records lacking a saved date.
        def inventory_date(saved_record):
            if not saved_record:
                return None
            for field in ("inventory_date",):
                value = saved_record.get(field)
                if not value:
                    continue
                if isinstance(value, datetime):
                    return value.date()
                if isinstance(value, date):
                    return value
                value = str(value).strip()
                try:
                    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
                except ValueError:
                    pass
                for fmt in ("%m/%d/%Y", "%Y/%m/%d", "%B %d, %Y", "%b %d, %Y"):
                    try:
                        return datetime.strptime(value, fmt).date()
                    except ValueError:
                        continue
            return None

        dated_boxes = defaultdict(list)
        for box in boxes:
            dated_boxes[inventory_date(db.get_box_dict(box[0]))].append(box)

        for group_date in sorted(dated_boxes, key=lambda d: (d is not None, d or date.min), reverse=True):
            heading = group_date.strftime("%B %d, %Y").replace(" 0", " ") if group_date else "Date not recorded"
            st.subheader(f":calendar: {heading}")
            # Export only the inventory records belonging to this date.
            date_file_label = group_date.isoformat() if group_date else "date_not_recorded"
            st.download_button(
                label=f"Download {heading} Inventory (.csv)",
                data=records_to_csv([box[0] for box in dated_boxes[group_date]]),
                file_name=f"herbarium_inventory_{date_file_label}.csv",
                mime="text/csv",
                key=f"download_date_csv_{date_file_label}",
            )
            for box in dated_boxes[group_date]:
                with st.expander(f":package: {box[0]}"):
                    st.write("Location:", (db.get_box_dict(box[0]) or {}).get("current_location", ""))
                    st.write("Barcode Identifier:", (db.get_box_dict(box[0]) or {}).get("barcode_identifier") or "Not recorded")
                    st.subheader("Saved assessment fields")
                    saved = db.get_box_dict(box[0])
                    for section, fields in db.ASSESSMENT_FIELDS.items():
                        st.markdown(f"**{section.replace('_', ' ').title()}**")
                        for field in fields:
                            raw = saved.get(f"{section}__{field}") if saved else None
                            st.write(f"{field.replace('_', ' ').title()}:", display_saved_field(raw))
                    st.write("Short AI Summary:", saved.get("short_ai_summary") or "")
                    st.write("AI Confidence Notes:", saved.get("ai_confidence_notes") or "")
                    st.write("Human Notes:", saved.get("human_notes") or "")
                    if st.button("Export JSON", key=f"export_{box[0]}"):
                        export_path = db.export_box_json(box[0])
                        if export_path is None:
                            st.error("Box record not found.")
                        else:
                            st.session_state[f"export_path_{box[0]}"] = str(export_path)
                    saved_export = st.session_state.get(f"export_path_{box[0]}")
                    if saved_export and Path(saved_export).exists():
                        st.download_button(
                            "Download JSON",
                            data=Path(saved_export).read_bytes(),
                            file_name=Path(saved_export).name,
                            mime="application/json",
                            key=f"download_{box[0]}",
                        )

                    st.download_button(
                        label="Download Box CSV",
                        data=records_to_csv([box[0]]),
                        file_name=f"{box[0]}_inventory.csv",
                        mime="text/csv",
                        key=f"download_csv_{box[0]}",
                    )

                    # Download a QR label already saved on the Streamlit host computer.
                    # No QR code is generated or changed by viewing this record.
                    st.subheader("Box QR Code")
                    qr_folder = Path(__file__).resolve().parent / "qr_codes"
                    # Restrict the filename to a single safe path component.
                    safe_box_title = "".join(
                        c if c.isalnum() or c in "-_" else "_" for c in str(box[0])
                    )
                    qr_filename = f"{safe_box_title}_QR_15x8p8cm.jpg"
                    qr_path = qr_folder / qr_filename

                    if qr_path.is_file():
                        st.image(str(qr_path), caption=f"QR Code — {box[0]}", width=150)
                        st.download_button(
                            label="Download QR Code (.jpg)",
                            data=qr_path.read_bytes(),
                            file_name=qr_filename,
                            mime="image/jpeg",
                            key=f"download_qr_{box[0]}",
                        )
                    else:
                        st.info(f"No saved QR code found for {box[0]} in qr_codes.")

                    # Display associated images
                    if saved and saved.get("image_paths"):
                        image_paths = saved["image_paths"].split(",")
                        columns = st.columns(3)

                        for i, image_path in enumerate(image_paths):
                            # Clean image path and extract filename
                            image_path = image_path.strip().replace("\\", "/")
                            image_filename = Path(image_path).name

                            # Find image inside captured_images folder
                            full_path = (
                                Path(__file__).resolve().parent
                                / "captured_images"
                                / image_filename
                            )

                            if full_path.exists():
                                with Image.open(full_path) as img:
                                    # Correct image orientation
                                    img = ImageOps.exif_transpose(img)

                                    with columns[i % 3]:
                                        st.image(img, use_container_width=True)
                                        st.download_button(
                                            "Download Image (.jpg)",
                                            data=full_path.read_bytes(),
                                            file_name=full_path.name,
                                            mime="image/jpeg",
                                            key=f"download_image_{box[0]}_{i}",
                                        )
                            else:
                                st.warning(f"Image not found: {image_filename}")

# -----------------------------
# Refresh Page
# -----------------------------
st.divider()
if st.button("🔄 Refresh for next box entry", use_container_width=True):
    # New widget keys create empty inputs, including the file uploader.
    # Existing saved records, images, and QR labels remain untouched.
    st.session_state["new_entry_version"] = st.session_state.get("new_entry_version", 0) + 1
    st.session_state["next_box_title_value"] = db.get_next_box_title()
    st.session_state["ai_results"] = {}
    st.session_state["ai_upload_signature"] = None
    st.session_state["ai_edit_version"] = st.session_state.get("ai_edit_version", 0) + 1
    st.rerun()

