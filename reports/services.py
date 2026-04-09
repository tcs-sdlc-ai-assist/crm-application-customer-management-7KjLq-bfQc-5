import logging
import uuid
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from audit_logs.models import AuditLog
from reports.exporters import CSVExporter, PDFExporter
from reports.generators import ReportGeneratorFactory
from reports.models import Report

logger = logging.getLogger(__name__)


class ReportService:
    """
    Business logic service for report generation, retrieval, and export.
    Orchestrates generator selection via ReportGeneratorFactory, stores results
    in the Report model, and delegates export to CSVExporter/PDFExporter.
    Includes audit logging for all report generation and export actions.
    """

    def generate_report(
        self,
        report_type: str,
        parameters: Dict[str, Any],
        user=None,
        title: Optional[str] = None,
        output_format: str = "json",
        ip_address: Optional[str] = None,
    ) -> Report:
        """
        Generate a new report based on the given type and parameters.

        Args:
            report_type: The type of report to generate (e.g., 'sales_performance',
                         'customer_engagement', 'pipeline_health').
            parameters: Dictionary of report parameters including date ranges,
                        user filters, stage filters, etc.
            user: The user requesting the report (for audit logging and ownership).
            title: Optional title for the report. Auto-generated if not provided.
            output_format: Output format ('json', 'csv', 'pdf'). Default: 'json'.
            ip_address: Optional IP address for audit logging.

        Returns:
            The generated Report instance with status 'completed' or 'failed'.

        Raises:
            ValueError: If the report_type is not supported or parameters are invalid.
        """
        self._validate_report_type(report_type)
        self._validate_format(output_format)

        if parameters is None:
            parameters = {}

        if not title:
            type_display = dict(Report.REPORT_TYPE_CHOICES).get(report_type, report_type)
            title = f"{type_display} - {timezone.now().strftime('%Y-%m-%d %H:%M')}"

        report = None

        try:
            with transaction.atomic():
                report_data = {
                    "report_type": report_type,
                    "title": title.strip() if isinstance(title, str) else title,
                    "parameters": parameters,
                    "status": "processing",
                    "format": output_format,
                    "data": {},
                }

                if user is not None and hasattr(user, "pk"):
                    report_data["generated_by"] = user

                report = Report.objects.create(**report_data)

            logger.info(
                "Report generation started: id=%s type=%s user=%s",
                report.pk,
                report_type,
                user,
            )

            generator = ReportGeneratorFactory.get_generator(report_type)
            result_data = generator.generate(parameters)

            with transaction.atomic():
                report.data = result_data
                report.status = "completed"
                report.generated_at = timezone.now()
                report.save(update_fields=["data", "status", "generated_at"])

            self._log_audit(
                entity_type="Report",
                entity_id=report.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={
                    "report_type": report_type,
                    "title": report.title,
                    "parameters": parameters,
                    "format": output_format,
                    "status": "completed",
                },
                ip_address=ip_address,
            )

            logger.info(
                "Report generation completed: id=%s type=%s user=%s",
                report.pk,
                report_type,
                user,
            )

            return report

        except ValueError:
            if report is not None:
                report.status = "failed"
                report.save(update_fields=["status"])
            raise

        except Exception as e:
            logger.error(
                "Report generation failed: type=%s user=%s error=%s",
                report_type,
                user,
                str(e),
                exc_info=True,
            )

            if report is not None:
                try:
                    report.status = "failed"
                    report.save(update_fields=["status"])
                except Exception:
                    logger.warning(
                        "Failed to update report status to 'failed': id=%s",
                        report.pk,
                        exc_info=True,
                    )

            self._log_audit(
                entity_type="Report",
                entity_id=report.pk if report else uuid.uuid4(),
                action=AuditLog.Action.CREATE,
                user=user,
                changes={
                    "report_type": report_type,
                    "title": title,
                    "parameters": parameters,
                    "format": output_format,
                    "status": "failed",
                    "error": str(e),
                },
                ip_address=ip_address,
            )

            raise

    def get_report(self, report_id: uuid.UUID, user=None) -> Optional[Report]:
        """
        Retrieve a single report by ID.

        Args:
            report_id: The UUID of the report to retrieve.
            user: Optional user for audit logging.

        Returns:
            The Report instance or None if not found.
        """
        try:
            report = Report.objects.select_related("generated_by").get(pk=report_id)

            logger.info(
                "Report retrieved: id=%s type=%s user=%s",
                report.pk,
                report.report_type,
                user,
            )

            return report

        except Report.DoesNotExist:
            logger.info(
                "Report not found: id=%s user=%s",
                report_id,
                user,
            )
            return None

    def list_reports(
        self,
        filters: Optional[Dict[str, Any]] = None,
        user=None,
    ):
        """
        List reports with optional filtering.

        Args:
            filters: Optional dictionary of filter parameters:
                - report_type: Filter by report type
                - status: Filter by status
                - generated_by: Filter by user who generated the report
                - date_from: Filter reports created from this date
                - date_to: Filter reports created up to this date
                - search: Search by title
            user: Optional user for context.

        Returns:
            A QuerySet of Report instances.
        """
        queryset = Report.objects.select_related("generated_by").all()

        if not filters:
            return queryset

        report_type = filters.get("report_type", "").strip() if filters.get("report_type") else ""
        if report_type:
            valid_types = [choice[0] for choice in Report.REPORT_TYPE_CHOICES]
            if report_type in valid_types:
                queryset = queryset.filter(report_type=report_type)

        status = filters.get("status", "").strip() if filters.get("status") else ""
        if status:
            valid_statuses = [choice[0] for choice in Report.STATUS_CHOICES]
            if status in valid_statuses:
                queryset = queryset.filter(status=status)

        generated_by = filters.get("generated_by")
        if generated_by is not None and str(generated_by).strip() != "":
            queryset = queryset.filter(generated_by_id=generated_by)

        date_from = filters.get("date_from")
        if date_from:
            if isinstance(date_from, str):
                queryset = queryset.filter(created_at__date__gte=date_from)
            else:
                queryset = queryset.filter(created_at__gte=date_from)

        date_to = filters.get("date_to")
        if date_to:
            if isinstance(date_to, str):
                queryset = queryset.filter(created_at__date__lte=date_to)
            else:
                queryset = queryset.filter(created_at__lte=date_to)

        search = filters.get("search", "").strip() if filters.get("search") else ""
        if search:
            queryset = queryset.filter(title__icontains=search)

        return queryset

    def list_report_types(self) -> List[Dict[str, str]]:
        """
        List all available report types with their descriptions.

        Returns:
            A list of dicts with 'type', 'description', and 'display_name' keys.
        """
        available_types = ReportGeneratorFactory.get_available_types()

        type_display_map = dict(Report.REPORT_TYPE_CHOICES)

        result = []
        for entry in available_types:
            report_type = entry["type"]
            result.append({
                "type": report_type,
                "description": entry.get("description", ""),
                "display_name": type_display_map.get(report_type, report_type),
            })

        return result

    def export_report(
        self,
        report_id: uuid.UUID,
        export_format: str,
        user=None,
        ip_address: Optional[str] = None,
    ):
        """
        Export a completed report in the specified format (CSV or PDF).

        Args:
            report_id: The UUID of the report to export.
            export_format: The export format ('csv' or 'pdf').
            user: The user requesting the export (for audit logging).
            ip_address: Optional IP address for audit logging.

        Returns:
            An HttpResponse with the exported file content.

        Raises:
            ValueError: If the report is not found, not completed, or format is invalid.
        """
        valid_export_formats = ("csv", "pdf")
        if export_format not in valid_export_formats:
            raise ValueError(
                f"Invalid export format '{export_format}'. "
                f"Must be one of: {', '.join(valid_export_formats)}"
            )

        report = self.get_report(report_id, user=user)
        if report is None:
            raise ValueError(f"Report with ID '{report_id}' not found.")

        if report.status != "completed":
            raise ValueError(
                f"Cannot export report with status '{report.status}'. "
                f"Only completed reports can be exported."
            )

        report_data = report.data
        if not report_data or not isinstance(report_data, dict):
            raise ValueError("Report has no data to export.")

        report_type_display = report.get_report_type_display()
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(
            c if c.isalnum() or c in ("-", "_", " ") else "_"
            for c in report.title
        ).strip().replace(" ", "_")[:50]

        if export_format == "csv":
            filename = f"{safe_title}_{timestamp}.csv"
            exporter = CSVExporter(filename=filename)

            try:
                response = exporter.export(report_data, include_summary=True)

                self._log_audit(
                    entity_type="Report",
                    entity_id=report.pk,
                    action=AuditLog.Action.EXPORT,
                    user=user,
                    changes={
                        "export_format": "csv",
                        "report_type": report.report_type,
                        "title": report.title,
                        "filename": filename,
                    },
                    ip_address=ip_address,
                )

                logger.info(
                    "Report exported as CSV: id=%s filename=%s user=%s",
                    report.pk,
                    filename,
                    user,
                )

                return response

            except Exception as e:
                logger.error(
                    "CSV export failed: report_id=%s error=%s",
                    report_id,
                    str(e),
                    exc_info=True,
                )
                raise ValueError(f"Failed to export report as CSV: {str(e)}") from e

        elif export_format == "pdf":
            filename = f"{safe_title}_{timestamp}.pdf"
            exporter = PDFExporter(filename=filename)

            extra_context = {
                "generated_by": "",
            }
            if report.generated_by:
                extra_context["generated_by"] = (
                    report.generated_by.get_full_name()
                    or str(report.generated_by.email)
                )

            if "title" not in report_data:
                report_data["title"] = report.title

            if report.parameters:
                if "date_range_start" not in report_data and "date_range_start" in report.parameters:
                    report_data["date_range_start"] = report.parameters["date_range_start"]
                if "date_range_end" not in report_data and "date_range_end" in report.parameters:
                    report_data["date_range_end"] = report.parameters["date_range_end"]

            try:
                response = exporter.export(report_data, extra_context=extra_context)

                self._log_audit(
                    entity_type="Report",
                    entity_id=report.pk,
                    action=AuditLog.Action.EXPORT,
                    user=user,
                    changes={
                        "export_format": "pdf",
                        "report_type": report.report_type,
                        "title": report.title,
                        "filename": filename,
                    },
                    ip_address=ip_address,
                )

                logger.info(
                    "Report exported as PDF: id=%s filename=%s user=%s",
                    report.pk,
                    filename,
                    user,
                )

                return response

            except ImportError:
                logger.error(
                    "PDF export failed: WeasyPrint not installed. report_id=%s",
                    report_id,
                )
                raise ValueError(
                    "PDF export is not available. WeasyPrint is not installed."
                )
            except Exception as e:
                logger.error(
                    "PDF export failed: report_id=%s error=%s",
                    report_id,
                    str(e),
                    exc_info=True,
                )
                raise ValueError(f"Failed to export report as PDF: {str(e)}") from e

    def delete_report(
        self,
        report_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a report by ID with audit logging.

        Args:
            report_id: The UUID of the report to delete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            True if deleted, False if not found.
        """
        report = self.get_report(report_id, user=user)
        if report is None:
            return False

        report_repr = str(report)
        report_pk = report.pk
        report_type = report.report_type
        report_title = report.title

        with transaction.atomic():
            report.delete()

            self._log_audit(
                entity_type="Report",
                entity_id=report_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={
                    "deleted": report_repr,
                    "report_type": report_type,
                    "title": report_title,
                },
                ip_address=ip_address,
            )

        logger.info(
            "Report deleted: id=%s type=%s user=%s",
            report_pk,
            report_type,
            user,
        )

        return True

    def archive_report(
        self,
        report_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Report]:
        """
        Archive a report by setting its status to 'archived'.

        Args:
            report_id: The UUID of the report to archive.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The archived Report instance, or None if not found.
        """
        report = self.get_report(report_id, user=user)
        if report is None:
            return None

        if report.status == "archived":
            return report

        old_status = report.status

        with transaction.atomic():
            report.status = "archived"
            report.save(update_fields=["status"])

            self._log_audit(
                entity_type="Report",
                entity_id=report.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes={
                    "status": {
                        "old": old_status,
                        "new": "archived",
                    },
                },
                ip_address=ip_address,
            )

        logger.info(
            "Report archived: id=%s type=%s user=%s",
            report.pk,
            report.report_type,
            user,
        )

        return report

    def get_recent_reports(self, user=None, limit: int = 10):
        """
        Get the most recent reports, optionally filtered by user.

        Args:
            user: Optional user to filter by generated_by.
            limit: Maximum number of reports to return.

        Returns:
            A QuerySet of Report instances.
        """
        queryset = Report.objects.select_related("generated_by").all()

        if user is not None and hasattr(user, "pk"):
            queryset = queryset.filter(generated_by=user)

        return queryset.order_by("-created_at")[:limit]

    def _validate_report_type(self, report_type: str) -> None:
        """Validate that the report type is supported."""
        valid_types = [choice[0] for choice in Report.REPORT_TYPE_CHOICES]
        if not report_type or report_type not in valid_types:
            supported = ", ".join(valid_types)
            raise ValueError(
                f"Invalid report type '{report_type}'. "
                f"Supported types: {supported}"
            )

    def _validate_format(self, output_format: str) -> None:
        """Validate that the output format is supported."""
        valid_formats = [choice[0] for choice in Report.FORMAT_CHOICES]
        if not output_format or output_format not in valid_formats:
            supported = ", ".join(valid_formats)
            raise ValueError(
                f"Invalid format '{output_format}'. "
                f"Supported formats: {supported}"
            )

    def _log_audit(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        user=None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Create an audit log entry. Failures are silently ignored."""
        try:
            audit_user = user if user is not None and hasattr(user, "pk") else None
            AuditLog.create_entry(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user=audit_user,
                changes=changes or {},
                ip_address=ip_address,
            )
        except Exception:
            logger.warning(
                "Failed to create audit log entry for %s %s",
                entity_type,
                entity_id,
                exc_info=True,
            )