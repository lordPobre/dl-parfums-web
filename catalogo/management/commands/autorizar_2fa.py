"""Autoriza a un usuario staff a registrar su app autenticadora (S7 de la auditoría de seguridad).

    python manage.py autorizar_2fa <usuario>              # usuario nuevo
    python manage.py autorizar_2fa <usuario> --reiniciar  # cambio o pérdida de teléfono

Lo mismo se puede hacer en el admin: Grupos → «Alta 2FA autorizada» → agregar al usuario.
Al confirmar su dispositivo, el usuario sale solo del grupo.
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_static.models import StaticDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.admin_2fa import GRUPO_ALTA


class Command(BaseCommand):
    help = "Autoriza a un usuario staff a registrar su app autenticadora. Con --reiniciar borra su 2FA actual."

    def add_arguments(self, parser):
        parser.add_argument("usuario")
        parser.add_argument("--reiniciar", action="store_true",
                            help="Borra su app autenticadora y sus códigos de respaldo actuales.")

    def handle(self, usuario, reiniciar, **opciones):
        User = get_user_model()
        u = User.objects.filter(username=usuario).first()
        if not u:
            raise CommandError(f"No existe el usuario «{usuario}».")
        if not u.is_staff:
            raise CommandError(f"«{usuario}» no es staff: no entra al admin.")
        if reiniciar:
            TOTPDevice.objects.filter(user=u).delete()
            StaticDevice.objects.filter(user=u).delete()
        grupo, _ = Group.objects.get_or_create(name=GRUPO_ALTA)
        u.groups.add(grupo)
        self.stdout.write(self.style.SUCCESS(
            f"«{usuario}» puede registrar su teléfono la próxima vez que entre al admin."
        ))
