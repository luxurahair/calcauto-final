# CalcAuto AiPro - PRD

## Problème Original
Application CRM pour concessionnaire automobile. Parser PDF déterministe (pdfplumber) pour extraire les données de programmes de financement mensuels FCA (Stellantis).

## Architecture
- **Frontend**: React Native (Expo) 
- **Backend**: FastAPI + MongoDB
- **Parser**: pdfplumber (déterministe, pas d'IA)
- **Excel**: openpyxl pour génération de fichiers Excel

## Fonctionnalités Implémentées

### P0 - Parser PDF Robuste
- Extraction Retail Finance (Layout A + Layout B)
- Extraction SCI Lease avec détection dynamique de colonnes
- Détection automatique des pages (TOC-first strategy)
- Parsing bonus cash depuis page séparée
- Détection des marqueurs de loyauté "P"
- Validation post-extraction automatique
- Protection contre les faux positifs MSRP (parse_dollar)

### P0 - Export Excel
- Onglet Financement (93 programmes, freeze panes, 20 colonnes)
- Onglet SCI Lease (73 véhicules, taux standard + alternatifs)
- Onglet Rapport (validation automatique, avertissements, statistiques)
- Endpoint `/api/download-excel?month=X&year=Y`
- Endpoint `/api/validate-data?month=X&year=Y`
- Envoi automatique par email

### P0 - CI/CD
- GitHub Actions configuré (test + deploy)
- Test unitaire local passant

### P2 - Mode Démo
- Compte demo@calcauto.ca sans mot de passe

### P3 - Détection Automatique des Pages
- TOC-first strategy pour identifier les sections du PDF

## Bugs Corrigés (Session Actuelle - Mars 2026)
1. Bug MSRP: `parse_dollar` extrayait des codes programme comme montants ($2,619)
2. Bug SCI Lease: Détection de colonnes incorrecte (lease_cash=col4 au lieu de col2)
3. Bug SCI Lease: `bonus_col` détecté à col17 au lieu de col30

## Tâches En Cours
- CI/CD pipeline bloqué - utilisateur doit "Save to GitHub"
- Splash screen animation - attente feedback utilisateur

## Backlog (P2-P3)
- P2: Bouton "Télécharger Excel" dans le frontend
- P2: Interface de gestion des corrections (CRUD /api/corrections)
- P3: Refactoring composants frontend (index.tsx, inventory.tsx, clients.tsx)

## Endpoints Clés
- `POST /api/extract-pdf` - Import PDF principal
- `POST /api/extract-pdf-async` - Import PDF async
- `GET /api/download-excel?month=X&year=Y` - Téléchargement Excel
- `GET /api/validate-data?month=X&year=Y` - Rapport de validation
- `GET /api/programs` - Liste des programmes
- `GET /api/sci/lease-rates` - Taux SCI Lease

## Schéma BD
- `programs`: brand, model, trim, year, consumer_cash, alt_consumer_cash, bonus_cash, option1_rates, option2_rates, loyalty_cash, loyalty_opt1, loyalty_opt2, program_month, program_year
- `residuals`: valeurs résiduelles véhicules
- `users`: comptes utilisateurs
