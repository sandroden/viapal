from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver


@receiver(post_migrate)
def crea_gruppi_default(sender, **kwargs):
    # Crea i gruppi alla migrazione di auth (cosi' parte sempre la prima volta)
    if sender.label != 'auth':
        return
    Group.objects.get_or_create(name='proprietari')
    Group.objects.get_or_create(name='inquilini')
