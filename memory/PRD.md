# CalcAuto AiPro - PRD

## Probleme original
Application CRM pour concessionnaire automobile. Parseur PDF deterministe avec `pdfplumber` pour extraire les programmes d'incitatifs mensuels (taux finance, location SCI, bonus cash, loyaute).

## Architecture
- **Frontend**: React Native / Expo (Web) - port 3000 (dist statique)
- **Backend**: FastAPI - port 8001
- **DB**: MongoDB
- **Parseur**: `pdfplumber` + `openpyxl` pour Excel

## Fonctionnalites implementees

### Import PDF avec Checkboxes (Mars 2026)
- TOC page 2 lu automatiquement via `improved_parse_toc`
- 13 sections detectees avec classification automatique (retail, lease, bonus, loyalty, info)
- Frontend: checkboxes pour selectionner les sections a extraire
- Backend: `/scan-pdf` retourne toutes les sections, `/extract-pdf-async` accepte `selected_sections`
- Auto-selection des sections extractibles (retail, lease, non_prime, bonus, loyalty)

### Parseur PDF robuste
- Strategie "content-driven" (identifie colonnes par headers, pas positions fixes)
- `parse_bonus_cash_page`: extraction bonus cash depuis page separee
- `parse_retail_programs_content_driven`: taux finance Option 1 & 2 + Consumer Cash
- `parse_sci_lease_programs`: taux location SCI
- Validation des donnees (`validate_extraction`) avec rapport dans Excel

### Autres
- Mode Demo: `demo@calcauto.ca` / acces sans mot de passe
- Detection automatique des pages (TOC-first)
- CI/CD GitHub Actions
- Export Excel avec onglets multiples

## Backlog

### P2 - UI Gestion des corrections
Interface frontend pour les APIs `/api/corrections` existantes

### P3 - Refactoring frontend
`index.tsx`, `inventory.tsx`, `clients.tsx` sont volumineux

### P1 - Splash screen anime
Animation "comet trail" - en attente feedback utilisateur

## Fichiers cles
- `backend/services/pdfplumber_parser.py` - Logique de parsing
- `backend/routers/import_wizard.py` - Orchestration import + Excel
- `frontend/app/import.tsx` - UI import PDF avec checkboxes
- `frontend/utils/leaseCalculator.ts` - Calcul taux frontend

## Schema BD
- `db.programs`: Donnees finance
- `db.sci_lease_rates`: Taux location SCI
- `db.corrections`: Corrections manuelles
- `db.extract_tasks`: Taches d'extraction async

## Credentials
- Demo: `demo@calcauto.ca`
- Admin password: `Liana2018`
