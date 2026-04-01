# CalcAuto AiPro - PRD

## Problem Statement
CRM complet pour concessionnaires automobiles qui analyse les PDFs mensuels d'incitatifs financiers FCA Canada/Stellantis. Extraction déterministe via pdfplumber, calcul de location/financement avec UI dynamique.

## Architecture
- **Backend:** FastAPI + pdfplumber + PyMuPDF(fitz), stockage fichiers dans `backend/data/`
- **Frontend:** Expo/React Native for Web (TypeScript)
- **DB:** MongoDB Atlas (users, submissions, corrections, inventory)
- **Stockage:** Supabase Storage (persistance fichiers JSON)
- **CI/CD:** GitHub Actions -> Render (backend) + Vercel (frontend)

## Completed Features
1. **Deterministic PDF Parser** (pdfplumber) - replaces old AI/OCR
2. **TOC-based Auto-Detection** - parses Table of Contents on page 2
3. **Retail Program Parser** - extracts Option 1, Option 2, Consumer Cash, Bonus Cash
4. **SCI Lease Parser** - with row alignment fix (2-row offset)
5. **Bonus Cash Parser** - separate page parsing
6. **Dynamic Event Banner** - promotional info from PDF cover page
7. **Loyalty Rate & 90-day Deferred Payment** - calculation modifiers
8. **Demo Mode** - password-free access via demo@calcauto.ca
9. **CI/CD Pipeline** - GitHub Actions with pytest + deploy hooks
10. **Animated Splash Screen** - comet trail loading animation
11. **Corrections Management UI** - Admin panel tab for corrections
12. **Improved Residual Vehicle Matching** - 10-priority matching
13. **Supabase Storage Integration** - persistence for ephemeral deployments
14. **Dynamic KM Adjustments Extraction** - parses "General Rules" section for Low/Super Low Kilometre residual enhancements from both retail PDF and residual guide PDF
15. **Auto-Import Résiduel Guide** - Auto-détection mois/année, extraction km adjustments depuis dernière page, comparaison ancien/nouveau avec rapport de changements (DONE - April 2026)

## Key APIs
- `POST /api/scan-pdf` - auto-detect section pages via TOC
- `POST /api/extract-pdf-async` - full PDF extraction pipeline (includes General Rules parsing)
- `GET /api/sci/residuals` - residuals + dynamic km_adjustments (merges standalone km_adjustments file)
- `POST /api/upload-residual-guide` - upload SCI residual PDF (auto-detect month, compare, extract km adj)
- `GET /api/sci/lease-rates` - lease rates data
- `GET /api/corrections` - list corrections

## Key Data Files
- `km_adjustments_{month}{year}.json` - dynamic km adjustments per month
- `sci_residuals_{month}{year}.json` - vehicle residual percentages (French month names)
- `sci_lease_rates_{month}{year}.json` - lease rates
- `program_meta_{month}{year}.json` - event/cover page metadata

## Credentials
- Admin: danielgiroux007@gmail.com / Liana2018$
- Demo: auto-login demo@calcauto.ca

## Upcoming Tasks
- **(P2)** Extraction des "Loyalty Rate Landscapes" comme type distinct
- **(P3)** Refactorisation composants massifs (index.tsx ~3700 lignes, inventory.tsx, clients.tsx)
