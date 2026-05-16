"""
Document 01 — Cahier de charges fonctionnel.

Fonctionnalités groupées par acteur, exprimées sous la forme Verbe-Complément.
Inclut les contraintes TFE : back-office, multilinguisme, API sécurisée, paiement.
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Cahier de charges fonctionnel",
        subtitle="Plateforme Parking.Belgium — gestion des cartes de stationnement",
    )
    pdf.cover()

    # ----- Introduction --------------------------------------------------
    pdf.h1("1. Présentation du projet")
    pdf.p(
        "Parking.Belgium est une plateforme web unique pour la gestion des cartes de "
        "stationnement des 19 communes de la Région de Bruxelles-Capitale. Elle "
        "remplace les 19 sites isolés actuels (un par commune) par une expérience "
        "centralisée, multilingue (FR/NL/EN), avec attribution automatique des "
        "zones selon l'adresse du citoyen et paiement en ligne via Stripe."
    )
    pdf.p(
        "Le projet couvre les contraintes obligatoires du TFE : back-office de "
        "gestion par rôle, multilinguisme natif, API REST sécurisée (DRF + token + "
        "throttling), intégration d'une solution de paiement (Stripe Checkout)."
    )

    pdf.h2("Acteurs identifiés")
    pdf.bullet("Citoyen — résident bruxellois ou professionnel exerçant en Région bruxelloise.")
    pdf.bullet("Agent — fonctionnaire communal habilité à traiter les dossiers en revue manuelle.")
    pdf.bullet("Admin — administrateur d'une commune ou de la Région ; configure les politiques métier.")
    pdf.bullet("Super-admin — autorité régionale ; promeut/révoque les admins, supervise toutes les communes.")
    pdf.bullet("Système (cron / scan-car) — agents non humains : expiration automatique, vérification des plaques.")

    # ----- Citoyen --------------------------------------------------------
    pdf.h1("2. Fonctionnalités — Citoyen")

    pdf.h2("Gestion du compte")
    pdf.bullet("Créer un compte citoyen avec son adresse principale à Bruxelles.")
    pdf.bullet("Se connecter / Se déconnecter.")
    pdf.bullet("Modifier son mot de passe.")
    pdf.bullet("Réinitialiser son mot de passe par email (token signé valide 3 jours).")
    pdf.bullet("Modifier son profil (téléphone, date de naissance, numéro de registre national).")
    pdf.bullet("Choisir sa langue préférée (FR, NL, EN) appliquée à l'interface et aux emails.")
    pdf.bullet("Accepter la politique de confidentialité et les CGU à l'inscription (RGPD art. 6.1.a).")
    pdf.bullet("Supprimer son compte (anonymisation après période de rétention comptable).")

    pdf.h2("Gestion des véhicules")
    pdf.bullet("Ajouter un véhicule (plaque, marque, modèle, certificat d'immatriculation).")
    pdf.bullet("Modifier les détails d'un véhicule.")
    pdf.bullet("Archiver un véhicule (avec motif optionnel) — refuse l'archivage si des cartes actives sont liées.")
    pdf.bullet("Restaurer un véhicule archivé.")
    pdf.bullet("Demander un changement de plaque (avec validation agent + nouveau certificat).")

    pdf.h2("Gestion de l'adresse")
    pdf.bullet("Demander un changement d'adresse (avec validation agent — suspend automatiquement les cartes riverain liées à l'ancienne adresse).")
    pdf.bullet("Annuler une demande de changement d'adresse en cours.")

    pdf.h2("Gestion des cartes de stationnement")
    pdf.bullet("Demander une carte riverain (attribution automatique de la zone selon l'adresse géocodée).")
    pdf.bullet("Demander une carte visiteur (gratuite, valable du 1ᵉʳ janvier au 1ᵉʳ décembre).")
    pdf.bullet("Demander une carte professionnelle (commune cible choisie, revue manuelle par un agent).")
    pdf.bullet("Suivre l'avancement d'une demande (brouillon, soumise, revue manuelle, en attente de paiement, active, refusée, expirée, annulée, suspendue).")
    pdf.bullet("Annuler une demande tant qu'elle n'est pas encore active.")
    pdf.bullet("Consulter le détail d'une carte active (zones autorisées, validité, montant payé).")
    pdf.bullet("Générer un code visiteur pour une plaque tierce (durée 1 à 72 h, jusqu'à 100 codes/an).")
    pdf.bullet("Annuler un code visiteur en cours.")

    pdf.h2("Paiement")
    pdf.bullet("Payer une carte via Stripe Checkout (Bancontact, Visa, Mastercard, Amex).")
    pdf.bullet("Payer via le formulaire interne (validation Luhn, sans saisie de coordonnées sur le serveur).")
    pdf.bullet("Recevoir un email de confirmation après paiement (avec détail de la carte et des zones).")

    pdf.h2("Consultation de la cartographie")
    pdf.bullet("Visualiser la carte interactive des zones de stationnement (Leaflet + react-leaflet).")
    pdf.bullet("Filtrer les zones par commune.")
    pdf.bullet("Rechercher une zone par zonecode.")
    pdf.bullet("Consulter les détails d'une zone (commune, superficie, codes associés).")

    pdf.h2("Gestion des entreprises (pour cartes pro)")
    pdf.bullet("Ajouter une entreprise (dénomination, numéro de TVA BE0XXXXXXXXX).")
    pdf.bullet("Modifier les informations d'une entreprise.")
    pdf.bullet("Supprimer une entreprise (refuse si elle a des cartes pro actives).")

    # ----- Agent ---------------------------------------------------------
    pdf.h1("3. Fonctionnalités — Agent")

    pdf.h2("Traitement des demandes")
    pdf.bullet("Consulter la file des demandes en attente de revue manuelle.")
    pdf.bullet("Approuver une carte en revue manuelle (passe en attente de paiement).")
    pdf.bullet("Refuser une carte en revue manuelle avec une note de décision obligatoire.")
    pdf.bullet("Ajouter une zone secondaire à une carte avant approbation.")
    pdf.bullet("Retirer une zone d'une carte avant approbation.")
    pdf.bullet("Consulter le détail d'une demande (citoyen, véhicule, adresse, attribution proposée par l'engine).")

    pdf.h2("Validation des changements")
    pdf.bullet("Approuver un changement d'adresse (déclenche la suspension automatique des cartes riverain liées).")
    pdf.bullet("Refuser un changement d'adresse avec motif.")
    pdf.bullet("Approuver un changement de plaque (met à jour le véhicule).")
    pdf.bullet("Refuser un changement de plaque avec motif.")

    pdf.h2("Édition des cartes actives")
    pdf.bullet("Mettre à jour la date de fin de validité d'une carte (ACTIVE ou SUSPENDED).")
    pdf.bullet("Remplacer la zone principale d'une carte par un nouveau code zone.")
    pdf.bullet("Suspendre une carte avec raison obligatoire (annule les codes visiteurs actifs liés).")
    pdf.bullet("Réactiver une carte suspendue.")
    pdf.bullet("Annuler un code visiteur émis par un citoyen.")

    # ----- Admin ---------------------------------------------------------
    pdf.h1("4. Fonctionnalités — Admin")

    pdf.h2("Configuration globale")
    pdf.bullet("Modifier la configuration globale (prix par défaut, limites véhicules/cartes par citoyen, durée des codes visiteurs).")

    pdf.h2("Politiques par commune")
    pdf.bullet("Créer une politique (commune × type de carte) avec stratégie tarifaire (fixe / grille / exponentielle), validité et limites spécifiques.")
    pdf.bullet("Modifier une politique existante.")
    pdf.bullet("Supprimer une politique.")
    pdf.bullet("Programmer un changement futur via les champs effective_from / effective_until.")

    pdf.h2("Données GIS")
    pdf.bullet("Importer un fichier shapefile/OSM contenant les polygones de stationnement (commande management).")
    pdf.bullet("Activer une version GIS (désactive automatiquement les précédentes).")
    pdf.bullet("Consulter la liste des versions GIS et des polygones par version.")
    pdf.bullet("Créer une règle d'attribution sur un polygone (override du zonecode, restriction par type de carte, motif).")
    pdf.bullet("Modifier ou supprimer une règle d'attribution.")
    pdf.bullet("Activer/désactiver une règle.")

    pdf.h2("Gestion des utilisateurs")
    pdf.bullet("Lister les utilisateurs avec filtres par rôle + recherche.")
    pdf.bullet("Inclure ou exclure les comptes désactivés.")
    pdf.bullet("Modifier les informations de base d'un utilisateur (nom, prénom, email).")
    pdf.bullet("Changer le rôle d'un utilisateur (selon hiérarchie : admin ne peut pas promouvoir un autre admin).")
    pdf.bullet("Désactiver / Réactiver un compte utilisateur.")
    pdf.bullet("Déclencher un email de réinitialisation de mot de passe pour un utilisateur.")

    pdf.h2("Tokens API")
    pdf.bullet("Émettre un token API pour un compte back-office (agent ou admin).")
    pdf.bullet("Révoquer un token API existant.")

    pdf.h2("Journal d'audit")
    pdf.bullet("Consulter le journal d'audit (datatable React avec filtres temps réel).")
    pdf.bullet("Filtrer les entrées par action, sévérité, type de cible, acteur, date.")
    pdf.bullet("Exporter le journal filtré au format CSV.")

    pdf.h2("Exports CSV")
    pdf.bullet("Exporter la liste des cartes (avec filtres appliqués).")
    pdf.bullet("Exporter la liste des paiements.")
    pdf.bullet("Exporter la liste des utilisateurs.")
    pdf.bullet("Exporter la liste des demandes de changement (adresse + plaque).")

    # ----- Super-admin ----------------------------------------------------
    pdf.h1("5. Fonctionnalités — Super-admin")

    pdf.p(
        "Le super-admin dispose de toutes les capacités de l'admin, avec les "
        "permissions supplémentaires suivantes :"
    )
    pdf.bullet("Promouvoir un compte au rôle admin.")
    pdf.bullet("Rétrograder un admin au rôle agent ou citoyen.")
    pdf.bullet("Promouvoir un compte au rôle super-admin.")
    pdf.bullet("Désactiver un compte admin (sans pouvoir le faire pour un autre super-admin).")
    pdf.bullet("Accéder à toutes les fonctionnalités d'administration sans restriction de hiérarchie.")

    # ----- Système / cron / API ------------------------------------------
    pdf.h1("6. Fonctionnalités — Système (cron, API)")

    pdf.h2("Tâches planifiées")
    pdf.bullet("Expirer automatiquement les cartes dont la date de fin est dépassée (commande expire_due, lancée quotidiennement).")
    pdf.bullet("Purger les données expirées : anonymisation des comptes inactifs > 3 ans, suppression des codes visiteurs > 1 an, suppression des journaux d'audit > 3 ans (commande purge_expired_data, lancée mensuellement).")

    pdf.h2("API REST publique (/api/v1/)")
    pdf.bullet("Vérifier le droit de stationnement d'une plaque (endpoint phare pour les scan-cars communaux).")
    pdf.bullet("Lister les communes desservies.")
    pdf.bullet("Lister les zones GIS de la version active (filtrable par commune).")
    pdf.bullet("Obtenir un token d'accès (échange username + password contre un token).")
    pdf.bullet("Pré-calculer l'éligibilité d'un véhicule à une carte riverain (consommé par le wizard React).")
    pdf.bullet("Soumettre une demande de carte (consommé par le wizard React).")
    pdf.bullet("Consulter le journal d'audit paginé (back-office uniquement).")

    pdf.h2("Documentation API auto-générée")
    pdf.bullet("Schéma OpenAPI YAML (endpoint /api/v1/schema/).")
    pdf.bullet("Documentation interactive Swagger UI (/api/v1/docs/).")
    pdf.bullet("Documentation Redoc (/api/v1/redoc/) pour présentation au jury.")

    # ----- Contraintes transversales --------------------------------------
    pdf.h1("7. Contraintes transversales (TFE)")

    pdf.h2("Multilinguisme")
    pdf.bullet("Servir l'ensemble du site en français, néerlandais et anglais.")
    pdf.bullet("Préfixer les URLs par la langue (/fr/, /nl/, /en/).")
    pdf.bullet("Sélectionner la langue depuis la navbar (FR · NL · EN).")
    pdf.bullet("Persister la langue choisie dans le profil utilisateur (preferred_language).")
    pdf.bullet("Envoyer les emails transactionnels dans la langue préférée du destinataire.")

    pdf.h2("Sécurité")
    pdf.bullet("Authentifier les utilisateurs via Django auth (mot de passe haché PBKDF2).")
    pdf.bullet("Authentifier les appels API via Token DRF + throttling (check-right : 120 req/min/user).")
    pdf.bullet("Cloisonner les permissions back-office par rôle (citoyen / agent / admin / super_admin).")
    pdf.bullet("Hasher les plaques (HMAC-SHA256) avant stockage dans les journaux d'audit (RGPD).")
    pdf.bullet("Vérifier la signature des webhooks Stripe (STRIPE_WEBHOOK_SECRET).")
    pdf.bullet("Journaliser chaque action sensible dans l'audit (28 actions × 4 sévérités).")
    pdf.bullet("Servir le site en HTTPS uniquement en production (HSTS + WhiteNoise).")

    pdf.h2("RGPD")
    pdf.bullet("Recueillir le consentement éclairé à l'inscription (politique de confidentialité + CGU).")
    pdf.bullet("Stocker un horodatage de consentement (accepted_privacy_at, accepted_terms_at).")
    pdf.bullet("Publier une politique de confidentialité accessible sans connexion (/legal/privacy/).")
    pdf.bullet("Publier des conditions d'utilisation (/legal/terms/).")
    pdf.bullet("Permettre l'exercice des droits RGPD (art. 15-22) via privacy@parking.belgium.local.")
    pdf.bullet("Limiter la collecte aux données strictement nécessaires (principe de minimisation).")
    pdf.bullet("Respecter les durées de rétention (comptes 3 ans, codes visiteurs 1 an, audit 3 ans, paiements 7 ans).")

    pdf.h2("Performance et disponibilité")
    pdf.bullet("Servir les pages statiques via WhiteNoise (assets compressés).")
    pdf.bullet("Throttler les endpoints API pour limiter les abus (60/min/user, 10/min/anon).")
    pdf.bullet("Streamer les exports CSV pour ne pas charger toute la liste en mémoire.")
    pdf.bullet("Utiliser le cursor-based pagination sur le journal d'audit (datatable React, scroll infini).")

    return str(save_to(pdf, "01_cahier_charges_fonctionnel.pdf"))


if __name__ == "__main__":
    print(generate())
