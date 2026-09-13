#!/usr/bin/env python3
from __future__ import annotations

import argparse
import bisect
import json
import re
from collections import Counter
from pathlib import Path


ENTRY_START_RE = re.compile(r"(?m)^\s*(?:#+\s*)?(?P<formula_id>\d{5})(?P<header>[^\n]*)")
ENTRY_START_AT_START_RE = re.compile(r"^\s*(?:#+\s*)?(?P<formula_id>\d{5})(?P<header>[^\n]*)")
HEADWORD_RE = re.compile(r"^\s*(?:#+\s*)?(?P<formula_id>\d{5})(?P<headword>[^\n（(《\s]+)")
HEADER_DIGITS_RUN_RE = re.compile(r"^\s*(?:#+\s*)?(?P<digits>\d{5,10})")
HEADWORD_ONLY_LINE_RE = re.compile(r"^\s*(?:#+\s*)?(?P<formula_id>\d{5})(?P<headword>[\u4e00-\u9fffA-Za-z0-9]{1,40})\s*$")
TRUNCATED_TAIL_RE = re.compile(r"^\s*#*\s*[\u4e00-\u9fff]{0,2}\s*$")
FIELD_START_RE = re.compile(r"(?m)^\s*#*\s*【(?P<field>[^】]+)】")
FIELD_START_ANY_RE = re.compile(
    r"【(?P<field>异名|组成|用法|功用|主治|宜忌|加减|方论选录|临床报道|现代研究|备考)】"
)
SOURCE_CITATION_RE = re.compile(r"[（(](?P<citation>[^）)]+)[）)]")
EMBEDDED_START_CANDIDATE_RE = re.compile(
    r"(?<!\d)(?P<formula_id>\d{5})(?=[\s#\$\^\+\*\-\u2014\u2013\uFF0D\u00B1]*[\u4e00-\u9fff])"
)
ID5_ANYWHERE_RE = re.compile(r"(?<!\d)\d{5}(?!\d)")
HTML_TAG_RE = re.compile(r"<[^>]+>")

FIELD_HEADING_STRINGS = (
    "【异名】",
    "【组成】",
    "【用法】",
    "【功用】",
    "【主治】",
    "【宜忌】",
    "【加减】",
    "【方论选录】",
    "【临床报道】",
    "【现代研究】",
    "【备考】",
)

# Many TOC/index blocks look like "09708飞补汤 1-720" (page locator), sometimes followed by HTML tables.
# Allow spaces inside OCR-damaged headwords and extra trailing tokens.
INDEX_HEADER_RE = re.compile(r"^\s*(?:#+\s*)?\d{5}.*?\b\d+\s*-\s*\d+\b.*$")
PAGE_LOCATOR_RE = re.compile(r"\b\d+\s*-\s*\d+\b")

FIELD_NAME_MAP = {
    "异名": "alias_raw",
    "组成": "composition_raw",
    "用法": "usage_raw",
    "功用": "efficacy_raw",
    "主治": "indication_raw",
    "宜忌": "contraindication_raw",
    "加减": "modification_raw",
    "方论选录": "commentary_raw",
    "临床报道": "clinical_report_raw",
    "现代研究": "modern_research_raw",
    "备考": "notes_raw",
}


def line_starts(text: str) -> list[int]:
    starts = [0]
    starts.extend(match.end() for match in re.finditer(r"\n", text))
    return starts


def line_number(starts: list[int], position: int) -> int:
    return bisect.bisect_right(starts, position)


def strip_html(text: str) -> str:
    # Lightweight tag stripper (keeps visible text, headings, ids).
    return HTML_TAG_RE.sub(" ", text or "")


def line_slice(text: str, pos: int) -> tuple[str, int]:
    line_end = text.find("\n", pos)
    if line_end < 0:
        line_end = len(text)
    return text[pos:line_end], line_end


def has_nearby_followup_entry(segment_text: str, pos: int, window_chars: int = 220) -> bool:
    """
    Detect the common OCR pattern:
    "...【主治】...00682二陈丸\n\n00683二陈汤（《...》）..."
    where the embedded id+headword is itself a short orphan line followed shortly by
    another bona fide entry start.
    """
    _, line_end = line_slice(segment_text, pos)
    tail = segment_text[line_end + 1 : min(len(segment_text), line_end + 1 + window_chars)]
    return bool(ENTRY_START_RE.search(tail))


