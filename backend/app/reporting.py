"""Portable XLSX and PDF report generation from saved local records."""
from __future__ import annotations
from io import BytesIO
from datetime import datetime, timezone

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

from backend.app.database import list_receipts, list_expenses, get_analytics


def build_financial_workbook() -> bytes:
    workbook = Workbook()
    documents = workbook.active
    documents.title = "Documents"
    documents.append(["Document ID", "Merchant", "Date", "Total", "Currency", "Category", "Status", "Filename"])
    for record in list_receipts(limit=500):
        documents.append([
            record.get("receipt_id"), record.get("merchant_name"), record.get("document_date"),
            record.get("total_amount"), record.get("currency_code"), record.get("category"),
            record.get("status"), record.get("original_filename"),
        ])
    expenses = workbook.create_sheet("Expenses")
    expenses.append(["Expense ID", "Description", "Merchant", "Date", "Amount", "Currency", "Category", "Payment Method", "Notes"])
    for record in list_expenses():
        expenses.append([
            record.get("expense_id"), record.get("description"), record.get("merchant_name"),
            record.get("expense_date"), record.get("amount"), record.get("currency_code"),
            record.get("category"), record.get("payment_method"), record.get("notes"),
        ])
    summary = workbook.create_sheet("Summary")
    analytics = get_analytics()
    summary.append(["Metric", "Value"])
    summary.append(["Documents", analytics["document_count"]])
    summary.append(["Manual expenses", analytics["expense_count"]])
    summary.append(["Documents needing review", analytics["review_required"]])
    summary.append([])
    summary.append(["Spend by currency", "Amount"])
    for currency, amount in sorted(analytics["spend_by_currency"].items()):
        summary.append([currency, amount])
    summary.append([])
    summary.append(["Spend by category", "Amount (currencies not converted)"])
    for category, amount in sorted(analytics["spend_by_category"].items()):
        summary.append([category, amount])
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="253858")
        for column in sheet.columns:
            width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 34)
            sheet.column_dimensions[column[0].column_letter].width = width
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def build_financial_pdf() -> bytes:
    analytics = get_analytics()
    documents = list_receipts(limit=500)
    expenses = list_expenses()
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=14*mm,
                            leftMargin=14*mm, topMargin=14*mm, bottomMargin=14*mm)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SmartReceipt AI — Financial Summary", styles["Title"]),
        Paragraph("Generated " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), styles["Normal"]),
        Spacer(1, 8*mm),
        Paragraph("Overview", styles["Heading2"]),
        Paragraph(
            f"Documents: {analytics['document_count']} &nbsp;&nbsp; "
            f"Manual expenses: {analytics['expense_count']} &nbsp;&nbsp; "
            f"Documents needing review: {analytics['review_required']}",
            styles["BodyText"],
        ),
        Spacer(1, 5*mm),
        Paragraph("Spend by currency (currencies are not converted)", styles["Heading2"]),
    ]
    rows = [["Currency", "Amount"]] + [[key, str(value)] for key, value in sorted(analytics["spend_by_currency"].items())]
    table = Table(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#253858")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D7DEE8")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.extend([table, Spacer(1, 5*mm), Paragraph("Recent documents", styles["Heading2"])])
    recent = [["Merchant", "Date", "Total", "Currency", "Category", "Status"]]
    for item in documents[:30]:
        recent.append([
            str(item.get("merchant_name") or "Unknown")[:35],
            str(item.get("document_date") or ""),
            str(item.get("total_amount") or ""),
            str(item.get("currency_code") or ""),
            str(item.get("category") or ""),
            str(item.get("status") or ""),
        ])
    table = Table(recent, repeatRows=1, colWidths=[48*mm, 25*mm, 25*mm, 22*mm, 35*mm, 35*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#253858")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("GRID", (0,0), (-1,-1), 0.35, colors.HexColor("#D7DEE8")),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("PADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)
    doc.build(story)
    return output.getvalue()
