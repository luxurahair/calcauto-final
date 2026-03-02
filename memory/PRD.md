# CalcAuto AiPro - Product Requirements Document

## Problem Statement
Application full-stack de financement véhiculaire avec calculateur de location/financement,
OCR pour factures, gestion d'inventaire et CRM.

## Architecture
```
/app
├── backend/
│   ├── server.py              # Point d'entrée FastAPI
│   ├── database.py            # Connexion MongoDB, config
│   ├── models.py              # Modèles Pydantic (incl. sort_order)
│   ├── dependencies.py        # Auth, utilitaires calcul
│   ├── routers/               # API endpoints
│   │   ├── programs.py, email.py, auth.py, submissions.py
│   │   ├── contacts.py, inventory.py, invoice.py
│   │   ├── import_wizard.py, sci.py, admin.py
│   ├── services/              # window_sticker.py, email_service.py
│   ├── scripts/               # setup_trim_orders.py
│   └── data/                  # JSON (taux, résiduels, codes)
├── frontend/
│   ├── app/(tabs)/            # index.tsx, inventory.tsx, clients.tsx, admin.tsx
│   ├── components/            # Calculator components, EmailModal, etc.
│   ├── contexts/              # AuthContext.tsx
│   ├── hooks/                 # useCalculator, useFinancingCalculation, etc.
│   ├── utils/                 # api.ts, i18n.ts
│   └── vercel.json            # Vercel deployment with rewrites to Render
├── ARCHITECTURE.md            # Documentation complète architecture & déploiement
└── memory/PRD.md
```

## Completed Features
- Calculateur location SCI + financement
- "Meilleur Choix" automatique, Grille d'analyse comparative
- Partage SMS/texto avec screenshot
- Soumission email avec taux dynamiques
- Scanner factures (OCR: Google Cloud Vision + GPT-4o)
- Import programmes depuis PDF, CRM avec rappels
- Gestion inventaire avec Window Sticker
- Inventaire filtré par modèle
- Tri logique PDF (sort_order aligné avec PDF FCA)
- Admin drag & drop pour réordonnement véhicules
- Email/SMS cohérence (taux dynamiques, Option 2 conditionnelle)

## Completed - Feb 27, 2026
- Bug fix: Calcul hebdomadaire en impression (Avant taxes/TPS/TVQ maintenant en montants hebdo)
- Bug fix: Bouton "Retour au calculateur" ajouté en mode impression
- Amélioration: Section "Meilleur choix location" adapte label et montants à la fréquence
- Amélioration: Grille d'analyse adapte titre et valeurs à la fréquence
- Documentation architecture complète (/app/ARCHITECTURE.md)

## Completed - Delivery Credit Fix (Feb 27, 2026)
- Removed all Delivery Credit values (261Q02, 'E' Only) incorrectly stored as bonus_cash
- 40 programs corrected: bonus_cash set to 0 for all vehicles
- Import wizard GPT prompt updated to explicitly ignore Delivery Credit column
- Green "+1 000 $" badges removed from all vehicle cards

## Completed - Excel Export/Import System (Feb 27, 2026)
- GET /api/programs/export-excel - Downloads all programs as formatted Excel
- POST /api/programs/import-excel - Imports corrected Excel (admin password required)
- New "Excel" tab in Admin panel with export/import UI
- Delivery Credit values removed from bonus_cash, import wizard updated to ignore them

## Completed - Excel Correction Memory System (Feb 27, 2026)
- Import Excel now saves corrections to `program_corrections` collection
- Future PDF imports automatically apply memorized corrections (by brand/model/trim/year)
- Startup migration script fixes production DB on deploy
- Email with Excel sent to user for manual correction

## Completed - Excel Final Truth Workflow (Mar 2, 2026)
- Added 'excel-correction' step to import page after PDF extraction
- User can download Excel, correct, re-upload as final truth
- 76 January duplicates removed (81 unique programs remain)
- New column "Rabais Alt. Cash ($)" = alternative_consumer_cash for Option 2
- All corrections memorized in program_corrections collection
- Future PDF imports auto-apply memorized corrections

## P1 Backlog
- Vérifier données "Option 2" sur tous les modèles

## P2 Backlog
- Refactoring complet frontend index.tsx (hooks + composants)
- Refactoring inventory.tsx

## Credentials
- Login: danielgiroux007@gmail.com / Liana2018$
- Admin: Liana2018$
