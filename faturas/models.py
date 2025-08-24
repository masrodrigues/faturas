from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Fatura(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "OPEN"
        CLOSED = "CLOSED", "CLOSED"
        FUTURE = "FUTURE", "FUTURE"
        CLOSED_NOT_DUE = "CLOSED_NOT_DUE", "CLOSED_NOT_DUE"

    account_id = models.CharField(max_length=20, db_index=True)
    statement_id = models.CharField(max_length=20, unique=True)

    status = models.CharField(max_length=20, choices=Status.choices)
    cycle = models.IntegerField(validators=[MinValueValidator(0)])
    cycle_closing_at = models.DateField()
    due_at = models.DateField()

    previous_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    debits = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    credits = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    amount_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    amount_paid_until_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    amount_paid_after_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    other_credits_until_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    other_credits_after_due = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    evolve_to_delinquency = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["account_id", "due_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.account_id} - {self.statement_id} - {self.status}"
