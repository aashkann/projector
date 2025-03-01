import os
import json
from datetime import datetime
from PyPDF2 import PdfReader
from PIL import Image
from PIL.ExifTags import TAGS

def get_file_info(file_path):
    """Extract basic file info using os.stat with a fallback for creation time."""
    stat = os.stat(file_path)
    # Use st_birthtime if available (e.g., on macOS/BSD), otherwise use st_ctime
    creation_time = getattr(stat, 'st_birthtime', stat.st_ctime)
    
    try:
        import pwd
        added_by = pwd.getpwuid(stat.st_uid).pw_name + "@example.com"
    except Exception:
        added_by = ""
    
    file_info = {
        "filename": os.path.basename(file_path),
        "file_path": file_path,
        "file_type": os.path.splitext(file_path)[1].lower(),
        "size": stat.st_size,
        "date_created": datetime.fromtimestamp(creation_time).isoformat(),
        "date_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "added_by": added_by,
        "tags": [],
        "content_summary": ""
    }
    return file_info

def get_pdf_metadata(file_path):
    """Extract PDF metadata using PyPDF2."""
    metadata = {}
    try:
        with open(file_path, "rb") as f:
            reader = PdfReader(f)
            metadata["page_count"] = len(reader.pages)
            doc_info = reader.metadata
            metadata["document_title"] = doc_info.title if doc_info and doc_info.title else ""
            metadata["author"] = doc_info.author if doc_info and doc_info.author else ""
            metadata["subject"] = doc_info.subject if doc_info and doc_info.subject else ""
            keywords = doc_info.get("/Keywords", "") if doc_info else ""
            metadata["keywords"] = [kw.strip() for kw in keywords.split(",")] if keywords else []
            metadata["producer"] = doc_info.get("/Producer", "") if doc_info else ""
            metadata["creation_date"] = doc_info.get("/CreationDate", "") if doc_info else ""
            metadata["modification_date"] = doc_info.get("/ModDate", "") if doc_info else ""
            # PDF version (if available)
            metadata["pdf_version"] = reader.pdf_header_version if hasattr(reader, "pdf_header_version") else ""
            # Additional keys not provided by PyPDF2; set defaults or leave empty
            metadata["font_usage"] = "Unknown"  # This detail isn't extracted
            metadata["color_profile"] = "sRGB"    # Default value; adjust as needed
            metadata["tagged_pdf"] = False        # Not available via PyPDF2
            metadata["encryption_status"] = "Encrypted" if reader.is_encrypted else "None"
    except Exception as e:
        metadata = {}
    return metadata

def get_image_metadata(file_path):
    """Extract basic image metadata using Pillow."""
    metadata = {}
    try:
        with Image.open(file_path) as img:
            metadata["dimensions"] = {"width": img.width, "height": img.height}
            metadata["color_mode"] = img.mode
            dpi = img.info.get("dpi", (0, 0))
            metadata["resolution"] = f"{dpi[0]} DPI" if dpi[0] else ""
            # Extract EXIF data, if available
            exif_data = img._getexif()
            if exif_data:
                exif = {}
                for tag, value in exif_data.items():
                    tag_name = TAGS.get(tag, tag)
                    exif[tag_name] = value
                metadata["exif"] = exif
            else:
                metadata["exif"] = {}
            metadata["ICC_profile"] = img.info.get("icc_profile", "")
    except Exception as e:
        metadata = {}
    return metadata

def map_folder(folder_path):
    """Recursively scan folder_path and map file details to a JSON-like structure."""
    files_list = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            full_path = os.path.join(root, file)
            file_data = get_file_info(full_path)
            ext = file_data["file_type"]
            if ext == ".pdf":
                file_data["pdf_metadata"] = get_pdf_metadata(full_path)
            elif ext in [".jpg", ".jpeg", ".png"]:
                file_data["image_metadata"] = get_image_metadata(full_path)
            files_list.append(file_data)
    return {"files": files_list}

if __name__ == "__main__":
    folder_to_read = "./project"
    mapping = map_folder(folder_to_read)
    
    output_file = "output.json"
    with open(output_file, "w", encoding="utf-8") as outfile:
        json.dump(mapping, outfile, indent=2)
    
    print(f"Mapping saved to {output_file}")
