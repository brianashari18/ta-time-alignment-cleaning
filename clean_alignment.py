"""
Time Alignment CSV Cleaner
==========================
Cleans one or more Sonic Visualizer time-alignment CSV exports.

Input format  : start_time, seq_order
Output format : track_id (artist-track), seq_order, start_time, end_time

Filename convention : artist-track.csv  (artist = part before the first '-')

Usage
-----
# Default: process all CSVs in ./input/, output to ./output/<artist>/
python clean_alignment.py

# Custom input directory
python clean_alignment.py --dir ./my_input

# Specific files
python clean_alignment.py file1.csv file2.csv

Output CSVs are written to ./output/<artist>/ by default.
Use --output-dir <path> to override the base output folder.
"""

import argparse
import csv
import os
import glob
import sys
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────────

def track_id_from_filename(filepath: str) -> str:
    """Derive track_id from the file stem (everything before the extension).
    Filename format: artist-track.csv → track_id: artist-track (unchanged).
    """
    return Path(filepath).stem


def artist_from_filename(filepath: str) -> str:
    """Extract artist name from filename (part before the first '-').
    adele-hello.csv        → adele
    ed_sheeran-shape.csv   → ed_sheeran
    """
    stem = Path(filepath).stem
    return stem.split("-")[0]


def parse_seq_order(raw: str) -> int | str:
    """
    Convert seq_order value to int when possible, otherwise keep as string.
    'New Point' → will be re-numbered sequentially (see clean_rows).
    Numeric strings → int.
    """
    stripped = raw.strip()
    try:
        return int(stripped)
    except ValueError:
        return stripped  # e.g. 'New Point'


def clean_rows(raw_rows: list[dict]) -> list[dict]:
    """
    Re-numbers every row sequentially (1-based) regardless of whether
    seq_order was an integer or 'New Point', then computes end_time.

    end_time of row N  = start_time of row N+1
    end_time of last row = None  (blank cell in the output)
    """
    cleaned = []
    for idx, row in enumerate(raw_rows, start=1):
        cleaned.append({
            "seq_order": idx,
            "start_time": float(row["start_time"].strip()),
        })

    # compute end_time
    for i, row in enumerate(cleaned):
        if i + 1 < len(cleaned):
            row["end_time"] = cleaned[i + 1]["start_time"]
        else:
            row["end_time"] = None  # last beat has no defined end

    return cleaned


def process_file(input_path: str, output_base_dir: str) -> str:
    """
    Process a single CSV file and write the cleaned version to
    output_base_dir/<artist>/.  Returns the path of the written output file.
    """
    track_id = track_id_from_filename(input_path)
    artist   = artist_from_filename(input_path)

    # ── read ──────────────────────────────────────────────────────────────────
    with open(input_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        # Normalise header names (strip spaces)
        reader.fieldnames = [f.strip() for f in reader.fieldnames]
        raw_rows = list(reader)

    if not raw_rows:
        print(f"  [SKIP] {input_path} — file is empty.")
        return ""

    # ── clean ─────────────────────────────────────────────────────────────────
    cleaned = clean_rows(raw_rows)

    # ── write ─────────────────────────────────────────────────────────────────
    output_dir = os.path.join(output_base_dir, artist)
    os.makedirs(output_dir, exist_ok=True)
    output_filename = f"{track_id}_cleaned.csv"
    output_path = os.path.join(output_dir, output_filename)

    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        fieldnames = ["track_id", "seq_order", "start_time", "end_time"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in cleaned:
            writer.writerow({
                "track_id": track_id,
                "seq_order": row["seq_order"],
                "start_time": f"{row['start_time']:.9f}",
                "end_time": f"{row['end_time']:.9f}" if row["end_time"] is not None else "",
            })

    print(f"  [OK]   {input_path}  →  {output_path}  ({len(cleaned)} rows)")
    return output_path


# ── main ───────────────────────────────────────────────────────────────────────

def collect_files(args) -> list[str]:
    """Collect all target CSV file paths from CLI args."""
    files = []

    # default to ./input/ when no files and no --dir given
    input_dir = args.dir if args.dir else ("input" if not args.files else None)
    if input_dir:
        pattern = os.path.join(input_dir, "*.csv")
        found = sorted(glob.glob(pattern))
        if not found:
            print(f"No CSV files found in directory: {args.dir}")
        files.extend(found)

    for pattern in args.files:
        expanded = sorted(glob.glob(pattern))
        if not expanded:
            # treat as literal path (may not exist yet — let process_file handle it)
            expanded = [pattern]
        files.extend(expanded)

    # deduplicate while preserving order
    seen = set()
    unique = []
    for f in files:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique


def main():
    parser = argparse.ArgumentParser(
        description="Clean Sonic Visualizer time-alignment CSV exports.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="CSV",
        help="One or more CSV files (glob patterns supported).",
    )
    parser.add_argument(
        "--dir",
        metavar="DIR",
        help="Input directory with CSV files (default: ./input).",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        metavar="DIR",
        help="Base output directory; artist sub-folders are created inside (default: ./output).",
    )

    args = parser.parse_args()

    target_files = collect_files(args)

    if not target_files:
        print("No files to process.")
        sys.exit(1)

    print(f"\nProcessing {len(target_files)} file(s) → base output dir: '{args.output_dir}/<artist>/'\n")
    results = []
    for fp in target_files:
        out = process_file(fp, args.output_dir)
        if out:
            results.append(out)

    print(f"\nDone. {len(results)}/{len(target_files)} file(s) cleaned successfully.")


if __name__ == "__main__":
    main()