def tail_is_truncated_noise(segment_text: str, pos: int, window_chars: int = 40) -> bool:
    _, line_end = line_slice(segment_text, pos)
    tail = segment_text[line_end + 1 : min(len(segment_text), line_end + 1 + window_chars)]
    return bool(TRUNCATED_TAIL_RE.match(tail or ""))


def is_headword_only_entry(entry_text: str) -> bool:
    lines = [ln.strip() for ln in (entry_text or "").splitlines() if ln.strip()]
    if not lines:
        return False
    if not HEADWORD_ONLY_LINE_RE.match(lines[0]):
        return False
    if len(lines) == 1:
        return True
    if len(lines) == 2 and TRUNCATED_TAIL_RE.match(lines[1]):
        return True
    return False


def looks_like_index_entry(header_line: str, entry_text: str) -> bool:
    hl = (header_line or "").strip()
    if INDEX_HEADER_RE.match(hl):
        # Exclude true formula headers which almost always contain a source citation like 《...》.
        if "《" not in hl and "（" not in hl and "(" not in hl and "【" not in hl:
            return True
    # Some OCR outputs wrap the TOC/index into HTML blocks; treat those as index-like if they contain page locators.
    if "<html" in (entry_text or "") and PAGE_LOCATOR_RE.search(entry_text):
        return True
    return False


def is_probable_embedded_entry_start(segment_text: str, pos: int) -> bool:
    """
    Distinguish real embedded entry starts (e.g. "...。【81730某方（《...》）【组成】...") from
    plain 5-digit numbers inside clinical/modern research or URLs.
    """
    window = segment_text[pos : pos + 900]
    window_head = window[:220]
    current_line, line_end = line_slice(segment_text, pos)
    orphan_headword_line = bool(HEADWORD_ONLY_LINE_RE.match(current_line.strip()))
    nearby_followup = has_nearby_followup_entry(segment_text, pos)
    reaches_tail = line_end >= len(segment_text.rstrip()) - 2
    truncated_tail = tail_is_truncated_noise(segment_text, pos)

    # Citations don't always appear in parentheses; many headers have 《...》 directly.
    has_source = ("《" in window_head) or ("（《" in window_head) or ("(《" in window_head)
    is_redirect = ("见该条" in window_head) or ("见该" in window_head)
    has_heading = any(h in window for h in ("【组成】", "【异名】", "【用法】", "【功用】", "【主治】"))
    header_like = bool(re.match(r"^\d{5}[\s#\$\^\+\*\-]*[\u4e00-\u9fff]{1,30}", window_head))

    prev = segment_text[max(0, pos - 3) : pos]
    good_prev = ("\n" in prev) or ("。" in prev) or ("】" in prev) or (" " in prev) or ("\t" in prev)

    if is_redirect:
        return True
    if has_heading:
        return True
    if has_source and "【" in window:
        return True
    # OCR often leaves a short orphan "id+headword" line between two real entries.
    if orphan_headword_line and good_prev and (nearby_followup or reaches_tail or truncated_tail):
        return True
    # As a last resort, accept header-like starts only when they also look like they carry a citation marker.
    if header_like and good_prev and ("《" in window_head or "（" in window_head or "(" in window_head):
        return True
    return False


def parse_fields(entry_text: str) -> dict[str, str]:
    text = entry_text or ""

    # If a valid entry is followed by an HTML index/table block, don't let that spill into the last field value.
    # We only trim when we already saw at least one known heading before the HTML starts.
    html_pos = text.find("<html")
    if html_pos >= 0 and any(h in text[:html_pos] for h in FIELD_HEADING_STRINGS):
        text = text[:html_pos]

    if "<html" in text or "</table>" in text:
        # Help prevent HTML tags from leaking into extracted fields.
        text = strip_html(text)

    # Normalize common OCR bracket variants in headings: 【主治〗 / 【功用》 / 【宜忌] etc.
    text = re.sub(r"【(?P<f>[^】》〗〕\]」』]{1,20})(?P<c>[】》〗〕\]」』])", r"【\g<f>】", text)
    # Some OCR outputs lose the bracket and produce a stray character like 厂/」/』 right after a known field name.
    text = re.sub(
        r"【(?P<f>异名|组成|用法|功用|主治|宜忌|加减|方论选录|临床报道|现代研究|备考)[厂」』]",
        r"【\g<f>】",
        text,
    )
    fields: dict[str, str] = {}
    # OCR frequently glues headings mid-line; treat headings as delimiters wherever they appear.
    # We still only extract whitelisted field names via FIELD_NAME_MAP.
    matches = list(FIELD_START_ANY_RE.finditer(text))
    for index, match in enumerate(matches):
        field_name = match.group("field").strip()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = text[start:end].strip()
        # Common boundary artifact: "...。【81730..." -> the previous field ends with a stray "【".
        if value.endswith("【"):
            value = value[:-1].rstrip()
        key = FIELD_NAME_MAP.get(field_name)
        if key and value:
            fields[key] = value
    return fields


