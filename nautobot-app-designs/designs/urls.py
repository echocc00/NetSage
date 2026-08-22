from django.urls import include, path

urlpatterns = [
    path("designs/", include("designs.api")),
]
