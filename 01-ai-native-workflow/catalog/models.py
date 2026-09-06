"""Data models for the Dataset Freshness Tracker.

The tool answers one question a data team asks constantly: *which of our datasets
are stale or failing right now?* A Dataset declares an expected refresh cadence and
an SLA; each refresh attempt is logged; freshness is derived from the last
*successful* refresh versus the cadence. See _docs/plan.md.
"""
from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone


class Source(models.Model):
    """Where a dataset comes from (a warehouse schema, an API, a file drop...)."""

    class Kind(models.TextChoices):
        WAREHOUSE = "warehouse", "Warehouse"
        API = "api", "API"
        FILE = "file", "File / storage"
        STREAM = "stream", "Stream"

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.WAREHOUSE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Dataset(models.Model):
    """A tracked dataset with an expected refresh cadence."""

    class Cadence(models.TextChoices):
        HOURLY = "hourly", "Hourly"
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"
        MONTHLY = "monthly", "Monthly"

    # Expected time between successful refreshes, in hours.
    CADENCE_HOURS = {"hourly": 1, "daily": 24, "weekly": 24 * 7, "monthly": 24 * 30}

    class Status(models.TextChoices):
        FRESH = "fresh", "Fresh"
        STALE = "stale", "Stale"
        FAILING = "failing", "Failing"
        NEVER = "never", "Never refreshed"

    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="datasets")
    name = models.CharField(max_length=160)
    owner = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    cadence = models.CharField(
        max_length=10, choices=Cadence.choices, default=Cadence.DAILY
    )
    # Grace period (hours) added on top of the cadence before a dataset is "stale".
    sla_grace_hours = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    # --- freshness logic --------------------------------------------------
    @property
    def cadence_hours(self) -> int:
        return self.CADENCE_HOURS[self.cadence]

    def last_refresh(self):
        return self.refreshes.order_by("-refreshed_at").first()

    def last_success(self):
        return self.refreshes.filter(status=RefreshLog.Status.SUCCESS).order_by(
            "-refreshed_at"
        ).first()

    def due_at(self):
        """When the next successful refresh is expected.

        Based on the last successful refresh + cadence + SLA grace. If there has
        never been a successful refresh, it is already due (returns None to mean
        'immediately / never met').
        """
        last = self.last_success()
        if last is None:
            return None
        return last.refreshed_at + timedelta(
            hours=self.cadence_hours + self.sla_grace_hours
        )

    def status(self) -> str:
        """Derive freshness status.

        Order matters: a dataset whose *latest* attempt failed is FAILING even if a
        previous run succeeded — the team needs to see the breakage.
        """
        last = self.last_refresh()
        if last is None:
            return self.Status.NEVER
        if last.status == RefreshLog.Status.FAILED:
            return self.Status.FAILING
        due = self.due_at()
        if due is not None and timezone.now() > due:
            return self.Status.STALE
        return self.Status.FRESH

    def needs_attention(self) -> bool:
        return self.status() in {self.Status.STALE, self.Status.FAILING, self.Status.NEVER}

    def hours_since_success(self):
        last = self.last_success()
        if last is None:
            return None
        delta = timezone.now() - last.refreshed_at
        return round(delta.total_seconds() / 3600, 1)

    # --- actions ----------------------------------------------------------
    def log_refresh(self, status: str = "success", row_count=None, note: str = ""):
        """Record a refresh attempt (success by default)."""
        return RefreshLog.objects.create(
            dataset=self, status=status, row_count=row_count, note=note
        )


class RefreshLog(models.Model):
    """One refresh attempt for a dataset."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"

    dataset = models.ForeignKey(
        Dataset, on_delete=models.CASCADE, related_name="refreshes"
    )
    refreshed_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.SUCCESS
    )
    row_count = models.PositiveIntegerField(null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-refreshed_at"]

    def __str__(self) -> str:
        return f"{self.dataset} · {self.status} @ {self.refreshed_at:%Y-%m-%d %H:%M}"
