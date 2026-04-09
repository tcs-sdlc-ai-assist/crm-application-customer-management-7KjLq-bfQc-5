import csv
import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from django.http import HttpResponse, StreamingHttpResponse
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)


class Echo:
    """A write-only pseudo-buffer for streaming CSV content."""

    def write(self, value):
        return value


class CSVExporter:
    """
    Generates CSV from report data dict, returns HttpResponse with CSV content.
    Handles large datasets gracefully with streaming responses.
    """

    def __init__(self, filename: Optional[str] = None):
        self.filename = filename or self._generate_filename()

    def _generate_filename(self) -> str:
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        return f"report_{timestamp}.csv"

    def _extract_headers(self, data: Dict[str, Any]) -> List[str]:
        """Extract column headers from report data."""
        if "headers" in data and isinstance(data["headers"], list):
            headers = []
            for header in data["headers"]:
                if isinstance(header, dict):
                    headers.append(str(header.get("label", header.get("key", ""))))
                else:
                    headers.append(str(header))
            return headers

        if "details" in data and isinstance(data["details"], list) and len(data["details"]) > 0:
            first_row = data["details"][0]
            if isinstance(first_row, dict):
                return list(first_row.keys())

        if "rows" in data and isinstance(data["rows"], list) and len(data["rows"]) > 0:
            first_row = data["rows"][0]
            if isinstance(first_row, dict):
                if "cells" in first_row and isinstance(first_row["cells"], list):
                    if "headers" in data:
                        return self._extract_headers({"headers": data["headers"]})
                    return [f"Column {i + 1}" for i in range(len(first_row["cells"]))]
                return list(first_row.keys())

        return []

    def _extract_rows(self, data: Dict[str, Any], headers: List[str]) -> List[List[str]]:
        """Extract row data from report data dict."""
        rows = []

        source_key = None
        if "details" in data and isinstance(data["details"], list):
            source_key = "details"
        elif "rows" in data and isinstance(data["rows"], list):
            source_key = "rows"

        if source_key is None:
            return rows

        for item in data[source_key]:
            if isinstance(item, dict):
                if "cells" in item and isinstance(item["cells"], list):
                    row = []
                    for cell in item["cells"]:
                        if isinstance(cell, dict):
                            row.append(str(cell.get("value", "")))
                        else:
                            row.append(str(cell))
                    rows.append(row)
                else:
                    row = []
                    for header in headers:
                        value = item.get(header, "")
                        row.append(str(value) if value is not None else "")
                    rows.append(row)
            elif isinstance(item, (list, tuple)):
                rows.append([str(v) if v is not None else "" for v in item])
            else:
                rows.append([str(item)])

        return rows

    def _add_summary_rows(self, data: Dict[str, Any]) -> List[List[str]]:
        """Extract summary data as rows to prepend to CSV."""
        summary_rows = []

        summary = data.get("summary")
        if isinstance(summary, dict) and summary:
            summary_rows.append(["--- Summary ---"])
            for key, value in summary.items():
                summary_rows.append([str(key), str(value) if value is not None else ""])
            summary_rows.append([])

        return summary_rows

    def export(self, data: Dict[str, Any], include_summary: bool = True) -> HttpResponse:
        """
        Export report data as a CSV HttpResponse.

        Args:
            data: Report data dictionary with optional keys:
                  headers, details/rows, summary.
            include_summary: Whether to include summary section at top.

        Returns:
            HttpResponse with CSV content.
        """
        try:
            headers = self._extract_headers(data)
            detail_rows = self._extract_rows(data, headers)

            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{self.filename}"'

            writer = csv.writer(response)

            if include_summary:
                summary_rows = self._add_summary_rows(data)
                for row in summary_rows:
                    writer.writerow(row)

            if headers:
                writer.writerow(headers)

            for row in detail_rows:
                writer.writerow(row)

            return response

        except Exception as e:
            logger.error("Failed to export CSV report: %s", str(e))
            raise

    def export_streaming(self, data: Dict[str, Any], include_summary: bool = True) -> StreamingHttpResponse:
        """
        Export report data as a streaming CSV response for large datasets.

        Args:
            data: Report data dictionary.
            include_summary: Whether to include summary section at top.

        Returns:
            StreamingHttpResponse with CSV content.
        """
        try:
            headers = self._extract_headers(data)
            detail_rows = self._extract_rows(data, headers)

            def row_generator():
                pseudo_buffer = Echo()
                writer = csv.writer(pseudo_buffer)

                if include_summary:
                    summary_rows = self._add_summary_rows(data)
                    for row in summary_rows:
                        yield writer.writerow(row)

                if headers:
                    yield writer.writerow(headers)

                for row in detail_rows:
                    yield writer.writerow(row)

            response = StreamingHttpResponse(
                row_generator(),
                content_type="text/csv",
            )
            response["Content-Disposition"] = f'attachment; filename="{self.filename}"'
            return response

        except Exception as e:
            logger.error("Failed to export streaming CSV report: %s", str(e))
            raise


