# CalcAuto AiPro - Product Requirements Document

## Overview
CalcAuto AiPro is a car dealership financing & leasing calculator app. Built with React Native (Expo) frontend and FastAPI + MongoDB backend. Deployed on Render with Supabase for file storage.

## Core Features
- **Vehicle Financing Calculator**: Compare Option 1 (Rebate + Rate) vs Option 2 (Lower Rate) with best-choice recommendation
- **SCI Lease Calculator**: Full lease analysis with residuals, km adjustments, standard vs alternative rates
- **PDF Import**: Extract vehicle programs from monthly incentive PDFs via pdfplumber
- **Inventory Management**: Track dealership vehicles with VIN, pricing, product codes
- **CRM**: Contact management, email/SMS submissions, submission history
- **Invoice Scanning**: OCR-based invoice scanning with Google Vision + OpenAI
- **Demo Mode**: Password-free access for demonstrations (demo@calcauto.ca)

## Architecture
```
/app
├── backend/          # FastAPI + MongoDB
│   ├── server.py     # Main server with Supabase sync
│   ├── routers/      # API routes (programs, contacts, inventory, etc.)
│   ├── services/     # PDF parser, storage
│   └── data/         # Extracted JSON data files
├── frontend/         # React Native (Expo Web)
│   ├── app/(tabs)/   # Tab screens (index, inventory, clients, admin)
│   ├── features/     # Feature-sliced architecture
│   │   └── calculator/
│   │       ├── hooks/useCalculatorPage.ts  # All calculator logic
│   │       └── index.ts                    # Barrel export
│   ├── components/   # Shared components
│   ├── hooks/        # Shared hooks (useCalculator, useAuth)
│   ├── utils/        # API, i18n, leaseCalculator
│   └── types/        # TypeScript types
└── memory/           # PRD and documentation
```

## Environment Variables
### Backend (.env)
- MONGO_URL, DB_NAME
- SUPABASE_URL, SUPABASE_SERVICE_KEY
- GOOGLE_VISION_API_KEY
- OPENAI_API_KEY
- JWT_SECRET

### Frontend (.env)
- REACT_APP_BACKEND_URL

## What's Been Implemented
- [x] Full financing calculator with Option 1/2 comparison
- [x] SCI Lease calculator with residual analysis grid
- [x] PDF import with automatic page detection (TOC-first strategy)
- [x] Inventory management (CRUD + VIN validation)
- [x] CRM contacts + submissions
- [x] Email/SMS/Print/Excel sharing
- [x] Demo mode (auto-login)
- [x] Bilingual support (FR/EN)
- [x] Supabase file sync on startup
- [x] CI/CD pipeline (GitHub Actions)
- [x] **Refactored index.tsx** (3695 → 1970 lines, logic extracted to hook)

## Completed Refactoring (March 2026)
- **index.tsx**: Reduced from 3695 to 1970 lines (47% reduction)
- **useCalculatorPage.ts**: Custom hook with all state, effects, callbacks (1547 lines)
- **Barrel export**: features/calculator/index.ts
- **Testing**: 100% backend (18/18) + 100% frontend (13/13) verification

## Backlog
### P1 - UI for Correction Management
- Frontend interface in admin panel for program corrections API (/api/corrections)

### P2 - Further Component Extraction
- Extract UI sub-components from index.tsx (HeaderBar, LeaseSection, etc.)
- Each component 200-300 lines

### P3 - Refactor Other Large Files
- inventory.tsx and clients.tsx are large and could be broken down

### Known Pre-existing Issues
- Parasitic 'styles/homeStyles' tab in navigation bar (cosmetic)
- Admin tab overlay intercepting clicks (cosmetic)

## Credentials
- Demo: demo@calcauto.ca / demo_access_2026
- Import password: Admin
- Supabase: https://oslbndkfizswhsipjavm.supabase.co
