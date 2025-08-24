from django.contrib import admin
from .models import Fatura

@admin.register(Fatura)
class FaturaAdmin(admin.ModelAdmin):
    list_display = ("account_id","statement_id","status","cycle","cycle_closing_at","due_at","amount_due","current_balance","evolve_to_delinquency")
    search_fields = ("account_id","statement_id")
    list_filter = ("status","cycle_closing_at","due_at","evolve_to_delinquency")
