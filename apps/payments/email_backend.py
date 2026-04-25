"""
Backends email custom :

- ``EmailBackend`` (console UTF-8) corrige l'UnicodeEncodeError sur Windows
  où ``sys.stdout`` est en cp1252 et casse sur les caractères non-latin1
  (→, ², é…).

- ``CertifiSMTPBackend`` corrige l'erreur ``SSLCertVerificationError``
  rencontrée sur Python Microsoft Store / certains environnements Windows
  où Python n'utilise pas le bon trust store. Il force l'usage du bundle
  CA fourni par ``certifi`` (déjà installé en dépendance via ``requests``).
"""
from __future__ import annotations

import ssl
import sys

import certifi
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.core.mail.backends.smtp import EmailBackend as DjangoSMTPBackend


class EmailBackend(ConsoleEmailBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            self.stream = sys.stdout


class CertifiSMTPBackend(DjangoSMTPBackend):
    """
    SMTP backend qui utilise le CA bundle de certifi pour la validation SSL.
    Résout 'CERTIFICATE_VERIFY_FAILED' sur Python Microsoft Store / Windows
    sans avoir à installer de certificat racine au niveau système.

    En dernier recours (antivirus / proxy d'entreprise qui intercepte SSL),
    régler ``EMAIL_INSECURE_SKIP_VERIFY=True`` dans .env pour désactiver la
    vérification du certificat. À NE JAMAIS faire en production.
    """

    @property
    def ssl_context(self):
        from django.conf import settings
        if getattr(settings, "EMAIL_INSECURE_SKIP_VERIFY", False):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            return ctx
        return ssl.create_default_context(cafile=certifi.where())

    @ssl_context.setter
    def ssl_context(self, value):
        # Setter no-op : le parent assigne parfois None dans __init__.
        pass
