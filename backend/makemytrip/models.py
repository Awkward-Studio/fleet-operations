from django.db import models


class MMTLifecycleEventType(models.TextChoices):
    SEARCH = "SEARCH", "Search"
    MARKETPLACE_SEARCH = "MARKETPLACE_SEARCH", "Marketplace Search"
    BLOCK = "BLOCK", "Block"
    PAID = "PAID", "Paid"
    CANCEL = "CANCEL", "Cancel"
    CUSTOMER_ARRIVED = "CUSTOMER_ARRIVED", "Customer Arrived"
    BOOKING_DETAILS = "BOOKING_DETAILS", "Booking Details"


class MMTLifecycleEvent(models.Model):
    event_type = models.CharField(max_length=40, choices=MMTLifecycleEventType.choices)
    event_key = models.CharField(max_length=180, unique=True)
    request_hash = models.CharField(max_length=64)
    search_id = models.CharField(max_length=120, blank=True, db_index=True)
    partner_reference_number = models.CharField(max_length=120, blank=True, db_index=True)
    order_reference_number = models.CharField(max_length=120, blank=True, db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    normalized_facts = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    trip = models.ForeignKey(
        "fleet.Trip",
        null=True,
        blank=True,
        related_name="mmt_lifecycle_events",
        on_delete=models.SET_NULL,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["event_type", "search_id"]),
            models.Index(fields=["event_type", "order_reference_number"]),
        ]

    def __str__(self):
        return f"{self.event_type}:{self.event_key}"


class MMTBookingLifecycle(models.Model):
    search_id = models.CharField(max_length=120, blank=True, db_index=True)
    partner_reference_number = models.CharField(max_length=120, blank=True)
    order_reference_number = models.CharField(max_length=120, blank=True)
    trip = models.OneToOneField(
        "fleet.Trip",
        null=True,
        blank=True,
        related_name="mmt_lifecycle",
        on_delete=models.SET_NULL,
    )
    status = models.CharField(max_length=40, default="SEARCHED")
    search_payload = models.JSONField(default=dict, blank=True)
    block_payload = models.JSONField(default=dict, blank=True)
    paid_payload = models.JSONField(default=dict, blank=True)
    cancel_payload = models.JSONField(default=dict, blank=True)
    booking_details_payload = models.JSONField(default=dict, blank=True)
    normalized_facts = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["search_id"],
                condition=~models.Q(search_id=""),
                name="unique_mmt_lifecycle_search_id",
            ),
            models.UniqueConstraint(
                fields=["partner_reference_number"],
                condition=~models.Q(partner_reference_number=""),
                name="unique_mmt_lifecycle_partner_reference",
            ),
            models.UniqueConstraint(
                fields=["order_reference_number"],
                condition=~models.Q(order_reference_number=""),
                name="unique_mmt_lifecycle_order_reference",
            ),
        ]

    def __str__(self):
        ref = self.order_reference_number or self.partner_reference_number or self.search_id
        return f"MMT {ref or self.id} ({self.status})"
