from django.urls import path

from . import views

app_name = "planetary_operations"
urlpatterns = [
    path("", views.index, name="index"),
    path("authorize/", views.authorize, name="authorize"),
    path("characters/<int:character_id>/refresh/", views.refresh, name="refresh"),
    path("plans/<int:pk>/", views.detail, name="detail"),
    path("plans/<int:pk>/status/", views.status, name="status"),
    path("plans/<int:pk>/export/", views.export, name="export"),
    path("plans/<int:pk>/prices/", views.prices, name="prices"),
    path("plans/<int:pk>/delete/", views.delete, name="delete"),
]
