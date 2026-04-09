from django.urls import path

from customers.views import (
    customer_create_view,
    customer_delete_view,
    customer_detail_view,
    customer_edit_view,
    customer_list_view,
)

urlpatterns = [
    path('', customer_list_view, name='customer-list'),
    path('create/', customer_create_view, name='customer-create'),
    path('<uuid:pk>/', customer_detail_view, name='customer-detail'),
    path('<uuid:pk>/edit/', customer_edit_view, name='customer-edit'),
    path('<uuid:pk>/delete/', customer_delete_view, name='customer-delete'),
]