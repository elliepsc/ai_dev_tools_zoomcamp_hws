# Agent Relay, Homework 3 : tester, conteneuriser, déployer

Fork du starter [alexeygrigorev/agent-relay](https://github.com/alexeygrigorev/agent-relay)
pour le Homework 3 de l'AI Dev Tools Zoomcamp 2026 (module 3). On part de
l'API FastAPI et du dashboard fournis, et on ajoute :

- un **test d'intégration boîte noire** qui passe par la vraie API HTTP et la vraie DB ;
- un **Dockerfile multi-stage** (image `agent-relay:local`, utilisateur non-root) ;
- le **portage PostgreSQL** du stockage, avec `FOR UPDATE SKIP LOCKED`, et un `compose.yaml` ;
- des **manifests Kubernetes** pour kind : Deployment, StatefulSet, PVC, Services, probes ;
- une **CI/CD GitHub Actions** exécutable en local avec `act` : tests → build → `kind load` → rollout → smoke test.

```text
 agent émetteur ──POST /tasks──┐                    ┌── GET /tasks/{id} (résultat)
                               ▼                    │
                        ┌──────────────┐   SQL   ┌────────────┐
 navigateur (dashboard)─▶│ API FastAPI  │────────▶│ PostgreSQL │  (tasks, attempts, agents)
                        └──────────────┘         └────────────┘
                               ▲
 worker ──POST /tasks/claim ───┘  (long polling, lease + claim token)
        ──POST /tasks/{id}/complete
```

---

## Réponses au questionnaire

| # | Question | Réponse |
|---|----------|---------|
| 1 | Architecture du projet | **Agents claim tasks from a DB through an HTTP API.** |
| 2 | Statut vu par l'émetteur après le résultat | **completed** |
| 3 | Option Docker qui publie un port | **`-p`** |
| 4 | Hostname de la DB dans Compose | **`postgres`** |
| 5 | Ressource qui maintient les réplicas et gère les mises à jour | **Deployment** |
| 6 | Si un test échoue dans le workflow | **Keep the existing version running and stop the deployment.** |

### Q1 : Agents claim tasks from a DB through an HTTP API

- **Dans le code** : il n'y a aucun broker dans les dépendances (`pyproject.toml` :
  FastAPI, SQLAlchemy, psycopg, uvicorn). `storage.claim_one()` sélectionne la plus
  ancienne ligne `tasks` en statut `queued` pour l'agent appelant, la passe en
  `processing` et crée une ligne `attempts` avec un lease de 60 s. Le worker
  (`worker.py`) ne fait que des requêtes HTTP : `POST /api/v1/tasks/claim` en long
  polling, puis `heartbeat` et `complete` ou `fail`.
- **Pourquoi pas les autres réponses** : les agents ne se parlent jamais
  directement, tout passe par le relay et son authentification Bearer. Il n'y a
  pas de message broker : c'est la DB qui sert de file d'attente, et le SPEC
  précise que « no external message broker » est un choix. Le navigateur ne fait
  que lire l'API : le dashboard appelle des `GET` et n'exécute rien.

### Q2 : completed

- **Observé** sur les quatre environnements (local, Docker, Compose, Kubernetes),
  du point de vue de l'émetteur : `queued` après l'envoi, `processing` après le
  claim, puis `completed` après `POST /complete`, avec `output = "HELLO RELAY"` et
  un historique `1:completed`. Le test `test_two_agents_exchange_task_and_result`
  vérifie chaque transition.
- **Pourquoi pas les autres** : `queued` et `processing` sont des états
  antérieurs. `delivered` n'existe pas : le cycle de vie du SPEC est
  `queued → processing → completed | failed`, et l'API rejette tout autre filtre
  `status` en 400.

### Q3 : `-p`

- `-p 8000:8000` (`--publish`) crée la règle NAT hôte → conteneur. **Vérifié** :
  avec `-p`, les tests d'intégration passent sur `http://127.0.0.1:8000`. Avec
  `--expose 8000` seul, `docker port` ne renvoie rien. `--expose` n'est qu'une
  métadonnée, comme `EXPOSE` dans le Dockerfile.
