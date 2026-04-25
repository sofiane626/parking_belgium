from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    CITIZEN = "citizen", _("Citoyen")
    AGENT = "agent", _("Agent")
    ADMIN = "admin", _("Admin")
    SUPER_ADMIN = "super_admin", _("Super Admin")


class User(AbstractUser):
    """
    Custom user. New signups default to ``Role.CITIZEN``.

    Back-office roles (agent / admin / super_admin) are assigned by an existing
    admin — never granted on self-service registration.
    """

    role = models.CharField(
        _("rôle"),
        max_length=20,
        choices=Role.choices,
        default=Role.CITIZEN,
    )

    @property
    def is_citizen(self) -> bool:
        return self.role == Role.CITIZEN

    @property
    def is_agent(self) -> bool:
        return self.role == Role.AGENT

    @property
    def is_admin_role(self) -> bool:
        return self.role == Role.ADMIN

    @property
    def is_super_admin(self) -> bool:
        return self.role == Role.SUPER_ADMIN

    @property
    def is_back_office(self) -> bool:
        return self.role in {Role.AGENT, Role.ADMIN, Role.SUPER_ADMIN}
