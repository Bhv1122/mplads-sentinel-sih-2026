"""
Provenance and Metadata Utility for MPLADS Data Acquisition
Maintains immutable records of source URLs, acquisition timestamps, HTTP status codes,
file sizes, and SHA-256 hashes for all raw datasets.
"""

import os
import json
import hashlib
import datetime
from pathlib import Path

PROVENANCE_FILE = Path(__file__).resolve().parent.parent / "documentation" / "provenance_log.json"

def calculate_sha256(filepath: str) -> str:
    """Calculate the SHA-256 checksum of a file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def record_provenance(
    source_name: str,
    source_url: str,
    raw_filepath: str,
    http_status: int = 200,
    http_method: str = "GET",
    request_payload: dict = None,
    notes: str = ""
) -> dict:
    """
    Records an entry in the provenance log.
    """
    raw_path = Path(raw_filepath)
    file_size_bytes = raw_path.stat().st_size if raw_path.exists() else 0
    file_hash = calculate_sha256(str(raw_path)) if raw_path.exists() else ""
    
    entry = {
        "timestamp_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "acquisition_date_local": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z"),
        "source_name": source_name,
        "source_url": source_url,
        "http_method": http_method,
        "http_status": http_status,
        "request_payload": request_payload,
        "relative_path": str(raw_path.relative_to(raw_path.parents[2])) if len(raw_path.parents) >= 3 else str(raw_path),
        "file_size_bytes": file_size_bytes,
        "sha256": file_hash,
        "notes": notes
    }
    
    PROVENANCE_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    records = []
    if PROVENANCE_FILE.exists():
        try:
            with open(PROVENANCE_FILE, "r", encoding="utf-8") as f:
                records = json.load(f)
        except Exception:
            records = []
            
    # Append or update
    records.append(entry)
    with open(PROVENANCE_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
        
    print(f"  [Provenance Recorded] {raw_path.name} ({file_size_bytes:,} bytes, SHA-256: {file_hash[:8]}...)")
    return entry
