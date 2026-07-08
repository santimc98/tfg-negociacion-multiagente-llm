"""Open the report in Word, update all fields (TOC, captions, lists), export PDF.

This guarantees the table of contents, the SEQ caption numbers and the lists of
figures/tables are recalculated, and produces a faithful PDF for review and page
counting. Requires Microsoft Word (uses COM automation via pywin32).
"""

from __future__ import annotations

import sys
from pathlib import Path

import win32com.client  # type: ignore

DOCX = Path(__file__).resolve().parent.parent / "docs" / "memoria" / "TFG_Santiago_Martin_Cabrera.docx"
PDF = DOCX.with_suffix(".pdf")

WD_FORMAT_PDF = 17


def main() -> None:
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        doc = word.Documents.Open(str(DOCX))
        # Update fields across every story (body, headers, footers, textboxes).
        for story in doc.StoryRanges:
            story.Fields.Update()
        for toc in doc.TablesOfContents:
            toc.Update()
        for tof in doc.TablesOfFigures:
            tof.Update()
        # Second pass so the TOC picks up page shifts from updated captions.
        for story in doc.StoryRanges:
            story.Fields.Update()
        doc.Repaginate()
        pages = doc.ComputeStatistics(2)  # wdStatisticPages
        doc.SaveAs(str(PDF), FileFormat=WD_FORMAT_PDF)
        doc.Close(False)
        print(f"PDF: {PDF}")
        print(f"PAGES (Word): {pages}")
    finally:
        word.Quit()


if __name__ == "__main__":
    main()
