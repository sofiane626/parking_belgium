# Paiement — 3 méthodes disponibles

Trois passerelles sont implémentées. Le citoyen choisit sur la page
`/me/payments/permit/<pk>/start/`. Chaque méthode est cachée si non configurée.

| Méthode | Setup | Carte test | Conditions |
|---|---|---|---|
| **Carte bancaire interne** | Aucun | `4242 4242 4242 4242` | Toujours active |
| **Stripe Checkout** | Compte Stripe (test) | `4242 4242 4242 4242` | `STRIPE_PUBLIC_KEY` + `STRIPE_SECRET_KEY` |
| **Simulation** | Rien | — | `DEBUG=True` ou staff |

---

## 1. Carte bancaire interne (toujours dispo)

C'est un **vrai formulaire** qui exige que le citoyen tape un numéro de carte
Luhn-valide, une date d'expiration future, un CVC à 3-4 chiffres et le nom du
porteur. Pas de banque réelle derrière, mais l'expérience est complète.

**Sécurité** :
- Le PAN n'est **jamais** stocké (seulement marque + 4 derniers chiffres)
- Le CVC n'est jamais stocké
- Algorithme de Luhn validé côté serveur (pas que JS)

**Cartes de test** :
| Carte | Comportement |
|---|---|
| `4242 4242 4242 4242` | Visa — succès |
| `5555 5555 5555 4444` | Mastercard — succès |
| `3782 822463 10005` | Amex — succès |
| `4000 0000 0000 0002` | Refusée (do_not_honor) |
| `4000 0000 0000 9995` | Solde insuffisant |
| `4000 0000 0000 0069` | Carte expirée |
| `4000 0000 0000 0127` | CVC incorrect |

Toute autre carte Luhn-valide est acceptée.

---

## 2. Stripe Checkout

Voir [STRIPE_SETUP.md](STRIPE_SETUP.md). Permet en plus Bancontact (paiement
belge officiel) et Apple/Google Pay.

---

## 3. Simulation (test rapide)

Bouton **🧪 Simuler le paiement** visible si `DEBUG=True` ou staff.
Court-circuite tout, active la carte instantanément. À utiliser uniquement
quand tu veux enchaîner les tests sans saisir de carte.

---

## Sécurité globale

- Toutes les transitions passent par des services centralisés avec
  `select_for_update`
- Contrainte unique partielle DB : 1 seul SUCCEEDED par permit (anti
  double-activation)
- Owner check (le citoyen ne peut traiter que ses propres paiements)
- Idempotence : confirmer 2× un paiement déjà succeeded = no-op
- Webhooks Stripe vérifiés via signature `STRIPE_WEBHOOK_SECRET`
- Email de confirmation envoyé au citoyen (`DEFAULT_FROM_EMAIL`)

---

## Récapitulatif des URLs

| Action | URL |
|---|---|
| Choix méthode | `/me/payments/permit/<pk>/start/` |
| Formulaire carte | `/me/payments/permit/<pk>/card/` |
| Lancer Stripe | POST `/me/payments/permit/<pk>/stripe/` |
| Webhook Stripe | POST `/me/payments/stripe/webhook/` |
| Simulation | POST `/me/payments/permit/<pk>/simulate/` |