def split_contaminated_segment(segment_text: str) -> list[tuple[int, int, str]]:
    """
    Some OCR lines lose newlines and glue multiple entries together:
    e.g. "...【主治】...00005某方（《...》）【组成】..."

    We only split at embedded 5-digit IDs that look like a new entry start,
    by requiring nearby field headings or a citation marker.
    """
    if not segment_text:
        return []

    # Only attempt splitting when we can see multiple 5-digit IDs in the same segment.
    # This is a safety guard against false splits caused by cross-references inside a field.
    ids = ID5_ANYWHERE_RE.findall(segment_text)
    if len(set(ids)) <= 1:
        return [(0, len(segment_text), segment_text.strip())]

    # HTML-heavy index blocks can contain thousands of ids; splitting them is both slow and unnecessary.
    if ("<html" in segment_text or "</table>" in segment_text) and not any(h in segment_text for h in FIELD_HEADING_STRINGS):
        return [(0, len(segment_text), segment_text.strip())]
    if ("<html" in segment_text or "</table>" in segment_text) and len(set(ids)) > 200:
        return [(0, len(segment_text), segment_text.strip())]

    candidates = []
    for m in EMBEDDED_START_CANDIDATE_RE.finditer(segment_text):
        pos = m.start()
        if pos <= 0:
            continue

        # If it appears to start a new line (possibly after whitespace), treat as a start.
        prev_nl = segment_text.rfind("\n", 0, pos)
        line_prefix = segment_text[prev_nl + 1 : pos]
        looks_line_start = (prev_nl >= 0) and (line_prefix.strip().lstrip("#").strip() == "")

        if looks_line_start or is_probable_embedded_entry_start(segment_text, pos):
            candidates.append(pos)

    # Nothing to split
    if not candidates:
        return [(0, len(segment_text), segment_text.strip())]

    positions = sorted(set(candidates))
    spans: list[tuple[int, int, str]] = []
    start = 0
    for pos in positions:
        if pos <= start:
            continue
        piece = segment_text[start:pos].strip()
        if piece:
            spans.append((start, pos, piece))
        start = pos
    tail = segment_text[start:].strip()
    if tail:
        spans.append((start, len(segment_text), tail))

    # One more pass: if any produced span still contains multiple IDs, try splitting it again.
    out: list[tuple[int, int, str]] = []
    for s, e, txt in spans:
        ids2 = ID5_ANYWHERE_RE.findall(txt)
        if len(set(ids2)) <= 1:
            out.append((s, e, txt))
            continue
        # Recursive split (depth=1) using same logic.
        inner = split_contaminated_segment(txt)
        if len(inner) <= 1:
            out.append((s, e, txt))
            continue
        for is_, ie, itxt in inner:
            out.append((s + is_, s + ie, itxt))
    return out


def detect_noise_flags(entry_text: str) -> list[str]:
    flags: list[str] = []
    if re.search(r"(?m)^#\s*【", entry_text):
        flags.append("markdown_field_heading")
    # Only flag inline ids that look like a true embedded entry start (not plain numbers in research, or ids inside URLs).
    header_digits = HEADER_DIGITS_RUN_RE.search(entry_text or "")
    ignore_before = header_digits.end("digits") if header_digits else 0
    for m in EMBEDDED_START_CANDIDATE_RE.finditer(entry_text):
        pos = m.start()
        if pos < ignore_before:
            continue
        if is_probable_embedded_entry_start(entry_text, pos):
            flags.append("inline_formula_id")
            break
    if "<html" in entry_text:
        flags.append("html_contamination")
    if "![" in entry_text:
        flags.append("image_contamination")
    return flags


