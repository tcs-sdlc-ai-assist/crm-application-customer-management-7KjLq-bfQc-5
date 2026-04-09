from django.urls import path

from accounts.views import (
    login_view,
    logout_view,
    profile_edit_view,
    profile_view,
    register_view,
    user_detail_view,
    user_list_view,
    user_update_view,
)

urlpatterns = [
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('register/', register_view, name='register'),
    path('profile/', profile_view, name='profile'),
    path('profile/edit/', profile_edit_view, name='profile-edit'),
    path('users/', user_list_view, name='user-list'),
    path('users/create/', register_view, name='user-create'),
    path('users/<uuid:pk>/', user_detail_view, name='user-detail'),
    path('users/<uuid:pk>/edit/', user_update_view, name='user-update'),
]