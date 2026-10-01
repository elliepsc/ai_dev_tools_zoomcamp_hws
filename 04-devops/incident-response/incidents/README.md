# Incident records

Un dossier par incident, écrit par le responder (jamais édité à la main, sauf la disposition humaine via `POST /incidents/{id}/close`).

| Fichier | Contenu |
|---|---|
| `status.json` | état courant (open → collecting_evidence → agent_running → deploying → verifying → resolved / closed / escalated) |
| `alert.json` | payload reçu (redacted) |
| `evidence/summary.md`, `evidence/evidence.json` | preuve collectée **avant** le modèle |
| `prompt.md` | prompt exact envoyé à l'agent |
| `agent/run.json` | commande (flags de permissions), code retour, durée, coût, modèles, nb de refus |
| `agent/agent-transcript.jsonl` | transcript complet (stream-json) de l'agent, redacted |
| `agent/agent-tool-calls.md` | liste lisible des appels d'outils et des refus |
| `response.json` | réponse structurée validée par `response.schema.json` |
| `decision.json` | niveau d'autonomie, checks du gate, commandes exécutées, issue |
| `fix.patch`, `tests.log`, `tests-before-fix.log` | diff réel, tests relancés par le responder, preuve que le test échoue sans le fix |
| `deploy.log`, `verify.log`, `rollback.log` | sortie des runbooks |
| `audit.jsonl` | journal horodaté de chaque étape |
| `report.md`, `escalation.md` | rapport lisible et paquet d'escalade |

## Incidents de ce dépôt (runs du 30/09/2026 dans le sandbox)

| ID | Pourquoi il est là |
|---|---|
| `INC-20260930-125408-4a25` | **Q5** : alerte de test, niveau 0, `test_notification` / `none` |
| `INC-20260930-130801-ecb8` | **Q6 (référence, code final)** : 5xx réels, fix de l'agent, gate (12 checks), déploiement, vérification, **resolved** |
| `INC-20260930-125833-d5da` | Q6, run précédent (avant le gate sur la surface d'extension), **resolved** |
| `INC-20260930-130646-e094` | Q6 : fix valide mais **bloqué** parce que la surface effective de l'agent (MCP navigateur et plugins injectés par le sandbox) ne correspondait pas à la surface déclarée |
| `INC-20260930-123438-47f5` | Drill : patch volontairement inefficace, la vérification échoue, **rollback**, escalade |
| `INC-20260930-123549-5c01` | Drill : même patch, **rejeté par le gate** (le test ne prouve rien) |
| `INC-20260930-125245-4feb` | Alerte de test sur une stack qui avait déjà des 500 : escalade (réponse dépendante de l'état) |
| `INC-20260930-125441-1979` | Bug du responder : fail-safe (escalade, aucun changement), corrigé ensuite |
| `INC-20260930-125626-5af5` | Fix valide mais **déploiement refusé** (fichiers suivis modifiés), corrigé ensuite |
| `INC-20260930-125751-bfcc` | **Budget** d'exécutions d'agent atteint, pas d'appel au modèle |

Les deux drills utilisent l'agent `fake` (`RESPONDER_AGENT=fake`) pour rendre l'échec déterministe. Les chemins absolus (`/home/claude/...`) sont ceux du sandbox.
