from __future__ import annotations

import argparse
import csv
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"


DOWNLOADS = [
    ("sc_ports", "chsgatetransactions.csv", "https://scspa.com/wp-content/uploads/chsgatetransactions.csv"),
    ("sc_ports", "chsturntimes.csv", "https://scspa.com/wp-content/uploads/chsturntimes.csv"),
    ("sc_ports", "chscraneproductivity.csv", "https://scspa.com/wp-content/uploads/chscraneproductivity.csv"),
    ("sc_ports", "chsvesselcalls.csv", "https://scspa.com/wp-content/uploads/chsvesselcalls.csv"),
    ("sc_ports", "gatemissions.csv", "https://scspa.com/wp-content/uploads/gatemissions.csv"),
    ("sc_ports", "lastweeksturntimes.csv", "https://scspa.com/wp-content/uploads/lastweeksturntimes.csv"),
    ("sc_ports", "piermoves.csv", "https://scspa.com/wp-content/uploads/piermoves.csv"),
    (
        "port_virginia_weekly_metrics",
        "POV-Weekly-Metrics-07-09-2023.pdf",
        "https://operations.portofvirginia.com/wp-content/uploads/2023/07/POV-Weekly-Metrics-07-09-2023.pdf",
    ),
    (
        "port_virginia_weekly_metrics",
        "POV-Weekly-Metrics-08-27-2023.pdf",
        "https://operations.portofvirginia.com/wp-content/uploads/2023/08/POV-Weekly-Metrics-08-27-2023.pdf",
    ),
    (
        "port_virginia_weekly_metrics",
        "POV-Weekly-Metrics-07-12-2026.pdf",
        "https://operations.portofvirginia.com/wp-content/uploads/2026/07/POV-Weekly-Metrics-07-12-2026.pdf",
    ),
    (
        "port_houston_terminal_reports",
        "Terminal-Status-Report-06.08.2026.pdf",
        "https://porthouston.com/wp-content/uploads/2026/06/Terminal-Status-Report-06.08.2026.pdf",
    ),
    (
        "port_houston_terminal_reports",
        "Terminal-Status-Report-06.22.2026.pdf",
        "https://porthouston.com/wp-content/uploads/2026/06/Terminal-Status-Report-06.22.2026.pdf",
    ),
    (
        "port_houston_terminal_reports",
        "Terminal-Status-Report-07.13.2026.pdf",
        "https://porthouston.com/wp-content/uploads/2026/07/Terminal-Status-Report-07.13.2026.pdf",
    ),
    (
        "mendeley_tas_tours",
        "82zzdkrxx8-v1.zip",
        "https://data.mendeley.com/public-api/zip/82zzdkrxx8/download/1",
    ),
    (
        "mendeley_capacity_management",
        "2b646hgkt7-v1.zip",
        "https://data.mendeley.com/public-api/zip/2b646hgkt7/download/1",
    ),
    (
        "mendeley_dwelling_time",
        "yvp2b4rtp3-v1.zip",
        "https://data.mendeley.com/public-api/zip/yvp2b4rtp3/download/1",
    ),
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def signature_ok(path: Path) -> bool:
    head = path.read_bytes()[:8]
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return head.startswith(b"%PDF-")
    if suffix == ".zip":
        return head.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))
    if suffix == ".csv":
        return path.stat().st_size > 0 and b"<html" not in head.lower()
    return path.stat().st_size > 0


def download(group: str, filename: str, url: str, overwrite: bool) -> dict[str, object]:
    target_dir = RAW / group
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / filename
    timestamp = datetime.now(timezone.utc).isoformat()
    if target.exists() and not overwrite:
        return {
            "group": group,
            "filename": filename,
            "source_url": url,
            "status": "existing_verified" if signature_ok(target) else "existing_invalid",
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "downloaded_at_utc": timestamp,
            "content_type": "",
            "error": "",
        }

    temporary = target.with_suffix(target.suffix + ".part")
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (research reproducibility audit)"})
    try:
        with urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                output.write(block)
            content_type = response.headers.get("Content-Type", "")
        if not signature_ok(temporary):
            raise ValueError("downloaded file failed its PDF/ZIP/CSV signature check")
        temporary.replace(target)
        return {
            "group": group,
            "filename": filename,
            "source_url": url,
            "status": "downloaded",
            "bytes": target.stat().st_size,
            "sha256": sha256(target),
            "downloaded_at_utc": timestamp,
            "content_type": content_type,
            "error": "",
        }
    except (HTTPError, URLError, OSError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        return {
            "group": group,
            "filename": filename,
            "source_url": url,
            "status": "failed",
            "bytes": 0,
            "sha256": "",
            "downloaded_at_utc": timestamp,
            "content_type": "",
            "error": str(exc),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Download the public raw calibration inputs.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing downloaded file.")
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    rows = [download(group, filename, url, args.overwrite) for group, filename, url in DOWNLOADS]
    manifest = RAW / "download_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        print(f"{row['status']:>17}  {row['group']}/{row['filename']}  {row['bytes']} bytes")
        if row["error"]:
            print(f"  error: {row['error']}")
    failed = sum(row["status"] == "failed" for row in rows)
    print(f"manifest: {manifest}")
    print(f"completed: {len(rows) - failed}/{len(rows)}; failed: {failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
