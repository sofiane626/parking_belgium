"""
Sitemaps pour les moteurs de recherche.

Inclut seulement les pages publiques (pas d'URLs nécessitant un login).
Pour le multilingue : Django sitemap génère une URL par (objet, langue active),
ce qui combiné avec hreflang dans <head> donne une indexation correcte.
"""
from __future__ import annotations

from django.contrib.sitemaps import Sitemap
from django.urls import reverse


class StaticViewSitemap(Sitemap):
    """Pages publiques avec URL statique."""
    priority = 0.8
    changefreq = "monthly"
    protocol = "https"

    def items(self):
        return [
            ("core:home", 1.0, "weekly"),
            ("gis_data:map", 0.9, "weekly"),
            ("core:legal_privacy", 0.4, "yearly"),
            ("core:legal_terms", 0.4, "yearly"),
            ("accounts:login", 0.5, "yearly"),
            ("accounts:register", 0.7, "monthly"),
        ]

    def location(self, item):
        return reverse(item[0])

    def priority(self, item):  # noqa: F811 — overrides class attribute
        return item[1]

    def changefreq(self, item):  # noqa: F811
        return item[2]
