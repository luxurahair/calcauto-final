# CalcAuto AiPro - Architecture & Guide de Deploiement

> Document complet pour comprendre, deployer et maintenir l'application de maniere independante.
> Derniere mise a jour : 17 mars 2026

---

## Table des matieres

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture Backend (FastAPI)](#2-architecture-backend-fastapi)
3. [Architecture Frontend (Expo React)](#3-architecture-frontend-expo-react)
4. [Base de donnees (MongoDB)](#4-base-de-donnees-mongodb)
5. [Stockage persistant (Supabase)](#5-stockage-persistant-supabase)
6. [Deploiement](#6-deploiement)
   - [GitHub](#61-github)
   - [Backend sur Render](#62-backend-sur-render)
   - [Frontend sur Vercel](#63-frontend-sur-vercel)
7. [Variables d'environnement](#7-variables-denvironnement)
8. [Flux de donnees](#8-flux-de-donnees)
9. [Maintenance et operations courantes](#9-maintenance-et-operations-courantes)
10. [Depannage](#10-depannage)

---

## 1. Vue d'ensemble

**CalcAuto AiPro** est une application full-stack de financement vehiculaire composee de 4 parties :

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│   FRONTEND      │       │   BACKEND       │       │   BASE DE       │
│   (Vercel)      │──────>│   (Render)      │──────>│   DONNEES       │
│   Expo/React    │       │   FastAPI       │       │   (MongoDB      │
│   TypeScript    │       │   Python 3.11   │       │    Atlas)       │
└─────────────────┘       └─────────────────┘       └─────────────────┘
                                │
                                │
                          ┌─────▼─────────────┐
                          │   STOCKAGE        │
                          │   (Supabase       │
                          │    Storage)       │
                          └───────────────────┘
```

| Composant | Technologie | Hebergement |
|-----------|-------------|-------------|
| Frontend  | Expo (React) + TypeScript | Vercel |
| Backend   | FastAPI + Python 3.11 | Render |
| Base de donnees | MongoDB | MongoDB Atlas (cloud) |
| Stockage fichiers | Supabase Storage | Supabase (cloud) |

**Repository GitHub (compte `Lianag2018`):**
- Monorepo : `Lianag2018/calcauto-aipro` (backend/ + frontend/)

---

## 2. Architecture Backend (FastAPI)

### Structure des fichiers

```
backend/
├── server.py              # Point d'entree principal (FastAPI app)
│                          #   - Startup: sync Supabase -> cache local
│                          #   - Startup: migration auto des donnees
├── database.py            # Connexion MongoDB + configuration globale
├── models.py              # Modeles Pydantic (validation des donnees)
├── dependencies.py        # Fonctions utilitaires (auth, calculs)
│
├── routers/               # Endpoints API (chaque fichier = un groupe)
│   ├── auth.py            # /api/auth/* (register, login, demo-login)
│   ├── programs.py        # /api/programs (CRUD), /api/calculate, /api/seed
│   ├── import_wizard.py   # /api/scan-pdf, /api/extract-pdf-async, /api/import-wizard
│   │                      #   - Scan TOC -> checkboxes -> extraction selective
│   │                      #   - Upload resultats vers Supabase apres extraction
│   ├── sci.py             # /api/sci/* (taux location SCI, residuels)
│   │                      #   - Lit depuis le cache local (sync Supabase au demarrage)
│   ├── submissions.py     # /api/submissions (CRM: soumissions clients)
│   ├── contacts.py        # /api/contacts (carnet d'adresses)
│   ├── inventory.py       # /api/inventory (gestion vehicules en stock)
│   ├── invoice.py         # /api/invoice/scan (scanner factures OCR/IA)
│   ├── email.py           # /api/email/send (envoi emails de calcul)
│   ├── admin.py           # /api/admin/* (gestion utilisateurs, stats)
│   └── pdf_parser.py      # /api/corrections (gestion corrections manuelles)
│
├── services/
│   ├── pdfplumber_parser.py  # Logique d'extraction PDF (pdfplumber)
│   │                         #   - improved_parse_toc: lecture TOC
│   │                         #   - parse_retail_programs_content_driven: programmes finance
│   │                         #   - parse_sci_lease_programs: taux location SCI
│   │                         #   - parse_bonus_cash_page: bonus cash
│   ├── storage.py            # Module Supabase Storage (upload/download/sync)
│   ├── email_service.py      # Service SMTP (envoi emails via Gmail)
│   └── window_sticker.py     # Recuperation Window Sticker Stellantis
│
├── scripts/
│   └── setup_trim_orders.py  # Script pour configurer l'ordre des trims
│
├── data/                  # Cache local (sync depuis Supabase au demarrage)
│   ├── sci_lease_rates_*.json     # Taux location SCI (par mois)
│   ├── key_incentives_*.json      # Incitatifs cles (par mois)
│   ├── program_meta_*.json        # Metadonnees programmes (par mois)
│   ├── sci_residuals_*.json       # Valeurs residuelles (par mois)
│   ├── fca_product_codes_2026.json  # Codes produits FCA (reference)
│   ├── code_program_mapping.json    # Mapping codes -> programmes
│   └── FCA_Master_Codes.xlsx        # Master reference codes produits
│
├── tests/                 # Tests unitaires et integration
│   ├── test_ci_unit.py             # Tests pour CI/CD
│   ├── test_content_driven_parser.py
│   ├── test_march_2026_extraction.py
│   ├── test_sci_lease.py
│   └── ... (30+ fichiers de test)
│
├── requirements.txt       # Dependances Python
├── Procfile               # Commande de demarrage (Render)
├── render.yaml            # Configuration Render
└── runtime.txt            # Version Python (3.11.4)
```

### Fichiers cles expliques

#### `server.py` - Point d'entree
C'est le fichier principal qui demarre l'application FastAPI. Il:
- Cree l'application FastAPI avec tous les routers sous `/api`
- Configure le CORS (toutes origines autorisees)
- **Sync Supabase au demarrage:** Telecharge les JSON mensuels depuis Supabase vers `/data`
- **Migration auto:** Corrige les donnees 2025/2026 au premier demarrage (bonus_cash, inversions)
- Gere la fermeture propre de MongoDB

#### `services/pdfplumber_parser.py` - Parseur PDF
Le coeur de l'application. Utilise `pdfplumber` pour extraire les donnees des PDF d'incitatifs mensuels :
- **`improved_parse_toc()`** : Lit la Table des Matieres (page 2) et retourne toutes les sections avec leurs numeros de page
- **`parse_retail_programs_content_driven()`** : Extrait les programmes de financement (taux Option 1/2, consumer cash, bonus cash)
- **`parse_sci_lease_programs()`** : Extrait les taux de location SCI avec alignement correct des noms/taux
- **`parse_bonus_cash_page()`** : Extrait les bonus cash depuis une page separee et les fusionne avec les programmes

#### `services/storage.py` - Supabase Storage
Module centralise pour toutes les operations de fichiers :
- **`sync_from_supabase()`** : Au demarrage, telecharge tous les JSON mensuels dans le cache local
- **`upload_monthly_json()`** : Apres extraction, uploade les JSON vers Supabase
- **`upload_local_file()` / `download_to_local()`** : Operations generiques upload/download

#### `routers/import_wizard.py` - Pipeline d'import
Orchestre le flux complet d'import PDF :
1. `/scan-pdf` : Upload le PDF, lit la TOC, retourne les sections trouvees
2. `/extract-pdf-async` : Recoit les sections selectionnees, lance l'extraction en arriere-plan
3. Sauvegarde les resultats en JSON local + upload vers Supabase
4. Genere un fichier Excel de validation

### Endpoints API principaux

| Methode | Endpoint | Description |
|---------|----------|-------------|
| **Authentification** | | |
| POST | `/api/auth/register` | Inscription d'un utilisateur |
| POST | `/api/auth/login` | Connexion (retourne un token) |
| POST | `/api/auth/demo-login` | Connexion mode demo (sans mot de passe) |
| **Programmes** | | |
| GET | `/api/programs` | Liste des programmes de financement |
| POST | `/api/calculate` | Calcul de financement pour un vehicule |
| PUT | `/api/programs/reorder` | Reordonnement des programmes (admin) |
| GET | `/api/periods` | Periodes disponibles (mois/annee) |
| GET | `/api/program-meta` | Metadonnees du programme mensuel |
| **Import PDF** | | |
| POST | `/api/scan-pdf` | Scan TOC du PDF -> retourne sections avec checkboxes |
| POST | `/api/extract-pdf-async` | Extraction selective des sections choisies |
| GET | `/api/extract-status/{task_id}` | Statut de l'extraction async |
| **SCI (Location)** | | |
| GET | `/api/sci/lease-rates` | Taux de location SCI (depuis cache local) |
| GET | `/api/sci/residuals` | Valeurs residuelles SCI |
| **CRM** | | |
| GET/POST | `/api/submissions` | Gestion des soumissions clients |
| GET/POST | `/api/contacts` | Gestion des contacts |
| **Inventaire** | | |
| GET/POST | `/api/inventory` | Gestion de l'inventaire vehiculaire |
| **Corrections** | | |
| GET/POST | `/api/corrections` | Corrections manuelles des programmes |
| **Utilitaires** | | |
| POST | `/api/invoice/scan` | Scanner une facture (OCR) |
| POST | `/api/email/send` | Envoyer un calcul par email |
| GET/HEAD | `/api/ping` | Keep-alive (UptimeRobot) |
| **Admin** | | |
| GET | `/api/admin/users` | Liste des utilisateurs |
| GET | `/api/admin/stats` | Statistiques globales |

---

## 3. Architecture Frontend (Expo React)

### Structure des fichiers

```
frontend/
├── app/
│   ├── _layout.tsx              # Layout racine (auth, navigation, splash screen)
│   ├── login.tsx                # Page de connexion
│   ├── import.tsx               # Page d'import PDF (checkboxes de sections)
│   ├── manage.tsx               # Page de gestion
│   └── (tabs)/
│       ├── _layout.tsx          # Configuration des onglets (barre de navigation)
│       ├── index.tsx            # Onglet "Calcul" (calculateur principal ~3000+ lignes)
│       ├── inventory.tsx        # Onglet "Inventaire"
│       ├── clients.tsx          # Onglet "CRM" (soumissions + contacts)
│       └── admin.tsx            # Onglet "Admin" (visible admin seulement)
│       └── styles/              # Styles des onglets
│
├── components/
│   ├── AnimatedSplashScreen.tsx # Animation d'ecran de demarrage (comete)
│   ├── EmailModal.tsx           # Modal d'envoi d'email
│   ├── EventBanner.tsx          # Banniere d'evenements promotionnels
│   ├── FilterBar.tsx            # Barre de filtres
│   ├── LanguageSelector.tsx     # Selecteur de langue (FR/EN)
│   ├── LoadingBorderAnimation.tsx # Animation de chargement
│   ├── index.ts                 # Barrel exports
│   └── calculator/              # Composants du calculateur
│       ├── CalculatorInputs.tsx # Champs de saisie du calculateur
│       ├── CostBreakdown.tsx    # Decomposition des couts
│       ├── PaymentResult.tsx    # Resultat de paiement
│       ├── ProgramSelector.tsx  # Selecteur de programme vehicule
│       └── index.ts
│
├── contexts/
│   └── AuthContext.tsx           # Contexte d'authentification (login, token, user, demo)
│
├── hooks/
│   ├── index.ts
│   ├── useCalculator.ts         # Hook du calculateur
│   ├── useFinancingCalculation.ts # Calculs de financement
│   ├── useNetCost.ts            # Calcul du cout net
│   └── usePrograms.ts           # Recuperation des programmes
│
├── utils/
│   ├── api.ts                   # Configuration de l'URL backend
│   ├── i18n.ts                  # Internationalisation (FR/EN)
│   └── leaseCalculator.ts      # Calcul taux location + matching strict vehicule
│
├── locales/
│   ├── fr.json                  # Traductions francaises
│   └── en.json                  # Traductions anglaises
│
├── types/
│   └── calculator.ts            # Types TypeScript du calculateur
│
├── assets/                      # Images et polices
├── public/                      # Fichiers statiques web
├── package.json                 # Dependances (yarn)
├── vercel.json                  # Configuration de deploiement Vercel
├── app.json                     # Configuration Expo
├── metro.config.js              # Configuration Metro bundler
└── tsconfig.json                # Configuration TypeScript
```

### Fichiers cles expliques

#### `app/import.tsx` - Import PDF avec checkboxes
Nouveau flux d'import base sur la Table des Matieres :
1. L'admin uploade un PDF
2. Le backend lit la TOC et retourne les sections trouvees
3. Le frontend affiche des checkboxes pour chaque section
4. L'admin selectionne les sections a extraire et lance l'extraction
5. Un indicateur de progression montre l'avancement

#### `utils/leaseCalculator.ts` - Calcul location
Contient la logique de matching vehicule pour les taux de location SCI. Utilise un **matching strict** pour eviter les confusions (ex: "Cherokee" vs "Grand Cherokee").

#### `contexts/AuthContext.tsx` - Authentification
Gere tout le cycle d'authentification :
- Login/Logout/Register standard
- **Mode Demo:** Connexion automatique comme `demo@calcauto.ca` avec acces admin
- Stockage du token (localStorage sur web, AsyncStorage sur mobile)

#### `vercel.json` - Configuration Vercel
```json
{
  "buildCommand": "npx expo export -p web",
  "outputDirectory": "dist",
  "framework": null,
  "rewrites": [
    { "source": "/api/(.*)", "destination": "https://calcauto-final-backend.onrender.com/api/$1" },
    { "source": "/(.*)", "destination": "/index.html" }
  ]
}
```
> **Important:** L'URL de destination dans `rewrites` doit pointer vers votre backend Render actuel.

---

## 4. Base de donnees (MongoDB)

### Connexion
L'application utilise **MongoDB Atlas** (cloud) via le driver `motor` (async Python).
La chaine de connexion est stockee dans la variable `MONGO_URL` du fichier `.env` backend.

### Collections principales

| Collection | Description | Champs cles |
|------------|-------------|-------------|
| `programs` | Programmes de financement | `id`, `brand`, `model`, `trim`, `year`, `consumer_cash`, `bonus_cash`, `option1_rates`, `option2_rates`, `sort_order`, `program_month`, `program_year` |
| `trim_orders` | Ordre des trims par modele | `brand`, `model`, `year`, `trims` (liste ordonnee) |
| `users` | Comptes utilisateurs | `id`, `name`, `email`, `password_hash`, `is_admin`, `is_blocked` |
| `tokens` | Tokens d'authentification | `user_id`, `token`, `created_at` |
| `submissions` | Soumissions clients (CRM) | `id`, `owner_id`, `client_name`, `client_phone`, `vehicle_*`, `payment_*`, `status` |
| `contacts` | Contacts importes | `id`, `owner_id`, `name`, `phone`, `email` |
| `inventory` | Vehicules en stock | `id`, `owner_id`, `stock_no`, `vin`, `brand`, `model`, `msrp`, `status` |
| `vehicle_options` | Options/equipements | `stock_no`, `product_code`, `description`, `amount` |
| `window_stickers` | Window Stickers caches | `vin`, `data`, `images` |
| `corrections` | Corrections manuelles | `model`, `trim`, `field`, `old_value`, `new_value`, `month`, `year` |
| `extract_tasks` | Taches d'extraction async | `task_id`, `status`, `progress`, `results` |
| `migrations` | Migrations executees | `key`, `executed_at` |

---

## 5. Stockage persistant (Supabase)

### Pourquoi Supabase ?
Render (backend) utilise un **filesystem ephemere** : les fichiers locaux sont perdus a chaque redemarrage. Supabase Storage sert de source de verite persistante pour tous les fichiers de donnees.

### Architecture de stockage

```
Supabase Storage (Bucket: calcauto-data)
├── monthly/
│   ├── feb2026/
│   │   ├── sci_lease_rates.json     # Taux location SCI fevrier
│   │   ├── key_incentives.json      # Incitatifs fevrier
│   │   ├── program_meta.json        # Metadonnees fevrier
│   │   ├── sci_residuals.json       # Residuels fevrier
│   │   └── source.pdf               # PDF source fevrier
│   ├── mar2026/
│   │   ├── sci_lease_rates.json
│   │   ├── key_incentives.json
│   │   ├── program_meta.json
│   │   └── source.pdf
│   └── ... (un dossier par mois)
│
└── reference/
    ├── 2025_pdfs/                   # Guides residuels (65 PDFs)
    ├── calcauto/                    # Guides residuels supplementaires
    ├── fca_product_codes_2025.json  # Codes produits 2025
    └── fca_product_codes_2026.json  # Codes produits 2026
```

### Flux de synchronisation

```
DEMARRAGE DU SERVEUR (Render)
    │
    ▼
sync_from_supabase() dans server.py
    │
    ▼
Telecharge tous les JSON mensuels + references
    │
    ▼
Sauvegarde dans backend/data/ (cache local)
    │
    ▼
Les APIs lisent depuis le cache local (rapide)


APRES UNE EXTRACTION PDF
    │
    ▼
Sauvegarde JSON en local
    │
    ▼
Upload JSON + PDF vers Supabase (persistant)
    │
    ▼
Disponible au prochain demarrage
```

---

## 6. Deploiement

### 6.1 GitHub

Le code source est stocke sur GitHub sous le compte `Lianag2018`.

**Important - .gitignore :**
Le `.gitignore` exclut correctement :
- `node_modules/` (41 654 fichiers supprimes du suivi Git)
- `.metro-cache/` (cache Metro bundler)
- `__pycache__/` (cache Python)
- `backend/data/*.json` mensuels (sync depuis Supabase)
- `*.env` (variables d'environnement)

> **Note :** Sur la plateforme Emergent, utilisez le bouton "Save to GitHub" pour pousser votre code.

---

### 6.2 Backend sur Render

#### Configuration

| Parametre | Valeur |
|-----------|--------|
| **Name** | `calcauto-backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn server:app --host 0.0.0.0 --port $PORT` |

#### Fichiers de configuration Render
- **`Procfile`** : `web: uvicorn server:app --host 0.0.0.0 --port $PORT`
- **`runtime.txt`** : `python-3.11.4`
- **`render.yaml`** : Configuration declarative complete

#### Deploiement automatique
- Deploie a chaque `git push` sur `main`
- URL : `https://calcauto-final-backend.onrender.com`
- Test : `GET /api/ping` → `{"status": "ok"}`

---

### 6.3 Frontend sur Vercel

#### Configuration

| Parametre | Valeur |
|-----------|--------|
| **Build Command** | `npx expo export -p web` |
| **Output Directory** | `dist` |
| **Framework Preset** | `Other` |
| **Install Command** | `yarn install` |

#### Rewrites (CRUCIAL)
Les requetes `/api/*` sont redirigees vers le backend Render via `vercel.json`.
Mettez a jour l'URL si vous changez de serveur backend.

---

## 7. Variables d'environnement

### Backend (`.env`)

| Variable | Description | Requis |
|----------|-------------|--------|
| `MONGO_URL` | Chaine de connexion MongoDB Atlas | Oui |
| `DB_NAME` | Nom de la base de donnees | Oui |
| `ADMIN_PASSWORD` | Mot de passe admin pour imports | Oui |
| `SUPABASE_URL` | URL du projet Supabase | Oui |
| `SUPABASE_SERVICE_KEY` | Cle de service Supabase | Oui |
| `OPENAI_API_KEY` | Cle API OpenAI (OCR/IA) | Oui |
| `GOOGLE_VISION_API_KEY` | Cle Google Cloud Vision (OCR) | Optionnel |
| `SMTP_EMAIL` | Email Gmail pour envoi | Oui |
| `SMTP_PASSWORD` | Mot de passe d'application Gmail | Oui |
| `SMTP_HOST` | Serveur SMTP (`smtp.gmail.com`) | Oui |
| `SMTP_PORT` | Port SMTP (`587`) | Oui |

> **SMTP_PASSWORD :** Doit etre un **mot de passe d'application** Google (Parametres > Securite > Verification en 2 etapes > Mots de passe d'application).

> **SUPABASE_SERVICE_KEY :** Trouvable dans Supabase Dashboard > Project Settings > API > `service_role` key.

### Frontend
Le frontend n'a **pas besoin de variables d'environnement en production** sur Vercel. La communication avec le backend se fait via les `rewrites` de `vercel.json`.

Pour le developpement local :
```
EXPO_PUBLIC_BACKEND_URL=http://localhost:8001
```

---

## 8. Flux de donnees

### Flux d'import PDF (nouveau - avec checkboxes)
```
1. L'admin televerse un PDF d'incitatifs mensuels
   │
2. POST /api/scan-pdf → Backend lit la TOC (page 2)
   │
3. Frontend affiche les sections trouvees avec checkboxes
   │
4. L'admin selectionne les sections a extraire
   │
5. POST /api/extract-pdf-async (sections selectionnees)
   │
6. Backend extrait les donnees en arriere-plan :
   │  - Programmes de financement (taux, cash)
   │  - Taux de location SCI
   │  - Bonus cash
   │  - Residuels
   │
7. Resultats sauvegardes :
   │  - MongoDB (programmes, SCI rates)
   │  - JSON local (cache)
   │  - Supabase Storage (persistant)
   │  - Fichier Excel (validation)
   │
8. Frontend affiche le rapport d'extraction
```

### Flux d'un calcul de financement
```
1. L'utilisateur selectionne un vehicule
   │
2. GET /api/programs → programmes tries par sort_order
   │
3. L'utilisateur entre un prix et choisit un terme
   │
4. POST /api/calculate → paiements Option 1 et Option 2
   │
5. GET /api/sci/lease-rates → taux location SCI (cache local)
   │
6. Frontend affiche les resultats (financement + location)
   │
7. Option: envoyer par email ou creer une soumission CRM
```

### Flux d'authentification
```
1. Email + mot de passe → POST /api/auth/login
   OU
   Mode Demo → POST /api/auth/demo-login (auto login demo@calcauto.ca)
   │
2. Backend retourne un token JWT
   │
3. Token stocke dans localStorage (web) / AsyncStorage (mobile)
   │
4. Chaque requete inclut: Authorization: Bearer <token>
```

---

## 9. Maintenance et operations courantes

### Mettre a jour les programmes mensuels
1. Connectez-vous en tant qu'admin
2. Allez dans l'onglet **Admin** > **Import**
3. Televersez le nouveau PDF des programmes
4. Le systeme affiche les sections trouvees avec des checkboxes
5. Selectionnez les sections pertinentes et lancez l'extraction
6. Verifiez le rapport genere (Excel)

### Modifier l'ordre des vehicules
1. Onglet Admin > Ordre vehicules
2. Faites glisser-deposer dans l'ordre souhaite
3. Sauvegardez (mot de passe admin requis)

### Forcer un redeploiement
- **Render:** Dashboard > Manual Deploy
- **Vercel:** Dashboard > Redeploy
- Ou simplement poussez un commit sur `main`

### Surveiller les erreurs
- **Render:** Dashboard > Logs
- **Vercel:** Dashboard > Deployments > Logs
- **Supabase:** Dashboard > Storage (verifier les fichiers)
- **MongoDB Atlas:** Dashboard > Monitoring

### Sauvegarder la base de donnees
```bash
mongodump --uri="mongodb+srv://user:pass@cluster.mongodb.net/calcauto_prod" --out=./backup
```

---

## 10. Depannage

### Le backend ne demarre pas sur Render
- Verifiez les logs dans le dashboard Render
- Assurez-vous que TOUTES les variables d'environnement sont configurees (incluant Supabase)
- Verifiez que `MONGO_URL` est accessible (whitelist IP dans MongoDB Atlas)

### Les donnees SCI (location) ne s'affichent pas
1. Verifiez que les fichiers JSON existent dans Supabase Storage (`monthly/{mois}{annee}/`)
2. Verifiez les logs du backend au demarrage (`[Storage] Synced:` doit apparaitre)
3. Si les fichiers manquent, relancez une extraction PDF

### "CORS error" dans le navigateur
- Le CORS accepte toutes les origines (`allow_origins=["*"]`)
- Si erreur CORS, le backend n'est probablement pas accessible
- Verifiez l'URL dans `vercel.json` > `rewrites`

### Les programmes ne s'affichent pas
- `GET /api/programs` → si vide, relancez un import PDF
- Verifiez que `program_month` et `program_year` correspondent au mois en cours

### Les emails ne sont pas envoyes
- `SMTP_PASSWORD` doit etre un **mot de passe d'application** Google
- Activez la verification en 2 etapes dans votre compte Google

### MongoDB Atlas : whitelist des IP
- Network Access > ajoutez `0.0.0.0/0` (toutes les IP)

### Le frontend affiche une page blanche
- Verifiez le build sur Vercel
- Console navigateur (F12) pour les erreurs
- Verifiez que `vercel.json` est correct

---

## Annexe : Dependances principales

### Backend (Python)

| Package | Usage |
|---------|-------|
| fastapi | Framework web API |
| uvicorn | Serveur ASGI |
| motor | Driver MongoDB async |
| pydantic | Validation de donnees |
| pdfplumber | Extraction texte/tables PDF |
| openpyxl | Lecture/ecriture Excel |
| supabase | Client Supabase Storage |
| openai | API OpenAI (OCR/IA) |
| PyMuPDF | Conversion PDF en images |
| pytesseract | OCR Tesseract |
| Pillow | Traitement d'images |
| PyJWT | Tokens JWT |
| python-dotenv | Variables d'environnement |

### Frontend (JavaScript/TypeScript)

| Package | Usage |
|---------|-------|
| expo ~54 | Framework React Native/Web |
| react 19 | Bibliotheque UI |
| react-native-web | React Native sur le web |
| axios | Requetes HTTP |
| zustand | Gestion d'etat |
| expo-router | Routing (navigation) |
| expo-document-picker | Selection de fichiers |
| html2canvas | Screenshots pour partage |

---

## Annexe : Comptes et acces

| Service | URL | Identifiants |
|---------|-----|-------------|
| Application (demo) | *(votre URL Vercel)* | Auto-login `demo@calcauto.ca` |
| Application (login) | *(votre URL Vercel)* | `danielgiroux007@gmail.com` / `Liana2018$` |
| Admin (import/gestion) | *(meme app, onglet Admin)* | Mot de passe: `Liana2018` |
| Supabase Dashboard | supabase.com | *(votre compte)* |
| MongoDB Atlas | cloud.mongodb.com | *(votre compte)* |
| Render Dashboard | dashboard.render.com | *(votre compte GitHub)* |
| Vercel Dashboard | vercel.com/dashboard | *(votre compte GitHub)* |
| GitHub | github.com/Lianag2018 | *(votre compte)* |

---

## Annexe : Historique des bugs critiques resolus

| Date | Bug | Cause | Fix |
|------|-----|-------|-----|
| Mars 2026 | Taux SCI assignes au mauvais vehicule | Offset de 2 rangees entre les tables PDF | Correction dans `parse_sci_lease_programs` |
| Mars 2026 | Cherokee affiche taux du Grand Cherokee | Matching partiel de chaine ("Cherokee" dans "Grand Cherokee") | Matching strict dans `leaseCalculator.ts` |
| Mars 2026 | JSON SCI non sauvegarde apres extraction | `import_wizard.py` n'ecrivait pas le fichier JSON | Ajout de la sauvegarde locale + upload Supabase |
| Fev 2026 | Bonus Cash manquant (Fiat 500e) | Bonus Cash sur une page separee non parsee | Ajout de `parse_bonus_cash_page()` |
| Fev 2026 | "All-New" extrait comme nom de modele | Regex trop permissive | Filtre dans le parseur |
| Fev 2026 | "Grand Cherokee Laredo" → "aredo" | Conflit avec le modele "Grand Cherokee L" | Logique de priorite dans le parseur |

---

*Document mis a jour le 17 mars 2026 pour CalcAuto AiPro v4*
