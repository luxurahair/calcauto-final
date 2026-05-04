# CalcAuto AiPro

> Application de financement vehiculaire pour concessionnaires automobiles Stellantis/FCA.
> Calculateur de paiements, import automatique de programmes mensuels, CRM integre.

---

## Apercu

CalcAuto AiPro est un outil professionnel concu pour les conseillers en financement automobile. Il permet de :

- **Calculer instantanement** les paiements de financement et de location (Option 1 / Option 2)
- **Importer automatiquement** les programmes d'incitatifs mensuels depuis les PDF officiels Stellantis
- **Gerer un inventaire** de vehicules avec decodage VIN et Window Stickers
- **Suivre les clients** via un CRM integre (soumissions, contacts, historique)
- **Comparer les options** de financement vs location SCI cote a cote

---

## Stack technique

| Composant | Technologie | Hebergement |
|-----------|-------------|-------------|
| Frontend | Expo 54 + React 19 + TypeScript | Vercel |
| Backend | FastAPI + Python 3.11 | Render |
| Base de donnees | MongoDB | MongoDB Atlas |
| Stockage fichiers | Supabase Storage | Supabase |

---

## Structure du projet

```
calcauto-aipro/
├── backend/                    # API FastAPI
│   ├── server.py               # Point d'entree (startup sync, migrations)
│   ├── routers/                # Endpoints API (/api/*)
│   │   ├── auth.py             # Authentification (login, register, demo)
│   │   ├── programs.py         # Programmes de financement
│   │   ├── import_wizard.py    # Import PDF (scan TOC + extraction)
│   │   ├── sci.py              # Taux location SCI + residuels
│   │   ├── inventory.py        # Inventaire vehicules
│   │   ├── submissions.py      # Soumissions CRM
│   │   ├── contacts.py         # Contacts
│   │   └── admin.py            # Administration
│   ├── services/
│   │   ├── pdfplumber_parser.py  # Parseur PDF deterministe
│   │   ├── storage.py            # Module Supabase Storage
│   │   └── email_service.py      # Envoi emails SMTP
│   ├── data/                   # Cache local (sync Supabase au demarrage)
│   └── tests/                  # Tests unitaires et integration
│
├── frontend/                   # App Expo/React Native (web + mobile)
│   ├── app/                    # Pages (Expo Router)
│   │   ├── (tabs)/             # Onglets principaux
│   │   │   ├── index.tsx       # Calculateur de financement
│   │   │   ├── inventory.tsx   # Inventaire
│   │   │   ├── clients.tsx     # CRM
│   │   │   └── admin.tsx       # Administration
│   │   ├── import.tsx          # Import PDF avec checkboxes
│   │   └── login.tsx           # Connexion
│   ├── components/             # Composants reutilisables
│   ├── hooks/                  # Hooks personnalises
│   ├── utils/                  # Utilitaires (API, i18n, calculs)
│   └── locales/                # Traductions (FR/EN)
│
└── ARCHITECTURE.md             # Documentation technique detaillee
```

---

## Fonctionnalites principales