class PDFExporter:
    """
    Uses WeasyPrint to render report HTML template to PDF,
    returns HttpResponse with PDF content.
    Handles large datasets gracefully.
    """

    DEFAULT_TEMPLATE = "reports/report_pdf.html"

    def __init__(self, filename: Optional[str] = None, template_name: Optional[str] = None):
        self.filename = filename or self._generate_filename()
        self.template_name = template_name or self.DEFAULT_TEMPLATE

    def _generate_filename(self) -> str:
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        return f"report_{timestamp}.pdf"

    def _build_context(self, data: Dict[str, Any], extra_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Build template context from report data."""
        context = {
            "generated_at": timezone.now(),
        }

        context["report_title"] = data.get("title", data.get("report_title", "Report"))
        context["report_subtitle"] = data.get("subtitle", data.get("report_subtitle", ""))
        context["date_range_start"] = data.get("date_range_start", data.get("start_date", ""))
        context["date_range_end"] = data.get("date_range_end", data.get("end_date", ""))
        context["generated_by"] = data.get("generated_by", "")

        summary = data.get("summary")
        if isinstance(summary, dict):
            summary_stats = []
            for key, value in summary.items():
                stat = {
                    "label": str(key).replace("_", " ").title(),
                    "value": value if value is not None else "N/A",
                    "change": None,
                }
                summary_stats.append(stat)
            context["summary_stats"] = summary_stats
        elif isinstance(summary, list):
            context["summary_stats"] = summary
        else:
            context["summary_stats"] = None

        table_data = self._build_table_data(data)
        if table_data:
            context["table_data"] = table_data
            context["table_title"] = data.get("table_title", "Details")
        else:
            context["table_data"] = None

        context["additional_tables"] = data.get("additional_tables", None)
        context["notes"] = data.get("notes", None)

        if extra_context:
            context.update(extra_context)

        return context

    def _build_table_data(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Build table data structure for the PDF template."""
        headers_raw = data.get("headers", [])
        details = data.get("details", data.get("rows", []))

        if not details:
            return None

        headers = []
        header_keys = []

        if headers_raw:
            for header in headers_raw:
                if isinstance(header, dict):
                    headers.append({
                        "label": header.get("label", header.get("key", "")),
                        "align": header.get("align", ""),
                    })
                    header_keys.append(header.get("key", header.get("label", "")))
                else:
                    headers.append({"label": str(header), "align": ""})
                    header_keys.append(str(header))
        elif details and isinstance(details[0], dict):
            first_row = details[0]
            if "cells" not in first_row:
                for key in first_row.keys():
                    headers.append({
                        "label": str(key).replace("_", " ").title(),
                        "align": "",
                    })
                    header_keys.append(key)

        rows = []
        for item in details:
            if isinstance(item, dict):
                if "cells" in item and isinstance(item["cells"], list):
                    cells = []
                    for cell in item["cells"]:
                        if isinstance(cell, dict):
                            cells.append({
                                "value": cell.get("value", ""),
                                "align": cell.get("align", ""),
                                "status": cell.get("status", ""),
                            })
                        else:
                            cells.append({
                                "value": str(cell) if cell is not None else "",
                                "align": "",
                                "status": "",
                            })
                    rows.append({"cells": cells})
                else:
                    cells = []
                    for key in header_keys:
                        value = item.get(key, "")
                        cells.append({
                            "value": str(value) if value is not None else "",
                            "align": "",
                            "status": "",
                        })
                    rows.append({"cells": cells})
            elif isinstance(item, (list, tuple)):
                cells = []
                for value in item:
                    cells.append({
                        "value": str(value) if value is not None else "",
                        "align": "",
                        "status": "",
                    })
                rows.append({"cells": cells})

        totals = data.get("totals")
        formatted_totals = None
        if isinstance(totals, list):
            formatted_totals = []
            for total in totals:
                if isinstance(total, dict):
                    formatted_totals.append({
                        "value": total.get("value", ""),
                        "align": total.get("align", ""),
                    })
                else:
                    formatted_totals.append({
                        "value": str(total) if total is not None else "",
                        "align": "",
                    })

        return {
            "headers": headers,
            "rows": rows,
            "totals": formatted_totals,
        }

    def export(self, data: Dict[str, Any], extra_context: Optional[Dict[str, Any]] = None) -> HttpResponse:
        """
        Export report data as a PDF HttpResponse.

        Args:
            data: Report data dictionary.
            extra_context: Additional template context variables.

        Returns:
            HttpResponse with PDF content.
        """
        try:
            from weasyprint import HTML

            context = self._build_context(data, extra_context)
            html_string = render_to_string(self.template_name, context)

            html_doc = HTML(string=html_string)
            pdf_bytes = html_doc.write_pdf()

            response = HttpResponse(pdf_bytes, content_type="application/pdf")
            response["Content-Disposition"] = f'attachment; filename="{self.filename}"'
            response["Content-Length"] = len(pdf_bytes)

            return response

        except ImportError:
            logger.error("WeasyPrint is not installed. Cannot generate PDF.")
            raise
        except Exception as e:
            logger.error("Failed to export PDF report: %s", str(e))
            raise

    def export_to_bytes(self, data: Dict[str, Any], extra_context: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Export report data as PDF bytes (useful for saving to file or storage).

        Args:
            data: Report data dictionary.
            extra_context: Additional template context variables.

        Returns:
            PDF content as bytes.
        """
        try:
            from weasyprint import HTML

            context = self._build_context(data, extra_context)
            html_string = render_to_string(self.template_name, context)

            html_doc = HTML(string=html_string)
            return html_doc.write_pdf()

        except ImportError:
            logger.error("WeasyPrint is not installed. Cannot generate PDF.")
            raise
        except Exception as e:
            logger.error("Failed to export PDF report to bytes: %s", str(e))
            raise

    def render_html(self, data: Dict[str, Any], extra_context: Optional[Dict[str, Any]] = None) -> str:
        """
        Render report data as HTML string (useful for previewing before PDF export).

        Args:
            data: Report data dictionary.
            extra_context: Additional template context variables.

        Returns:
            Rendered HTML string.
        """
        try:
            context = self._build_context(data, extra_context)
            return render_to_string(self.template_name, context)
        except Exception as e:
            logger.error("Failed to render report HTML: %s", str(e))
            raise