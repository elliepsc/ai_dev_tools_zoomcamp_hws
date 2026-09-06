from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("datasets/<int:dataset_id>/refresh/", views.mark_refreshed, name="mark_refreshed"),
    path("history/", views.history, name="history"),
]