### Import PDF intelligent
- Upload du PDF mensuel d'incitatifs Stellantis
- Lecture automatique de la Table des Matieres
- Selection des sections a extraire via checkboxes
- Extraction deterministe avec `pdfplumber` (pas d'IA)
- Sauvegarde automatique vers Supabase Storage

## Fonctionnalites detaillees par onglet

L'application est organisee en **4 onglets** principaux. Voici ce que fait chacun.

### 🟢 Onglet 1 : CALCUL (`app/(tabs)/index.tsx` — 1970 lignes)

Le **coeur** de l'application : calculateur de paiements financement + location SCI cote a cote.

**En-tete**
- Titre "CalcAuto AiPro"
- Selecteur de periode (mois Stellantis : Fev / Mars / Avril 2026)
- Toggle FR / EN
- Bouton ⬆️ Import PDF (admin, protege par mot de passe)
- Bouton ⚙️ Logout

**Filtres vehicules**
- Annee : Tous / 2024 / 2025 / 2026
- Marque : Tous / Chrysler / Dodge / Fiat / Jeep / Ram
- Cartes affichant : Modele + Trim, Consumer Cash, Taux Option 1 & 2

**Section calcul (apres selection d'un vehicule)** — environ 25 champs configurables :
- Vehicule selectionne (Marque + Modele + Trim + Annee)
- Consumer Cash (rabais usine)
- Bonus Cash (ex: $5,000 pour Fiat 500e 2025)
- Toggle Option 1 / Option 2 (deux grilles de taux)
- Terme : 36 / 48 / 60 / 72 / 84 / 96 mois
- Frequence : Mensuel / Bi-mensuel / Hebdomadaire
- Loyaute (taux reduit si eligible)
- Paiement differe (premier paiement apres 90 jours)

**Section prix**
- Prix vehicule (manuel ou auto-rempli depuis l'inventaire)
- Bouton "Inventaire" : selection d'un vehicule en stock → prix automatique
- Bonus Cash custom, comptant TTC, accessoires, frais dossier
- Taxe pneus, frais RDPRM
- Prix d'echange + montant du sur l'echange

**Section Location SCI** (toggle "Voir Location")
- Terme : 24 / 36 / 39 / 48 / 60 mois
- Km/an : 18,000 / 20,000 / 24,000
- Lease Cash (rabais SCI automatique)
- PDSF Location (base du calcul residuel)
- Solde reporte (transfert d'un ancien bail)
- Rabais concessionnaire
- Resultat : paiement mensuel + bi-mensuel + hebdomadaire
- **Grille d'analyse** : tous les termes × tous les km, **meilleur choix surligne**

**Section resultats financement**
- Taux applique (du terme/option choisi)
- Paiement mensuel / bi-mens / hebdo (incluant taxes)
- Resume complet : taxe federale, provinciale, cout total

**Actions en bas**
- 📧 Envoyer par email (modal nom/tel/email du client → envoie + sauve la soumission)
- 📱 Partager par SMS (texte formate pret a envoyer)
- 🖨️ Imprimer (version imprimable)
- 📊 Exporter Excel (`.xlsx` complet)

---

### 🟠 Onglet 2 : INVENTAIRE (`app/(tabs)/inventory.tsx` — 1792 lignes)

**Gestion complete du stock** de vehicules.

**Stats en haut**
- Total / Disponible / Reserve / Vendu (badges colores)

**Filtres**
- Type : Tous / Neuf / Occasion
- Statut : Tous / Disponible / Reserve / Vendu
- Recherche par stock #, marque, modele, VIN

**Cartes vehicules**
- Badge statut (vert dispo / orange reserve / rouge vendu)
- Stock #, annee, marque, modele, trim
- VIN (17 caracteres)
- Grille prix : PDSF / Prix affiche / Cout net / Profit
- Boutons : Changer statut (Dispo ↔ Reserve ↔ Vendu) / Supprimer

**4 methodes d'entree**

| Methode | Endpoint | Description |
|---|---|---|
| ➕ Ajouter manuel | (UI seulement) | Formulaire complet avec dropdowns SCI cascade (marque → modele → trim → carrosserie) |
| 📷 Scanner photo | `POST /api/scan-invoice` | Photo via camera/galerie → OCR Google Vision → modal de verification |
| 📄 Importer PDFs | `POST /api/scan-invoice-file` | Multi-fichiers de factures FCA, parsing batch |
| 📊 Importer Excel | `POST /api/invoice/import-excel` | Fichier `.xlsx` formate avec template |

**Modal "Verifier et corriger"** (apres OCR)
- Tous les champs pre-remplis et **modifiables** : stock, VIN, marque, modele, trim, annee, type, EP, PDCO, holdback, PDSF, prix affiche, couleur
- Indicateur de **score de confiance OCR** (%)
- Boutons "Passer" / "Confirmer et ajouter"

---

### 🔵 Onglet 3 : CRM (`app/(tabs)/clients.tsx` — 2308 lignes)

**4 sous-onglets** pour la relation client.

#### Sous-onglet "Clients"
- Liste triee par derniere interaction
- Recherche par nom ou telephone
- Badge nb soumissions par client
- Bouton "Ajouter" (contact manuel)
- Bouton "Importer" : **vCard (iCloud)** ou **CSV (Google Contacts)**
- Detail expand → toutes ses soumissions, notes, rappels
- Actions : Appeler / SMS / Email / Nouvelle soumission

#### Sous-onglet "Rappels"
- Liste des suivis planifies avec dates
- Badges urgence : 🔴 En retard / 🟡 Aujourd'hui / 🟢 A venir
- Actions : "Fait" / "Appeler" / "Modifier"
- Planification : date + heure + notes

#### Sous-onglet "Offres" (Meilleures offres) — relance automatique
**Comparaison automatique** quand un nouveau mois arrive : compare TOUS les clients actifs vs les nouveaux programmes.

- Affichage : ancien paiement vs nouveau paiement → **economie $/mois**
- Grille par terme : economie pour chaque terme (36-96 mois)
- Bouton "Verifier nouveaux programmes" pour lancer manuellement
- **Approuver & Envoyer** : email auto au client avec la nouvelle offre
- **Ignorer** : cache l'offre

> 🔍 **Methode Delta** (`POST /api/compare-programs`) : on calcule la difference theorique sans taxes/frais entre ancien et nouveau programme, puis on applique ce delta au paiement reel du client. Evite la confusion "ancien paiement avec taxes" vs "nouveau sans taxes".

#### Sous-onglet "Historique"
- Toutes les soumissions chronologiques
- Detail par soumission : client, vehicule, prix, terme, paiement, date
- 🔑 **"Ouvrir le calcul"** : restaure l'**EXACT** etat du calculateur → permet de modifier/renvoyer
- Filtres par mois de programme

---

### 🟣 Onglet 4 : ADMIN (`app/(tabs)/admin.tsx` — 926 lignes)

**3 sous-onglets** d'administration.

#### Sous-onglet "Utilisateurs"
- Liste users avec stats (email, role, nb contacts, nb soumissions, derniere connexion)
- Actions : Bloquer / Debloquer / Promouvoir admin / Supprimer
- Stats globales : total users, actifs, bloques, contacts, soumissions

#### Sous-onglet "Ordre" (Vehicle Order Manager)
- **Drag & drop** pour reorganiser l'ordre d'affichage des vehicules dans le calculateur
- Filtre par marque
- Bouton "Sauvegarder l'ordre"

#### Sous-onglet "Excel" (Import/Export Manager)
- **Exporter programmes** : telecharge un `.xlsx` avec tous les programmes
- **Importer Excel corrige** : upload du fichier modifie → mise a jour
- **Rapport de comparaison** : montre les differences avant/apres import (Consumer Cash change, taux modifie, etc.)
- Protection : mot de passe admin requis

---

## Refonte parser PDF (mars 2026) — suggestions Grok appliquees

L'extraction des programmes mensuels Stellantis a ete **reecrite en mode deterministe** :

| Avant (IA) | Apres (Grok suggestions) |
|---|---|
| GPT-4 Vision sur chaque page | `pdfplumber` direct → tables natives |
| ~70-85% precision (hallucinations) | ✅ **100% reproductible** sur PDFs FCA |
| ~$0.05 par PDF | ✅ **$0** (zero IA) |
| Index hardcodes des pages | ✅ **Content-driven** : detection par signature de table |
| Brand infere ligne par ligne | ✅ **TOC-based** : extraction par section TOC |

**3 parsers deterministes** dans `backend/services/pdfplumber_parser.py` :

1. `parse_retail_programs()` — Finance Prime / Non-Prime (pages ~20-21)
2. `parse_sci_lease()` — taux SCI Lease + residuels (pages ~28-29)
3. `parse_key_incentives()` — Go-to-Market summary + Consumer Cash + Bonus (pages 3-4)

**Test de reference** : `backend/tests/test_march_2026_extraction.py` valide **93 programmes** extraits du PDF de mars 2026 (`test_extract_pdf_returns_93_programs`).

**Suite de tests dediee** :
- `test_pdfplumber_extraction.py`
- `test_content_driven_parser.py` (verifie l'identification par contenu)
- `test_extract_pdf_dual_page.py` (PDFs sur 2 pages)
- `test_toc_extraction.py` (TOC parsing)

---

## Calculateur de financement
- Taux Option 1 et Option 2
- Consumer Cash et Bonus Cash
- Termes de 24 a 96 mois
- Calcul de location SCI avec residuels
- Comparaison financement vs location

### CRM
- Soumissions clients avec details vehicule/financement
- Carnet de contacts
- Envoi de calculs par email
- Historique des soumissions

### Administration
- Gestion des utilisateurs
- Import de programmes
- Reordonnement des vehicules
- Mode demo (sans mot de passe)

---

## Installation locale

### Prerequis
- Python 3.11+
- Node.js 18+
- MongoDB (local ou Atlas)
- Yarn

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Linux/Mac
# venv\Scripts\activate       # Windows
pip install -r requirements.txt
```

Creer un fichier `backend/.env` :
```env
MONGO_URL=mongodb+srv://user:pass@cluster.mongodb.net/calcauto
DB_NAME=calcauto_prod
ADMIN_PASSWORD=VotreMotDePasse
SUPABASE_URL=https://votre-projet.supabase.co
SUPABASE_KEY=votre-cle-service-role
OPENAI_API_KEY=sk-...
GOOGLE_VISION_API_KEY=AIza...
SMTP_EMAIL=votre@email.com
SMTP_PASSWORD=mot-de-passe-application
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

> **OPENAI_API_KEY** : Pour GPT-4o Vision (structuration IA des factures). Obtenir sur [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
>
> **GOOGLE_VISION_API_KEY** : Pour l'OCR haute precision des factures. Obtenir sur [Google Cloud Console](https://console.cloud.google.com) > APIs & Services > Activer "Cloud Vision API" > Credentials
>
> **SUPABASE_KEY** : Cle `service_role` (pas `anon`). Obtenir sur Supabase > Project Settings > API

Demarrer le serveur :
```bash
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

### Frontend

```bash
cd frontend
yarn install
```

Creer un fichier `frontend/.env` :
```env
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
```

Demarrer en mode web :
```bash
npx expo start --web
```

---

## Deploiement

| Service | Plateforme | Configuration |
|---------|-----------|---------------|
| Backend | Render | `Procfile` + `render.yaml` inclus |
| Frontend | Vercel | `vercel.json` inclus (rewrites vers le backend) |
| Base de donnees | MongoDB Atlas | Configurer `MONGO_URL` dans les variables d'environnement |
| Stockage | Supabase | Bucket `calcauto-data` (cree automatiquement) |

> Voir `ARCHITECTURE.md` pour le guide de deploiement complet pas a pas.

---

## Endpoints API

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/auth/login` | Connexion (email + password) |
| POST | `/api/auth/demo-login` | Mode demo automatique |
| POST | `/api/auth/register` | Creation de compte |
| GET | `/api/programs` | Liste programmes du dernier mois |
| GET | `/api/programs?program_month=3&program_year=2026` | Programmes d'un mois specifique |
| POST | `/api/programs` | Creer un programme (admin) |
| POST | `/api/calculate` | Calcul paiement financement + location |
| POST | `/api/scan-pdf` | **Detecte ranges de pages depuis la TOC** |
| POST | `/api/extract-pdf` | **Extraction deterministe via pdfplumber** |
| POST | `/api/extract-pdf-async` | Extraction async pour gros PDFs |
| GET | `/api/program-meta` | Metadata du mois (taux loyaute, no payments days) |
| GET | `/api/sci/lease-rates` | Taux location SCI |
| GET | `/api/sci/residuals` | Valeurs residuelles |
| GET | `/api/inventory` | Liste vehicules en stock |
| POST | `/api/inventory` | Ajouter un vehicule |
| PUT | `/api/inventory/{id}` | Modifier un vehicule |
| DELETE | `/api/inventory/{id}` | Supprimer un vehicule |
| POST | `/api/scan-invoice` | **OCR Google Vision** sur image base64 |
| POST | `/api/scan-invoice-file` | OCR sur fichier PDF de facture |
| POST | `/api/test-ocr` | Endpoint debug Google Vision |
| GET | `/api/window-sticker/{vin}` | Window Sticker Stellantis (PDF) |
| GET | `/api/submissions` | Soumissions CRM (historique) |
| POST | `/api/submissions` | Sauver une soumission |
| GET | `/api/contacts` | Carnet d'adresses |
| POST | `/api/contacts/bulk` | **Import vCard / CSV** (iCloud / Google) |
| POST | `/api/compare-programs` | **Methode Delta : meilleures offres** |
| DELETE | `/api/better-offers/{id}` | Ignorer une offre |
| POST | `/api/send-calculation-email` | Envoyer le calcul par email |
| GET | `/api/admin/users` | Gestion users (admin) |
| GET | `/api/admin/parsing-stats` | Stats OCR (methodes, economies vs GPT-4) |
| GET | `/api/ping` | Keep-alive |

---

## Etat actuel / Limites

- Le stockage fichiers passe par **Supabase Storage** — le backend maintient un **cache local** synchronise au demarrage
- **MongoDB** reste la base principale pour les programmes, utilisateurs et CRM
- Le parseur PDF (`pdfplumber`) est deterministe mais **sensible aux changements de format** des PDF mensuels — chaque nouveau mois peut reveler des cas limites
- Les composants frontend `index.tsx` (~3000 lignes), `inventory.tsx` et `clients.tsx` sont encore **monolithiques** et candidats au refactoring
- L'authentification utilise des tokens SHA256 maison — pas de JWT standard ni OAuth
- Le projet utilise **yarn** comme gestionnaire de paquets (pas npm)

---

## Tests

```bash
cd backend
pytest tests/ -v
```

---

## Licence

Projet prive - Tous droits reserves.
