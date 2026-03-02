# CalcAuto AiPro - PRD

## Problem Statement
Application de gestion de financement et location automobile pour concessionnaires FCA Canada.

## Completed Features
- [x] Calcul financement Option 1/2 avec alternative_consumer_cash
- [x] Calcul location SCI avec résiduels
- [x] Import PDF via IA (GPT-4o)
- [x] Export/Import Excel programmes et SCI Lease (freeze panes)
- [x] Système de comparaison avant/après (MongoDB) avec matching flexible
- [x] Force logout après import
- [x] Upload multiple PDFs + scan batch + file d'attente de révision - 2 mars 2026
- [x] Migration données (corrections rebates, doublons)

## Latest Changes (2 mars 2026)
- **Batch PDF scan**: Sélection multiple de PDFs, scan séquentiel avec progression, file d'attente de révision 1 par 1
- **alternative_consumer_cash**: Intégré dans calcul Option 2 et toute l'UI
- **Matching flexible**: 5 stratégies pour import Excel (normalisation codes produit)

## Backlog
- (P1) Améliorer mémoire corrections pour futurs imports PDF
- (P2) Refactorer index.tsx (3700+ lignes)
- (P2) Refactorer inventory.tsx
