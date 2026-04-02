# CalcAuto AiPro - PRD

## Problem Statement
Application CRM pour concessionnaires automobiles (Stellantis). Extraction automatique des données depuis PDFs mensuels (programmes retail et guides résiduels) pour alimenter un calculateur de location et financement.

## Architecture
- Frontend: React Native/Expo for Web (TypeScript)
- Backend: FastAPI (Python 3.11), pdfplumber, regex
- DB: MongoDB Atlas (users, programs, submissions)
- Storage: Fichiers JSON locaux + Supabase

## Core Features (Completed)
1. Parseur pdfplumber déterministe (remplace OCR/AI)
2. Auto-détection du mois/année depuis les PDFs
3. Extraction dynamique des ajustements kilométrage (12k/18k)
4. Comparaison automatique résiduels (améliorés/détériorés/nouveaux/retirés)
5. Comparaison automatique programmes retail (taux + cash vs mois précédent)
6. Détection de la plage de dates effective (ex: Mar 01 - Apr 30) → sauvegarde multi-mois
7. Séparation correcte des trims (Sport ≠ Rebel pour résiduels)
8. Dynamic Event Banner + loyalty rates + 90j deferred payment
9. Demo Mode (auto-login sans mot de passe)
10. CI/CD GitHub Actions (tests + deploy Render/Vercel)
11. Matching progressif des noms de véhicules (priorité premier trim)
12. Bug fix `/api/periods` (filtrage documents avec month=None)

## Data Files
- `sci_residuals_{mois}{année}.json` - Résiduels par véhicule/trim
- `sci_lease_rates_{month}{year}.json` - Taux de location SCI
- `km_adjustments_{month}{year}.json` - Ajustements kilométrage
- `program_meta_{month}{year}.json` - Métadonnées événement

## Key API Endpoints
- `POST /api/upload-residual-guide` - Upload résiduel (auto-detect, compare, multi-month save)
- `POST /api/extract-pdf-async` - Extraction programmes retail (async, compare)
- `POST /api/scan-pdf` - Scan pages via TOC
- `GET /api/sci/residuals` - Résiduels courants
- `GET /api/sci/lease-rates` - Taux location SCI
- `GET /api/periods` - Périodes disponibles

## Upcoming Tasks
- (P2) Interface CorrectionsManager dans le panneau admin
- (P3) Refactorisation des gros composants (index.tsx ~3700 lignes, inventory.tsx, clients.tsx)

## Known Issues
- Aucun bloquant connu
