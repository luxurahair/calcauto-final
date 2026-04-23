# CalcAuto AiPro - PRD

## Problem Statement
Application CRM pour un concessionnaire automobile. Permet de calculer les paiements de financement et de location pour les vehicules Chrysler/Dodge/Fiat/Jeep/Ram a partir des programmes mensuels d'incitatifs PDF.

## Core Features
- Calculateur de paiements (financement et location SCI)
- Importation et parsing de PDF mensuels d'incitatifs
- Gestion de l'inventaire vehicules
- CRM clients avec historique des soumissions
- Comparaison automatique "meilleures offres" entre mois
- Mode demo sans mot de passe
- Admin panel avec gestion d'ordre des vehicules

## Architecture
- **Frontend**: React/Expo (web) avec TypeScript
- **Backend**: FastAPI (Python) + MongoDB
- **Storage**: Supabase pour fichiers persistants
- **PDF Parsing**: pdfplumber (deterministe)
- **Hosting**: Vercel (frontend) + Render (backend)
- **CI/CD**: GitHub Actions (tests -> deploy)

## Code Architecture (Hooks)
```
frontend/features/calculator/hooks/
  useCalculatorPage.ts   (orchestrateur principal)
  useProgramsData.ts     (chargement, filtrage, periodes)
  useInventoryData.ts    (inventaire, auto-financing)
  useLeaseModule.ts      (calculs SCI lease)
```

## What's Been Implemented

### Session 2026-04-23
- **Fix: Onglet parasite** - Fichier `homeStyles.ts` deplace de `(tabs)/styles/` vers `/frontend/styles/` pour eliminer le tab fantome dans la navigation
- **Fix: Overlay Admin** - Plus reproductible apres la correction du tab parasite

### Session 2026-03-18
- **Backend: Comparaison multi-variantes** - La logique "meilleures offres" verifie maintenant TOUTES les variantes/trims
- **Backend: Gestion None** - Les taux `None` dans les programmes ne causent plus de crash
- **Frontend: Token refresh** - Re-authentification automatique si le token expire
- **Frontend: Retry 401** - Si la sauvegarde echoue avec 401, retry avec un nouveau token
- **Frontend: Refactoring Phase 2** - Extraction de 3 sous-hooks depuis useCalculatorPage.ts
- **Fix: Boucle infinie** - Resolu dans useProgramsData.ts (stabilisation deps avec useRef)
- **Fix: Restauration soumissions** - useFocusEffect + selectedProgram direct depuis saved state

### Previous Sessions
- Refactoring Phase 1: index.tsx (3695 -> 1970 lignes) + useCalculatorPage.ts
- Bug fix: Soumissions email sauvegardees correctement
- Bug fix: Comparaison "meilleures offres" utilise Option 1 ET Option 2
- Mode demo, detection automatique de pages PDF, parsing pdfplumber

## Pending Issues
- P0: Restauration soumissions ("Ouvrir le calcul") - EN ATTENTE VALIDATION UTILISATEUR

## Upcoming Tasks
- (P1) UI gestion des corrections (`/api/corrections` admin interface)
- (P1) Refactorer le UI de index.tsx en sous-composants
- (P2) Refactorer `inventory.tsx` et `clients.tsx`

## Key Endpoints
- POST /api/auth/demo-login
- GET /api/programs?month=X&year=Y
- GET /api/program-meta?month=X&year=Y
- POST /api/compare-programs
- POST /api/submissions
- GET /api/submissions
- GET /api/better-offers
- POST /api/extract-pdf-async
- GET /api/sci/lease-rates
- POST /api/sci/calculate-lease

## Database
- MongoDB: test_database (dev) / calcauto_prod (prod)
- Collections: programs, submissions, better_offers, users, residuals, contacts, inventory, tokens, program_corrections, trim_orders, extract_tasks, import_comparisons, parsing_metrics, code_guides, migrations, window_stickers

## Credentials
- Demo: demo@calcauto.ca / demo_access_2026
- Supabase: https://oslbndkfizswhsipjavm.supabase.co
