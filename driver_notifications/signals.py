from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import Ticket
from .ticket_cleanup import queue_ticket_cleanup


@receiver(pre_delete, sender=Ticket)
def ticket_deleted(sender, instance, **kwargs):
    # Capture Telegram message IDs before Notification's cascade removes them.
    queue_ticket_cleanup(instance.pk, instance.owner_id)
