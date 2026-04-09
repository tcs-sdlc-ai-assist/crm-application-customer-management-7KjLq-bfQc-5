from django.urls import path

from deals.views import (
    deal_assign_view,
    deal_create_view,
    deal_delete_view,
    deal_detail_view,
    deal_edit_view,
    deal_list_view,
    deal_stage_update_view,
    pipeline_list_view,
    sales_stage_create_view,
    sales_stage_delete_view,
    sales_stage_edit_view,
    sales_stage_list_view,
)

urlpatterns = [
    path('', deal_list_view, name='deal-list'),
    path('create/', deal_create_view, name='deal-create'),
    path('<uuid:pk>/', deal_detail_view, name='deal-detail'),
    path('<uuid:pk>/edit/', deal_edit_view, name='deal-update'),
    path('<uuid:pk>/delete/', deal_delete_view, name='deal-delete'),
    path('<uuid:pk>/assign/', deal_assign_view, name='deal-assign-owner'),
    path('<uuid:pk>/stage/', deal_stage_update_view, name='deal-stage-update'),
    path('pipeline/', pipeline_list_view, name='pipeline-list'),
    path('stages/', sales_stage_list_view, name='sales-stage-list'),
    path('stages/create/', sales_stage_create_view, name='sales-stage-create'),
    path('stages/<uuid:pk>/edit/', sales_stage_edit_view, name='sales-stage-update'),
    path('stages/<uuid:pk>/delete/', sales_stage_delete_view, name='sales-stage-delete'),
]