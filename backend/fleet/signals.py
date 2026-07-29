from django.db.models.signals import post_delete
from django.dispatch import receiver
from fleet.models import Driver


@receiver(post_delete, sender=Driver)
def delete_user_on_driver_delete(sender, instance, **kwargs):
    """
    When a Driver instance is deleted, automatically delete the corresponding User account.
    """
    try:
        if instance.user:
            instance.user.delete()
    except Exception:
        pass
