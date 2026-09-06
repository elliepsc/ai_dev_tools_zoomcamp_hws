"""Seed a demo catalog with a realistic mix of freshness states.

Usage: python manage.py seed_demo
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.models import Dataset, RefreshLog, Source


class Command(BaseCommand):
    help = "Create demo sources, datasets, and refresh logs (fresh/stale/failing/never)."

    def handle(self, *args, **options):
        Source.objects.all().delete()  # demo reset

        wh = Source.objects.create(name="Snowflake · ANALYTICS", kind="warehouse")
        api = Source.objects.create(name="Stripe API", kind="api")
        files = Source.objects.create(name="S3 · raw-drops", kind="file")

        now = timezone.now()

        def backdated(ds, hours_ago, status="success"):
            log = ds.log_refresh(status=status)
            RefreshLog.objects.filter(pk=log.pk).update(
                refreshed_at=now - timedelta(hours=hours_ago)
            )

        # Fresh: daily dataset refreshed 2h ago
        d1 = Dataset.objects.create(source=wh, name="fct_orders", owner="Data Eng", cadence="daily")
        backdated(d1, 2)

        # Stale: daily dataset last success 40h ago (> 24h)
        d2 = Dataset.objects.create(source=wh, name="dim_customer", owner="Data Eng", cadence="daily")
        backdated(d2, 40)

        # Failing: last attempt failed (even though an older one succeeded)
        d3 = Dataset.objects.create(source=api, name="stripe_charges", owner="Finance", cadence="hourly")
        backdated(d3, 5)                 # old success
        backdated(d3, 1, status="failed")  # latest = failed

        # Never refreshed
        Dataset.objects.create(source=files, name="marketing_leads.csv", owner="Growth", cadence="weekly")

        # Fresh weekly with grace
        d5 = Dataset.objects.create(
            source=wh, name="agg_revenue_weekly", owner="Analytics", cadence="weekly", sla_grace_hours=12
        )
        backdated(d5, 100)

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Source.objects.count()} sources, {Dataset.objects.count()} datasets, "
            f"{RefreshLog.objects.count()} refresh logs."
        ))
