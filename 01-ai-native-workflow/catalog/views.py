"""Views for the Dataset Freshness Tracker."""
from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Dataset, RefreshLog

# Sort order for the dashboard: problems first.
_SEVERITY = {"failing": 0, "never": 1, "stale": 2, "fresh": 3}


def dashboard(request):
    datasets = list(
        Dataset.objects.filter(is_active=True).select_related("source")
    )
    rows = []
    for ds in datasets:
        rows.append({"ds": ds, "status": ds.status(), "hours": ds.hours_since_success()})
    rows.sort(key=lambda r: (_SEVERITY.get(r["status"], 9), r["ds"].name))

    summary = {"fresh": 0, "stale": 0, "failing": 0, "never": 0}
    for r in rows:
        summary[r["status"]] = summary.get(r["status"], 0) + 1
    summary["total"] = len(rows)
    summary["attention"] = summary["stale"] + summary["failing"] + summary["never"]

    return render(
        request, "catalog/dashboard.html", {"rows": rows, "summary": summary}
    )


@require_POST
def mark_refreshed(request, dataset_id: int):
    ds = get_object_or_404(Dataset, pk=dataset_id, is_active=True)
    outcome = request.POST.get("outcome", "success")
    status = (
        RefreshLog.Status.FAILED
        if outcome == "failed"
        else RefreshLog.Status.SUCCESS
    )
    ds.log_refresh(status=status)
    if status == RefreshLog.Status.SUCCESS:
        messages.success(request, f"Logged a successful refresh for “{ds.name}”.")
    else:
        messages.error(request, f"Logged a FAILED refresh for “{ds.name}”.")
    return redirect("catalog:dashboard")


def history(request):
    logs = (
        RefreshLog.objects.select_related("dataset", "dataset__source")
        .order_by("-refreshed_at")[:100]
    )
    return render(request, "catalog/history.html", {"logs": logs})
