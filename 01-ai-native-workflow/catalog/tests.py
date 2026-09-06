"""Tests for the Dataset Freshness Tracker.

Scenarios:
- status() returns NEVER / FRESH / STALE / FAILING correctly, including the rule
  that the latest *attempt* failing overrides an older success.
- SLA grace extends the freshness window.
- due_at() is based on the last success + cadence.
- mark_refreshed view logs a success/failure and redirects; requires POST.
- dashboard summary counts and severity ordering.
"""
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Dataset, RefreshLog, Source


def backdate(log, hours):
    RefreshLog.objects.filter(pk=log.pk).update(
        refreshed_at=timezone.now() - timedelta(hours=hours)
    )


class StatusTests(TestCase):
    def setUp(self):
        self.src = Source.objects.create(name="WH", kind="warehouse")

    def _ds(self, cadence="daily", grace=0):
        return Dataset.objects.create(source=self.src, name="d", cadence=cadence, sla_grace_hours=grace)

    def test_never_refreshed(self):
        ds = self._ds()
        self.assertEqual(ds.status(), Dataset.Status.NEVER)
        self.assertTrue(ds.needs_attention())
        self.assertIsNone(ds.due_at())
        self.assertIsNone(ds.hours_since_success())

    def test_fresh_after_recent_success(self):
        ds = self._ds(cadence="daily")
        backdate(ds.log_refresh("success"), hours=2)
        self.assertEqual(ds.status(), Dataset.Status.FRESH)
        self.assertFalse(ds.needs_attention())

    def test_stale_after_old_success(self):
        ds = self._ds(cadence="daily")
        backdate(ds.log_refresh("success"), hours=40)  # > 24h
        self.assertEqual(ds.status(), Dataset.Status.STALE)

    def test_failing_overrides_older_success(self):
        ds = self._ds(cadence="hourly")
        backdate(ds.log_refresh("success"), hours=5)
        backdate(ds.log_refresh("failed"), hours=1)  # latest = failed
        self.assertEqual(ds.status(), Dataset.Status.FAILING)

    def test_sla_grace_extends_window(self):
        ds = self._ds(cadence="daily", grace=24)  # 24 + 24 = 48h window
        backdate(ds.log_refresh("success"), hours=40)
        self.assertEqual(ds.status(), Dataset.Status.FRESH)  # within 48h

    def test_due_at_based_on_last_success(self):
        ds = self._ds(cadence="daily")
        log = ds.log_refresh("success")
        backdate(log, hours=0)
        log.refresh_from_db()
        expected = log.refreshed_at + timedelta(hours=24)
        self.assertEqual(ds.due_at(), expected)

    def test_hours_since_success_ignores_failures(self):
        ds = self._ds(cadence="daily")
        backdate(ds.log_refresh("success"), hours=10)
        backdate(ds.log_refresh("failed"), hours=1)
        self.assertAlmostEqual(ds.hours_since_success(), 10, delta=0.2)


class ViewTests(TestCase):
    def setUp(self):
        self.src = Source.objects.create(name="WH", kind="warehouse")
        self.ds = Dataset.objects.create(source=self.src, name="fct_orders", cadence="daily")

    def test_dashboard_renders(self):
        resp = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "fct_orders")

    def test_dashboard_summary_counts(self):
        # one fresh, one stale
        backdate(self.ds.log_refresh("success"), hours=2)
        stale = Dataset.objects.create(source=self.src, name="dim_customer", cadence="daily")
        backdate(stale.log_refresh("success"), hours=40)
        resp = self.client.get(reverse("catalog:dashboard"))
        self.assertEqual(resp.context["summary"]["fresh"], 1)
        self.assertEqual(resp.context["summary"]["stale"], 1)
        self.assertEqual(resp.context["summary"]["attention"], 1)

    def test_dashboard_orders_problems_first(self):
        backdate(self.ds.log_refresh("success"), hours=2)  # fresh
        failing = Dataset.objects.create(source=self.src, name="aaa_failing", cadence="daily")
        backdate(failing.log_refresh("failed"), hours=1)
        resp = self.client.get(reverse("catalog:dashboard"))
        first = resp.context["rows"][0]
        self.assertEqual(first["ds"], failing)  # failing sorts before fresh

    def test_mark_refreshed_success(self):
        resp = self.client.post(
            reverse("catalog:mark_refreshed", args=[self.ds.id]), {"outcome": "success"}
        )
        self.assertRedirects(resp, reverse("catalog:dashboard"))
        self.assertEqual(self.ds.refreshes.filter(status="success").count(), 1)
        self.assertEqual(self.ds.status(), Dataset.Status.FRESH)

    def test_mark_refreshed_failed(self):
        self.client.post(
            reverse("catalog:mark_refreshed", args=[self.ds.id]), {"outcome": "failed"}
        )
        self.assertEqual(self.ds.status(), Dataset.Status.FAILING)

    def test_mark_refreshed_requires_post(self):
        resp = self.client.get(reverse("catalog:mark_refreshed", args=[self.ds.id]))
        self.assertEqual(resp.status_code, 405)

    def test_history_renders(self):
        self.ds.log_refresh("success")
        resp = self.client.get(reverse("catalog:history"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "fct_orders")
