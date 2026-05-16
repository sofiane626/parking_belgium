"""
Document 10 — Stratégie de référencement SEO / SEA.

Décrit les éléments mis en place dans le code (robots.txt, sitemap.xml,
hreflang, meta, OG) et la stratégie complémentaire (contenu, netlinking).
"""
from __future__ import annotations

from .pdf_base import PBPdf, save_to


def generate() -> str:
    pdf = PBPdf(
        title="Stratégie de référencement (SEO / SEA)",
        subtitle="Optimisations techniques en place, stratégie de contenu et acquisition",
    )
    pdf.cover()

    # ----- Contexte ------------------------------------------------------
    pdf.h1("1. Contexte et objectifs SEO")

    pdf.p(
        "Parking.Belgium est un service public administratif : son audience "
        "cible est extrêmement spécifique (résidents bruxellois cherchant à "
        "obtenir ou renouveler une carte de stationnement). Le SEO doit "
        "garantir que ce public trouve le service par les requêtes naturelles "
        "qu'il utilise (« carte riverain Bruxelles », « parking résident "
        "Schaerbeek », etc.), sans entrer en concurrence frontale avec les "
        "sites communaux officiels existants."
    )

    pdf.h2("Objectifs mesurables")
    pdf.bullet("Position top 3 sur Google.be pour les requêtes 'carte stationnement <commune>' (les 19 communes).")
    pdf.bullet("Position top 5 pour 'parking résident Bruxelles', 'carte visiteur stationnement', 'demande carte parking'.")
    pdf.bullet("Visibilité multilingue : index correct des versions /fr/, /nl/, /en/.")
    pdf.bullet("Taux de rebond < 60 % sur la page d'accueil (engagement utilisateur).")
    pdf.bullet("Temps moyen de session > 90 secondes (consultation effective).")

    pdf.h2("Pas de SEA (publicité payante)")
    pdf.p(
        "En tant que service public financé par subvention, le projet n'a "
        "pas vocation à pratiquer le SEA. Le SEO est suffisant pour atteindre "
        "l'audience cible (qui cherche activement le service). Une campagne "
        "Google Ads serait éventuellement justifiable au lancement pour "
        "informer les citoyens du nouveau portail, sur budget communication "
        "régionale dédié — mais ce n'est pas l'objet de cette stratégie."
    )

    # ----- SEO technique ----------------------------------------------
    pdf.h1("2. SEO technique — éléments en place")

    pdf.h2("Balises HTML essentielles")
    pdf.p(
        "Le template base.html définit les balises SEO suivantes, "
        "surchargeables par chaque page via les `{% block %}` :"
    )
    pdf.bullet("<title> — bloc title surchargeable, suffixé par « · Parking.Belgium ».")
    pdf.bullet("<meta name='description'> — 1 ligne contextuelle, bloc meta_description.")
    pdf.bullet("<meta name='robots' content='index, follow'> — surchargeable à 'noindex' pour les pages privées.")
    pdf.bullet("<meta name='author' content='Parking.Belgium'>")
    pdf.bullet("<meta name='theme-color' content='#08447F'> — couleur de l'application sur mobile (PWA-ready).")
    pdf.bullet("<html lang='fr'|'nl'|'en'> — attribut linguistique correct selon la langue active.")

    pdf.h2("URLs propres et structurées")
    pdf.bullet("URLs en kebab-case, descriptives : /me/permits/, /me/permits/<pk>/, /dashboard/admin/audit/.")
    pdf.bullet("Préfixe de langue (/fr/, /nl/, /en/) pour indexation séparée par moteur.")
    pdf.bullet("Pas de paramètres GET inutiles dans les URLs publiques (URLs canoniques).")
    pdf.bullet("Pas de duplication via trailing slash (Django ajoute le slash final automatiquement).")

    pdf.h2("Hreflang — annonce du multilingue aux moteurs")
    pdf.p(
        "Chaque page expose dans <head> des balises <link rel='alternate' "
        "hreflang='X' href='URL'> pour chaque langue disponible (FR/NL/EN), "
        "ainsi qu'un x-default vers la version française. Cela permet à "
        "Google de comprendre que /fr/me/permits/ et /nl/me/permits/ sont "
        "la même page traduite (pas du contenu dupliqué)."
    )
    pdf.code(
        '<link rel="alternate" hreflang="fr" href="https://parking.belgium/fr/">\n'
        '<link rel="alternate" hreflang="nl" href="https://parking.belgium/nl/">\n'
        '<link rel="alternate" hreflang="en" href="https://parking.belgium/en/">\n'
        '<link rel="alternate" hreflang="x-default" href="https://parking.belgium/fr/">'
    )

    pdf.h2("robots.txt (en place)")
    pdf.p(
        "Le fichier /robots.txt est servi par la vue apps.core.views.robots_txt. "
        "Il indique aux crawlers les zones à ne pas indexer (back-office, "
        "données privées) et référence le sitemap."
    )
    pdf.code(
        "User-agent: *\n"
        "Disallow: /admin/\n"
        "Disallow: /dashboard/\n"
        "Disallow: /me/\n"
        "Disallow: /accounts/password/\n"
        "Disallow: /api/v1/audit/\n"
        "Allow: /\n"
        "\n"
        "Sitemap: https://parking.belgium/sitemap.xml"
    )

    pdf.h2("sitemap.xml (en place)")
    pdf.p(
        "Le sitemap XML est généré dynamiquement par "
        "django.contrib.sitemaps. La classe StaticViewSitemap "
        "(apps/core/sitemaps.py) liste les pages publiques avec leur "
        "priorité et fréquence de mise à jour. Disponible à /sitemap.xml."
    )
    pdf.table(
        headers=["URL", "Priorité", "changefreq"],
        rows=[
            ["/",                  "1.0",  "weekly"],
            ["/map/",              "0.9",  "weekly"],
            ["/accounts/register/", "0.7", "monthly"],
            ["/accounts/login/",   "0.5",  "yearly"],
            ["/legal/privacy/",    "0.4",  "yearly"],
            ["/legal/terms/",      "0.4",  "yearly"],
        ],
        col_widths=[80, 30, 64],
    )

    pdf.h2("Open Graph + Twitter Cards")
    pdf.p(
        "Pour optimiser l'apparence des partages sur les réseaux sociaux et "
        "messageries (Facebook, LinkedIn, Twitter, Teams) :"
    )
    pdf.bullet("og:site_name, og:type, og:title, og:description, og:locale.")
    pdf.bullet("og:locale:alternate pour annoncer les autres langues disponibles.")
    pdf.bullet("twitter:card type 'summary_large_image' pour un rendu attrayant sur X.")
    pdf.bullet("À compléter : og:image avec une vignette 1200×630 de la page d'accueil.")

    pdf.h2("Sémantique HTML")
    pdf.bullet("Hiérarchie de titres respectée : <h1> unique par page (titre principal), <h2> pour sections, <h3> pour sous-sections.")
    pdf.bullet("Balises landmark : <header>, <main>, <footer>, <nav> — facilitent la lecture par les robots et les lecteurs d'écran.")
    pdf.bullet("Attributs alt sur les <img>, surtout les images décoratives (alt='' pour les ignorer).")
    pdf.bullet("Liens descriptifs (pas 'cliquez ici', mais 'Demander une carte riverain').")

    pdf.h2("Performance (Core Web Vitals)")
    pdf.p(
        "Google utilise depuis 2021 les Core Web Vitals comme critère de "
        "classement (LCP, FID, CLS). Le projet est optimisé pour atteindre "
        "le seuil 'Good' sur les trois métriques :"
    )
    pdf.bullet("LCP < 2.5 s — Tailwind CSS minifié 68 ko, images optimisées (WebP), pas de blocking script.")
    pdf.bullet("FID < 100 ms — JavaScript minimal (îlots React seulement où nécessaire), pas de framework lourd.")
    pdf.bullet("CLS < 0.1 — dimensions explicites sur les images, pas d'injection de contenu différée.")
    pdf.bullet("Compression gzip + brotli sur les statiques (WhiteNoise).")
    pdf.bullet("Cache HTTP : 1 an sur les assets versionnés (hash dans le nom).")

    pdf.h2("Mobile-first")
    pdf.p(
        "Google indexe les sites en priorité depuis sa version mobile (Mobile-First "
        "Indexing). Le projet est mobile-first par construction : toutes les "
        "pages sont conçues pour fonctionner sur 375 px (iPhone SE) avant "
        "d'être enrichies en desktop. Tailwind responsive utilities (sm:, md:, "
        "lg:) appliquées systématiquement."
    )

    # ----- SEO contenu ---------------------------------------------------
    pdf.h1("3. SEO de contenu — stratégie éditoriale")

    pdf.h2("Mots-clés cibles")
    pdf.table(
        headers=["Mot-clé", "Volume mensuel estimé (BE)", "Difficulté", "Page de destination"],
        rows=[
            ["carte stationnement Bruxelles",   "1 900",   "Moyenne", "/"],
            ["carte riverain Bruxelles",        "1 200",   "Moyenne", "/"],
            ["parking résident Bruxelles",      "850",     "Faible",  "/"],
            ["carte stationnement Schaerbeek",  "320",     "Faible",  "/ (commune détectée)"],
            ["carte stationnement Ixelles",     "290",     "Faible",  "/ (commune détectée)"],
            ["carte visiteur parking",          "180",     "Faible",  "/me/permits/visitor/new/"],
            ["demande carte parking en ligne",  "230",     "Faible",  "/"],
            ["parking professionnel Bruxelles", "150",     "Faible",  "/me/permits/professional/"],
        ],
        col_widths=[55, 35, 25, 59],
    )

    pdf.h2("Contenu de la page d'accueil")
    pdf.bullet("Hero clair avec le bénéfice utilisateur principal (« Stationnez à Bruxelles en toute simplicité »).")
    pdf.bullet("3 cartes (riverain / visiteur / professionnel) avec mots-clés naturels intégrés.")
    pdf.bullet("Section 'Comment ça marche' en 4 étapes — répond aux requêtes informationnelles.")
    pdf.bullet("FAQ — riche en longue-traîne, schemas FAQPage envisageable (rich snippets).")
    pdf.bullet("Pas de jargon administratif inutile — vocabulaire grand public.")

    pdf.h2("Pages dédiées à venir (recommandation)")
    pdf.bullet("Page par commune : /communes/schaerbeek/ avec règles spécifiques, prix, contacts (longue traîne géo).")
    pdf.bullet("Page FAQ détaillée : /faq/ structurée avec schema.org FAQPage pour les rich snippets Google.")
    pdf.bullet("Page « Que faire si je déménage ? » : guide pratique, ciblage des requêtes informationnelles.")
    pdf.bullet("Page « Tarifs des cartes » : tableau récap des prix par commune (très recherché).")
    pdf.bullet("Blog/actualités : annonces de mises à jour, changements de règles, FAQ vivante.")

    # ----- SEO local ----------------------------------------------------
    pdf.h1("4. SEO local (très important pour ce projet)")

    pdf.h2("Optimisation Google My Business")
    pdf.bullet("Créer une fiche Google My Business 'Service public — Bruxelles' si déclaré officiel.")
    pdf.bullet("Catégorie principale : 'Service administratif gouvernemental'.")
    pdf.bullet("Photos de la couverture (Grand-Place, Atomium) — déjà disponibles dans le site.")
    pdf.bullet("Horaires : 24/7 (plateforme en ligne).")

    pdf.h2("Schéma JSON-LD (à implémenter)")
    pdf.p(
        "Ajouter des données structurées schema.org dans le <head> pour "
        "aider Google à comprendre la nature du service :"
    )
    pdf.code(
        '<script type="application/ld+json">\n'
        "{\n"
        '  "@context": "https://schema.org",\n'
        '  "@type": "GovernmentService",\n'
        '  "name": "Parking.Belgium",\n'
        '  "description": "Plateforme officielle...",\n'
        '  "provider": {"@type": "GovernmentOrganization",\n'
        '               "name": "Région de Bruxelles-Capitale"},\n'
        '  "areaServed": {"@type": "City",\n'
        '                 "name": "Bruxelles"},\n'
        '  "availableLanguage": ["fr", "nl", "en"]\n'
        "}\n"
        "</script>"
    )

    pdf.h2("Inscription dans les annuaires administratifs")
    pdf.bullet("Be.brussels — portail officiel régional, lien depuis la page Mobilité.")
    pdf.bullet("Belgium.be — portail fédéral, section 'Mobilité'.")
    pdf.bullet("Sites communaux des 19 communes — lien depuis leur page 'Stationnement'.")
    pdf.bullet("Annuaires des services publics : Service Public Fédéral Mobilité, e-government.be.")

    # ----- Netlinking ---------------------------------------------------
    pdf.h1("5. Netlinking — acquisition de liens entrants")

    pdf.h2("Liens institutionnels (priorité haute, faciles à obtenir)")
    pdf.bullet("Sites officiels des 19 communes — lien depuis leur page 'Stationnement résidentiel' (légitime car le service les remplace).")
    pdf.bullet("Bruxelles Mobilité (parking.brussels) — lien depuis la rubrique 'Outils' ou 'Démarches'.")
    pdf.bullet("Region de Bruxelles-Capitale (be.brussels) — annuaire des services publics.")

    pdf.h2("Médias et presse locale (priorité moyenne)")
    pdf.bullet("Communiqué de presse au lancement vers Le Soir, RTBF, BX1, Bruzz, La Capitale — couverture initiale.")
    pdf.bullet("Article invité dans des médias spécialisés mobilité urbaine (Mobiliteit.brussels, Velocité).")
    pdf.bullet("Interventions dans des podcasts/émissions locales mobilité.")

    pdf.h2("Wikipédia (qualité élevée)")
    pdf.bullet("Mention dans l'article 'Stationnement à Bruxelles' (à créer ou enrichir).")
    pdf.bullet("Mention dans 'Région de Bruxelles-Capitale' section 'Services numériques'.")
    pdf.bullet("⚠ Wikipédia interdit l'auto-promotion : passer par des éditeurs neutres avec sources tierces.")

    pdf.h2("Réseaux sociaux (signal de popularité)")
    pdf.bullet("LinkedIn — page officielle Parking.Belgium avec mises à jour produit.")
    pdf.bullet("Twitter/X — annonces ponctuelles (maintenance, nouvelles fonctionnalités).")
    pdf.bullet("Pas de Facebook/Instagram (audience pas pertinente pour un service administratif).")

    # ----- Stratégie multilingue ----------------------------------------
    pdf.h1("6. Stratégie multilingue")

    pdf.h2("Indexation séparée FR / NL / EN")
    pdf.bullet("URLs préfixées (/fr/, /nl/, /en/) — Google indexe chaque version séparément.")
    pdf.bullet("Hreflang dans <head> — relie les versions pour éviter la duplication perçue.")
    pdf.bullet("Sitemap inclut une URL par langue active (Django sitemaps natif).")

    pdf.h2("Contenu localisé")
    pdf.bullet("950 chaînes traduites à 100 % en NL et EN — couverture intégrale de l'interface.")
    pdf.bullet("Détection automatique de la langue préférée du visiteur (cookie + Accept-Language header).")
    pdf.bullet("Persistance de la langue dans le profil utilisateur (User.preferred_language).")
    pdf.bullet("Sélecteur de langue toujours visible dans la navbar (FR · NL · EN).")

    pdf.h2("Mots-clés par langue")
    pdf.bullet("FR — 'carte stationnement Bruxelles', 'parking résident', 'carte riverain'.")
    pdf.bullet("NL — 'parkeerkaart Brussel', 'bewonerskaart Brussel', 'gemeente parkeren'.")
    pdf.bullet("EN — 'Brussels parking permit', 'resident parking card Brussels', 'visitor parking'.")

    # ----- Mesure et suivi ----------------------------------------------
    pdf.h1("7. Mesure et suivi (à mettre en place)")

    pdf.h2("Outils gratuits compatibles RGPD")
    pdf.bullet("Google Search Console — métriques d'indexation, requêtes Google, CTR, position moyenne. Gratuit, requiert vérification de propriété.")
    pdf.bullet("Bing Webmaster Tools — équivalent pour Bing (~5 % du marché belge).")
    pdf.bullet("Plausible Analytics (self-hosted) ou Matomo — analytics respectueux de la vie privée, sans cookies tiers (alternative à GA).")
    pdf.bullet("Page de statut (UptimeRobot) — vérifie indirectement que les pages ne tombent pas (impact négatif SEO).")

    pdf.h2("KPI suivis")
    pdf.bullet("Position moyenne sur les 20 mots-clés cibles.")
    pdf.bullet("Trafic organique (visiteurs depuis moteurs de recherche).")
    pdf.bullet("Taux de clics depuis les pages Google (CTR).")
    pdf.bullet("Taux d'indexation (pages indexées / pages soumises).")
    pdf.bullet("Backlinks acquis (Ahrefs, SEMrush ou alternative gratuite).")
    pdf.bullet("Core Web Vitals (LCP, FID, CLS) — pour chaque langue.")

    pdf.h2("Revue trimestrielle")
    pdf.bullet("Analyse des requêtes émergentes (Search Console).")
    pdf.bullet("Identification des pages avec fort potentiel non exploité (impressions hautes, CTR bas).")
    pdf.bullet("Audit technique : pages 404, redirections cassées, vitesse de chargement.")
    pdf.bullet("Ajustement des meta descriptions sur les pages à fort potentiel.")

    # ----- Risques et bonnes pratiques ---------------------------------
    pdf.h1("8. Risques SEO à éviter")

    pdf.bullet("Contenu dupliqué FR/NL/EN — neutralisé par hreflang.")
    pdf.bullet("URLs avec paramètres inutiles indexés — robots.txt bloque /me/, /dashboard/, /api/.")
    pdf.bullet("Liens en nofollow non maîtrisés — auditer les liens sortants externes.")
    pdf.bullet("Vitesse de chargement dégradée — surveillance Core Web Vitals continue.")
    pdf.bullet("Pénalité Google pour pratiques douteuses (achat de liens, cloaking) — strictement écarté.")
    pdf.bullet("Pas de keyword stuffing — densité naturelle, lisibilité humaine prioritaire.")
    pdf.bullet("Pas d'AMP (le service n'a pas vocation à servir des médias news).")

    # ----- Conclusion ---------------------------------------------------
    pdf.h1("9. Conclusion")

    pdf.p(
        "Le SEO du projet est optimisé techniquement (URLs propres, "
        "hreflang multilingue, sitemap dynamique, robots.txt, OG/Twitter, "
        "performance Core Web Vitals). Le contenu de la page d'accueil "
        "intègre les mots-clés cibles de façon naturelle."
    )
    pdf.p(
        "La phase suivante consiste à enrichir le contenu (pages par "
        "commune, FAQ détaillée, blog/actualités) et à obtenir les premiers "
        "backlinks institutionnels (sites communaux, Bruxelles Mobilité). "
        "Pas de campagne SEA prévue — l'audience cible vient naturellement "
        "via la recherche organique pour ce type de service public."
    )

    return str(save_to(pdf, "10_strategie_seo.pdf"))


if __name__ == "__main__":
    print(generate())
