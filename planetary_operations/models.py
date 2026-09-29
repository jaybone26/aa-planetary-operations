from django.conf import settings
from django.db import models


class CharacterSnapshot(models.Model):
    """Skills belong to the current AA ownership, not just an EVE character ID."""

    ownership = models.OneToOneField("authentication.CharacterOwnership", on_delete=models.CASCADE)
    owner_hash = models.CharField(max_length=64)
    skills = models.JSONField(default=dict)
    colonies = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)


class Plan(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Queued"
        RUNNING = "running", "Building"
        READY = "ready", "Ready"
        FAILED = "failed", "Needs attention"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    config = models.JSONField()
    character_ids = models.JSONField(default=list)
    character_snapshot = models.JSONField(default=list)
    replace_existing = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    result = models.JSONField(default=dict)
    valuation = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        permissions = [("basic_access", "Can use Planetary Operations")]

    def __str__(self):
        return self.name