def classify_entry(entry_text: str, fields: dict[str, str], noise_flags: list[str]) -> tuple[str, list[str]]:
    header_line = entry_text.splitlines()[0].strip() if entry_text else ""
    if not fields and looks_like_index_entry(header_line, entry_text):
        return "TOC_INDEX", ["doc_type_classification"]
    if not fields and ("见该条" in entry_text or is_headword_only_entry(entry_text)):
        return "FORMULA_ENTRY_REDIRECT", ["entry_segmentation", "alias_resolution"]
    if fields and not noise_flags:
        return (
            "FORMULA_ENTRY_FULL",
            ["entry_segmentation", "field_extraction", "herb_normalization", "alias_resolution"],
        )
    if fields or noise_flags:
        return (
            "FORMULA_ENTRY_NOISY",
            ["entry_segmentation", "field_extraction", "herb_normalization", "alias_resolution"],
        )
    return "MIXED_UNKNOWN", ["manual_review_required"]


def parse_file(path: Path, root: Path) -> tuple[list[dict], Counter]:
    text = path.read_text(encoding="utf-8")
    starts = line_starts(text)
    matches = list(ENTRY_START_RE.finditer(text))
    records: list[dict] = []
    stats = Counter()
    record_seq = 0

    for index, match in enumerate(matches):
        seg_start = match.start()
        seg_end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        segment_text = text[seg_start:seg_end].strip()
        if not segment_text:
            continue

        # If the segment appears to contain embedded entry starts, split it.
        spans = split_contaminated_segment(text[seg_start:seg_end])
        for off_s, off_e, entry_text in spans:
            # Ensure each sub-entry starts with an entry header; otherwise skip.
            header_match = ENTRY_START_AT_START_RE.match(entry_text)
            if not header_match:
                stats["skipped_non_entry_span"] += 1
                continue

            header_line = entry_text.splitlines()[0].strip()
            headword_match = HEADWORD_RE.match(header_line)
            citation_match = SOURCE_CITATION_RE.search(header_line)
            fields = parse_fields(entry_text)
            noise_flags = detect_noise_flags(entry_text)
            doc_type, eligibility = classify_entry(entry_text, fields, noise_flags)

            record_seq += 1
            char_start = seg_start + off_s
            char_end = seg_start + off_e

            record = {
                "record_id": f"{path.stem}-{record_seq:05d}",
                "formula_id_text": header_match.group("formula_id"),
                "headword_raw": headword_match.group("headword") if headword_match else None,
                "source_citation_raw": citation_match.group("citation") if citation_match else None,
                "source_file": path.relative_to(root).as_posix(),
                "source_char_start": char_start,
                "source_char_end": char_end,
                "source_line_start": line_number(starts, char_start),
                "source_line_end": line_number(starts, char_end),
                "doc_type": doc_type,
                "eligibility": eligibility,
                "noise_flags": noise_flags,
                "parse_status": "bootstrap_parsed",
                "raw_text": entry_text.strip(),
                **fields,
            }
            records.append(record)
            stats["records"] += 1
            stats[f"doc_type::{doc_type}"] += 1
            for flag in noise_flags:
                stats[f"noise::{flag}"] += 1

    return records, stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap parser for OCR-derived TCM formula markdown files.")
    parser.add_argument("root", help="Directory containing markdown files.")
    parser.add_argument("--output-jsonl", required=True, help="Output path for JSONL records.")
    parser.add_argument("--summary-json", help="Optional output path for parse summary JSON.")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    md_files = sorted(root.glob("*.md"))
    if not md_files:
        raise SystemExit(f"No markdown files found in {root}")

    output_path = Path(args.output_jsonl).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    summary = Counter()
    file_summaries: dict[str, dict[str, int]] = {}

    with output_path.open("w", encoding="utf-8") as handle:
        for path in md_files:
            records, stats = parse_file(path, root.parent)
            file_summaries[path.name] = dict(stats)
            summary.update(stats)
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    if args.summary_json:
        summary_path = Path(args.summary_json).resolve()
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            # Keep the original label to avoid machine-specific absolute paths in saved JSON.
            "root": str(args.root),
            "files": len(md_files),
            "summary": dict(summary),
            "per_file": file_summaries,
        }
        summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Root: {root}")
    print(f"Files: {len(md_files)}")
    print(f"Records written: {summary['records']}")
    for key in sorted(k for k in summary if k.startswith('doc_type::')):
        print(f"{key}: {summary[key]}")
    for key in sorted(k for k in summary if k.startswith('noise::')):
        print(f"{key}: {summary[key]}")


if __name__ == "__main__":
    main()
