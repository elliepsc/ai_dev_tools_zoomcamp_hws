# Audit run 2026-09-30 : validation humaine

Entrées de ce run :

- `semgrep.json` : premier passage, 17 résultats.
- `semgrep-final.json` : après les correctifs, 16 résultats.
- `model-review.json` : Claude Code headless en read-only, `audit-brief.md`, sortie validée par `findings.schema.json`. 51 tours, 0,84 USD.
- `snyk-agent-scan-inspect.txt` : surface MCP/skills du responder.

**Triage** : fait par Claude pendant la session d'implémentation, en relisant le code cité ligne par ligne.
**Contre-signature** : ☐ Ellie Pascaud, à valider avant de partager le rapport. Une disposition « accepted » est une décision de risque qui revient à la propriétaire du système, pas au modèle.

## Revue par le modèle (12 findings)

| ID | Sév. | Finding | Vérifié ? | Disposition | Preuve et changement |
|---|---|---|---|---|---|
| M-01 | high | Confiance accordée au loopback sur `POST /alerts` : une page web ouverte dans le navigateur peut POSTer en `text/plain` sans preflight CORS et déclencher un run d'agent | **Oui**, exploitable : le serveur parsait le JSON quel que soit le Content-Type | **Corrigé** | `server.py` : 403 si un header `Origin` est présent, 415 si le Content-Type n'est pas `application/json`. Test `test_browser_csrf_and_read_endpoints_are_guarded`. Le token reste facultatif en loopback pour que la commande curl du homework marche telle quelle (choix assumé). |
| M-02 | high | Du code de test écrit par l'agent est exécuté sur l'hôte, avant le gate, avec un environnement quasi complet | **Oui** | **Atténué** | Le gate de chemins, de taille et de confiance passe désormais **avant** toute exécution. Les tests tournent avec un environnement minimal (`TEST_ENV` : PATH, HOME, proxy, uv, sans aucune clé API ni token). **Résiduel accepté** : un `conftest.py` sous `tests/` reste de l'exécution de code sur l'hôte. La vraie correction serait un conteneur sans réseau (suite n°5 du rapport). |
| M-03 | medium | Déploiement autonome de code écrit par le modèle au niveau 2 par défaut | Oui | **Accepté (homework)** | La Q6 exige ce comportement. Recommandation actée dans le rapport : `default_level: 1` hors exercice. |
| M-04 | medium | Endpoints de lecture non authentifiés sur 0.0.0.0 | **Oui** : `/incidents` exposait les rapports sur le LAN | **Corrigé** | `_require_auth` sur tous les endpoints. Test associé. |
| M-05 | medium | Deny-list de fichiers secrets incomplète, sortie du modèle stockée sans redaction | Oui | **Corrigé (partiel)** | Les transcripts, `run.json` et `response.json` sont redacted avant écriture. Ajout de `Read(./.env)`, `Read(**/.env)`, `~/.ssh`, `~/.aws` et `~/.docker` aux refus. Résiduel : une deny-list n'est pas une isolation. |
| M-06 | medium | Fingerprint choisi par l'émetteur, file et store non bornés | **Oui** | **Corrigé** | Fingerprint calculé côté serveur à partir des labels. File bornée à 50 (429 au-delà). Budget de 6 exécutions d'agent par heure, **observé en conditions réelles** : `INC-20260930-125751-bfcc`. |
| M-07 | medium | L'allowlist autorise `git diff --output=<fichier>` (écriture arbitraire) et `uv run pytest` non figé (réseau) | **Oui, le plus intéressant du lot** : un vrai contournement que je n'avais pas vu | **Corrigé** | git retiré des outils de l'agent (le responder calcule le diff lui-même). Seul `uv run --frozen pytest` reste autorisé. |
| M-08 | low | Du texte de télémétrie non fiable arrive dans le prompt | Oui | **Accepté** | Encadré comme données (`<evidence>`, règle n°1 du prompt), tronqué et redacted. L'agent n'a aucun outil réseau pour exfiltrer. Le gate ne lit pas la prose du modèle. |
| M-09 | low | Grafana en `admin/admin`, token de repli pour le responder | Oui | **Accepté** | Ports liés à 127.0.0.1 uniquement. Le token de repli ne marche pas : le responder sans `RESPONDER_TOKEN` n'accepte que le loopback, donc on échoue fermé. `.env.example` et le README génèrent un token aléatoire. |
| M-10 | low | Les dossiers d'incident ne sont pas ignorés par git | Oui | **Accepté (intentionnel)** | Le module demande de « remember ». Les dossiers sont redacted, et un scan du token réel sur `incidents/` n'a rien trouvé. Effet de bord découvert et corrigé : `deploy-fix.sh` refusait de déployer quand un dossier d'incident suivi était modifié (`INC-20260930-125626-5af5`). |
| M-11 | info | Images non épinglées par digest | Oui | **Accepté** | Versions épinglées par tag. Recommandation : digest. |
| M-12 | info | L'API ne fait ni authentification ni rate limiting, et des chaînes fournies par l'utilisateur arrivent dans la télémétrie | Oui | **Accepté (hors périmètre)** | App du starter. `order.id` n'est pas une PII. |

