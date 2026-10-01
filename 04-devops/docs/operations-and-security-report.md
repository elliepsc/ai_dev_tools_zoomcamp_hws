# Operations and Security Report : Order Tracker

*Auteure : Ellie Pascaud. Implémentation et runs : sandbox Linux, 30/09/2026. Incident de référence : **INC-20260930-130801-ecb8** (code final).*

Ce rapport doit permettre à un lecteur, à partir d'**un seul ID d'incident**, de reconstituer ce qui s'est passé, qui a décidé quoi, et ce qui a réellement été exécuté. Tous les chemins cités sont relatifs à `incident-response/incidents/<ID>/`.

---

## 1. Reconstitution de l'incident INC-20260930-130801-ecb8

| Question | Réponse | Source |
|---|---|---|
| **Version déployée** | L'image `order-tracker:local` construite depuis le HEAD `3982ab3`, avec `service_version=3982ab3` sur les 5xx. Le container est `healthy`. | `evidence/evidence.json` → `deploy`, `metrics.deployed_versions` |
| **Impact utilisateur** | Toute consultation de `express-1002` renvoie HTTP 500 : 7 erreurs 5xx sur `/api/orders/{order_id}` dans les 5 dernières minutes, toutes `error_type=ValueError`. Commandes standard, liste et `/healthz` non affectées. | `evidence/summary.md`, `response.json` → `user_impact` |
| **Alerte** | `OrderTracker5xx` : `http_route=/api/orders/{order_id}`, `severity=critical`, annotations `endpoint`, `window=5m`, `dashboard_url`. Payload au format Grafana, reçu **avec Bearer token** depuis le réseau Docker (non-loopback). Fingerprint recalculé côté serveur. | `alert.json`, `status.json` |
| **Preuve inspectée** | 20 lignes de log ERROR (Loki) avec stack trace menant à `app/main.py:81 order_detail`. 5 traces d'erreur (Tempo) avec `order.id=express-1002`, `order.priority=express`, span `orders.build_detail` en ERROR. Séries Prometheus par status et par version. État git et Docker. Échantillon d'échec reconstitué : `GET /api/orders/express-1002`. Collecte en 0,35 s, **avant** tout appel au modèle. | `evidence/` |
| **Modèle et configuration** | Claude Code 2.1.285 headless, modèle par défaut du CLI (le CLI rapporte `claude-sonnet-5-5` plus `claude-haiku-4-5`), 12 tours, 26 s, 0,16 USD. Mode `edit` dans le worktree `incident/<ID>`. Outils autorisés : `Read Glob Grep Edit Write Bash(uv run --frozen pytest:*)`. Skills désactivés, réglages utilisateur ignorés, `--strict-mcp-config` avec une config MCP vide. **Surface effective** rapportée par le CLI : MCP `claude-in-chrome` (22 outils) et 2 plugins gérés, injectés par l'hôte du sandbox (voir F8). | `agent/run.json` → `command`, `meta.extension_surface` |
| **Policy utilisée** | `autonomy-policy.yaml` **surchargée pour le sandbox** (`docs/sandbox-run/autonomy-policy.sandbox-override.yaml`) : budget passé de 6 à 20 exécutions/h à cause des re-runs, et autorisation explicite des 3 éléments injectés par le sandbox. Sans cette surcharge, le déploiement est bloqué : `INC-20260930-130646-e094`. | diff dans le fichier cité |
| **Action proposée** | `patch`, confiance 0,95 : `placed_at + timedelta(days=2)` et un test à date fixe (31/01 → 02/02). | `response.json`, `fix.patch` |
| **Ce que le modèle a tenté** | 10 appels d'outils, dont **2 refusés** (heredoc `cat >> tests/…`, hors allowlist). L'agent s'est rabattu sur `Edit`. 2 commandes shell en lecture seule (`git diff`, `tail`) ont été **auto-approuvées** par Claude Code alors qu'elles ne sont pas dans l'allowlist (voir F5). | `agent/agent-tool-calls.md`, `agent/agent-transcript.jsonl` |
| **Décision de la policy** | Niveau 2 (remediate). Les **12 checks** passent : classification, action, confiance ≥ 0,7, chemins allowlistés, 2 fichiers, 7 lignes, test ajouté, suite **relancée par le responder** (6 passed), suite **qui échoue quand on retire le fix**, action permise au niveau 2, surface d'extension conforme à la policy. | `decision.json` → `checks`, `tests.log`, `tests-before-fix.log` |
| **Commandes réellement exécutées** (par le responder, jamais par le modèle) | `runbooks/deploy-fix.sh <repo> incident/<ID> inc-…` : tag de rollback, `git merge --ff-only`, `docker compose up --build -d --wait --no-deps app`, exit 0. Puis `runbooks/verify-recovery.sh /api/orders/{order_id} /api/orders/express-1002`, exit 0. | `decision.json` → `executed`, `deploy.log` |
| **Vérification de la reprise** | `/healthz` renvoie 200. Trois replays de `GET /api/orders/express-1002` renvoient 200. Compteur 5xx de la route : 7 avant, 7 après. Résultat : **resolved**. | `verify.log` |
| **Escalade** | Aucune. Pour des exemples : `…123438-47f5` (rollback), `…123549-5c01` (gate), `…130646-e094` (surface d'extension). | `escalation.md` dans ces dossiers |
| **Finding sécurité lié et disposition humaine** | M-07 (écriture arbitraire via `git diff --output`) : **corrigé**, puis prouvé (un `claude -p` avec la deny-list finale refuse la commande et le fichier n'est pas créé). M-02 (du code de test écrit par l'agent s'exécute sur l'hôte) : **atténué**, résiduel accepté. Finding F8/S-01 (surface déclarée différente de la surface effective) : **corrigé** par un gate. | `security-audit/runs/2026-09-30/human-review.md` |

Chronologie (`audit.jsonl`, UTC) : 13:08:01 ouverture, preuve, niveau, worktree, début de l'agent. 13:08:27 fin de l'agent. 13:08:29 tests relancés, preuve que le test échoue sans le fix, gate, commit. 13:08:36 déploiement. 13:09:00 vérification OK et clôture. **Entre l'alerte et la reprise vérifiée : 59 s.**

---

## 2. Registre des incidents (sandbox)

| ID | Déclencheur | Résultat | Ce que ça démontre |
|---|---|---|---|
| `INC-20260930-125408-4a25` | Alerte de test (Q5) | closed, `test_notification` / `none` | Le niveau 0 est imposé par le label `test=true`. Mode read-only. |
| `INC-20260930-130801-ecb8` | 5xx réels (Q6), code final | **resolved** | La boucle complète (voir §1) |
| `INC-20260930-125833-d5da` | 5xx réels (Q6), avant le gate de surface | resolved | Reproductibilité : même diagnostic, même patch |
| `INC-20260930-130646-e094` | 5xx réels (Q6) avec la policy par défaut | fix valide, **deploy bloqué** (`agent_extension_surface_as_declared`) | Surface déclarée différente de la surface effective (F8) : le gate l'attrape |
| `INC-20260930-123438-47f5` | Drill : faux agent, patch inefficace | la vérification échoue (5xx : 6 → 9), **rollback** automatique, escalade | `verify-recovery.sh` mesure la télémétrie, pas seulement des codes HTTP. `rollback.sh` fonctionne. |
| `INC-20260930-123549-5c01` | Drill : même patch inefficace | **rejeté par le gate** (`regression_test_fails_without_fix`) | Le drill précédent a révélé qu'un test trivial passait le gate. Le guard a été ajouté, puis prouvé. |
| `INC-20260930-125245-4feb` | Alerte de test avec des 500 récents dans la stack | escalade (aucun patch possible au niveau 0), fermé par un humain | La réponse à Q5 dépend de l'état. La policy l'emporte sur l'avis du modèle, qui voulait patcher. |
| `INC-20260930-125441-1979` | 5xx | **bug du responder** (AttributeError), escalade, aucun changement | Le fail-safe marche : une exception n'entraîne ni déploiement ni perte de l'incident. Corrigé ensuite. |
| `INC-20260930-125626-5af5` | 5xx | fix validé, **déploiement refusé** (exit 3, tree dirty), fermé par un humain | Le runbook refuse d'écraser des changements non commités. Défaut de conception corrigé : les dossiers d'incident étaient versionnés. |
| `INC-20260930-125751-bfcc` | 5xx | **budget épuisé** (6 exécutions/h), pas d'agent | Le garde-fou coût/boucle se déclenche réellement. |

---

## 3. Observabilité : ce qui est mesuré et pourquoi

- **SLI implicite** : proportion de requêtes non-5xx par route (panneau « 5xx ratio »). Pas de SLO formel (non-goal du module) : c'est la prochaine étape.
- **Signal d'alerte** : au moins un 5xx sur une route dans les 5 dernières minutes, avec `for: 30s`. Ce seuil est volontairement sensible, parce qu'un 500 veut dire qu'un client ne peut pas voir sa commande. Sur une app à fort trafic, il faudrait un ratio ou un burn rate.
- **Piège trouvé et corrigé** : `increase()` ignore le premier 5xx d'une série neuve. Je l'ai reproduit (valeur 0 après un 500), puis contourné avec `(X unless X offset 5m) or increase(X[5m])`. Le flag Prometheus `created-timestamp-zero-ingestion` **n'a pas suffi** pour l'ingestion OTLP en 3.5.
- **Corrélation** : chaque log porte `trace_id` et `span_id`, et depuis la correction `order.id` pour les requêtes d'API. Les datasources relient logs → traces (derived field), traces → logs (`tracesToLogsV2`) et traces → métriques.
- **Cardinalité et PII** : les attributs de métrique se limitent à la méthode, au template de route, au status et au type d'erreur. `customer` et `item` ne sont jamais émis, et le collector supprime en plus ces attributs s'ils apparaissent (défense en profondeur). La télémétrie native de FastAPI, qui capturait `url.query` et les entrées de validation, est désactivée.

---

## 4. Findings opérationnels (revue critique)

| # | Constat | Gravité | Statut |
|---|---|---|---|
| F1 | **Grafana n'a pas été exécuté** : les registres d'images sont bloqués dans le sandbox. Provisioning, évaluation réelle de l'alerte et envoi du webhook restent à valider. | élevée (pour la preuve) | à faire sur la machine d'Ellie |
| F2 | Les explications du modèle varient d'un run à l'autre et contiennent des erreurs factuelles secondaires (« jour 29+ », « 27+ », « aujourd'hui c'est le 30 »), avec une confiance de 0,95 à 0,97. Diagnostic central et patch identiques sur 8 runs. | moyenne | atténué : le gate vérifie les faits (tests, test qui échoue sans le fix, diff), et la vérification mesure la reprise |
| F3 | **Traçabilité version ↔ commit cassée** : `service_version` vaut des SHA (par exemple `c592846`, le fix d'un run précédent) qui n'existent plus dans la branche, à cause de la réécriture d'historique faite pour livrer une branche qui contient le bug. | moyenne | leçon : ne jamais réécrire l'historique de commits déployés, et tagger les images avec SHA + digest |
| F4 | Le modèle n'est pas épinglé (« cli default ») : un changement de version du CLI change silencieusement le comportement. | moyenne | le modèle réellement utilisé est enregistré. Recommandation : fixer `RESPONDER_MODEL`. |
| F5 | Claude Code auto-approuve des commandes shell en lecture seule (`sed -n`, `ls`, `git status`, `git diff`) **même hors allowlist**. Il refuse en revanche `git diff --output=…`, testé. | faible | deny explicite `Bash(git:*)` ajouté (les denies l'emportent sur l'auto-approbation). La lecture reste possible via `Read`, comme prévu. |
| F6 | La vérification rejoue uniquement des GET idempotents observés. Ça ne couvre pas un bug sur POST ou PATCH. | faible | par conception (ne jamais rejouer une écriture) |
| F7 | Un seul worker : un incident long bloque les suivants (file bornée à 50). | faible | acceptable à cette échelle |
| F8 | **Surface déclarée différente de la surface effective** : `agent-mcp.json` est vide (Snyk Agent Scan : « no mcp servers or skills found »), pourtant le CLI de l'agent chargeait 61 skills, 7 plugins et un MCP d'automatisation de navigateur. Ils étaient hérités de l'environnement hôte, malgré `--strict-mcp-config`. | **élevée** (supply chain de l'agent) | corrigé : `--disable-slash-commands --setting-sources project` (skills : 61 → 0), plus un gate sur la surface effective lue dans l'événement `init`. Tout élément non déclaré bloque le déploiement (`INC-…130646-e094`). |

---

## 5. Sécurité

- Scanner déterministe : Semgrep 1.178 avec les règles communautaires (python, bash, dockerfile, yaml) et 5 règles projet (`security-audit/semgrep-rules.yaml`). 17 résultats au 1er run, 16 au run final. Tous triés : aucun vrai positif exploitable, 1 durcissement accepté (images non épinglées par digest), 1 corrigé (le `$ok` exécuté comme une commande dans `verify-recovery.sh`).
- Revue par le modèle : Claude Code read-only avec `audit-brief.md`, sortie validée par `findings.schema.json`. 12 findings (2 high, 5 medium, 3 low, 2 info). **Validation humaine** dans `security-audit/runs/2026-09-30/human-review.md` : 5 corrigés, 1 atténué, 6 acceptés avec justification.
- Surface d'extension de l'agent : Snyk Agent Scan 0.6.8 → `agent-mcp.json`, *no mcp servers or skills found*. **Ce scan ne couvre que la surface déclarée** : la surface effective était plus large (F8). D'où le contrôle à l'exécution, qui lit l'événement `init` du CLI. Le scan complet exige un `SNYK_TOKEN` : à lancer chez Ellie.
- Capacités, credentials et provenance : `security-audit/capability-table.md`.

---

## 6. Ordre recommandé pour la suite

1. Valider la partie Grafana (F1) : section 4 du README, Q3 à Q6.
2. Épingler le modèle (F4) et les images par digest. Vérifier dans `agent/run.json` que la surface effective est vide sur ta machine (F8).
3. Passer le niveau par défaut à **1** (le fix arrive sous forme de PR, merge par un humain), et garder le niveau 2 pour des runbooks non-code (restart, rollback vers une version taggée).
4. Définir un SLI/SLO sur le parcours « consulter ma commande », et remplacer l'alerte « ≥ 1 erreur » par une alerte de burn rate.
5. Exécuter le responder sous un utilisateur dédié ou dans une VM, sans accès aux credentials de l'opérateur, au-delà des allow/deny lists.
