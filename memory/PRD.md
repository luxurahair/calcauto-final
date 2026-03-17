# CalcAuto AiPro - PRD

## Problem Statement
Car dealership CRM that parses FCA Canada monthly incentive PDFs to extract retail programs, SCI lease rates, and display them via a dynamic calculator UI. Originally used AI/OCR; now uses deterministic pdfplumber parsing.

## Architecture
- **Backend:** FastAPI + pdfplumber + pandas, file-based storage in `backend/data/`
- **Frontend:** React/Expo (static export), served from `dist/`
- **DB:** MongoDB (users, submissions)
- **CI/CD:** GitHub Actions -> Render (backend) + Vercel (frontend)

## Completed Features
1. **Deterministic PDF Parser** (pdfplumber) - replaces old AI/OCR
2. **TOC-based Auto-Detection** - parses Table of Contents on page 2 for section pages
3. **Retail Program Parser** - extracts Option 1, Option 2, Consumer Cash, Bonus Cash
4. **SCI Lease Parser** - extracts vehicle names, lease cash, standard/alternative rates (FIXED: row alignment bug)
5. **Bonus Cash Parser** - separate page parsing for bonus cash (e.g., Fiat 500e $5,000)
6. **Dynamic Event Banner** - shows promotional info from PDF cover page
7. **Loyalty Rate & 90-day Deferred Payment** - calculation modifiers in UI
8. **Demo Mode** - password-free access via demo@calcauto.ca
9. **CI/CD Pipeline** - GitHub Actions with pytest + deploy hooks
10. **Animated Splash Screen** - comet trail loading animation

## Key Bug Fixes (March 2026)
- **SCI Lease Row Alignment (P0):** Fixed 2-row offset between names table (row 14) and rates table (row 12). Now uses zip of filtered lists instead of same-index iteration.
- **Missing Bonus Cash:** Added `parse_bonus_cash_page()` for separate bonus page
- **Model Name Prefix:** Fixed "All-New" prefix handling for Charger Daytona, Hornet
- **Trim Parsing:** Fixed "Grand Cherokee Laredo" split into "Grand Cherokee L" + "aredo"

## API Endpoints
- `POST /api/scan-pdf` - auto-detect section pages
- `POST /api/extract-pdf` - full PDF extraction pipeline
- `POST /api/corrections` - manage program corrections
- `GET /api/programs/:month/:year` - get programs by month

## Credentials
- Admin: password `Liana2018`
- Demo: auto-login `demo@calcauto.ca`

## Upcoming Tasks
- **(P1)** UI for Correction Management (admin panel frontend)
- **(P2)** Refactor large frontend components (index.tsx, inventory.tsx, clients.tsx)
- **(P3)** Parse Loyalty Rate Landscapes (pages 34-39 in March PDF)
