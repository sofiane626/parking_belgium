# Stripe Checkout — Setup local

Le paiement utilise **Stripe Checkout en mode TEST** : tu vis le vrai parcours
(page hostée Stripe, formulaire carte bancaire ou Bancontact, validation 3DS),
mais aucun débit réel ne se produit. Cartes test fournies par Stripe.

## 1. Créer un compte Stripe (gratuit, 2 minutes)

1. Va sur https://dashboard.stripe.com/register
2. Inscris-toi avec ton email — pas besoin de fournir un IBAN ni un SIREN pour
   le mode test
3. Tu arrives sur le dashboard, tout en haut tu verras le bandeau orange
   **"Mode test"** (laisse-le activé)

## 2. Récupérer les clés

1. Menu de gauche → **Développeurs** → **Clés API**
2. Tu vois deux clés :
   - **Publishable key** : `pk_test_51XXXXX…`
   - **Secret key** (cliquer "Révéler") : `sk_test_51XXXXX…`

## 3. Coller dans `.env`

Ajoute ces lignes à la fin de `.env` :

```env
STRIPE_PUBLIC_KEY=pk_test_51XXXXX…
STRIPE_SECRET_KEY=sk_test_51XXXXX…
STRIPE_CURRENCY=eur
```

Redémarre `runserver`. Le bouton bleu **"Payer par carte"** apparaît
maintenant sur la page de paiement à la place du flux interne.

## 4. Tester un paiement

1. Connecte-toi en citoyen avec une carte en `awaiting_payment` (prix > 0)
2. Clique **Payer** → **Payer par carte**
3. Tu es redirigé sur `https://checkout.stripe.com/c/pay/cs_test_…`
4. Saisis :
   - Numéro de carte : `4242 4242 4242 4242`
   - Date : `12 / 34` (n'importe quelle date future)
   - CVC : `123`
   - Code postal : `1000`
5. Clique **Payer**
6. Tu es redirigé sur Parking.Belgium → carte ACTIVE → email de confirmation

## 5. Cartes test utiles

| Carte | Numéro | Comportement |
|---|---|---|
| Visa OK | `4242 4242 4242 4242` | Succès immédiat |
| Mastercard OK | `5555 5555 5555 4444` | Succès immédiat |
| Visa 3DS requise | `4000 0027 6000 3184` | Redemande authentification |
| Échec décliné | `4000 0000 0000 0002` | Carte refusée |
| Solde insuffisant | `4000 0000 0000 9995` | Échec après autorisation |

Liste complète : https://stripe.com/docs/testing#cards

## 6. (Optionnel) Webhook local pour la fiabilité

Sans webhook : le succès est confirmé via la **redirection success_url** quand
le citoyen revient sur le site. C'est suffisant pour tester. Mais si le
citoyen ferme l'onglet pendant qu'il paie, le statut ne se met pas à jour.

Pour tester le filet de sécurité webhook :

1. Installe la CLI Stripe : https://stripe.com/docs/stripe-cli
2. Lance dans un terminal :
   ```bash
   stripe login
   stripe listen --forward-to localhost:8000/me/payments/stripe/webhook/
   ```
3. La CLI affiche `whsec_…` → copie dans `.env` :
   ```env
   STRIPE_WEBHOOK_SECRET=whsec_xxxxx
   ```
4. Redémarre runserver. Désormais Stripe pousse `checkout.session.completed`
   vers ton serveur local et la confirmation est garantie même si l'utilisateur
   ferme l'onglet.

## 7. Bouton simulation (toujours dispo)

Le bouton **🧪 Simuler le paiement (test)** reste affiché à côté quand tu es
en `DEBUG=True` ou staff/back-office. Il court-circuite Stripe et active la
carte instantanément — utile quand tu enchaînes les tests.

## Sécurité

- En mode test, ta clé secrète `sk_test_…` ne donne accès qu'au mode test
  (aucun vrai charge possible)
- Ne commit JAMAIS la clé `sk_live_…` dans Git — utilise toujours `.env`
- Le webhook vérifie la signature `Stripe-Signature` avec
  `STRIPE_WEBHOOK_SECRET` → même un attaquant qui connaît l'URL ne peut pas
  forger un event
