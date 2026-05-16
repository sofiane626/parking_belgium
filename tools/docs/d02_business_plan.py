"""
Document 02 — Business Plan.

Modèle économique : projet d'intérêt public financé par subvention régionale
(Région de Bruxelles-Capitale + Bruxelles Mobilité), service gratuit pour les
communes et les citoyens (pas de commission sur les paiements de carte).
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Business Plan",
        subtitle="Modèle économique, coûts, financement et rentabilité",
    )
    pdf.cover()

    # ----- Contexte ------------------------------------------------------
    pdf.h1("1. Contexte et positionnement")
    pdf.p(
        "Parking.Belgium est une plateforme web mutualisée pour la gestion des "
        "cartes de stationnement résidentielles, visiteurs et professionnelles "
        "valables dans les 19 communes de la Région de Bruxelles-Capitale. Elle "
        "remplace les 19 portails communaux actuels — fragmentés, hétérogènes, "
        "peu accessibles — par une expérience unifiée."
    )

    pdf.h2("Constat de marché")
    pdf.bullet("19 communes opèrent aujourd'hui chacune leur propre solution de gestion (Anderlecht, Etterbeek, parking.brussels, etc.) avec des UX et des règles fiscales différentes.")
    pdf.bullet("Le citoyen qui déménage de Schaerbeek à Ixelles doit recréer un compte, refournir ses pièces, payer à un nouvel opérateur — friction administrative.")
    pdf.bullet("Les scan-cars communaux interrogent des bases hétérogènes ; aucune API publique régionale standardisée n'existe.")
    pdf.bullet("Bruxelles Mobilité (administration régionale) opère parking.brussels pour la zone payante générale, mais sans intégration aux cartes résidentielles.")

    pdf.h2("Proposition de valeur")
    pdf.bullet("Pour le citoyen — un seul compte, une seule procédure, multilingue (FR/NL/EN), démarches < 10 min.")
    pdf.bullet("Pour les communes — externalisation de la maintenance technique, conformité RGPD garantie, journalisation auditée des actions.")
    pdf.bullet("Pour la Région — API publique standardisée pour les scan-cars, données ouvertes anonymisées pour la mobilité.")
    pdf.bullet("Pour le citoyen mobile (livreur, infirmier à domicile) — carte professionnelle valable dans la commune choisie sans démultiplier les démarches.")

    # ----- Modèle économique ---------------------------------------------
    pdf.h1("2. Modèle économique")

    pdf.h2("Mission de service public")
    pdf.p(
        "La gestion des cartes de stationnement résidentielles est une compétence "
        "communale, exercée dans le cadre d'une mission d'intérêt public (RGPD "
        "art. 6.1.e). Le service est par nature non-lucratif : il vise à "
        "organiser l'occupation rationnelle de l'espace public, pas à générer "
        "des profits commerciaux."
    )
    pdf.p(
        "Le modèle retenu est donc une plateforme financée par subvention "
        "publique régionale, gratuite à l'usage pour les communes et les "
        "citoyens. Le seul flux d'argent qui transite par le site est le "
        "paiement par les citoyens des cartes (riverain : ~10 €/an, "
        "professionnelle : ~50 €/an, visiteur : gratuit) — sommes intégralement "
        "reversées aux communes, sans commission prélevée par Parking.Belgium."
    )

    pdf.h2("Acteurs et flux financiers")
    pdf.table(
        headers=["Acteur", "Flux", "Sens"],
        rows=[
            ["Région bruxelloise", "Subvention annuelle de fonctionnement", "→ Plateforme"],
            ["19 communes", "Contribution clé NIS si la Région ne couvre pas tout", "→ Plateforme"],
            ["Citoyens", "Paiement des cartes (10–50 €/an)", "→ Stripe → commune"],
            ["Stripe", "Frais de transaction (~1,5 % + 0,25 €)", "← Plateforme"],
        ],
        col_widths=[40, 95, 39],
    )

    pdf.h2("Comparaison avec alternatives commerciales")
    pdf.p(
        "Un opérateur privé classique (SaaS B2G) facturerait typiquement un "
        "abonnement mensuel par commune (500–2 000 €/mois selon la taille) ou "
        "prélèverait 2 à 5 % sur chaque transaction. Dans le contexte "
        "bruxellois — service public, données sensibles, exigence RGPD forte — "
        "le modèle subvention reste le plus cohérent avec la nature de la "
        "mission et garantit l'absence de conflit d'intérêt."
    )

    # ----- Coûts ---------------------------------------------------------
    pdf.h1("3. Budget prévisionnel — coûts")

    pdf.h2("Coûts de développement initial (one-shot)")
    pdf.p(
        "Le développement initial est porté par le projet de fin d'études "
        "(temps étudiant non valorisé monétairement). Pour une mise en "
        "production réelle, le budget équivalent serait :"
    )
    pdf.table(
        headers=["Poste", "Détail", "Estimation"],
        rows=[
            ["Développement back-end", "Django/PostGIS/DRF, ~8 mois × 1 développeur senior", "60 000 €"],
            ["Développement front-end", "Tailwind + React-Leaflet (3 îlots), ~3 mois", "22 000 €"],
            ["Design UX/UI", "Wireframes, maquettes, design system, ~1 mois", "8 000 €"],
            ["Intégration GIS", "Récupération + traitement shapefiles 19 communes, ~1 mois", "7 000 €"],
            ["Tests + audit sécurité externe", "Pentest, audit RGPD, ~3 semaines", "8 000 €"],
            ["Documentation + i18n NL/EN", "Traduction certifiée 950 chaînes × 2 langues, manuels", "5 000 €"],
            ["Total développement initial", "", "110 000 €"],
        ],
        col_widths=[55, 75, 44],
    )

    pdf.h2("Coûts récurrents annuels")
    pdf.table(
        headers=["Poste", "Détail", "Estimation/an"],
        rows=[
            ["Hébergement applicatif", "VPS dédié (8 vCPU, 16 Go RAM) chez Scaleway BE/FR — 80 €/mois", "960 €"],
            ["Base de données managée", "PostgreSQL 17 + PostGIS — 60 €/mois (Scaleway DB)", "720 €"],
            ["CDN + protection DDoS", "Cloudflare Pro — 20 USD/mois", "240 €"],
            ["Backups + stockage S3", "100 Go Scaleway Object Storage", "120 €"],
            ["Nom de domaine", "parking.belgium ou parking.brussels — registrar BE", "15 €"],
            ["Certificat SSL", "Let's Encrypt — automatisé via Certbot", "0 €"],
            ["Stripe (frais transaction)", "~50 000 paiements/an × 1,5 % × 15 € moyen + 0,25 € fixe", "23 750 €"],
            ["SMTP transactionnel", "SendGrid Essentials — 50k mails/mois", "240 €"],
            ["Monitoring + alerting", "Sentry team plan + UptimeRobot", "360 €"],
            ["Maintenance corrective", "0,5 ETP développeur ~ 6 mois × 5 000 €", "30 000 €"],
            ["Maintenance évolutive", "0,3 ETP (nouvelles fonctionnalités, mises à jour)", "18 000 €"],
            ["Support utilisateur", "1 agent niveau 1 mutualisé (0,3 ETP)", "12 000 €"],
            ["Conformité RGPD (DPO)", "Audit annuel + DPIA", "5 000 €"],
            ["Hébergement React/static", "Inclus dans VPS (WhiteNoise)", "0 €"],
            ["Total coûts récurrents", "", "91 405 €/an"],
        ],
        col_widths=[55, 85, 34],
    )

    pdf.p(
        "Note importante : le poste Stripe est calculé sur un volume "
        "prévisionnel de 50 000 paiements/an (sur les ~400 000 ménages "
        "bruxellois, environ 12 % détiennent une carte riverain payante). Il "
        "est entièrement répercuté sur le coût de la carte (la commune le "
        "facture au citoyen) — il n'est donc pas un coût net pour la "
        "plateforme."
    )

    pdf.h2("Coût net annuel hors transaction Stripe")
    pdf.kv("Coûts récurrents totaux", "91 405 €")
    pdf.kv("− Frais Stripe (refacturés)", "− 23 750 €")
    pdf.kv("Coût net à financer par subvention", "67 655 € / an")

    # ----- Financement ---------------------------------------------------
    pdf.h1("4. Financement")

    pdf.h2("Source principale : subvention Bruxelles Mobilité")
    pdf.p(
        "Bruxelles Mobilité opère déjà parking.brussels (gestion de la zone "
        "payante générale, smart parking). Parking.Belgium s'inscrit comme "
        "complément logique : alors que parking.brussels gère la voirie "
        "horodatée, Parking.Belgium gère les droits permanents (cartes "
        "résidentielles, professionnelles, visiteurs)."
    )
    pdf.p(
        "Une subvention annuelle de fonctionnement de l'ordre de 70 000 € "
        "couvre l'intégralité des coûts récurrents nets. Le développement "
        "initial (110 000 €) est porté ponctuellement par une enveloppe "
        "d'investissement régionale dans le cadre du plan Good Move 2030."
    )

    pdf.h2("Sources complémentaires")
    pdf.bullet("Cofinancement européen — Fonds européen de développement régional (FEDER), volet « mobilité urbaine durable ». Subvention pouvant couvrir 30 à 50 % du développement initial.")
    pdf.bullet("Quote-part communale — si la Région ne finance que la moitié, les 19 communes peuvent contribuer au prorata de leur population (clé NIS). Anderlecht (~120 000 hab.) contribuerait ~5 500 €/an, Saint-Josse (~25 000 hab.) ~1 100 €/an.")
    pdf.bullet("Vente de données anonymisées (Open Data) — la Région peut commercialiser certains agrégats anonymes (taux d'occupation par zone, par exemple) sous licence Etalab à des opérateurs de mobilité (Waze, Google Maps, opérateurs de scan-cars). Recette estimée : 5 000–15 000 €/an.")

    pdf.h2("Pas de modèle de monétisation directe envers le citoyen")
    pdf.p(
        "Conformément à l'éthique d'un service public, aucune publicité, "
        "aucun tracking commercial, aucune revente de données personnelles. "
        "Le coût de la carte reste celui défini par chaque commune (politique "
        "locale), sans surcharge de plateforme."
    )

    # ----- Rentabilité ---------------------------------------------------
    pdf.h1("5. Rentabilité et indicateurs")

    pdf.h2("ROI pour la collectivité")
    pdf.p(
        "Le retour sur investissement n'est pas mesuré en bénéfice "
        "financier (le projet n'en génère pas), mais en gains d'efficience "
        "publique :"
    )
    pdf.bullet("Économies d'échelle — mutualisation de l'infrastructure technique (1 plateforme vs 19) : économie estimée à 200 000 € de coûts cumulés évités sur les budgets communaux annuels.")
    pdf.bullet("Réduction du temps administratif — la dématérialisation complète des cartes riverain économise ~3 ETP back-office sur les 19 communes (estimation 150 000 €/an).")
    pdf.bullet("Conformité RGPD garantie — externalisation du risque légal vers une plateforme auditée centralement.")
    pdf.bullet("Disponibilité 24/7 — démarches accessibles hors heures de bureau, sans déplacement physique.")

    pdf.h2("Indicateurs de suivi (KPI)")
    pdf.bullet("Nombre de cartes actives par commune (équité de service).")
    pdf.bullet("Taux d'approbation automatique vs revue manuelle (efficacité de l'engine d'attribution, cible > 80 %).")
    pdf.bullet("Temps moyen de traitement d'une demande en revue manuelle (cible < 48 h).")
    pdf.bullet("Volume d'appels API check-right par scan-car (suivi de l'adoption).")
    pdf.bullet("Taux de satisfaction citoyen (NPS — enquête semestrielle, cible > 50).")
    pdf.bullet("Coût de fonctionnement par carte délivrée (cible < 2 €).")
    pdf.bullet("Taux de disponibilité (SLA cible 99,5 % en production).")

    pdf.h2("Seuil d'autonomie financière")
    pdf.p(
        "Étant un service public, le projet n'a pas vocation à être "
        "autofinancé sur ses recettes. Le seuil de pérennité correspond à "
        "l'inscription du financement de fonctionnement (67 655 €/an) dans "
        "le budget récurrent de Bruxelles Mobilité — soit ~0,02 % de son "
        "budget annuel (estimé à 350 M€)."
    )

    # ----- Risques -------------------------------------------------------
    pdf.h1("6. Analyse des risques")

    pdf.h2("Risques techniques")
    pdf.bullet("Migration progressive des 19 communes — risque de cohabitation prolongée avec les systèmes existants. Mitigation : phases pilotes avec 3 communes volontaires sur 6 mois avant déploiement régional.")
    pdf.bullet("Évolution des données GIS — un changement de zonage par une commune nécessite un nouveau shapefile + import. Mitigation : gestion versionnée (GISSourceVersion) + cohabitation pendant la transition.")
    pdf.bullet("Disponibilité de Stripe — dépendance à un acteur externe pour les paiements. Mitigation : double rail (Stripe + paiement interne simulé pour DEBUG / mode dégradé).")

    pdf.h2("Risques juridiques")
    pdf.bullet("Modification du règlement RGPD européen — exigence de relecture annuelle de la DPIA et de la politique de confidentialité.")
    pdf.bullet("Recours sur l'attribution automatique de zones — si un citoyen conteste sa zone attribuée. Mitigation : journal d'audit complet + procédure de revue manuelle déclenchable.")
    pdf.bullet("Marchés publics — un projet d'intérêt général financé par fonds publics doit respecter les règles de marché public belge. Mitigation : montage en régie ou via in-house.")

    pdf.h2("Risques organisationnels")
    pdf.bullet("Adhésion politique — l'adoption par les 19 communes dépend de l'accord politique de chacune. Mitigation : commencer par les communes alignées politiquement avec Bruxelles Mobilité.")
    pdf.bullet("Continuité après TFE — projet académique sans structure juridique d'exploitation. Mitigation : remise du code source à Bruxelles Mobilité ou à une asbl mandataire.")
    pdf.bullet("Multilinguisme NL — exigence légale en Région bruxelloise. Mitigation : traductions à 100 % validées par traducteurs certifiés avant mise en production.")

    # ----- Conclusion ---------------------------------------------------
    pdf.h1("7. Conclusion")
    pdf.p(
        "Parking.Belgium est viable comme service public mutualisé financé "
        "par subvention régionale. Le coût d'exploitation net (~68 000 €/an) "
        "représente une fraction négligeable du budget de Bruxelles Mobilité "
        "et génère des économies d'échelle largement supérieures (estimées à "
        "350 000 €/an cumulés sur les 19 communes)."
    )
    pdf.p(
        "Le projet académique a démontré la faisabilité technique. La phase "
        "suivante est l'inscription dans la stratégie régionale Good Move "
        "(commande politique + arbitrage budgétaire 2026-2028)."
    )

    return str(save_to(pdf, "02_business_plan.pdf"))


if __name__ == "__main__":
    print(generate())