- `-v` monte un volume et `--name` nomme le conteneur. Ni l'un ni l'autre ne
  concerne le réseau.
- Le piège signalé dans l'énoncé est **vérifié** aussi : avec uvicorn sur son
  défaut `127.0.0.1`, `-p 8001:8000` renvoie une connexion en échec (HTTP `000`).
  C'est pour ça que l'image lance `uvicorn --host 0.0.0.0`.

### Q4 : `postgres`

- Compose crée un réseau dédié avec un DNS interne où chaque **nom de service**
  est résolvable. Depuis le conteneur `app`, `postgres` résout vers l'IP du
  conteneur DB (vérifié : `postgres -> 172.18.0.2`). L'URL utilisée est donc
  `postgresql://relay:…@postgres:5432/relay`.
- **Vérifié par l'absurde** : avec `localhost`, l'app échoue sur
  `connection to server at "127.0.0.1", port 5432 failed: Connection refused`.
  Dans un conteneur, `localhost` désigne le conteneur lui-même.
- `host.docker.internal` désigne la machine hôte. Ça ne marcherait que si
  Postgres était publié sur l'hôte, ce qui fait sortir le trafic du réseau Compose
  et n'est pas portable sur Linux. `0.0.0.0` est une adresse d'écoute, pas une
  destination.

### Q5 : Deployment

- Le Deployment gère un ReplicaSet qui maintient `replicas: 2`, et il fait les
  rolling updates quand le template change (nouvelle image). **Vérifié** : si je
  supprime un pod, il est recréé immédiatement (`2/2` en quelques secondes).
  Après deux runs CI, `kubectl get rs` montre un ReplicaSet par version
  (`local`, `f9a2673-…`, `50e4a37-…`) et seul le dernier a des pods.
  `maxUnavailable: 0` garantit qu'on ne descend jamais sous la capacité demandée.
- **Service** : endpoint réseau stable et répartition de charge vers les pods
  ready, sans gestion de réplicas. **ConfigMap** et **Secret** : configuration et
  identifiants, sans gestion de pods.

### Q6 : garder la version existante et arrêter le déploiement

- Dans `ci.yml`, le job `deploy` a `needs: test` : si un test échoue, on ne
  construit pas d'image, on ne charge rien dans kind et on ne touche pas au
  cluster.
- **Vérifié** : j'ai cassé volontairement une assertion du test d'intégration et
  changé le heading en `v3-broken`. Le job `test` échoue, le job `deploy` ne se
  lance pas, le cluster sert toujours `agent-relay:50e4a37-…` avec
  « Agent Relay v2 », et aucune image v3 n'est construite.
- Si l'échec arrive **pendant** le rollout (image qui ne démarre pas, readiness
  KO), `maxUnavailable: 0` garde les anciens pods en service. Vérifié avec une
  image inexistante : le nouveau pod reste en `ImagePullBackOff` pendant que les
  deux pods v2 servent toujours la page. Le workflow fait alors
  `kubectl rollout undo` et termine en échec.
- **Pourquoi pas les autres** : déployer puis signaler l'échec met du code non
  validé en production, ce qui annule l'intérêt du gating. Supprimer le
  déploiement provoque une panne sans aucune raison. Re-tagger l'ancienne image
  avec le nouveau tag casse la traçabilité, puisque le tag ne dit plus quel code
  tourne.

---

## Ce qui a été ajouté ou modifié

