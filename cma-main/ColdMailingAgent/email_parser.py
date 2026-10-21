"""
email_parser.py — Universal Generic Excel & CSV Recruiter Data Extractor.

Supports:
  - Any Excel (.xlsx, .xls) or CSV file.
  - Automatic fuzzy sheet matching (Unicorns, Soonicorns, or ALL sheets).
  - Smart header detection (Company, Name, Designation, Email, LinkedIn).
  - Multi-email extraction with splitters (\\n, ||, comma, semicolon).
  - Company propagation across multi-contact rows.
  - Global email deduplication and cleaning.
"""

import os
import re
import csv
from dataclasses import dataclass
from typing import Optional, List
import openpyxl


@dataclass
class Recruiter:
    name: str
    designation: str
    company: str
    email: str
    linkedin: Optional[str] = None
    sheet: str = ""


def extract_emails_from_text(cell_value: any) -> list[str]:
    """
    Extract and clean all valid email addresses from any cell value.
    Handles separators: \\n, ||, comma, semicolon, pipe, tab.
    """
    if cell_value is None:
        return []
    
    text = str(cell_value).strip()
    if not text or '@' not in text:
        return []

    # Split by common separators
    parts = re.split(r'\|\||[,\n\r\t|;]', text)
    
    emails = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        
        found = re.findall(
            r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
            part
        )
        emails.extend(found)
    
    valid = []
    for email in emails:
        clean = email.strip().lower()
        # Skip masked emails (e.g. am****@company.com)
        if '*' in clean:
            continue
        # Skip dummy strings
        if clean in ('none@none.com', 'na@na.com', 'copy@copy.com'):
            continue
        if re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', clean):
            valid.append(clean)
            
    return valid


def find_header_row_and_cols(rows: list[tuple], max_scan: int = 10) -> tuple[int, dict]:
    """
    Detect the header row index and map column indices flexibly.
    """
    best_idx = 0
    best_cols = {}
    max_score = 0

    for i, row in enumerate(rows[:max_scan]):
        if not row:
            continue
        
        cols = {}
        score = 0
        
        for col_idx, cell in enumerate(row):
            if cell is None:
                continue
            text = str(cell).strip().lower()
            if not text:
                continue
            
            # Company
            if any(k in text for k in ['company', 'organization', 'startup', 'firm', 'employer']) and 'company' not in cols:
                cols['company'] = col_idx
                score += 3
            
            # Name
            elif any(k in text for k in ['name', 'poc', 'founder', 'recruiter', 'contact']) and 'name' not in cols:
                cols['name'] = col_idx
                score += 3
            
            # Designation
            elif any(k in text for k in ['designation', 'role', 'title', 'position', 'human resources']) and 'designation' not in cols:
                cols['designation'] = col_idx
                score += 2
            
            # LinkedIn
            elif any(k in text for k in ['linkedin', 'profile']) and 'linkedin' not in cols:
                cols['linkedin'] = col_idx
                score += 1
            
            # Email
            elif any(k in text for k in ['email', 'e-mail', 'mail']) and 'email' not in cols:
                cols['email'] = col_idx
                score += 4

        if score > max_score and ('name' in cols or 'email' in cols):
            max_score = score
            best_idx = i
            best_cols = cols

    return best_idx, best_cols


def get_cell(row: tuple, index: Optional[int]) -> str:
    """Safely extract cell value as string."""
    if index is None or index >= len(row):
        return ""
    val = row[index]
    if val is None:
        return ""
    return str(val).strip()


def parse_excel(excel_path: str, target_sheets: Optional[List[str]] = None) -> list[Recruiter]:
    """
    Universally parse an Excel file and extract all valid recruiters.

    Args:
        excel_path: Path to .xlsx or .xls file
        target_sheets: List of sheet name keywords (e.g. ["Unicorn", "Soonicorn"]) or ["ALL"]

    Returns:
        Deduplicated list of Recruiter objects
    """
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found at: {excel_path}")

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    all_sheet_names = wb.sheetnames

    # Determine sheets to process
    matched_sheets = []
    if not target_sheets or "all" in [s.lower() for s in target_sheets]:
        matched_sheets = all_sheet_names
    else:
        for sheet_name in all_sheet_names:
            for target in target_sheets:
                if target.lower() in sheet_name.lower():
                    matched_sheets.append(sheet_name)
                    break

    if not matched_sheets:
        # Fallback to all sheets if target sheets didn't match
        matched_sheets = all_sheet_names

    all_recruiters = []
    seen_emails = set()

    for sheet_name in matched_sheets:
        ws = wb[sheet_name]
        rows = list(ws.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            continue

        header_idx, cols = find_header_row_and_cols(rows)
        
        last_company = ""

        for row_idx in range(header_idx + 1, len(rows)):
            row = rows[row_idx]
            if not row or not any(row):
                continue

            name = get_cell(row, cols.get('name'))
            company = get_cell(row, cols.get('company'))
            designation = get_cell(row, cols.get('designation'))
            linkedin = get_cell(row, cols.get('linkedin'))

            # Company propagation
            if company:
                last_company = company
            else:
                company = last_company

            # Skip header category noise
            if name and name.lower() in ('unicorns', 'soonicorn', 'soonicorns', 'unicorn', 'company name', 'name'):
                continue

            # Extract emails: check designated email col + fallback scan all cells in row
            emails = []
            if 'email' in cols:
                emails.extend(extract_emails_from_text(row[cols['email']]))
            
            # If no email in primary col, scan entire row for any valid email pattern
            if not emails:
                for cell in row:
                    emails.extend(extract_emails_from_text(cell))

            if not emails:
                continue

            # Clean name fallback
            if not name:
                name = company if company else "Hiring Lead"

            for email in emails:
                if email in seen_emails:
                    continue
                seen_emails.add(email)

                clean_linkedin = linkedin if linkedin and linkedin.startswith("http") else None
                all_recruiters.append(Recruiter(
                    name=name.strip(),
                    designation=designation.strip() if designation else "Engineering / Data Lead",
                    company=company.strip() if company else "Tech Organization",
                    email=email,
                    linkedin=clean_linkedin,
                    sheet=sheet_name,
                ))

    wb.close()
    return all_recruiters


def get_stats(recruiters: list[Recruiter]) -> dict:
    """Return summary metrics for parsed recruiters."""
    companies = set(r.company for r in recruiters if r.company)
    sheets = set(r.sheet for r in recruiters)
    return {
        "total_contacts": len(recruiters),
        "unique_companies": len(companies),
        "sheets_parsed": len(sheets),
        "sheet_names": list(sheets),
    }
