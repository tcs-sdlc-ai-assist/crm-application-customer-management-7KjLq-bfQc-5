from django.urls import path

from reports.views import (
    report_dashboard_view,
    report_delete_view,
    report_detail_view,
    report_export_view,
    report_generate_view,
    report_list_view,
)

urlpatterns = [
    path('', report_list_view, name='report-list'),
    path('dashboard/', report_dashboard_view, name='report-dashboard'),
    path('generate/', report_generate_view, name='report-generate'),
    path('<uuid:pk>/', report_detail_view, name='report-detail'),
    path('<uuid:pk>/delete/', report_delete_view, name='report-delete'),
    path('<uuid:pk>/export/<str:format>/', report_export_view, name='report-export'),
    path('<uuid:pk>/export/csv/', report_export_view, {'format': 'csv'}, name='report-export-csv'),
    path('<uuid:pk>/export/pdf/', report_export_view, {'format': 'pdf'}, name='report-export-pdf'),
]