## Semgrep (16 résultats finaux)

| Règle | Occurrences | Disposition |
|---|---|---|
| `dockerfile-source-not-pinned` | 1 | Accepté : identique à M-11 |
| `dangerous-subprocess-use-audit` | 3 | **Faux positif** : `subprocess.run` reçoit toujours une liste d'arguments (jamais `shell=True`, ce que vérifie la règle projet `subprocess-shell-true`, 0 résultat). Les arguments viennent de templates fixes, d'IDs générés côté serveur et d'une route passée par la regex d'allowlist. |
| `return-not-in-function` | 6 | Faux positif : ce sont des lambdas dans `field(default_factory=...)`, mal parsées |
| `is-function-without-parentheses` | 3 | Faux positif : `is_valid` et `is_loopback` sont des propriétés |
| `string-concat-in-list` | 3 | Intentionnel : f-strings multilignes dans le rendu du rapport |
| `unquoted-variable-expansion-in-command` | 1 (1er run) | **Corrigé** : `$ok` était exécuté comme une commande à la fin de `verify-recovery.sh`, remplacé par `[[ "$ok" == true ]]` |
| Règles projet (`agent-cli-dangerous-flag`, `yaml-unsafe-load`, `subprocess-shell-true`, `responder-token-compared-with-eq`, `otel-attribute-may-carry-pii`) | 0 | Les garanties voulues tiennent |

## Supply chain de l'agent

- `snyk-agent-scan inspect incident-response/agent-mcp.json` : *no mcp servers or skills found*. Conforme au design (`--strict-mcp-config`).
- `snyk-agent-scan scan` (vérification complète) demande `SNYK_TOKEN` : **à lancer par Ellie** avec `SNYK_TOKEN=... uvx snyk-agent-scan@0.6.8 scan incident-response/agent-mcp.json`.

## Trouvé pendant la revue, hors outils

- **S-01 (élevée) : surface déclarée différente de la surface effective.** Snyk Agent Scan sur la config déclarée ne trouve rien, mais l'événement `init` du CLI montre 61 skills, 7 plugins et le MCP `claude-in-chrome` chargés dans la session de l'agent (hérités de l'hôte, malgré `--strict-mcp-config`). **Corrigé** : flags `--disable-slash-commands --setting-sources project`, deny `mcp__claude-in-chrome`, et gate `agent_extension_surface_as_declared` sur la surface effective. Prouvé par `INC-20260930-130646-e094` (deploy bloqué). Leçon : scanner la configuration ne suffit pas, il faut aussi contrôler ce qui tourne réellement.
- **M-07, preuve complémentaire** : sans deny, Claude Code auto-approuve `git status` et `git diff`, mais refuse `git diff --output=…`. L'allow explicite `Bash(git diff:*)`, lui, aurait autorisé ce second cas par préfixe. Deny `Bash(git:*)` ajouté, et la commande est refusée (testé).

- La redaction des e-mails masquait `@pytest.mark.parametrize` dans les transcripts JSON (`\n@...`). Regex corrigée, test ajouté.