| Fichier | Rôle |
|---------|------|
| `database.py`, `storage.py` | Portage PostgreSQL : normalisation de l'URL (`postgresql+psycopg`), transaction standard au lieu de `BEGIN IMMEDIATE`, verrou de ligne sur la **task d'abord** (ordre unique, pas de deadlock), `FOR UPDATE SKIP LOCKED` pour les claims, verrou advisory pour le `CREATE TABLE` concurrent de plusieurs réplicas, retry de connexion au démarrage, idempotency-key protégée par la contrainte unique. SQLite reste disponible en local. |
| `tests/integration/` | Tests boîte noire via HTTP (scénario SPEC n°1, idempotence de la complétion, contrôle d'accès, 401, 204, vrai process `main.py worker`), avec vérification optionnelle des lignes en base et du dialecte (`RELAY_EXPECT_DB=postgresql`). Sans `RELAY_BASE_URL`, ils sont *skipped*. Avec `RELAY_REQUIRE_SERVER=1` (en CI), un serveur absent fait **échouer** les tests au lieu de les ignorer. |
| `Dockerfile`, `.dockerignore` | Multi-stage, `uv sync --locked --no-dev`, utilisateur non-root 10001, `--host 0.0.0.0`, HEALTHCHECK. |
| `compose.yaml` | Services `postgres` (healthcheck `pg_isready`, volume `pgdata`) et `app` (`depends_on: service_healthy`, healthcheck sur `/ready`). |
| `k8s/` | Namespace, Secret (identifiants de démo), StatefulSet Postgres avec PVC de 1 Gi, readiness et liveness, Services, ConfigMap, Deployment à 2 réplicas (startup, readiness sur `/ready`, liveness sur `/health`, rootfs en lecture seule, capabilities supprimées), `kustomization.yaml` avec override du tag d'image. |
| `kind-config.yaml` | Configuration du cluster kind. |
| `.github/workflows/ci.yml` | Job `test` (Postgres en service, tests unitaires du starter et tests d'intégration sur PG) puis job `deploy` (tag unique `<sha>-<timestamp>`, build, `kind load`, `kubectl apply -k`, `rollout status` avec `rollout undo` si échec, smoke test qui compare le heading déployé à celui du code). |
| `scripts/demo_flow.py` | Rejoue le scénario n°1 et affiche un token à coller dans le dashboard. |
| `scripts/export_session.py` | Convertit un transcript Claude Code (JSONL) en Markdown lisible (voir « Garder la trace du travail de Claude Code »). |
| `pyproject.toml` | Config pytest et `exclude-newer` fixé dans le projet (voir les points de vigilance). |
| `dashboard.html` | Heading `Agent Relay v2`. |

---

## Reproduire pas à pas

### Faut-il un venv ? Faut-il Docker Compose ?

- **Pas de venv à créer à la main.** `uv sync --locked` crée `.venv/` dans le
  dossier du projet et y installe les versions exactes de `uv.lock`.
  `uv run <commande>` exécute ensuite la commande dans ce venv, sans `activate`.
  Si tu préfères activer le venv : `source .venv/bin/activate`, puis `uvicorn …`
  et `pytest …` directement.
- **Docker Compose n'est pas nécessaire pour Q1 et Q2** : l'app tourne alors avec
  SQLite, sans aucun service externe. Docker sert à partir de Q3, Compose pour
  Q4, et kind (qui tourne dans Docker) pour Q5 et Q6.
- Le venv reste utile même quand l'app tourne dans Docker ou Kubernetes : c'est
  de ta machine que tu lances les tests d'intégration et `scripts/demo_flow.py`,
  et ils envoient des requêtes HTTP à l'app conteneurisée.

### Étape 0 : installer les outils (une seule fois)

| Outil | Sert à | Installation | Vérifier |
|-------|--------|--------------|----------|
| Docker (Desktop ou Engine) + Compose v2 | Q3 à Q6 | <https://docs.docker.com/get-docker/> | `docker version` et `docker compose version` |
| uv | venv, dépendances, tests | `curl -LsSf https://astral.sh/uv/install.sh \| sh` (ou `brew install uv`) | `uv --version` |
| kind | cluster Kubernetes local (Q5, Q6) | `brew install kind` ou <https://kind.sigs.k8s.io/docs/user/quick-start/#installation> | `kind version` |
| kubectl | piloter le cluster | `brew install kubectl` ou <https://kubernetes.io/docs/tasks/tools/> | `kubectl version --client` |
| act | lancer la CI GitHub en local (Q6) | `brew install act` ou <https://nektosact.com/installation/> | `act --version` |

Python 3.11 n'est pas un prérequis : uv le télécharge si besoin (`.python-version`).

```bash
git clone https://github.com/<ton-user>/agent-relay.git && cd agent-relay
uv sync --locked
```

### Étape 1 (Q1–Q2) : app en local, scénario et test d'intégration

Terminal 1, le serveur (laisse-le tourner) :

```bash
uv run uvicorn main:app --port 8000
```

Terminal 2 :

```bash
uv run python scripts/demo_flow.py      # affiche queued → processing → completed, puis un token
```

Ouvre <http://127.0.0.1:8000/>, colle le token affiché, clique sur **Use token**.
La tâche doit apparaître en `completed`, avec l'input `hello relay`, l'output
`HELLO RELAY` et l'historique `1:completed (demo)`.

```bash
RELAY_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/integration -v   # attendu : 5 passed
uv run pytest -q                                                          # attendu : 4 passed, 5 skipped
```

Les 5 tests *skipped* du second run sont normaux : ce sont les tests
d'intégration, qui ne tournent que si `RELAY_BASE_URL` est défini.

Arrête le serveur (Ctrl+C dans le terminal 1), sinon le port 8000 reste occupé
pour l'étape suivante.

### Étape 2 (Q3) : image Docker

```bash
docker build -t agent-relay:local .
docker run -d --name relay -p 8000:8000 agent-relay:local
docker ps                                                     # STATUS : healthy après ~10 s
RELAY_BASE_URL=http://127.0.0.1:8000 uv run pytest tests/integration -v   # 5 passed
uv run python scripts/demo_flow.py                           # puis dashboard sur http://127.0.0.1:8000/
docker rm -f relay                                            # libère le port 8000
```

### Étape 3 (Q4) : Docker Compose + PostgreSQL

```bash
docker compose up --build -d          # ou sans -d pour voir les logs (il faut alors un 2e terminal)
docker compose ps                     # app et postgres en (healthy)
RELAY_BASE_URL=http://127.0.0.1:8000 RELAY_REQUIRE_SERVER=1 \
RELAY_TEST_DATABASE_URL=postgresql://relay:relay@127.0.0.1:5432/relay RELAY_EXPECT_DB=postgresql \
  uv run pytest tests/integration -v                          # 5 passed, lignes vérifiées dans PG
docker compose exec postgres psql -U relay -d relay -c "select status, count(*) from tasks group by 1"
docker compose down                   # ajouter -v pour effacer aussi le volume de données
```

La vérification en base prouve que les données sont dans PostgreSQL. Si un
Postgres local occupe déjà le port 5432, arrête-le ou change le port publié
dans `compose.yaml`.

### Étape 4 (Q5) : Kubernetes avec kind

```bash
kind create cluster --name agent-relay --config kind-config.yaml
docker build -t agent-relay:local .                           # si ce n'est pas déjà fait
kind load docker-image agent-relay:local --name agent-relay
kubectl apply -k k8s/
kubectl -n agent-relay rollout status statefulset/postgres
kubectl -n agent-relay rollout status deployment/agent-relay
kubectl -n agent-relay get pods,svc,pvc                       # 2 pods app 1/1, postgres-0 1/1, PVC Bound
```

Terminal 2, le port-forward (laisse-le tourner) :

```bash
kubectl -n agent-relay port-forward svc/agent-relay 8080:8000
```

Terminal 1 :

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 uv run pytest tests/integration -v   # 5 passed
uv run python scripts/demo_flow.py --base-url http://127.0.0.1:8080      # dashboard : http://127.0.0.1:8080/
```

Postgres n'a pas besoin de pull : kind récupère `postgres:16` lui-même sur
Docker Hub.

### Étape 5 (Q6) : CI/CD avec act

Le cluster kind de l'étape 4 doit exister, et le repo doit être un repo git avec
au moins un commit. Au premier lancement, act demande quelle image utiliser :
choisis **Medium**, ou passe-la directement :

```bash
act push -P ubuntu-latest=catthehacker/ubuntu:act-latest
```

Résultat attendu : les jobs `Tests …` puis `Build image and deploy to kind` en
**Job succeeded**, avec les lignes `Deployed image: agent-relay:<sha>-<date>` et
`Deployed heading: …`.

Pour reproduire le passage v1 → v2 demandé par l'énoncé : ce repo contient déjà
`Agent Relay v2`. Remets d'abord `Agent Relay` dans le `<h1>` de
`dashboard.html`, commit, lance `act`. Remets ensuite `Agent Relay v2`, commit,
relance `act`. Après chaque rollout, relance le port-forward : il reste attaché
à l'ancien pod. Vérifie enfin :

```bash
kubectl -n agent-relay port-forward svc/agent-relay 8080:8000 &
curl -s http://127.0.0.1:8080/ | grep '<h1>'                  # <h1>Agent Relay v2</h1>
kubectl -n agent-relay get rs                                 # un ReplicaSet par version déployée
```

Pour vérifier le gating (optionnel) : casse une assertion dans
`tests/integration/test_task_flow.py` et relance `act`. Le job de tests échoue,
le job deploy ne démarre pas, et `kubectl -n agent-relay get deploy agent-relay -o wide`
montre toujours l'ancienne image.

### Nettoyage

```bash
kind delete cluster --name agent-relay
docker compose down -v
```

### Dépannage

- **`address already in use` sur 8000** : un uvicorn, le conteneur `relay` ou
  Compose tourne encore. Arrête-le avant l'étape suivante.
- **Les tests d'intégration sont `skipped`** : `RELAY_BASE_URL` n'est pas défini.
- **macOS ou Windows avec act** : si le job deploy n'arrive pas à joindre le
  cluster, voir la note sur `host.docker.internal` ci-dessous. Ce chemin n'a pas
  été testé.

À savoir :

- `act` monte le socket Docker dans le conteneur du job : c'est ce qui permet
  `docker build` et `kind load`. Le job exporte la kubeconfig de kind dans le
  workspace (`.kubeconfig`, ignorée par git).
- Sous Linux, le job atteint l'API kind sur `127.0.0.1`. Sous Docker Desktop
  (macOS ou Windows), le workflow bascule automatiquement sur
  `host.docker.internal` (avec `tls-server-name=localhost`). Je n'ai pas pu
  tester ce chemin, voir « Limites ».
- `DOCKER_BUILD_FLAGS` (optionnel, vide par défaut) sert à passer des options de
  build, par exemple derrière un proxy d'entreprise.
- `kubectl port-forward svc/...` s'attache à **un seul pod**. Après un rollout,
  il faut le relancer.

---

## Garder la trace du travail de Claude Code

Le module 3 insiste sur un point : relire ce que l'agent a produit, pas
seulement le résultat. Voici comment récupérer, relire et archiver ce qu'une
session Claude Code a fait. Ces fonctions évoluent d'une version à l'autre :
vérifie avec `claude --help` et la doc officielle.

### 1. Le transcript enregistré automatiquement

Claude Code enregistre chaque session sur la machine où il tourne, sans rien
configurer. Le fichier est au format JSONL (un objet JSON par ligne) :

```text
~/.claude/projects/<chemin-du-projet-avec-des-tirets>/<id-session>.jsonl
# exemple : ~/.claude/projects/-Users-ellie-code-agent-relay/3f2a….jsonl
```

On y trouve les prompts, les réponses, chaque appel d'outil (commande shell,
fichier lu ou modifié) et son résultat, avec l'heure. `claude --continue`
reprend la dernière session du dossier, et `claude --resume` permet d'en
choisir une.

### 2. Pendant la session

- **`Ctrl+O`** ouvre la vue détaillée du transcript. On y voit les appels
  d'outils en entier et, selon le modèle et les réglages, la réflexion de Claude
  (parfois seulement résumée).
- Demande à Claude **d'expliquer ses choix dans ses réponses**, par exemple :
  « avant de modifier, explique ce que tu vas changer et pourquoi ». C'est la
  forme de raisonnement la plus fiable à relire, parce qu'elle est explicite et
  enregistrée dans le transcript.

### 3. Export manuel : `/export`

Dans une session interactive, `/export` copie la conversation dans le
presse-papiers ou l'écrit dans un fichier.

### 4. Run non interactif avec journal complet

```bash
claude -p "Lis SPEC.md et crée un test d'intégration pour le scénario 1" \
  --output-format stream-json --verbose > logs/run-q2.jsonl
```

Chaque événement (message, appel d'outil, résultat, coût) est écrit au fil de
l'eau. Pratique pour **relancer un exercice de zéro** et garder une trace
comparable d'un run à l'autre.

### 5. Rendre le JSONL lisible : `scripts/export_session.py`

Ce script n'utilise que la bibliothèque standard. Il transforme un transcript
(ou un log `stream-json`) en Markdown : prompts, réponses visibles, commandes
lancées, fichiers modifiés, et résultats tronqués dans des blocs repliables.

```bash
uv run python scripts/export_session.py --list                         # sessions de ce projet
uv run python scripts/export_session.py --latest -o docs/session-hw3.md
uv run python scripts/export_session.py logs/run-q2.jsonl -o docs/run-q2.md
uv run python scripts/export_session.py <fichier>.jsonl --max-result-chars 0   # résultats complets
```

`--latest` et `--list` cherchent dans le dossier `~/.claude/projects/…` qui
correspond au dossier courant (option `--project` pour en viser un autre). Les
entrées que le script ne sait pas rendre sont comptées en tête du fichier plutôt
qu'affichées. Le script est testé par `tests/test_export_session.py`, sur un
transcript synthétique.

### Pour relancer le HW de zéro et archiver

```bash
git clone https://github.com/alexeygrigorev/agent-relay.git hw3-replay && cd hw3-replay
mkdir -p logs
claude -p "$(cat ../prompt-q1.txt)" --output-format stream-json --verbose > logs/q1.jsonl
# … une commande par question, ou une session interactive terminée par /export
uv run --no-project python ../agent-relay/scripts/export_session.py logs/q1.jsonl -o logs/q1.md
```

### Précautions

- **Secrets** : un transcript contient tout ce qui s'est affiché, y compris les
  tokens d'agents (`agt_…`), les mots de passe de démo et les variables
  d'environnement. Relis le Markdown avant de le committer, et ne committe
  jamais le JSONL brut. `logs/` est dans `.gitignore`.
- **Ce que le transcript n'est pas** : il enregistre ce que l'agent a dit et
  fait. Ce n'est pas une preuve que le résultat est correct. Ce sont les tests,
  les commandes rejouées et la relecture qui valident le travail, comme dans la
  section « Vérifications effectuées ».
- Les sessions Claude dans une app cloud (Cowork, claude.ai) ne sont pas dans
  `~/.claude` sur ton ordinateur. Pour elles, les traces à conserver sont
  l'historique de la conversation dans l'app, les commits et ce README.

---

## Vérifications effectuées

Tout a été exécuté, pas seulement écrit :

| Étape | Commande / preuve | Résultat |
|-------|-------------------|----------|
| Tests du starter (SQLite) | `uv run pytest` | 4 passed |
| Tests du starter sur **PostgreSQL** | `RELAY_DATABASE_URL=postgresql://… pytest test_agent_relay.py`, 3 fois | 4 passed à chaque fois |
| Mutation : suppression de `FOR UPDATE SKIP LOCKED` | même commande | **1 failed** : le test de claims concurrents (16 threads) détecte la double attribution. Le verrou est donc réellement testé. |
| Intégration en local | `RELAY_BASE_URL=… pytest tests/integration` | 5 passed |
| Garde-fous du test | mauvais `RELAY_EXPECT_DB` → échec ; serveur absent avec `RELAY_REQUIRE_SERVER=1` → erreur (pas de skip) | conforme |
| Dashboard | Playwright : token de l'émetteur, ligne `completed / hello relay / HELLO RELAY / 1:completed` | conforme sur les 4 environnements |
| Docker | `agent-relay:local`, `-p 8000:8000`, `id` → `uid=10001(relay)` | 5 passed |
| Compose | `docker compose up --build`, les deux services healthy, tests avec contrôle des lignes en base, `\dt` montre `agents / attempts / tasks`, `/data` vide (pas de fichier SQLite) | 5 passed, les données survivent à `docker compose restart` |
| Kubernetes | pods `2/2` + `1/1` Ready, PVC `Bound`, tests via port-forward, lignes vérifiées dans Postgres | 5 passed, données conservées après suppression du pod `postgres-0` |
| CI v1 | `act push` : tests, puis build `agent-relay:f9a2673-…`, `kind load`, rollout, smoke test | les 2 jobs réussis |
| CI v2 | heading `Agent Relay v2`, `act push` | déployé `agent-relay:50e4a37-…`, heading déployé = heading du code, smoke 5 passed |
| CI avec un test cassé | assertion volontairement fausse | job `test` en échec, job `deploy` **non exécuté**, v2 toujours servie |
| Rollout en échec | image inexistante | anciens pods toujours servis (`maxUnavailable: 0`), `rollout undo` OK |

### Limites de l'environnement de vérification (transparence)

J'ai fait la vérification dans un sandbox cloud dont la politique réseau **bloque
tous les registres d'images** (Docker Hub, ghcr.io, registry.k8s.io, quay.io).
Pour pouvoir quand même tout exécuter :

1. **Images de base** : `python:3.11-slim`, `postgres:16` et l'image runner de
   `act` ont été reconstruites en local à partir d'un rootfs Ubuntu 24.04. La
   stand-in de `postgres:16` reproduit l'interface de l'image officielle
   (`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `PGDATA`, `pg_isready`).
   Le Dockerfile, le `compose.yaml`, les manifests et le workflow sont
   **inchangés** et utilisent les images officielles chez toi.
2. **kind** : `kind create cluster` échoue ici parce que `kindest/node` ne
   s'obtient que via Docker Hub (erreur vérifiée). Le nœud a donc été remplacé
   par un conteneur Kubernetes **k3s v1.34.1**, qui porte les mêmes labels que
   kind (`io.x-k8s.kind.cluster`, `io.x-k8s.kind.role`) et expose la même
   interface. Le **vrai CLI kind v0.30.0** a fonctionné tel quel dessus :
   `kind get clusters`, `kind export kubeconfig` et `kind load docker-image`.
   Seule la création du cluster diffère.
3. Le chemin macOS / Docker Desktop du workflow (`host.docker.internal`) n'a pas
   pu être testé. Sous Linux ou WSL2, le chemin testé est celui qui s'applique.

Ce qui reste à faire sur ta machine avant de soumettre : `kind create cluster`,
puis Q5 et Q6 tels que ci-dessus. Le code est le même, seul le nœud kind
officiel remplace le mien.

---

## Choix techniques et points de vigilance

- **Concurrence PostgreSQL** : le starter sérialisait toutes les écritures avec
  `BEGIN IMMEDIATE`, ce qui revient à un verrou global. Sur PG, chaque opération
  verrouille la ligne `tasks` concernée, et les claims utilisent `SKIP LOCKED` :
  des workers concurrents prennent des tâches différentes au lieu de s'attendre.
  La recovery des leases prend le même verrou (task d'abord) et relit l'attempt
  une fois le verrou obtenu. Plusieurs réplicas peuvent donc faire tourner la
  recovery sans conflit.
- **Readiness et liveness** : `/ready` vérifie la DB **et** le schéma, et sert à
  décider si un pod reçoit du trafic. `/health` ne dépend pas de la DB, pour
  qu'une panne Postgres ne redémarre pas tous les pods API en boucle.
- **Lockfile** : le `uv.lock` du starter avait été généré avec un réglage
  `exclude-newer` propre à la machine de l'auteur. Sur un runner vierge,
  `uv sync --locked` échouait (la CI l'a détecté). Le cutoff est maintenant fixé
  dans `pyproject.toml` : les versions sont identiques au starter et reproductibles.
- **Secrets** : `k8s/postgres-secret.yaml` contient des identifiants de démo pour
  un cluster local. Sur un cluster partagé, il faudrait passer à
  SealedSecrets / External Secrets ou à un `kubectl create secret` hors du repo.
- **Tag unique** : `<sha court>-<horodatage UTC>`. Le SHA seul ne suffit pas avec
  `act`, qui build la copie de travail (possiblement non commitée).
- **Hors périmètre du HW3** mais attendu par le module 3 : déploiement public
  (Render, Fly.io…), environnement de staging, fichiers `docs/*.md`.

---

# Agent Relay: documentation du starter

> Ce qui suit est la documentation d'origine du starter. Ce qui a changé pour
> le HW3 est décrit plus haut ; en particulier, PostgreSQL est maintenant le
> backend de déploiement et SQLite reste le mode local sans dépendance.

Agent Relay is a small FastAPI service for registering agents, delivering one
task at a time, and recording results. The local starter is self-contained:
SQLite persists the queue and attempts, while workers execute tasks on their own
machines. The included worker deterministically returns `input.upper()`.

## Run it

```bash
uv sync
uv run uvicorn main:app --reload
```

Open <http://127.0.0.1:8000/> for the token-based local dashboard. The default
database is `./agent-relay.db`; set `RELAY_DATABASE_URL` to use another SQLite
file. `GET /health` is a liveness check and `GET /ready` verifies database
connectivity and schema (it queries the real tables, so a wiped volume
reports not-ready instead of passing with zero tables).

Register two identities and send a task:

```bash
alice=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"alice"}')
bob=$(curl -sS -X POST http://127.0.0.1:8000/api/v1/agents \
  -H 'content-type: application/json' -d '{"name":"uppercase"}')
```

The response contains each agent's secret `token` once. Keep it outside source
control. Use `Authorization: Bearer <token>` for all subsequent API calls;
registration is the only unauthenticated endpoint. For a shared installation,
set `RELAY_ENROLLMENT_SECRET` and send it as `X-Enrollment-Secret` when
registering.

## Run the deterministic worker

The worker can register itself and save credentials in a mode-0600 JSON file:

```bash
uv run python main.py worker \
  --base-url http://127.0.0.1:8000 \
  --name uppercase \
  --credentials ./uppercase-credentials.json \
  --worker-id laptop-1
```

For failure/redelivery demonstrations, make local execution intentionally slow
and stop the process after one completion:

```bash
uv run python main.py worker --credentials ./uppercase-credentials.json \
  --slow-seconds 75 --worker-id slow-laptop
```

The worker heartbeats during long work. Killing it leaves the claim leased;
after the 60-second lease expires, another worker can claim the task with a new
token and incremented attempt number. `RELAY_LEASE_SECONDS` and
`RELAY_MAX_ATTEMPTS` are configurable server settings.

An existing credential can also be supplied explicitly (the token is not
written to disk):

```bash
uv run python main.py worker --agent-id agent_123 --token agt_… --worker-id laptop-2
```

## Storage and delivery behavior

`database.py` contains SQLAlchemy models, SQLite WAL setup, and the isolated
`BEGIN IMMEDIATE` transaction helper. `storage.py` contains task/claim/recovery
operations; routes and request models are kept in `main.py` and `schemas.py`.
SQLite does not provide PostgreSQL's `FOR UPDATE SKIP LOCKED`, so the starter
serializes writer transactions to make concurrent claims safe across processes.
Students can port this storage seam to PostgreSQL later without changing the
HTTP protocol or lifecycle in `SPEC.md`.

Claims are at-least-once and leased for 60 seconds by default. Heartbeats extend
an active lease. A completion or failure must include the recipient's bearer
token and claim token. Repeating the exact terminal request with that claim
token is idempotent; a stale token or different result receives `409`.

## Verify

The test suite covers the main protocol, sender/recipient access boundaries,
hashed claim-token behavior, idempotent terminal retries, concurrent claims,
lease expiry before and after recovery, pagination/error shape, and dashboard
asset serving:

```bash
uv run pytest -q
```

Tests default to a scratch database at `/tmp/agent-relay-test.db` so they
don't reset your dev server's `./agent-relay.db`. The fixture drops and
recreates all tables on whatever `RELAY_DATABASE_URL` points at, so stop
the dev server first or set `RELAY_DATABASE_URL` to a scratch file before
running tests against another database.

The original starter did not include Docker, Kubernetes, CI or PostgreSQL;
this fork adds them (see the Homework 3 section at the top of this file).
