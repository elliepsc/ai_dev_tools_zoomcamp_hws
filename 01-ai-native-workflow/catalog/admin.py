from django.contrib import admin

from .models import Dataset, RefreshLog, Source


class DatasetInline(admin.TabularInline):
    model = Dataset
    extra = 0
    fields = ["name", "owner", "cadence", "sla_grace_hours", "is_active"]


@admin.register(Source)
class SourceAdmin(admin.ModelAdmin):
    list_display = ["name", "kind", "created_at"]
    list_filter = ["kind"]
    inlines = [DatasetInline]


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ["name", "source", "owner", "cadence", "status", "is_active"]
    list_filter = ["source", "cadence", "is_active"]
    search_fields = ["name", "owner"]

    @admin.display(description="Freshness")
    def status(self, obj):
        return obj.status()


@admin.register(RefreshLog)
class RefreshLogAdmin(admin.ModelAdmin):
    list_display = ["dataset", "status", "row_count", "refreshed_at"]
    list_filter = ["status", "dataset__source"]
    date_hierarchy = "refreshed_at"
