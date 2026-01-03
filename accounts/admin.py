from django.contrib import admin

from .models import UserAccount


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = ("user", "pending_deletion", "deletion_requested_at", "created_at")
    list_filter = ("pending_deletion",)
    search_fields = ("user__email", "user__username")
