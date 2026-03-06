# CalcAuto AiPro - PRD (Product Requirements Document)

## Problem Statement
Application CRM pour concessionnaire automobile Stellantis/FCA Canada. Calculateur de financement véhicules, gestion des clients, et importation automatique des programmes d'incitatifs mensuels depuis les PDFs Stellantis.

## Architecture
- **Frontend**: React Native (Expo) avec export web statique (dist/)
- **Backend**: FastAPI (Python)
- **Database**: MongoDB + fichiers JSON versionnés (données mensuelles)
- **PDF Parsing**: pdfplumber (déterministe, ZERO IA, auto-détection des pages)

## Core Features
- CRM client avec historique des offres
- Calculateur de financement (Option 1/Option 2, Bonus Cash, taxes)
- Inventaire véhicules avec VIN decoder
- Importation automatique des programmes FCA depuis PDF (auto-détection des sections)
- Export Excel et envoi par email
- Panneau admin avec gestion des corrections
- Accès démo sans restriction (auto-login, admin complet)

## What's Been Implemented

### Completed (March 6, 2026)
- [x] **P0 - Parser pdfplumber déterministe** (18/18 tests passent)
  - `parse_retail_programs()`: 81 programmes Finance Prime
  - `parse_sci_lease()`: 74 véhicules SCI Lease
  - `parse_key_incentives()`: 13 entrées Go-to-Market summary
  - OpenAI/GPT-4o entièrement supprimé du flux d'extraction

- [x] **Auto-détection des pages PDF** (TERMINÉ)
  - `auto_detect_pages()`: scanne le PDF et identifie automatiquement les sections
  - Endpoint `POST /api/scan-pdf`: retourne les pages détectées
  - Endpoints sync/async: auto-détectent si pages non fournies
  - Frontend: auto-remplit les numéros de pages après upload
  - Plus besoin d'entrer manuellement 20-21 et 28-29

- [x] **Accès Démo sans restriction** (TERMINÉ)
  - Auto-login Demo Admin, mot de passe admin pré-rempli

- [x] **P0 - Bandeau Événementiel Dynamique + Logique Fidélité** (TERMINÉ - Mars 6, 2026)
  - Composant `EventBanner` : affiche nom événement, période, taux vedette, jours sans paiement
  - Toggle fidélité : visible uniquement quand `loyalty_rate > 0` dans les métadonnées
  - Logique de calcul : réduction du taux appliquée aux Options 1 et 2 via `useCalculator`
  - Backend : endpoint `GET /api/program-meta` + parsing couverture PDF
  - Testé : Mars 2026 "Month of Ram" (-0.5%) et Février 2026 "4X4 Winter Event" (0%)
  - Tests 100% : backend (10/10) + frontend (toutes fonctionnalités vérifiées)

### Previously Completed
- [x] SCI Lease Data Pipeline (dynamique + historique)
- [x] Data Carry-over (copie taux du mois précédent)
- [x] Offer Savings Calculation (méthode delta)
- [x] CRM Offer Modal & History Tab
- [x] Data Versioning by Filename

## Prioritized Backlog

### P1 - UI Gestion des Corrections
- Interface admin pour gérer les corrections de programmes

### P2 - Refactoring Frontend
- Refactorer `index.tsx`, `inventory.tsx`, `clients.tsx`

## Key API Endpoints
- `POST /api/scan-pdf` - Auto-détection des sections du PDF (NOUVEAU)
- `POST /api/extract-pdf-async` - Extraction async (auto-détecte si pages non fournies)
- `POST /api/extract-pdf` - Extraction sync (auto-détecte si pages non fournies)
- `POST /api/auth/demo-login` - Auto-login démo
- `GET /api/programs` - Liste des programmes
- `GET /api/sci/lease-rates` - Taux SCI Lease
- `GET /api/program-meta` - Métadonnées événement du mois (couverture PDF)

## Key Files
- `/app/backend/services/pdfplumber_parser.py` - Parser + auto_detect_pages()
- `/app/backend/routers/import_wizard.py` - scan-pdf endpoint + extraction + program-meta
- `/app/backend/routers/auth.py` - Auth + demo login
- `/app/frontend/app/import.tsx` - Import wizard avec auto-détection
- `/app/frontend/contexts/AuthContext.tsx` - Auth context + auto-demo
- `/app/frontend/components/EventBanner.tsx` - Bandeau événementiel dynamique
- `/app/frontend/hooks/useCalculator.ts` - Logique calcul financement + loyauté

## Credentials
- Admin: `Liana2018`
- User: `danielgiroux007@gmail.com` / `Liana2018$`
- Demo: `demo@calcauto.ca` (auto-login)
