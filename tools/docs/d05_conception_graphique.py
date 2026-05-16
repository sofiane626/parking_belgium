"""
Document 05 — Rapport de conception graphique.

Couleurs, polices, logo, structure, trames, maquettes.
"""
from __future__ import annotations

from .pdf_base import (
    BRAND_700, BRAND_500, BRAND_100, SIGNAL_400,
    SLATE_900, SLATE_700, SLATE_300, SLATE_100, WHITE,
    PBPdf, save_to,
)


def generate() -> str:
    pdf = PBPdf(
        title="Rapport de conception graphique",
        subtitle="Identité visuelle, ergonomie et expérience utilisateur",
    )
    pdf.cover()

    # ----- Philosophie ---------------------------------------------------
    pdf.h1("1. Philosophie design")
    pdf.p(
        "Parking.Belgium est un service public dématérialisé : la conception "
        "graphique doit refléter trois valeurs clés — la confiance "
        "institutionnelle (couleur bleu profond du drapeau bruxellois), "
        "l'identité bruxelloise (touches de jaune signalisation, ancrées dans "
        "l'imagerie urbaine de la ville), et la modernité (typographie "
        "épurée, animations subtiles, design system Tailwind)."
    )
    pdf.p(
        "L'inspiration directe est parking.brussels (le portail officiel de "
        "Bruxelles Mobilité) — mêmes codes couleur dominants, mêmes principes "
        "d'épuration, mais avec une expérience plus moderne et adaptée à "
        "l'usage citoyen quotidien."
    )

    pdf.h2("Principes ergonomiques retenus")
    pdf.bullet("Mobile-first — toutes les pages sont conçues pour fonctionner sur smartphone (375 px) avant d'être enrichies en desktop.")
    pdf.bullet("Cognitive load minimal — chaque page a un seul objectif principal, signalé par un CTA proéminent.")
    pdf.bullet("Feedback immédiat — les actions (clic, soumission de formulaire) déclenchent un retour visuel (messages, animations).")
    pdf.bullet("Accessibilité — contrastes WCAG AA respectés, labels explicites sur les formulaires, navigation au clavier possible.")
    pdf.bullet("Multilinguisme natif — sélecteur de langue toujours visible (FR · NL · EN), interface adaptée aux trois langues.")

    # ----- Couleurs -----------------------------------------------------
    pdf.h1("2. Charte couleurs")
    pdf.p(
        "Trois familles de couleurs structurent le design : la marque brand "
        "(bleu profond pour les éléments principaux), le signal (jaune "
        "drapeau bruxellois pour les éléments de mise en avant) et les neutres "
        "slate (gris pour les contenus secondaires)."
    )

    pdf.h2("Palette brand (bleu institutionnel)")
    pdf.table(
        headers=["Token", "Hex", "RGB", "Usage"],
        rows=[
            ["brand-50",  "#EDF5FC", "237, 245, 252", "Fond de section léger"],
            ["brand-100", "#D4E7F8", "212, 231, 248", "Hover discret"],
            ["brand-500", "#2375C0", "35, 117, 192",  "Boutons primaires, accents"],
            ["brand-600", "#0F5BA3", "15, 91, 163",   "Hover boutons primaires"],
            ["brand-700", "#08447F", "8, 68, 127",    "Titres H1, logo"],
            ["brand-900", "#042648", "4, 38, 72",     "Texte sombre sur fond clair"],
        ],
        col_widths=[28, 32, 40, 74],
    )

    pdf.h2("Palette signal (jaune drapeau bruxellois)")
    pdf.table(
        headers=["Token", "Hex", "RGB", "Usage"],
        rows=[
            ["signal-100", "#FFF7C2", "255, 247, 194", "Fond surlignage"],
            ["signal-400", "#FFCD00", "255, 205, 0",   "Liseré actif, badge urgent, mise en avant"],
            ["signal-500", "#E6B400", "230, 180, 0",   "Hover signal-400"],
            ["signal-700", "#806300", "128, 99, 0",    "Texte sur fond jaune"],
        ],
        col_widths=[28, 32, 40, 74],
    )

    pdf.h2("Palette accent (cyan, secondaire)")
    pdf.table(
        headers=["Token", "Hex", "RGB", "Usage"],
        rows=[
            ["accent-400", "#22CDEE", "34, 205, 238", "Highlights secondaires"],
            ["accent-500", "#06B0D4", "6, 176, 212",  "Liens secondaires, info"],
            ["accent-700", "#0E7490", "14, 116, 144", "Texte info sombre"],
        ],
        col_widths=[28, 32, 40, 74],
    )

    pdf.h2("Palette slate (neutres)")
    pdf.table(
        headers=["Token", "Hex", "RGB", "Usage"],
        rows=[
            ["slate-50",  "#F8FAFC", "248, 250, 252", "Fond de page principal"],
            ["slate-100", "#F1F5F9", "241, 245, 249", "Fond de bloc subtil"],
            ["slate-300", "#CBD5E1", "203, 213, 225", "Bordures"],
            ["slate-500", "#64748B", "100, 116, 139", "Texte secondaire, aides"],
            ["slate-700", "#334155", "51, 65, 85",    "Texte principal"],
            ["slate-900", "#0F172A", "15, 23, 42",    "Titres, contrastes maximaux"],
        ],
        col_widths=[28, 32, 40, 74],
    )

    pdf.h2("Couleurs sémantiques")
    pdf.bullet("Succès : emerald-600 #059669 (paiement validé, opération réussie).")
    pdf.bullet("Avertissement : amber-500 #F59E0B (carte en attente, action requise).")
    pdf.bullet("Erreur : red-600 #DC2626 (refus, suspension, action interdite).")
    pdf.bullet("Information : cyan-600 #0891B2 (messages neutres, aides).")

    pdf.h2("Ratios de contraste WCAG")
    pdf.bullet("Texte slate-700 sur fond slate-50 : ratio 12.6 (AAA ✓).")
    pdf.bullet("Texte WHITE sur fond brand-700 : ratio 11.1 (AAA ✓).")
    pdf.bullet("Texte slate-900 sur fond signal-400 : ratio 11.8 (AAA ✓).")
    pdf.bullet("Texte slate-500 sur fond WHITE : ratio 4.8 (AA ✓).")

    # ----- Typographie --------------------------------------------------
    pdf.h1("3. Typographie")

    pdf.h2("Police principale : Inter")
    pdf.p(
        "Inter (par Rasmus Andersson, 2017) est une police sans-serif "
        "open-source spécifiquement dessinée pour les interfaces utilisateur "
        "à l'écran. Elle se distingue par :"
    )
    pdf.bullet("Une lisibilité optimale à toutes les tailles (10-72 px).")
    pdf.bullet("Une famille complète : 9 graisses (Thin 100 à Black 900).")
    pdf.bullet("Un support international large (latin étendu, cyrillique, grec).")
    pdf.bullet("Des chiffres tabulaires pour les tableaux de données.")
    pdf.bullet("Une licence SIL Open Font (utilisation commerciale libre).")
    pdf.p(
        "Servie via Google Fonts (woff2 optimisé). Fallback : ui-sans-serif → "
        "system-ui → Segoe UI → Roboto → sans-serif. Tailwind config :"
    )
    pdf.code(
        "fontFamily: {\n"
        "  sans: ['Inter', 'ui-sans-serif', 'system-ui',\n"
        "         '-apple-system', 'Segoe UI', 'Roboto', 'sans-serif'],\n"
        "  display: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],\n"
        "}"
    )

    pdf.h2("Hiérarchie typographique")
    pdf.table(
        headers=["Niveau", "Taille (rem)", "Graisse", "Usage"],
        rows=[
            ["Display 1", "4 (64px)", "Bold 700",     "Hero home"],
            ["H1",        "2.25 (36px)", "Semibold 600", "Titre de page"],
            ["H2",        "1.5 (24px)",  "Semibold 600", "Section"],
            ["H3",        "1.25 (20px)", "Semibold 600", "Sous-section"],
            ["Body L",    "1.125 (18px)", "Regular 400",  "Paragraphe lead"],
            ["Body",      "1 (16px)",     "Regular 400",  "Texte principal"],
            ["Caption",   "0.875 (14px)", "Regular 400",  "Aide, métadonnée"],
            ["Small",     "0.75 (12px)",  "Medium 500",   "Badge, lien tertiaire"],
            ["Tiny",      "0.625 (10px)", "Semibold 600", "Tag rôle, label"],
        ],
        col_widths=[28, 32, 40, 74],
    )

    pdf.h2("Espacement vertical (line-height)")
    pdf.bullet("Titres : 1.1 (compact, impactant).")
    pdf.bullet("Corps : 1.6 (lecture confortable).")
    pdf.bullet("Tableaux : 1.4 (densité).")

    # ----- Logo ---------------------------------------------------------
    pdf.h1("4. Logo et marque")

    pdf.h2("Logotype")
    pdf.p(
        "Le logo se compose d'un mark (carré arrondi 36×36 px avec un 'P' "
        "blanc sur fond gradient brand) et d'un wordmark (Parking.Belgium en "
        "Inter Semibold 17 px, avec '.Belgium' en accent brand-600)."
    )
    pdf.p(
        "Le 'P' évoque à la fois la première lettre du nom et le symbole "
        "international du stationnement (panneau bleu carré avec 'P' blanc). "
        "Cette double lecture renforce la reconnaissance immédiate du service."
    )

    pdf.h2("Variations du logo")
    pdf.bullet("Logo complet (mark + wordmark) — header desktop.")
    pdf.bullet("Logo réduit (mark uniquement) — favicon, mobile, contextes restreints.")
    pdf.bullet("Logo en monochrome blanc — fond brand sombre (page de garde, hero overlay).")
    pdf.bullet("Logo en monochrome brand-700 — fond clair (footer, documents).")

    pdf.h2("Espace de protection")
    pdf.p(
        "Conserver au minimum 1× la hauteur du mark autour du logo en zone "
        "vierge — empêche l'empilement visuel avec d'autres éléments."
    )

    pdf.h2("Hover du logo (subtilité)")
    pdf.p(
        "Au survol du logo en navbar : translation -1px + scale 1.05 + halo "
        "jaune signal (rgba(255,205,0,0.18)) — anime la marque sans la rendre "
        "intrusive."
    )

    # ----- Icônes et boutons --------------------------------------------
    pdf.h1("5. Icônes et boutons")

    pdf.h2("Iconographie")
    pdf.p(
        "Bibliothèque : Heroicons (https://heroicons.com) — set officiel "
        "fourni par les créateurs de Tailwind. Style outline 1.5 px par "
        "défaut, sauf indication contraire (filled pour les états actifs)."
    )
    pdf.bullet("Taille standard : 24×24 px (1.5 rem).")
    pdf.bullet("Taille compacte : 16×16 px (utilisée dans la navbar).")
    pdf.bullet("Couleur héritée du parent (currentColor) — facilite les états hover/focus.")
    pdf.bullet("Icônes contextuelles par rôle dans la navbar : maison (citoyen), boîte (cartes), grille (dashboard agent/admin/super_admin), enveloppe (demandes).")

    pdf.h2("Système de boutons")
    pdf.table(
        headers=["Classe", "Apparence", "Usage"],
        rows=[
            [".btn-primary", "Fond brand-600, texte blanc, ombre brand", "Action principale (CTA majeur)"],
            [".btn-accent",  "Fond accent-500, texte blanc",               "Action secondaire (paiement Stripe)"],
            [".btn-signal",  "Fond signal-400, texte slate-900",           "Mise en avant (carte visiteur, urgent)"],
            [".btn-outline", "Bordure brand-600, texte brand-600, fond transparent", "Action neutre, annulation"],
            [".btn-danger",  "Fond red-600, texte blanc",                  "Action destructive (supprimer, suspendre)"],
            [".btn-sm",      "Modifier — padding réduit",                  "Boutons dans tableaux"],
            [".btn-lg",      "Modifier — padding augmenté",                "Hero CTAs"],
        ],
        col_widths=[35, 65, 74],
    )

    pdf.h2("États interactifs")
    pdf.bullet("default — couleur de base.")
    pdf.bullet("hover — assombrir de 10 % + élever le shadow.")
    pdf.bullet("active — assombrir de 20 % + réduire le shadow.")
    pdf.bullet("focus — anneau brand-400/40 (2 px) pour navigation clavier.")
    pdf.bullet("disabled — opacity 0.5 + cursor not-allowed.")

    # ----- Structure ----------------------------------------------------
    pdf.h1("6. Structure du site")

    pdf.h2("Arborescence")
    pdf.code(
        "/                        Page d'accueil (publique, hero + 3 cartes)\n"
        "├── /fr/ /nl/ /en/       Idem dans la langue choisie\n"
        "├── /accounts/\n"
        "│    ├── login/          Connexion\n"
        "│    ├── register/       Inscription citoyen (form en 1 page)\n"
        "│    └── password/...    Reset / change password\n"
        "├── /me/                 Espace citoyen (login requis)\n"
        "│    ├── (citizens)      Dashboard, profil, demandes\n"
        "│    ├── vehicles/       Liste, ajout, édition, archive\n"
        "│    ├── permits/        Liste, détail, wizard, paiement\n"
        "│    ├── payments/       Stripe checkout, success, cancel\n"
        "│    └── companies/      Gestion entreprises (pour pro)\n"
        "├── /dashboard/\n"
        "│    ├── agent/          Espace agent (revue manuelle)\n"
        "│    ├── admin/          Espace admin (config + users + audit)\n"
        "│    └── super-admin/    Espace super-admin (idem + promotions)\n"
        "├── /map/                Carte interactive (publique, React-Leaflet)\n"
        "├── /api/v1/             API REST (token requis)\n"
        "│    ├── docs/           Swagger UI\n"
        "│    └── redoc/          Redoc\n"
        "└── /legal/\n"
        "     ├── privacy/        Politique de confidentialité (RGPD)\n"
        "     └── terms/          Conditions générales d'utilisation\n"
    )

    pdf.h2("Layout général")
    pdf.bullet("Header (sticky) — logo + liens primaires + sélecteur langue + avatar.")
    pdf.bullet("Hero (optionnel via block) — section pleine largeur pour les pages d'accueil ou marketing.")
    pdf.bullet("Main (container 1280 max) — contenu principal centré, padding latéral.")
    pdf.bullet("Footer — liens légaux, mentions, copyright, sélecteur langue redondé.")
    pdf.bullet("Cookies banner (bottom-right, sticky) — bandeau d'information, dismissible.")

    # ----- Trames de pages -----------------------------------------------
    pdf.h1("7. Trames de pages")

    pdf.h2("Page d'accueil (home)")
    pdf.code(
        "┌──────────────────────────────────────────┐\n"
        "│ HEADER (navbar)                          │\n"
        "├──────────────────────────────────────────┤\n"
        "│ HERO FULL-BLEED                          │\n"
        "│   Image (Grand-Place / Atomium)          │\n"
        "│   ┌──────────────────────────┐           │\n"
        "│   │ Titre + sous-titre        │           │\n"
        "│   │ CTA primaire              │           │\n"
        "│   │ Stats (19/3/100/24-7)     │           │\n"
        "│   └──────────────────────────┘           │\n"
        "├──────────────────────────────────────────┤\n"
        "│ 3 CARTES (riverain/visiteur/pro)         │\n"
        "│ ┌──────┐ ┌──────┐ ┌──────┐               │\n"
        "│ │ Card │ │ Card │ │ Card │               │\n"
        "│ └──────┘ └──────┘ └──────┘               │\n"
        "├──────────────────────────────────────────┤\n"
        "│ COMMENT ÇA MARCHE (4 étapes)             │\n"
        "├──────────────────────────────────────────┤\n"
        "│ SPLASH VISUEL Bruxelles + slogan         │\n"
        "├──────────────────────────────────────────┤\n"
        "│ FAQ (questions/réponses)                 │\n"
        "├──────────────────────────────────────────┤\n"
        "│ FOOTER                                   │\n"
        "└──────────────────────────────────────────┘\n"
    )

    pdf.h2("Page de rubrique (liste de cartes)")
    pdf.code(
        "┌──────────────────────────────────────────┐\n"
        "│ HEADER                                   │\n"
        "├──────────────────────────────────────────┤\n"
        "│ H1 'Mes cartes'                          │\n"
        "│ ─────                                    │\n"
        "│ Filtres (status, type, recherche)        │\n"
        "│                                          │\n"
        "│ ┌──────────────────────────────────┐    │\n"
        "│ │ Card 1 : plaque + statut + zone  │    │\n"
        "│ │   → Voir   → Renouveler          │    │\n"
        "│ ├──────────────────────────────────┤    │\n"
        "│ │ Card 2 : ...                     │    │\n"
        "│ └──────────────────────────────────┘    │\n"
        "│                                          │\n"
        "│ Pagination                               │\n"
        "├──────────────────────────────────────────┤\n"
        "│ FOOTER                                   │\n"
        "└──────────────────────────────────────────┘\n"
    )

    pdf.h2("Page de détail (carte)")
    pdf.code(
        "┌──────────────────────────────────────────┐\n"
        "│ HEADER                                   │\n"
        "├──────────────────────────────────────────┤\n"
        "│ Breadcrumb : Cartes > #42                │\n"
        "│                                          │\n"
        "│ ┌─────────────────────────┐ ┌────────┐  │\n"
        "│ │ INFOS PRINCIPALES        │ │ ZONES  │  │\n"
        "│ │ Type : Riverain          │ │ Map    │  │\n"
        "│ │ Statut : Active          │ │ ZONE-A │  │\n"
        "│ │ Validité : 1/1 → 31/12   │ │ ZONE-B │  │\n"
        "│ │ Plaque : 1-AAA-111       │ │        │  │\n"
        "│ └─────────────────────────┘ └────────┘  │\n"
        "│                                          │\n"
        "│ Historique (paiement, événements)        │\n"
        "│ Actions : Annuler / Renouveler           │\n"
        "├──────────────────────────────────────────┤\n"
        "│ FOOTER                                   │\n"
        "└──────────────────────────────────────────┘\n"
    )

    # ----- Maquettes ----------------------------------------------------
    pdf.h1("8. Maquettes et prototypage")

    pdf.h2("Maquettes fonctionnelles")
    pdf.p(
        "Les maquettes fonctionnelles ont été réalisées directement en code "
        "(HTML + Tailwind) plutôt qu'en Figma — l'utilisation de Tailwind "
        "permet d'itérer rapidement sur des composants réels, "
        "browser-rendered, plutôt que de produire des artefacts intermédiaires "
        "à transposer."
    )
    pdf.bullet("Bénéfice — pas de fossé maquette/implémentation.")
    pdf.bullet("Inconvénient — pas de visualisation séparée pour validation client en amont.")
    pdf.bullet("Mitigation — itérations courtes (push → demo → feedback) plutôt que validation lourde unique.")

    pdf.h2("Composants réutilisables (design system Tailwind)")
    pdf.bullet(".card / .card-hover — conteneurs blancs avec shadow et bordure subtile.")
    pdf.bullet(".input — champ texte avec focus brand et erreur red.")
    pdf.bullet(".badge-* (info/success/warning/danger) — pastilles d'état.")
    pdf.bullet(".btn-* (primary/accent/signal/outline/danger) — boutons normalisés.")
    pdf.bullet(".pb-nav-link — lien de navigation avec liseré actif jaune.")
    pdf.bullet(".pb-avatar — pastille circulaire avec ring coloré par rôle.")
    pdf.bullet(".pbc-stepper-* — stepper visuel adaptatif (mobile / desktop).")
    pdf.bullet(".reveal — animation fade-in sur scroll via IntersectionObserver.")

    pdf.h2("Animations")
    pdf.bullet("fade-in / fade-in-up / fade-in-down — apparition douce (0.5-0.6 s).")
    pdf.bullet("slide-in-right — entrée latérale des panneaux dropdown.")
    pdf.bullet("scale-in — apparition zoomée pour modales et menus.")
    pdf.bullet("float — flottement subtil (6 s) pour les éléments graphiques.")
    pdf.bullet("pulse-slow — clignotement lent (4 s) pour les badges de notification.")
    pdf.bullet("shimmer — animation gradient pour skeletons et loaders.")

    pdf.h2("Responsive design")
    pdf.bullet("Breakpoints Tailwind : sm (640 px) · md (768 px) · lg (1024 px) · xl (1280 px) · 2xl (1536 px).")
    pdf.bullet("Mobile (< 768 px) — burger menu, listes empilées, CTAs full-width, stepper compact 28 px.")
    pdf.bullet("Desktop (≥ 768 px) — navbar horizontale, tables détaillées, stepper standard 36 px.")
    pdf.bullet("Large desktop (≥ 1280 px) — container max-width 1280 px avec marges latérales généreuses.")

    return str(save_to(pdf, "05_rapport_conception_graphique.pdf"))


if __name__ == "__main__":
    print(generate())
