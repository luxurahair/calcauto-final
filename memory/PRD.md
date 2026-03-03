# CalcAuto AiPro - PRD

## Problem Statement
Application de gestion de financement et location automobile pour concessionnaires FCA/Stellantis Canada (Quebec).

## Completed Features
- [x] Calcul financement Option 1/2 avec alternative_consumer_cash
- [x] Calcul location SCI — moteur refactore (leaseCalculator.ts) + backend /api/sci/calculate-lease
- [x] Import PDF via IA (GPT-4o) avec auto-correction
- [x] Export/Import Excel avec comparaison avant/apres + matching flexible
- [x] Memoire des corrections (P1) — matching flexible, compteur d'application
- [x] Upload multiple PDFs + file d'attente revision
- [x] Fix modal "Envoyer par email" — layout compact inline, boutons toujours visibles
- [x] Fix SMTP import manquant — email Excel jamais envoye
- [x] Extraction PDF asynchrone — upload immediat + traitement background + polling
- [x] Fix parser Excel import — supporte format avec en-tetes, $, %, -
- [x] Excel freeze_panes E4 (Programmes) + D4 (SCI Lease)
- [x] Import Excel cree les programmes manquants
- [x] Prompt AI standardise dans build_extraction_prompt() — structure FIGEE, incluant alt_consumer_cash
- [x] Excel 2 onglets: Programmes + SCI Lease — email inclut les deux
- [x] Modal detail offre CRM — comparaison complete avec METHODE DELTA (vraies economies)
- [x] Fix "Ouvrir le calcul" historique — restauration partielle pour anciennes soumissions
- [x] **FIX: Endpoints SCI dynamiques** — plus de fichiers codes en dur `feb2026`. Trouve automatiquement le fichier le plus recent (Mars, Avril, etc.) — 3 mars 2026

## Standard Excel Structure (FIGEE)
### Onglet 1: Programmes
- Row 1: Titre | Row 2: Categories | Row 3: Colonnes | Row 4+: Donnees
- A:Marque B:Modele C:Trim D:Annee | E:Rabais Opt1 F-K:Taux Opt1 | L:Rabais Opt2 M-R:Taux Opt2 | S:Bonus
- Freeze: E4

### Onglet 2: SCI Lease
- Row 1: Titre | Row 2: Categories | Row 3: Colonnes | Row 4+: Donnees
- A:Marque B:Modele | C:Lease Cash | D-L:Standard Rates(24-60m) | M-U:Alt Rates(24-60m)
- Freeze: D4

## Architecture Notes
- Frontend: Expo/React Native Web, pre-built to /app/frontend/dist
- Backend: FastAPI on port 8001
- Frontend rebuild: npx expo export --platform web + supervisorctl restart expo
- Async extraction: POST /api/extract-pdf-async + GET /api/extract-task/{task_id}
- Prompt AI centralise dans build_extraction_prompt() - NEVER modify column structure
- **SCI files dynamiques**: `_get_latest_data_file()` dans sci.py scanne le dossier data/ et retourne le fichier le plus recent par mois/annee

## CRM Offer System — METHODE DELTA
- POST /api/compare-programs: Compare anciennes soumissions vs programmes actuels
  - Methode delta: compare sur meme base (sans taxes/frais)
  - Delta = old_theoretical - new_theoretical
  - New estimated payment = old_actual_payment - delta
- GET /api/better-offers: Offres stockees
- POST /api/better-offers/{id}/approve: Approuver et envoyer

## Backlog
- (P1) Creer UI admin pour gestion des corrections sauvegardees
- (P2) Refactorer index.tsx (3600+ lignes)
- (P2) Refactorer inventory.tsx
- (P2) Refactorer clients.tsx
