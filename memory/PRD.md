# CalcAuto AiPro - PRD

## Problem Statement
Application de gestion de financement et location automobile pour concessionnaires FCA/Stellantis Canada (Québec).

## Moteur de calcul
### Financement (useCalculator.ts)
- Option 1: consumer_cash + taux standard + bonus_cash
- Option 2: alternative_consumer_cash + taux réduit (pas de bonus)
- Taxes capitalisées (financées), PMT standard

### Location SCI (leaseCalculator.ts)
- Annuité en avance: PMT_arrears / (1 + taux_mensuel)
- Taxes SUR le paiement mensuel (5% TPS + 9.975% TVQ)
- Crédit taxe échange réparti sur les paiements
- Validé mathématiquement le 2 mars 2026 (match exact)

## Completed Features
- [x] Calcul financement Option 1/2 avec alternative_consumer_cash
- [x] Calcul location SCI — moteur refactoré en module (leaseCalculator.ts)
- [x] Backend endpoint /api/sci/calculate-lease — formule SCI exacte
- [x] Audit Option 1 vs Option 2 — cohérence confirmée
- [x] Import PDF via IA (GPT-4o)
- [x] Export/Import Excel avec comparaison avant/après
- [x] Matching flexible (normalisation codes produit)
- [x] Upload multiple PDFs + file d'attente révision
- [x] Force logout après import

## Backlog
- (P1) Améliorer mémoire corrections pour futurs imports PDF
- (P2) Refactorer index.tsx (3700+ lignes)
- (P2) Refactorer inventory.tsx
