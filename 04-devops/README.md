# Order Tracker : observabilité et incident responder (HW4, AI Dev Tools Zoomcamp)

Fork du starter [alexeygrigorev/order-tracker](https://github.com/alexeygrigorev/order-tracker). J'y ai ajouté :

- **OpenTelemetry** dans l'app : métriques, traces et logs structurés, sans PII ni secrets.
- Une **chaîne de télémétrie** : OTel Collector → Prometheus, Loki et Tempo, avec Grafana par-dessus (datasources, dashboard, alerte et contact point, tous provisionnés en fichiers).
- Une **alerte 5xx** qui reflète l'impact utilisateur et transporte le contexte : endpoint, fenêtre, lien vers le dashboard.
- Un **incident responder** sur `POST /alerts:8001`. Dans l'ordre, il collecte la preuve, lance un agent headless (Claude Code ou Codex) derrière un adapter neutre, passe la proposition au policy gate, exécute un runbook allowlisté, vérifie la reprise, puis archive le tout.
- Un **audit sécurité** : Semgrep, revue par le modèle, validation humaine et table des capacités de l'agent.

> Principe directeur du module : *the model may reason; the system must observe, authorize, verify, and remember.*

---

## Sommaire

1. [Réponses au homework](#1-réponses-au-homework)
2. [Architecture et choix](#2-architecture-et-choix)
3. [Docker Compose ou venv ?](#3-docker-compose-ou-venv-)
4. [Refaire l'exercice pas à pas](#4-refaire-lexercice-pas-à-pas)
5. [Ce qui a été vérifié, et comment](#5-ce-qui-a-été-vérifié-et-comment)
6. [Structure du dépôt](#6-structure-du-dépôt)
7. [Dépannage](#7-dépannage)
8. [Revue senior : limites et suites](#8-revue-senior--limites-et-suites)

---

## 1. Réponses au homework

| # | Question | Réponse | Preuve |
|---|---|---|---|
| 1 | Que renvoie le health check ? | **`{"status":"ok"}`** | `curl http://localhost:8000/healthz` |
| 2 | Code HTTP enregistré par la métrique pour `standard-1001` | **200** | export console : `app.http.requests{http.route="/api/orders/{order_id}", http.response.status_code=200}` |
| 3 | Code HTTP de la métrique dans Grafana pour `standard-1002` | **404** | `standard-1002` n'existe pas : le seed contient `standard-1001`, `express-1002` et `standard-1003`. Même `trace_id` dans Prometheus, Loki et Tempo. |
| 4 | État de l'alerte 5xx après ce lookup | **Normal** | aucune série 5xx, donc NoData, mappé sur `noDataState: OK`, donc **Normal** (et non « No data ») |
| 5 | Réponse de l'agent (dernière ligne) | voir ci-dessous | `incident-response/incidents/INC-20260930-125408-4a25/` |
| 6 | Quel était le problème ? | **The express delivery date calculation tried to use a day that does not exist in that month.** | `ValueError: day is out of range for month` à `app/main.py:81` |

**Q5, réponse complète de l'agent** (Claude Code headless, read-only, niveau d'autonomie 0 imposé par le label `test="true"`) :

```
INC-20260930-125408-4a25: the alert is labelled test="true" (ResponderTest).
There are no 5xx responses, error logs or error traces. /healthz returns 200 and the container is healthy.
Nothing was changed and there is nothing to fix.
Verdict: test_notification, no action needed.
```

À copier dans le formulaire : `Verdict: test_notification, no action needed.`. Le texte exact change d'un run à l'autre, mais le fond reste le même : notification de test, aucun incident, aucune action.

> ⚠️ **La réponse à Q5 dépend de l'état du système.** Si des 500 sur `express-1002` existent déjà dans les 15 dernières minutes, par exemple parce que Q6 a été lancée avant Q5, l'agent le voit dans la preuve. Il signale alors le vrai bug et escalade. Il ne patche pas, parce que le niveau 0 l'interdit : voir `INC-20260930-125245-4feb`. Respecte l'ordre Q1 → Q6.

**Q6, en détail** : `express-1002` est seedée au **dernier jour du mois précédent** (`now.replace(day=1) - 1 day`, donc toujours un jour 28 à 31). Or `order_detail` calcule `placed_at.replace(day=placed_at.day + 2)`, ce qui demande par exemple le 33 août. On obtient `ValueError`, puis un 500. La commande échoue donc **à toute date**, pas seulement en fin de mois. Le correctif proposé et déployé par l'agent tient en une ligne : `placed_at + timedelta(days=2)`, avec un test de régression à date fixe.

---

## 2. Architecture et choix

```
                  ┌────────────────────────── docker compose (réseau 10.215.24.0/24) ─────────────────────────┐
  curl / web ───► │ app :8000 (FastAPI, uid 10001)                                                          │
                  │   └─ middleware OTel : 1 span SERVER, 1 compteur, 1 histogramme et 1 log JSON/requête   │
                  │        │ OTLP/HTTP                                                                       │
                  │        ▼                                                                                  │
                  │ otel-collector :4318 ─ memory_limiter → attributes/scrub (PII) → batch                   │
                  │        ├─ métriques ─► Prometheus :9090  (OTLP natif, --web.enable-otlp-receiver)        │
                  │        ├─ logs ─────► Loki :3100        (OTLP natif, attributs → structured metadata)    │
                  │        └─ traces ───► Tempo :3200       (OTLP gRPC)                                      │
                  │ Grafana :3000 ── datasources + dashboard + alerte OrderTracker5xx + contact point webhook │
                  └──────────────────────────────────────────────┬──────────────────────────────────────────┘
                                                                 │ webhook POST (Bearer token)
                                                                 │ via host.docker.internal
                                                                 ▼
   hôte : incident-response (uv) :8001 ──────────────────────────────────────────────────────────────────────
     1. OBSERVE     collect-evidence : requêtes allowlistées Prometheus/Loki/Tempo, bornées et redacted (sans modèle)
     2. AUTHORIZE   autonomy-policy.yaml → niveau 0 observe | 1 propose | 2 remediate (label test=true → 0)
     3. REASON      agent headless (claude -p / codex exec) dans un git worktree isolé, JSON schema strict
     4. AUTHORIZE   gate sur le VRAI diff : paths, taille, confiance, tests relancés par le responder,
                    test de régression qui échoue sans le fix
     5. ACT         runbooks/deploy-fix.sh (ff-only et rebuild de l'app seule). Jamais par le modèle.
     6. VERIFY      runbooks/verify-recovery.sh : healthz, replay des GET qui échouaient, delta du compteur 5xx
                    → échec : runbooks/rollback.sh (image précédente) puis escalade
     7. REMEMBER    incidents/<INC-id>/ : alert, evidence, prompt, transcript, response, decision, logs, report
```

### Décisions et pourquoi

| Décision | Raison | Alternative écartée |
|---|---|---|
| **Middleware OTel explicite** plutôt que l'auto-instrumentation | Contrôle total des noms et des attributs, et une cardinalité maîtrisée (`http.route` = template, jamais le path brut) | `opentelemetry-instrumentation-fastapi` : plus de dépendances et de sémantique implicite |
| **Télémétrie native de FastAPI désactivée** | Les versions récentes de FastAPI embarquent de l'OTel qui s'auto-configure depuis `OTEL_*`. J'ai mesuré le problème : chaque span était exporté **en double**, et `url.query` ainsi que les valeurs de validation (PII) étaient capturées. | La laisser active : double comptage et fuite potentielle de PII |
| Compteur `app.http.requests` + histogramme semconv `http.server.request.duration` | Le compteur sert au dashboard et à l'alerte, l'histogramme à la latence p95 | Tout dériver de `_count` : faisable, mais moins lisible |
| `service.instance.id` par process | Après un redéploiement, le compteur démarre une **nouvelle série** au lieu de « reculer ». Sans ça, la vérification post-deploy peut rater des 5xx. | - |
| **Expression d'alerte « first-error-safe »** | `increase()` renvoie **0** pour le tout premier 5xx d'une route, parce que la série naît à 1 et qu'il faut deux échantillons. Je l'ai reproduit dans le sandbox. J'utilise donc `(X unless X offset 5m) or increase(X[5m])`. | `increase(...[5m]) > 0` : une erreur isolée ne page jamais |
| `noDataState: OK`, `execErrState: Error`, `for: 30s` | Pas de 5xx signifie Normal. Une requête cassée doit se voir. 30 s, c'est 3 évaluations. | `NoData` → alerting : faux positifs permanents |
| Collector comme **seul** point de sortie de l'app | On change de backend sans toucher l'app, et le scrub PII est centralisé | L'app qui pousse directement vers chaque backend |
| Ports liés à **127.0.0.1** uniquement | Prometheus, Loki et Tempo n'ont pas d'auth | `0.0.0.0` |
| **Responder sur l'hôte** et non dans un conteneur | L'agent a besoin du repo, de l'auth du CLI (Claude/Codex) et de `docker compose` pour redéployer. Le mettre en conteneur exigerait de monter le socket Docker, ce qui équivaut à root, et d'y copier des credentials. | Conteneur avec `/var/run/docker.sock` |
| Agent dans un **git worktree** (branche `incident/<id>`) | Le modèle ne touche jamais le working tree de l'opérateur, et le diff est mesurable | Édition en place |
| **Policy en code, hors du modèle** | La confiance du modèle ne vaut pas permission : le gate relance lui-même les tests et vérifie le diff réel | Faire confiance au `tests.passed=true` déclaré par l'agent |
| Webhook : loopback sans token, sinon `Bearer` | La commande curl de Q5 marche telle quelle, et Grafana (non-loopback) doit s'authentifier | Endpoint ouvert |

---

## 3. Docker Compose ou venv ?

**Les deux, chacun à sa place :**

- **Docker Compose** pour l'app et toute la stack d'observabilité : une seule commande, des versions d'images pinnées, reproductible et proche de la prod. C'est aussi ce que le homework suppose (`docker compose up --build -d --wait`).
- **uv (venv géré par uv)** pour :
  - les tests de l'app : `uv run --frozen pytest -q` ;
  - le **responder**, qui tourne sur l'hôte : `cd incident-response && uv run responder`. uv crée et synchronise le venv tout seul à partir de `uv.lock`. Pas de `python -m venv` ni de `pip install` à la main, et pas de dérive de dépendances (`--frozen`).

---

## 4. Refaire l'exercice pas à pas

### Prérequis

- Docker avec Compose v2.20 ou plus (pour `include:`), et environ 3 Go de RAM libres pour la stack.
- `uv`. Python 3.11+ est installé par uv si besoin.
- **Claude Code** (`claude`, connecté) ou **Codex** (`codex`, connecté) pour Q5 et Q6.
- Ports libres : 8000, 8001, 3000, 3100, 3200, 4318, 9090.

### 0. Récupérer le code

```bash
# fork de alexeygrigorev/order-tracker sur GitHub, puis :
git clone git@github.com:<toi>/order-tracker.git && cd order-tracker
# importer mon travail (bundle livré avec ce README) :
git fetch /chemin/vers/order-tracker-hw4.bundle hw4-observability:hw4-observability "refs/tags/*:refs/tags/*"
git checkout hw4-observability
cp .env.example .env
# mets un vrai secret :
sed -i.bak "s/^RESPONDER_TOKEN=.*/RESPONDER_TOKEN=$(openssl rand -hex 24)/" .env && rm .env.bak
```

> La branche contient **volontairement le bug d'origine**. Le correctif de l'agent n'est pas dans l'historique, sinon Q6 ne se reproduirait pas. Le fix obtenu dans le sandbox est conservé sous le tag `sandbox-agent-fix-INC-20260930-130801-ecb8`, pour comparer.

### Q1 : lancer l'app

```bash
OTEL_EXPORTER=none docker compose up --build -d --wait app
curl http://localhost:8000/healthz          # → {"status":"ok"}
```

### Q2 : métriques, logs et traces vers la console

```bash
OTEL_EXPORTER=console docker compose up --build -d --wait app
curl -i http://localhost:8000/api/orders/standard-1001
sleep 6    # intervalle d'export des métriques : 5 s
docker compose logs app | grep -A 12 '"name": "app.http.requests"'
# → datapoint {"http.request.method":"GET","http.route":"/api/orders/{order_id}","http.response.status_code":200}
```

### Q3 : chaîne de télémétrie complète

```bash
docker compose up --build -d --wait          # app + collector + prometheus + loki + tempo + grafana
curl -i http://localhost:8000/api/orders/standard-1002      # → 404
```

Ouvre http://localhost:3000 (admin / admin, ou ce qui est défini dans `.env`), puis **Dashboards → Order Tracker → Order Tracker** :

- « Requests / s by route and status » : série `/api/orders/{order_id} 404`
- « All request logs » : `GET /api/orders/{order_id} -> 404`. Dépliez-le et cliquez **View trace** sur `trace_id`.
- « Recent error traces » : vide (un 404 n'est pas une erreur serveur)

Même vérification sans UI :

```bash
curl -s localhost:9090/api/v1/query --data-urlencode 'query=app_http_requests_total{http_route="/api/orders/{order_id}"}'
curl -s -G localhost:3100/loki/api/v1/query_range --data-urlencode 'query={service_name="order-tracker"}'
```

### Q4 : alerte 5xx

L'alerte est déjà provisionnée : **Alerting → Alert rules → Order Tracker Alerts → OrderTracker5xx**.

```bash
curl -i http://localhost:8000/api/orders/standard-1002
# attendre 20-30 s → état : Normal
```

### Q5 : responder et alerte de test

Dans un **second terminal**, à la racine du repo :

```bash
cd incident-response
uv run responder              # écoute 0.0.0.0:8001 et lit RESPONDER_TOKEN / RESPONDER_AGENT dans ../.env
# pour Codex : RESPONDER_AGENT=codex uv run responder
```

Dans le premier terminal :

```bash
curl -X POST http://localhost:8001/alerts \
  -H 'Content-Type: application/json' \
  -d '{"alerts":[{"status":"firing","labels":{"alertname":"ResponderTest","test":"true"},"annotations":{"summary":"Test notification; no incident to fix"}}]}'
# → {"accepted":[{"incident":"INC-...","status":"queued"}]}

curl -s localhost:8001/incidents | python3 -m json.tool          # attendre state = closed (10-30 s)
cat incident-response/incidents/INC-*/report.md | less           # rapport complet
python3 -c "import json,glob;print(json.load(open(sorted(glob.glob('incident-response/incidents/INC-*/response.json'))[-1]))['final_message'])"
```

### Q6 : l'incident complet, de Grafana jusqu'au fix vérifié

```bash
for i in 1 2 3; do curl -si http://localhost:8000/api/orders/express-1002 | head -1; done   # 500 x3
```

Ensuite, observe :

1. **Grafana** : l'alerte passe de Normal à **Pending** (30 s) puis **Firing**. Le panneau « 5xx responses in the last 5m by route (alert query) » monte.
2. Grafana envoie le **webhook** à `http://host.docker.internal:8001/alerts`, avec le token. Le terminal du responder affiche `incident_opened`, puis `evidence_collected`, puis `agent_started`.
3. L'agent corrige dans `incident-response/.worktrees/<id>` (compter environ 30 s). Le responder relance les tests, vérifie que le test de régression **échoue sans le fix**, committe sur `incident/<id>`, exécute `deploy-fix.sh` puis `verify-recovery.sh`, et affiche `incident_closed {"state": "resolved"}`.
4. Vérifie toi-même :

```bash
curl -i http://localhost:8000/api/orders/express-1002      # → 200 + "estimated_delivery"
git log --oneline -2                                        # → fix(INC-...): ...
cat incident-response/incidents/INC-*/report.md | tail -60
```

Nettoyage : `docker compose down` (ajoute `-v` pour effacer les données et la télémétrie).

---

## 5. Ce qui a été vérifié, et comment

J'ai tout exécuté dans un sandbox Linux (Docker 29, Compose v5). Les sorties sont archivées dans `docs/sandbox-run/`.

| Élément | Statut | Détail |
|---|---|---|
| Q1, Q2, Q3 (Prometheus, Loki, Tempo) | ✅ exécuté | même `trace_id` retrouvé dans Loki et Tempo, métrique `status=404` dans Prometheus |
| Expression d'alerte (Q4, Q6) | ✅ exécutée dans Prometheus | vide avec seulement des 2xx/4xx (Normal), `3` après trois 500 (firing) |
| Requêtes du dashboard (11 panneaux) | ✅ toutes exécutées contre Prometheus, Loki et Tempo | |
| Q5 avec Claude Code headless réel | ✅ | `INC-20260930-125408-4a25` |
| Q6 avec Claude Code headless réel : fix, tests, déploiement, vérification | ✅ 8 runs réels avec le même diagnostic et le même patch (déployés et vérifiés, sauf quand un garde-fou a bloqué) | `INC-20260930-130801-ecb8` (run de référence, code final) |
| Webhook non-loopback : 401 sans token, 202 avec token | ✅ depuis un conteneur sur le réseau compose, via `host.docker.internal` | |
| Rollback automatique si la vérification échoue | ✅ drill avec un faux agent qui livre un patch inefficace | `INC-20260930-123438-47f5` |
| Gate qui rejette un test de régression qui ne prouve rien | ✅ drill | `INC-20260930-123549-5c01` |
| Budget d'exécutions de l'agent et deploy refusé sur un tree dirty | ✅ déclenchés pour de vrai pendant les re-runs | `...125751-bfcc`, `...125626-5af5` |
| Surface d'extension **effective** de l'agent différente de la surface déclarée → deploy bloqué | ✅ dans le sandbox, le CLI chargeait un MCP navigateur et 2 plugins malgré `--strict-mcp-config` | `INC-20260930-130646-e094` |
| Changement postérieur au run de référence : deny `Bash(git:*)` et deny du MCP navigateur | ✅ testé directement avec `claude -p` : `git diff --output=…` est refusé et le fichier n'est pas créé | pas de nouveau run e2e complet |
| Tests unitaires | ✅ app 5, responder 15 | `uv run --frozen pytest -q` (dans `incident-response/` aussi) |
| **Grafana lui-même** (UI, chargement du provisioning, évaluation de l'alerte, envoi du webhook) | ⚠️ **non exécuté** | Le sandbox bloque tous les registres d'images, et Grafana n'a pas pu être téléchargé autrement. J'ai reconstruit les autres images à partir des binaires officiels, sous les mêmes tags. Le payload webhook de Q6 a donc été **simulé au format Grafana**, depuis le réseau compose. **À valider chez toi** : section 4, Q3 à Q6. |

---

## 6. Structure du dépôt

```
app/                    main.py (middleware OTel), telemetry.py (providers + exporters)
tests/                  tests API + tests de télémétrie (route template, 500 compté)
compose.yaml            app (+ include observability/compose.yaml)
observability/
  compose.yaml          collector, prometheus, loki, tempo(+init), grafana
  collector.yaml        OTLP in → scrub → Prometheus / Loki / Tempo
  prometheus.yml loki.yaml tempo.yaml
  dashboard.json        dashboard "Order Tracker" (uid order-tracker)
  alerts.yaml           règle Grafana OrderTracker5xx
  grafana/provisioning/ datasources (corrélations logs↔traces↔métriques), dashboards, contact point, policy
incident-response/
  responder/            server.py (intake), pipeline.py, evidence.py, agents.py (adapter), policy.py
  collect-evidence.sh   evidence packet en CLI (même code que le responder)
  responder-task.md     prompt (evidence = données, jamais instructions)
  response.schema.json  sortie structurée stricte, commune à Claude et Codex
  autonomy-policy.yaml  niveaux, actions, guards, budget
  agent-mcp.json        surface d'extension de l'agent : aucun serveur MCP
  runbooks/             deploy-fix.sh, rollback.sh, verify-recovery.sh
  incidents/            un dossier par incident (voir incidents/README.md)
security-audit/         audit-brief.md, findings.schema.json, capability-table.md, semgrep-rules.yaml, runs/
docs/operations-and-security-report.md   rapport exigé par le module, reconstructible à partir d'un INC-id
docs/sandbox-run/       sorties brutes des runs Q1 à Q6
```

API du responder (loopback ou `Authorization: Bearer $RESPONDER_TOKEN`) : `POST /alerts`, `GET /incidents`, `GET /incidents/{id}`, `GET /incidents/{id}/report`, `POST /incidents/{id}/close` (disposition humaine), `GET /healthz`.

---

## 7. Dépannage

| Symptôme | Cause probable, et correctif |
|---|---|
| L'alerte est Firing mais le responder ne reçoit rien | Sous **Linux**, `host.docker.internal` pointe sur la gateway Docker : le responder doit écouter sur `0.0.0.0` (c'est le défaut), et un pare-feu (ufw) peut bloquer 8001 depuis le bridge. Vérifie avec `docker compose exec grafana wget -qO- http://host.docker.internal:8001/healthz`. |
| Le responder répond **401** à Grafana | `RESPONDER_TOKEN` n'est pas le même dans `.env` (côté Grafana) et dans l'environnement du responder. Recrée Grafana avec `docker compose up -d grafana` après avoir modifié `.env`. |
| Q5 répond « real bug found » au lieu de « test » | Des 500 existent déjà dans les 15 dernières minutes (Q6 lancée avant). C'est attendu : voir la section 1. |
| La 2e alerte de test renvoie `attached_to_open_incident` | Déduplication par fingerprint (30 min) tant que l'incident est ouvert ou escaladé. Ferme-le : `curl -X POST localhost:8001/incidents/<id>/close -H 'Content-Type: application/json' -d '{"by":"ellie","disposition":"..."}'` |
| `patch rejected by policy: agent_extension_surface_as_declared` | Ton Claude Code charge des serveurs MCP ou des plugins (voir `agent/run.json` → `extension_surface`). Soit tu les désactives pour le responder, soit tu les autorises explicitement dans `autonomy-policy.yaml` → `extension_surface`. |
| `agent run budget exhausted` | Garde-fou coût/boucle, 6 exécutions de l'agent par heure. Monte `budget.max_agent_runs_per_hour` dans une copie de la policy et pointe `RESPONDER_POLICY` dessus. |
| `deploy-fix.sh failed (exit 3)` | Fichiers suivis modifiés dans le repo : le runbook refuse d'écraser ton travail. Committe ou stashe, puis relance. |
| `permission denied` sur `/data` après être passée du starter à cette version | L'app tourne maintenant en uid 10001. Le service `app-volume-init` reprend la propriété du volume automatiquement, sans rien effacer. |
| Tempo : `permission denied /var/tempo` | C'est le rôle de `tempo-init`, qui chown le volume. Relance `docker compose up -d`. |
| `grafana/grafana:12.4.12` introuvable | Remplace par la dernière 12.x disponible. Le provisioning est stable sur toute la 12.x. |

---

## 8. Revue senior : limites et suites

Le détail est dans [`docs/operations-and-security-report.md`](docs/operations-and-security-report.md). Voici ce qu'un reviewer exigeant retiendrait.

- **Verdict : défendable avec réserves.** La boucle observe → alert → evidence → reason → authorize → act → verify → remember a été exécutée de bout en bout, plusieurs fois, avec un agent réel. Les chemins d'échec (rollback, gate, budget, deploy refusé, bug du responder lui-même) ont tous été déclenchés et ont échoué **en sécurité**.
- **Réserve n°1 : Grafana n'a pas tourné.** Q3/Q4 (UI) et le webhook réel de Q6 restent à valider sur ta machine. J'ai vérifié le fond (requêtes, format du payload, auth), pas l'intégration.
- **Réserve n°2 : le modèle se trompe sur des détails.** Le diagnostic central et le patch restent stables sur 8 runs. En revanche, l'explication de « pourquoi maintenant » a varié : « jour 29+ », « 27+ », « aujourd'hui c'est le 30 ». Ces affirmations sont fausses ou imprécises, puisque le seed tombe *toujours* sur un dernier jour de mois. Dans un run intermédiaire (non archivé), l'agent a même affirmé que « le test échoue sans le fix » alors que ses deux tentatives shell pour le vérifier avaient été **refusées**, et rien dans ce qu'on avait enregistré ne permettait de confirmer l'affirmation. C'est exactement pour ça que le responder refait lui-même cette vérification, et qu'il conserve désormais le transcript complet.
- **Réserve n°3 : la surface déclarée n'est pas la surface effective.** `agent-mcp.json` est vide et Snyk Agent Scan le confirme. Pourtant, dans le sandbox, le CLI chargeait 61 skills, 7 plugins et un MCP d'automatisation de navigateur. Correctif : flags `--disable-slash-commands --setting-sources project`, puis un gate qui lit la surface **effective** dans l'événement `init` et bloque le déploiement si elle diffère de la surface déclarée. Chez toi, la policy par défaut exige une surface vide : si tu as des plugins Claude Code installés, le fix sera escaladé au lieu d'être déployé. C'est voulu. Ajoute-les explicitement dans `extension_surface` si tu les acceptes.
- **Réserve n°4 : le niveau 2 (déploiement autonome) est un choix pédagogique.** En vrai, je recommanderais le niveau 1 (PR proposée) ou le niveau 2 limité à des runbooks non-code (restart, rollback).
- Hors périmètre, conformément aux non-goals du module : SLO et burn rate, canary, digests d'images, sandbox OS pour l'agent Claude (qui repose ici sur des allow/deny lists et non sur de l'isolation noyau).
