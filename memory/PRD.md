# CalcAuto AiPro - PRD

## Problem Statement
Application de gestion de financement et location automobile pour concessionnaires FCA Canada.

## Completed Features
- [x] Calcul financement Option 1 (consumer_cash + taux standard) et Option 2 (alternative_consumer_cash + taux réduit)
- [x] Calcul location SCI avec résiduels
- [x] Import PDF via IA (GPT-4o)
- [x] Export/Import Excel programmes et SCI Lease (freeze panes)
- [x] Système de comparaison avant/après (MongoDB) avec matching flexible
- [x] 5 stratégies de matching: exact, None vs "", normalisé (retire codes CPOS), trim partiel, modèle partiel
- [x] Force logout après import
- [x] Migration données (corrections rebates, doublons)
- [x] alternative_consumer_cash utilisé dans calcul Option 2 ET affiché dans UI/impression/partage
- [x] Historique des comparaisons d'imports

## Key Changes (2 mars 2026)
- **Backend**: Matching flexible avec normalisation regex pour codes produit (CPOS, WLJH74, etc.)
- **Frontend**: `alternative_consumer_cash` ajouté dans: type VehicleProgram, useCalculator (déduction avant taxes Option 2), résumé rabais (Opt.1/Opt.2), boutons options, cartes résultat, vue impression HTML, texte partage SMS
- **Comparaison avant/après**: Snapshot MongoDB, diff champ par champ, collection `import_comparisons`

## Backlog
- (P1) Améliorer mémoire corrections pour futurs imports PDF
- (P2) Refactorer index.tsx (3700+ lignes) en composants
- (P2) Refactorer inventory.tsx
