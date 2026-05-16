"""
Document 09 — Stratégie de sécurité.

Couvre l'authentification, l'autorisation, la protection des données, la
détection d'intrusion et le plan de reprise d'activité.
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Stratégie de sécurité",
        subtitle="Authentification, RGPD, IDS, DRP — défense en profondeur",
    )
    pdf.cover()

    # ----- Vue d'ensemble -----------------------------------------------
    pdf.h1("1. Modèle de menaces et approche")

    pdf.h2("Données sensibles manipulées")
    pdf.bullet("Identité civile : nom, prénom, date de naissance, numéro de registre national (donnée hautement sensible RGPD).")
    pdf.bullet("Adresse postale géocodée — donnée à caractère personnel.")
    pdf.bullet("Plaque d'immatriculation — donnée à caractère personnel (identifie un véhicule et son propriétaire).")
    pdf.bullet("Téléphone et email — données de contact.")
    pdf.bullet("Paiements (montants, méthodes) — sans stocker les numéros de cartes bancaires (délégué à Stripe, PCI-DSS niveau 1).")
    pdf.bullet("Documents uploadés : certificats d'immatriculation (photo/scan).")

    pdf.h2("Acteurs malveillants potentiels")
    pdf.bullet("Citoyen mal intentionné — tente d'obtenir une carte avec de fausses informations, ou de consulter les données d'un autre citoyen.")
    pdf.bullet("Attaquant externe (script kiddie, bot) — brute-force sur les comptes, injection SQL, XSS.")
    pdf.bullet("Insider (agent malveillant) — abus de privilèges pour consulter / modifier indûment.")
    pdf.bullet("Adversaire à motivation politique — DDoS, défacement, exfiltration de la base.")

    pdf.h2("Approche : défense en profondeur")
    pdf.p(
        "La sécurité est traitée à 4 niveaux superposés : périmètre réseau "
        "(HTTPS, CORS, headers), authentification/autorisation, validation "
        "des données, audit et détection. Une faille à un niveau ne compromet "
        "pas l'ensemble du système."
    )

    # ----- Authentification ---------------------------------------------
    pdf.h1("2. Authentification")

    pdf.h2("Web (citoyens + back-office)")
    pdf.bullet("Système Django auth standard — sessions cookie-based avec SameSite=Lax + Secure (HTTPS only en prod).")
    pdf.bullet("Mot de passe haché avec PBKDF2-SHA256, 600 000 itérations (Django 5.1 défaut, conforme NIST 2024).")
    pdf.bullet("Validators de complexité activés : UserAttributeSimilarity, MinimumLength (8 chars), CommonPassword, NumericPassword.")
    pdf.bullet("CSRF token obligatoire sur tous les POST (cookie + form input).")
    pdf.bullet("X-Frame-Options: DENY — protection clickjacking.")

    pdf.h2("API REST (scan-cars + intégrations)")
    pdf.bullet("Token DRF (header Authorization: Token <token>) — 40 caractères hexadécimaux générés aléatoirement.")
    pdf.bullet("Émis uniquement pour les comptes back-office (jamais aux citoyens).")
    pdf.bullet("Pas d'expiration automatique — rotation manuelle recommandée tous les 6 mois.")
    pdf.bullet("Affiché en clair une seule fois (au moment de l'émission) — pas de récupération possible ensuite.")

    pdf.h2("Récupération de mot de passe")
    pdf.bullet("Génération d'un token signé Django (TimestampSigner) valide 3 jours.")
    pdf.bullet("Lien envoyé par email à l'adresse enregistrée — pas de divulgation : la réponse est neutre même si l'email n'existe pas (anti-énumération).")
    pdf.bullet("Token à usage unique (invalidé après définition du nouveau mot de passe).")
    pdf.bullet("Audit de chaque demande de reset (PASSWORD_RESET_SENT).")

    pdf.h2("Protection contre le brute-force")
    pdf.bullet("Throttle anon 10 req/min sur les endpoints publics.")
    pdf.bullet("Journalisation des AUTH_FAILED (severity warning) — détection des patterns d'attaque.")
    pdf.bullet("À implémenter en production : verrouillage temporaire après 5 échecs (django-axes ou équivalent).")

    # ----- Autorisation -------------------------------------------------
    pdf.h1("3. Autorisation et accès aux ressources")

    pdf.h2("Modèle de rôles")
    pdf.table(
        headers=["Rôle", "Accès aux propres données", "Accès back-office", "Promotion d'autres"],
        rows=[
            ["citizen",     "Lecture + écriture",                  "Aucun",                                  "Aucune"],
            ["agent",       "Lecture/écriture pour les dossiers en revue manuelle", "Approuver/refuser, gérer zones",          "Aucune"],
            ["admin",       "Tous les dossiers de sa commune",     "Tous les comptes back-office",           "Citoyen ↔ agent uniquement"],
            ["super_admin", "Tous les dossiers, toutes communes",  "Tout, sans restriction",                  "Tous les rôles, sans limite"],
        ],
        col_widths=[28, 50, 55, 45],
    )

    pdf.h2("Garde-fous applicatifs (services.py)")
    pdf.bullet("Une fonction _ensure_can_act_on() refuse systématiquement : auto-modification de rôle/active, admin sur admin, super_admin sur super_admin.")
    pdf.bullet("Un admin ne peut JAMAIS promouvoir un autre user au rang d'admin (seul un super_admin peut).")
    pdf.bullet("Toute modification de rôle est journalisée avec diff (USER_ROLE_CHANGED, payload.diff = ['agent', 'admin']).")
    pdf.bullet("Les endpoints API renvoient 403 Forbidden si le rôle est insuffisant (jamais 404 — pas de leak d'info).")

    pdf.h2("Accès aux données métier")
    pdf.bullet("Citoyen : voit uniquement ses propres véhicules, cartes, paiements, demandes.")
    pdf.bullet("Agent : voit toutes les demandes en revue manuelle mais pas les paiements détaillés.")
    pdf.bullet("Admin : voit tout sur sa commune (à terme — actuellement : tout, scope commune à venir).")
    pdf.bullet("Vue post_login_redirect — single source of truth pour la redirection après login.")

    # ----- Protection des données --------------------------------------
    pdf.h1("4. Protection des données personnelles (RGPD)")

    pdf.h2("Principes RGPD appliqués")
    pdf.bullet("Minimisation — seuls les champs strictement nécessaires sont collectés (pas d'âge si date_de_naissance suffit, pas de RIB).")
    pdf.bullet("Limitation de finalité — les données collectées ne servent qu'à l'attribution de cartes (jamais de revente, jamais de profilage marketing).")
    pdf.bullet("Limitation de conservation — durées de rétention explicites par catégorie (cf. section 6).")
    pdf.bullet("Intégrité et confidentialité — chiffrement TLS, contrôles d'accès stricts, audit complet.")
    pdf.bullet("Responsabilité (accountability) — politique de confidentialité publique, DPIA, registre des traitements à tenir.")

    pdf.h2("Consentement à l'inscription")
    pdf.bullet("Case 'J'accepte la politique de confidentialité et les CGU' obligatoire au registration (BooleanField required=True).")
    pdf.bullet("Snapshot User.accepted_privacy_at + User.accepted_terms_at = horodatage exact de l'acceptation.")
    pdf.bullet("Lien direct vers /legal/privacy/ et /legal/terms/ depuis le label.")

    pdf.h2("Hashage des plaques dans l'audit (HMAC-SHA256)")
    pdf.bullet("Les appels API check-right hashent la plaque (HMAC avec SECRET_KEY, tronqué à 16 hex) avant de la stocker dans le payload.")
    pdf.bullet("La corrélation reste possible (le même hash pour la même plaque) sans exposer la plaque en clair dans les logs.")
    pdf.bullet("Conforme à la recommandation APD belge sur les logs applicatifs.")

    pdf.h2("Droits RGPD (art. 15-22) exposés")
    pdf.bullet("Droit d'accès — interface citoyen + export des données sur demande à privacy@parking.belgium.local.")
    pdf.bullet("Droit de rectification — modifiable directement depuis l'espace personnel pour les champs basiques.")
    pdf.bullet("Droit à l'effacement — suppression / anonymisation après période de rétention (cron purge_expired_data).")
    pdf.bullet("Droit à la portabilité — export JSON sur demande.")
    pdf.bullet("Droit à la limitation — suspension du compte sur demande.")
    pdf.bullet("Droit d'opposition — résiliation possible (avec préservation des données comptables 7 ans).")
    pdf.bullet("Droit de recours auprès de l'APD belge (autoriteprotectiondonnees.be).")

    pdf.h2("Cookies")
    pdf.bullet("Un seul cookie de session, strictement nécessaire au fonctionnement du site (article ePrivacy 5.3 — exempté de consentement).")
    pdf.bullet("Pas de cookies analytics, pas de cookies publicitaires, pas de cookies tiers.")
    pdf.bullet("Bandeau d'information cookies (notice, dismissible, mémo dans localStorage).")
    pdf.bullet("Cookie de langue (django_language) — fonctionnel.")
    pdf.bullet("Cookie csrftoken — sécurité (anti-CSRF).")

    # ----- Sécurité applicative -----------------------------------------
    pdf.h1("5. Sécurité applicative")

    pdf.h2("Protection injection SQL")
    pdf.bullet("Utilisation systématique de l'ORM Django ou de requêtes paramétrées (`cursor.execute(sql, params)`).")
    pdf.bullet("Aucune concaténation de strings dans les requêtes.")
    pdf.bullet("Validators sur les champs CharField (max_length, regex pour codes postaux, etc.).")

    pdf.h2("Protection XSS")
    pdf.bullet("Templating Django avec escape HTML automatique sur toutes les variables (`{{ var }}` est échappé).")
    pdf.bullet("Marqueurs explicites `|safe` réservés aux contenus contrôlés (politique de confidentialité, etc.).")
    pdf.bullet("Content Security Policy à activer en production (en-tête HTTP).")

    pdf.h2("Protection CSRF")
    pdf.bullet("Token CSRF obligatoire sur tous les POST/PUT/DELETE (Django middleware CsrfViewMiddleware).")
    pdf.bullet("Cookies csrftoken + form input vérifiés ensemble (double submit).")
    pdf.bullet("Stripe webhook exempté de CSRF via @csrf_exempt + vérification de signature.")

    pdf.h2("Sécurité des fichiers uploadés")
    pdf.bullet("Validation des extensions (FileExtensionValidator) : PDF, JPG, PNG, WebP uniquement pour les certificats d'immatriculation.")
    pdf.bullet("Limite de taille : 5 Mo par fichier.")
    pdf.bullet("Stockage dans un dossier non exécutable côté serveur (uploads/, hors webroot statique).")
    pdf.bullet("Future production : analyse antivirus à l'upload (ClamAV en background worker).")

    pdf.h2("Sécurité des paiements")
    pdf.bullet("Stripe Checkout — page hostée Stripe, aucune donnée carte ne transite par notre serveur (réduction PCI scope).")
    pdf.bullet("Signature webhook vérifiée systématiquement (STRIPE_WEBHOOK_SECRET).")
    pdf.bullet("Stockage local : uniquement card_brand + card_last4 (jamais PAN ni CVC).")
    pdf.bullet("Contrainte unique partielle one_succeeded_payment_per_permit — empêche un double paiement.")
    pdf.bullet("Validation Luhn côté serveur sur le formulaire interne (fallback).")

    pdf.h2("Sécurisation des sessions")
    pdf.bullet("SESSION_COOKIE_SECURE=True en prod (HTTPS uniquement).")
    pdf.bullet("SESSION_COOKIE_HTTPONLY=True (pas d'accès JavaScript).")
    pdf.bullet("SESSION_COOKIE_SAMESITE='Lax' (protection CSRF cross-site).")
    pdf.bullet("Rotation du cookie session à chaque connexion (Django auth standard).")

    # ----- Audit et IDS ------------------------------------------------
    pdf.h1("6. Intrusion Detection System (IDS) et audit")

    pdf.h2("Journal d'audit applicatif")
    pdf.bullet("28 actions auditées (PERMIT_*, PAYMENT_*, USER_*, API_*, GIS_*, RGPD_*).")
    pdf.bullet("4 niveaux de sévérité : info, notice, warning, critical.")
    pdf.bullet("Service log() résilient — capture les exceptions, ne casse jamais le métier.")
    pdf.bullet("Stockage horodaté (TIMESTAMPTZ), IP source, acteur, cible (polymorphique), diff before/after.")
    pdf.bullet("Page back-office /dashboard/admin/audit/ avec filtres temps réel + export CSV.")

    pdf.h2("Détection de patterns suspects (à brancher en production)")
    pdf.bullet("Plus de 5 AUTH_FAILED dans les 5 min depuis la même IP → alerte Sentry.")
    pdf.bullet("Plus de 100 check-right en 1 min depuis le même token → throttle 429 (déjà actif).")
    pdf.bullet("Changement de rôle en série (3 promotions en 10 min) → alerte critique.")
    pdf.bullet("Détection de scrapping API : requêtes séquentielles sur permits/, communes/ → throttle agressif.")

    pdf.h2("Monitoring externe")
    pdf.bullet("Sentry — capture des exceptions Python (back) + JavaScript (front), grouping intelligent, alertes mail/Slack.")
    pdf.bullet("UptimeRobot — ping HTTP toutes les 5 min sur /, /api/v1/check-right/, /dashboard/admin/, alerte si down > 1 min.")
    pdf.bullet("Logs structurés JSON → Grafana Loki en prod, dashboards de métriques métier.")

    # ----- Disaster Recovery Plan --------------------------------------
    pdf.h1("7. Disaster Recovery Plan (DRP)")

    pdf.h2("Stratégie de sauvegarde")
    pdf.bullet("Backup PostgreSQL automatique quotidien (Scaleway Database managed) — rétention 30 jours, point-in-time recovery 7 jours.")
    pdf.bullet("Backup objet (uploads) quotidien — bucket S3 secondaire (Hetzner DE ou Scaleway autre AZ).")
    pdf.bullet("Backup off-site annuel — archive chiffrée GPG vers un second fournisseur (cross-cloud).")
    pdf.bullet("Test de restauration mensuel automatisé — restore sur environnement staging + smoke tests pour valider.")

    pdf.h2("RPO et RTO cibles")
    pdf.table(
        headers=["Scénario", "RPO (perte max)", "RTO (rétablissement max)"],
        rows=[
            ["Crash applicatif (process Gunicorn)", "0 (zéro perte)",  "5 min (auto-restart systemd)"],
            ["Panne base de données",                "5 min (WAL ship)", "30 min (failover Scaleway managed)"],
            ["Perte totale d'une AZ",                "1 h",              "4 h (restore vers AZ secondaire)"],
            ["Suppression accidentelle de données",  "24 h",             "1 h (PITR sur DB managed)"],
            ["Compromission complète",               "24 h",             "8 h (reinstall + restore last clean backup)"],
        ],
        col_widths=[60, 35, 79],
    )

    pdf.h2("Plan de continuité")
    pdf.bullet("Documentation runbook d'incidents — procédures pas-à-pas pour chaque scénario (à rédiger).")
    pdf.bullet("Contacts d'urgence : équipe technique (24/7 en production), DPO, hébergeur.")
    pdf.bullet("Page de statut publique (statuspage.io ou self-hosted Cachet) — communication aux utilisateurs en cas d'incident.")
    pdf.bullet("Tests de bascule trimestriels — simulation d'une panne (game day) pour vérifier les procédures.")

    pdf.h2("Plan de reprise")
    pdf.bullet("Étape 1 — Stop la dégradation : couper le trafic, isoler la base si compromission suspectée.")
    pdf.bullet("Étape 2 — Diagnostic : lecture des logs Sentry + audit applicatif, identification de la cause racine.")
    pdf.bullet("Étape 3 — Restauration : restore du backup le plus récent jugé sain.")
    pdf.bullet("Étape 4 — Validation : tests smoke sur staging avant remise en production.")
    pdf.bullet("Étape 5 — Communication : notification utilisateurs + statut public + rapport d'incident.")
    pdf.bullet("Étape 6 — Post-mortem : analyse des causes, action items pour empêcher la récidive.")

    # ----- Durées de rétention -----------------------------------------
    pdf.h1("8. Durées de rétention RGPD")

    pdf.table(
        headers=["Catégorie", "Durée", "Justification"],
        rows=[
            ["Compte citoyen actif",         "Tant qu'inscrit",         "Article 5.1.e — finalité"],
            ["Compte inactif",               "3 ans après dernière connexion", "Anonymisation puis purge — recommandation APD"],
            ["Cartes de stationnement actives", "Tant qu'actives",       "Finalité"],
            ["Cartes expirées",              "10 ans",                  "Obligation comptable belge"],
            ["Paiements",                    "7 ans",                   "Obligation TVA"],
            ["Codes visiteurs émis",         "1 an après expiration",   "Traçabilité + RGPD minimisation"],
            ["Journaux d'audit",             "3 ans",                   "Recommandation APD"],
            ["Sessions web",                 "2 semaines (max)",        "Sécurité"],
            ["Tokens API",                   "Tant qu'actifs",          "Réémission manuelle"],
            ["Tokens password reset",        "3 jours",                 "Sécurité"],
        ],
        col_widths=[50, 30, 94],
    )

    pdf.h2("Mise en œuvre")
    pdf.bullet("Cron purge_expired_data — mensuel, anonymise/supprime selon ces durées.")
    pdf.bullet("Cron expire_due — quotidien, passe les cartes en EXPIRED.")
    pdf.bullet("Future : export de données sur demande citoyen (RGPD art. 15+20).")
    pdf.bullet("Future : suppression de compte avec anonymisation immédiate sur demande (art. 17).")

    # ----- Audit externe et compliance ---------------------------------
    pdf.h1("9. Audit externe et compliance")

    pdf.h2("Audits planifiés")
    pdf.bullet("Pentest externe avant mise en production — 1 audit complet de boîte noire + boîte blanche.")
    pdf.bullet("Audit RGPD annuel — par un DPO externe, validation de la DPIA et du registre des traitements.")
    pdf.bullet("Code review trimestrielle par un développeur externe — détection des smells de sécurité.")
    pdf.bullet("Audit dépendances continu — Dependabot (GitHub) + alertes CVE.")

    pdf.h2("Certifications cibles (long terme)")
    pdf.bullet("ISO 27001 — système de management de la sécurité de l'information (à terme).")
    pdf.bullet("Référentiel SecNumCloud (français) ou C5 (allemand) — pour la sous-traitance d'hébergement.")
    pdf.bullet("Pas de PCI-DSS pour nous : Stripe absorbe le scope cartes bancaires.")

    pdf.h2("Documents légaux à produire (cadre RGPD belge)")
    pdf.bullet("Politique de confidentialité publique — déjà en place (/legal/privacy/).")
    pdf.bullet("Conditions générales d'utilisation — déjà en place (/legal/terms/).")
    pdf.bullet("Registre des activités de traitement (art. 30 RGPD) — à compléter avec finalités, destinataires, durées.")
    pdf.bullet("DPIA (Data Protection Impact Assessment, art. 35) — obligatoire pour un service public traitant des plaques.")
    pdf.bullet("Procédure de notification de violation (art. 33-34) — délai 72 h vers APD si fuite avérée.")

    return str(save_to(pdf, "09_strategie_securite.pdf"))


if __name__ == "__main__":
    print(generate())
