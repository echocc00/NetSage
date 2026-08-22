"""DRF serializer + viewset for NetworkDesign."""
from __future__ import annotations

from rest_framework import serializers, viewsets
from rest_framework.routers import DefaultRouter

from .models import NetworkDesign


class NetworkDesignSerializer(serializers.ModelSerializer):
    class Meta:
        model = NetworkDesign
        fields = "__all__"


class NetworkDesignViewSet(viewsets.ModelViewSet):
    queryset = NetworkDesign.objects.all()
    serializer_class = NetworkDesignSerializer
    filterset_fields = ["site", "scenario", "vendor", "created_by"]


router = DefaultRouter()
router.register(r"network-designs", NetworkDesignViewSet, basename="networkdesign")

urlpatterns = router.urls
