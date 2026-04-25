# Envoi d'emails réels (SMTP)

Par défaut, le projet **n'envoie pas** d'emails — il les affiche dans le
terminal `runserver` (backend console). C'est pratique pour développer mais
tu ne reçois rien dans ta boîte.

Pour recevoir vraiment les emails (mot de passe oublié, validation paiement,
réinitialisation par admin…), configure un serveur SMTP dans `.env`.

Deux options simples ci-dessous.

---

## Option 1 — Gmail (recommandée pour test rapide avec ton vrai email)

### a) Activer la 2FA sur ton compte Google
Indispensable pour pouvoir générer un App Password.
- https://myaccount.google.com/security
- Section **« Connexion à Google »** → active **« Validation en 2 étapes »** si ce n'est pas déjà fait.

### b) Créer un App Password
- https://myaccount.google.com/apppasswords (apparaît seulement une fois la 2FA activée)
- Nom de l'app : `Parking.Belgium` (ou ce que tu veux)
- Google génère un code de **16 caractères** type `xxxx xxxx xxxx xxxx`
- Copie-le — il ne sera plus affiché ensuite.

### c) Ajouter dans `.env`
```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=sofianeezzahti@gmail.com
EMAIL_HOST_PASSWORD=xxxx xxxx xxxx xxxx
EMAIL_USE_TLS=True
DJANGO_DEFAULT_FROM_EMAIL=Parking.Belgium <sofianeezzahti@gmail.com>
```

### d) Redémarrer runserver
Les emails partent maintenant **réellement** depuis ton Gmail vers les
adresses des destinataires.

> Limite Gmail : ~500 emails/jour. Largement suffisant pour développer/tester.

---

## Option 2 — Mailtrap (sandbox de test, pas de vraie boîte)

Mailtrap **capture** les emails envoyés mais ne les délivre pas réellement —
parfait pour tester sans spammer de vraies boîtes.

1. Crée un compte gratuit sur https://mailtrap.io
2. Dashboard → **Inboxes** → ton inbox par défaut → onglet **Show Credentials**
   → choisis "Django" en haut à droite
3. Mailtrap te donne un bloc tout fait à copier dans `.env` :
   ```env
   EMAIL_HOST=sandbox.smtp.mailtrap.io
   EMAIL_PORT=2525
   EMAIL_HOST_USER=xxxxxxxxxxxxxx
   EMAIL_HOST_PASSWORD=xxxxxxxxxxxxxx
   EMAIL_USE_TLS=True
   ```
4. Redémarre runserver
5. Tous les emails atterrissent dans ton inbox Mailtrap (pas de boîte réelle
   destinataire impactée)

---

## Vérifier que ça marche

```bash
.venv\Scripts\python.exe manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail("Test Parking.Belgium", "Hello !", None, ["destinataire@example.com"])
1
```

- Si ça retourne `1` sans erreur → email envoyé
- Si erreur `SMTPAuthenticationError` → mauvais user/password (App Password
  pour Gmail, vérifier la 2FA est active)
- Si erreur `SMTPServerDisconnected` → vérifier `EMAIL_PORT` (587 pour TLS,
  465 pour SSL avec `EMAIL_USE_SSL=True`)

---

## Repasser en mode console (sans SMTP)

Vide simplement `EMAIL_HOST` dans `.env` et redémarre runserver. Les emails
seront à nouveau affichés dans le terminal.

---

## Sécurité

- **Ne commit jamais `.env`** (il est gitignored)
- L'App Password Gmail peut être révoqué à tout moment depuis
  https://myaccount.google.com/apppasswords
- En production, utilise un service dédié (SendGrid, Mailgun, AWS SES…) avec
  une **adresse expéditrice vérifiée** sur ton domaine — sinon les emails
  partent en spam.
