# ComplianceIQ — Guide Technique de Référence

> Document de compréhension approfondie, support de soutenance et documentation
> d'architecture. Rédigé strictement sur la base de l'état réel et vérifié du
> projet (voir `PROJECT_CONTEXT_README.md`) — aucune fonctionnalité non construite
> n'est présentée comme construite. Ce qui relève de la roadmap est explicitement
> marqué **[ROADMAP — non implémenté]**.

---

# Chapitre 1 — Introduction

## 1.1 Définition du projet

ComplianceIQ est une plateforme de scan de conformité cloud (AWS aujourd'hui,
Azure/GCP en roadmap) qui :

1. **détecte** les mauvaises configurations sur des ressources cloud réelles,
2. **cite** une référence normative (ISO 27001, DNSSI) pour chaque règle,
3. **traduit** chaque finding en risque financier estimé (MAD).

C'est un PFE à 2 étudiants sur 6 semaines — cette contrainte de temps et
d'effectif **structure toutes les décisions d'architecture** présentées dans
ce document. Un choix jugé "trop simple" par un standard industriel (ex. pas
de vrai moteur de règles déclaratif en production) est souvent le bon choix
dans ce contexte, et ce guide explique pourquoi à chaque fois que c'est le cas.

## 1.2 Le problème que ça résout

### Pourquoi l'audit cloud est difficile

```
┌─────────────────────────────────────────────────────────────┐
│  Un compte AWS "moyen" en entreprise :                       │
│                                                               │
│   • Des centaines à milliers de ressources                  │
│   • Qui changent tous les jours (drift)                     │
│   • Réparties sur plusieurs comptes / régions                │
│   • Documentées dans des standards de 100+ pages             │
│     (ISO 27001 Annexe A : 93 contrôles)                      │
└─────────────────────────────────────────────────────────────┘
```

Un auditeur humain qui lit une configuration ligne par ligne pour la comparer
à un standard :
- ne peut pas suivre le rythme du changement (drift),
- produit un résultat qui n'est déjà plus à jour à la fin de l'audit,
- ne relie pas facilement "ce bucket est public" à "Annexe A.8.3, risque
  estimé à X MAD" — ce sont trois métiers différents (technique, normatif,
  financier) rarement réunis dans une même tête.

### Ce que ComplianceIQ automatise

```
Ressource cloud mal configurée
        │
        ▼
   Détection automatique (scan)
        │
        ▼
   Citation normative vérifiée (ISO 27001 / DNSSI)
        │
        ▼
   Traduction en risque financier (MAD)
        │
        ▼
   Proposition de remédiation (jamais auto-appliquée)
```

Chaque flèche de ce schéma correspond à un module réel du projet, détaillé
dans les chapitres suivants.

## 1.3 Pourquoi ces choix techniques (et pas d'autres)

Il existe des outils industriels qui font (en partie) la même chose : **Wiz**,
**Prisma Cloud**, **Orca Security** (plateformes commerciales, agentless,
CNAPP complet) et **Prowler** / **ScoutSuite** (outils open-source de scan de
conformité, plus proches en esprit de ce que fait ce projet).

Différence structurante à retenir pour la soutenance :

| | Outils industriels (Wiz, Prisma, Orca) | Prowler / ScoutSuite | ComplianceIQ (ce projet) |
|---|---|---|---|
| Portée | Multi-cloud complet, temps réel | Multi-cloud, scan ponctuel | AWS-first, scan ponctuel |
| Citation normative | Oui, mais propriétaire/fermée | Basique (nom de contrôle) | Vérifiée, tracée à la source |
| Traduction financière | Rare, souvent absente | Absente | **Différenciant du projet** |
| Remédiation | Semi-automatique | Manuelle | Proposée, jamais auto-appliquée |
| Moteur de règles | Propriétaire, opaque | Règles Python codées en dur | Catalogue YAML déclaratif (voir Ch. 5 — **pas encore branché en production**, c'est un point à assumer clairement en soutenance) |

Le positionnement défendable de ce projet n'est **pas** "on a fait un Wiz en
6 semaines" (ce serait intenable et un jury verrait tout de suite le bluff),
mais : **"on a démontré, sur un périmètre volontairement restreint et
réellement fonctionnel, la chaîne complète détection → citation vérifiée →
impact financier — ce que même les outils matures font rarement bien."**

## 1.4 Cycle de vie d'un scan (tel qu'il existe réellement aujourd'hui)

```
┌──────────────┐     ┌───────────────┐     ┌──────────────────┐
│ boto3 Session │────▶│ Collecteur    │────▶│ FindingDict       │
│ (rôle dédié,  │     │ AWS           │     │ (cloud_provider,  │
│  lecture seule│     │ (aws.py :     │     │  resource_id,     │
│  uniquement)  │     │  IAM/S3/SG/   │     │  rule_id,         │
│               │     │  CloudTrail/  │     │  severity,        │
│               │     │  RDS)         │     │  domain,          │
│               │     │               │     │  description,    │
│               │     │               │     │  detected_at)     │
└──────────────┘     └───────────────┘     └──────────────────┘
                                                     │
                                                     ▼
                                          ┌────────────────────┐
                                          │ Sortie JSON         │
                                          │ (CLI, stdout ou     │
                                          │  --output fichier)  │
                                          └────────────────────┘
```

**Point important à assumer en soutenance** : dans l'état actuel, la
"détection de règle" (ex. `s3.encryption_disabled`) est **codée directement
en Python dans le collecteur**, pas évaluée par un moteur de règles
déclaratif séparé. Le Chapitre 5 explique pourquoi c'est un choix
défendable à ce stade, et ce qu'il faudrait faire pour passer à l'étape
suivante (hors périmètre des 6 semaines).

---

## Résumé du chapitre

- ComplianceIQ résout un problème réel : l'audit cloud manuel est trop lent
  et ne relie pas technique/normatif/financier.
- Le projet est volontairement restreint (AWS, 6 semaines, 2 personnes) —
  c'est une force à assumer, pas une faiblesse à cacher.
- Le différenciant réel face à des outils comme Prowler/ScoutSuite est la
  citation vérifiée + la traduction financière, pas la couverture multi-cloud.
- Le cycle de vie actuel du scan est : session boto3 → collecteur Python →
  `FindingDict` → sortie JSON. Le rule engine déclaratif (YAML) existe comme
  catalogue mais n'est pas branché sur ce flux (voir Ch. 5).

## Points clés à retenir

- **Contrainte → décision** : chaque choix technique découle de la contrainte
  réelle (temps, effectif), pas d'une méconnaissance des bonnes pratiques.
- **Différenciation honnête** : ne pas comparer le projet à Wiz sur la
  couverture, mais sur la chaîne citation→financier.

## Bonnes pratiques illustrées ici

- Séparer clairement, dans toute documentation de projet étudiant, ce qui
  est **construit** de ce qui est **prévu** — un jury vérifie systématiquement.

## Erreurs fréquentes à éviter

- Présenter un outil à 2 personnes/6 semaines comme "concurrent de Wiz" sans
  nuance — un jury cybersécurité connaît ces outils et posera la question.
- Confondre "on a écrit des règles YAML" avec "on a un moteur de règles qui
  tourne" — ce sont deux affirmations différentes (voir Ch. 5).

## Questions possibles du jury

1. *"En quoi votre projet diffère-t-il d'un simple script Prowler ?"*
   → Réponse : la citation normative vérifiée + la traduction financière
   MAD, absentes ou faibles dans Prowler/ScoutSuite.
2. *"Pourquoi ne pas avoir couvert Azure/GCP dès le départ ?"*
   → Réponse : périmètre réaliste à 2 personnes/6 semaines ; profondeur sur
   un cloud plutôt que largeur superficielle sur trois.
3. *"Votre moteur de règles est-il utilisé en production dans le scan ?"*
   → Réponse honnête : non, pas encore — le catalogue YAML existe comme
   travail de conception, la détection réelle est aujourd'hui codée dans les
   collecteurs. C'est assumé comme limite connue (voir Ch. 5).

## Références

- ISO/IEC 27001:2022 — Annexe A (contrôles de sécurité de l'information)
- OWASP Cloud Security — https://owasp.org/www-project-cloud-security/
- Prowler (open source) — https://github.com/prowler-cloud/prowler
- ScoutSuite (open source) — https://github.com/nccgroup/ScoutSuite

---

# Chapitre 2 — Architecture réelle (construite vs planifiée)

## 2.1 Pourquoi ce chapitre commence par une mise en garde

La plupart des guides d'architecture décrivent un système comme s'il était
entièrement fini. Ici, on fait l'inverse volontairement : on distingue à
chaque étape ce qui **tourne réellement aujourd'hui** de ce qui est
**prévu mais pas encore construit**. C'est ce qui rend ce document
défendable devant un jury qui peut demander "montre-moi le code".

## 2.2 Vue d'ensemble — état réel

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CE QUI EST CONSTRUIT                         │
│                                                                       │
│   Terraform (AWS)          scanner/collectors/aws.py                │
│   ┌─────────────────┐      ┌──────────────────────────┐             │
│   │ IAM              │      │ collect_iam()            │             │
│   │ S3               │─────▶│ collect_s3()             │             │
│   │ EC2 / SG         │      │ collect_security_groups()│             │
│   │ CloudTrail       │      │ collect_cloudtrail()     │             │
│   │ VPC              │      │ collect_rds()            │             │
│   │ RDS              │      └──────────────────────────┘             │
│   └─────────────────┘                   │                            │
│                                          ▼                            │
│                              list[FindingDict] (JSON)                │
│                                          │                            │
│                                          ▼                            │
│                          scanner/schema.py (Pydantic)                │
│                          Finding, ExploitProof, etc.                 │
│                                          │                            │
│                    ┌─────────────────────┴──────────────────┐        │
│                    ▼                                         ▼        │
│         proof_engine.py                          rules/*.yaml       │
│         (Red-Team Proof Engine)                  (catalogue, 111    │
│         3 scénarios non destructifs               règles, PAS       │
│                                                     branché — Ch. 5) │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    [ROADMAP — non implémenté]                        │
│                                                                       │
│   scanner/scoring.py (pseudo-code écrit, pas implémenté)             │
│   Core Backend (FastAPI, JWT, audit log)                             │
│   Findings/Scores API (endpoints déjà spécifiés dans openapi.yaml,   │
│                         implémentation réelle absente)                │
│   Dashboard (React + Recharts)                                       │
│   Déploiement (Docker, docker-compose, CI)                           │
│   Financial Translator / Remediation Generator — code non vu         │
│   RAG pipeline / corpus DNSSI (côté teammate)                        │
└─────────────────────────────────────────────────────────────────────┘
```

## 2.3 Architecture logicielle : pourquoi un style "pipeline en couches" et pas autre chose

Le projet suit un enchaînement linéaire strict :

```
Infrastructure (Terraform)
        │  décrit l'état voulu du cloud
        ▼
Collecteur (aws.py)
        │  lit l'état réel du cloud via boto3
        ▼
Finding (schema.py)
        │  contrat de données validé (Pydantic)
        ▼
Consommateurs (Red-Team Proof Engine, futur Financial Translator,
               futur Remediation Generator, futur Backend/API)
```

**Pourquoi ce style et pas une architecture hexagonale ou microservices
complète (comme le propose parfois une autre session IA que tu as consultée) ?**

| Critère | Pipeline en couches (choisi) | Microservices / hexagonal complet |
|---|---|---|
| Effort d'implémentation | Faible — un seul processus Python | Élevé — plusieurs services, réseau, orchestration |
| Pertinent à l'échelle du projet | Oui — un seul cloud, un seul scan à la fois | Non — sur-ingénierie pour 65 ressources testées |
| Testable seul | Oui, un module à la fois | Nécessite Docker Compose pour tout démarrer |
| Défendable en soutenance | Oui — "j'ai choisi la complexité minimale suffisante" | Risqué si non terminé — un jury voit vite un `docker-compose.yml` qui ne démarre pas |

C'est une application directe du principe **YAGNI** (*You Aren't Gonna Need
It*) et de **KISS** (*Keep It Simple, Stupid*) — développés au Chapitre 12.

## 2.4 Le seul vrai contrat partagé du projet : `schema.py`

Le README l'indique explicitement : *"Toute modification ici nécessite une
conversation entre Student A et Student B, jamais un edit solo."* C'est la
définition même d'un **Anti-Corruption Layer** léger — le point unique où
les deux moitiés du projet (scan AWS d'un côté, RAG/citations de l'autre)
se rencontrent, sans que l'une ait besoin de connaître les détails internes
de l'autre.

```
   Toi (AWS, IAM, Network)              Teammate (GCP/Azure, Encryption,
        │                                Logging, Storage, RAG)
        │                                         │
        └──────────────┬──────────────────────────┘
                        ▼
                  schema.py (Finding)
                  = le SEUL contrat commun
```

C'est ce qui permet aux deux étudiants de travailler en parallèle sans se
bloquer mutuellement — chacun produit ou consomme des `Finding`, sans avoir
à connaître comment l'autre les génère.

## 2.5 Ce que ce document NE couvrira PAS en détail (et pourquoi)

Contrairement à un guide "produit fini", on ne détaillera **pas** :
- de schéma PostgreSQL avec clés étrangères et index (rien n'est conçu),
- de `docker-compose.yml` (rien n'est écrit),
- d'architecture multi-tenant (explicitement rejetée par ton README comme
  proposition incompatible d'une autre session IA).

Ces sujets seront mentionnés brièvement au Chapitre 10 (Core Backend) comme
**vision roadmap**, sans faux détail d'implémentation.

---

## Résumé du chapitre

- Le projet suit un pipeline linéaire simple : Terraform → Collecteur →
  Finding → Consommateurs — pas une architecture microservices.
- `schema.py` est le seul contrat partagé entre les deux étudiants, et sert
  d'Anti-Corruption Layer léger.
- Le choix d'une architecture simple est justifié par YAGNI/KISS, pas par
  méconnaissance des alternatives.

## Points clés

- Toujours pouvoir dessiner, en soutenance, la frontière entre "construit"
  et "roadmap" — c'est ce schéma (2.2) qui sert de base à cette réponse.

## Bonnes pratiques illustrées ici

- Un contrat de données unique et versionné (`schema.py` v1.2.0) plutôt que
  chaque module qui invente sa propre structure.

## Erreurs fréquentes à éviter

- Vouloir "montrer" une architecture microservices en soutenance alors
  qu'un seul script Python tourne réellement — la cohérence entre le
  discours et la démo est ce qui est jugé.

## Questions possibles du jury

1. *"Pourquoi ne pas avoir choisi une architecture microservices dès le
   départ, vu que c'est la norme dans l'industrie ?"*
   → Réponse : la norme industrielle s'applique à des équipes et des
   échéances différentes ; à 2 personnes/6 semaines, la complexité
   additionnelle (réseau, orchestration, déploiement) aurait consommé le
   temps disponible pour la détection elle-même, qui est le cœur du sujet.
2. *"Quel est le seul point de couplage entre vous et votre binôme ?"*
   → Réponse : `schema.py`, versionné et modifié uniquement en concertation.
3. *"Que se passe-t-il si un des deux modifie `schema.py` seul ?"*
   → Réponse : risque de rupture de contrat côté API/RAG — c'est justement
   pour ça que le README impose une règle de gouvernance dessus.

## Références

- Martin Fowler — *Microservices* (2014) : https://martinfowler.com/articles/microservices.html
- Eric Evans — *Domain-Driven Design*, concept d'Anti-Corruption Layer
- Principes YAGNI/KISS — Extreme Programming (Kent Beck)

---

# Chapitre 3 — Les Collectors (le connecteur AWS)

## 3.1 Définition

Un **collector** est le module qui interroge une API cloud (ici AWS via
`boto3`) et transforme sa réponse brute en un format normalisé exploitable
par le reste du pipeline (`FindingDict`). Dans ce projet, le collector vit
dans un seul fichier : `scanner/collectors/aws.py`, avec une fonction par
domaine de ressource : `collect_iam`, `collect_s3`,
`collect_security_groups`, `collect_cloudtrail`, `collect_rds`.

## 3.2 Objectif

Répondre à une question simple mais critique : **"qu'est-ce qui est
réellement déployé et configuré sur ce compte AWS, là, maintenant ?"** —
par opposition à ce que le Terraform *devrait* avoir créé. Le collector ne
fait jamais confiance au code d'infrastructure : il interroge l'API AWS
directement, ce qui permet de détecter un drift (quelqu'un modifie une
ressource à la main dans la console, hors Terraform).

## 3.3 Fonctionnement interne

### 3.3.1 Authentification — jamais de credentials en dur

```python
session = boto3.Session(profile_name=..., region_name=...)
```

Le collector reçoit une **session boto3 déjà authentifiée**, construite en
amont (profil AWS CLI, rôle assumé, ou variables d'environnement). Il ne
gère jamais lui-même la création de clés d'accès. C'est une application du
principe de **moindre privilège** : le rôle utilisé doit être en lecture
seule (`Describe*`, `List*`, `Get*`), jamais en écriture.

### 3.3.2 Pagination

Les API AWS renvoient des résultats par pages (ex. max 100 utilisateurs IAM
par appel). Le code utilise systématiquement les **paginators** boto3 :

```python
paginator = iam.get_paginator("list_users")
users = [user for page in paginator.paginate() for user in page.get("Users", [])]
```

Sans ça, un compte avec 500 utilisateurs IAM ne remonterait que les 100
premiers — un faux négatif silencieux, pire qu'une erreur visible.

### 3.3.3 Retry avec backoff exponentiel

```python
def with_retry(func, *, config, action_description):
    attempt = 0
    while True:
        try:
            return func()
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            attempt += 1
            if error_code in config.throttling_error_codes and attempt <= config.max_retries:
                delay = config.backoff_base_seconds * (2 ** (attempt - 1))
                time.sleep(delay)
                continue
            raise
```

**Pourquoi le backoff est exponentiel et pas fixe** : AWS applique du
rate-limiting par compte/région. Si 10 scans échouent en même temps et
réessaient toutes après exactement 1 seconde, ils se re-percutent tous en
même temps (effet "thundering herd"). Le délai qui double à chaque tentative
(1s, 2s, 4s, 8s...) étale les réessais dans le temps.

**Pourquoi seulement certains codes d'erreur déclenchent un retry** :
`Throttling`, `RequestLimitExceeded`, etc. sont **transitoires** — retenter
a du sens. Une erreur `AccessDenied` ne l'est pas — retenter 5 fois une
permission qui n'existe pas ne fait que gaspiller du temps. C'est pour ça
que `with_retry` relance immédiatement (`raise`) toute erreur qui n'est pas
dans `throttling_error_codes`.

### 3.3.4 Le principe non négociable : ne jamais confondre erreur et non-conformité

```python
except ClientError as e:
    error_code = e.response.get("Error", {}).get("Code", "")
    if error_code == "NoSuchPublicAccessBlockConfiguration":
        # cas réel : la ressource n'a effectivement pas cette config
        return [normalize_finding(..., rule_id="s3.no_public_access_block", ...)]
    # toute autre erreur (ex. AccessDenied) → scan incomplet, PAS un finding
    logger.warning("scan incomplet, aucun finding généré")
    return []
```

C'est la décision d'architecture la plus importante de tout le connecteur.
Si le rôle scanner n'a pas la permission de lire une configuration, ne
**jamais** en déduire "donc ce n'est pas configuré, donc c'est une
non-conformité". Ce serait un **faux positif critique** capable de faire
perdre toute confiance dans l'outil dès le premier audit réel. La bonne
réponse est : "je ne sais pas, et je le dis" (même logique de prudence que
le principe d'abstention du RAG côté teammate — *"je ne sais pas"* plutôt
qu'une réponse inventée).

## 3.4 Architecture — design patterns en jeu

```
┌─────────────────────────────────────────────────────────────┐
│                     COLLECTORS (tuple)                       │
│                                                                │
│   ("iam", collect_iam)                                       │
│   ("s3", collect_s3)              ← chaque entrée a la même  │
│   ("security_groups", ...)          signature (session,      │
│   ("cloudtrail", ...)                config) -> list[Finding]│
│   ("rds", collect_rds)                                       │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
              run_all() itère dessus,
              sans connaître le détail
              de chaque collecteur
```

- **Pattern Strategy** : `run_all()` traite chaque collecteur comme une
  stratégie interchangeable ayant la même signature. Ajouter un domaine
  (ex. `collect_rds`) ne demande aucune modification de `run_all()` —
  seulement une nouvelle entrée dans le tuple `COLLECTORS`. C'est le
  principe **Open/Closed** de SOLID (ouvert à l'extension, fermé à la
  modification) — détaillé au Chapitre 12.
- **Pattern Adapter** (embryonnaire ici) : chaque fonction `collect_*`
  adapte la forme spécifique de l'API AWS (`DBInstances`, `SecurityGroups`,
  `Users`...) vers la forme commune `FindingDict`. Un vrai pattern Adapter
  au sens strict impliquerait une interface explicite (ex. une classe
  abstraite `CloudCollector`) — ici c'est une **convention de signature**,
  suffisante à cette échelle mais qui deviendrait nécessaire si Azure/GCP
  rejoignaient vraiment le pipeline (roadmap, côté teammate).
- **Pas de pattern Factory** : les collecteurs sont des fonctions, pas des
  classes instanciées dynamiquement — inutile ici, un seul cloud (AWS) est
  réellement câblé.

## 3.5 Workflow complet d'un scan

```
1. main() parse les arguments CLI (--profile, --region, --output)
2. Session boto3 construite avec le profil demandé
3. get_caller_identity() confirme l'identité utilisée
   → si échec : AWSCollectorError, le scan s'arrête (rien de fiable à faire)
4. run_all() itère sur COLLECTORS :
     pour chaque collecteur :
       - appelle la fonction avec (session, config)
       - logue le nombre de findings produits
       - agrège dans une liste unique
5. Findings sérialisés en JSON (stdout ou fichier --output)
6. Résumé par sévérité et par domaine loggé en fin d'exécution
```

## 3.6 Bonnes pratiques illustrées

- **Logging structuré** avec niveau configurable (`--log-level`), jamais de
  `print()` mêlé à la sortie JSON (`print()` réservé exclusivement au
  résultat final ; tout le reste passe par `logger`).
- **Séparation config/code** (`CollectorConfig`, `.env`) : ports sensibles,
  patterns de buckets ignorés, nombre de tentatives — tout est
  paramétrable sans toucher au code.
- **CLI avec `argparse`** plutôt qu'un script à variables codées en dur —
  rend le collecteur utilisable en pipeline CI ou en cron sans modification.

## 3.7 Pièges fréquents (et comment ce code les évite)

| Piège | Conséquence si non traité | Comment `aws.py` l'évite |
|---|---|---|
| Ignorer la pagination | Faux négatifs silencieux sur les gros comptes | Paginators boto3 systématiques |
| Traiter `AccessDenied` comme non-conforme | Faux positifs critiques, perte de confiance | `except ClientError` distingue explicitement les codes d'erreur |
| Retry sans backoff | Aggrave le throttling AWS (thundering herd) | Backoff exponentiel |
| Credentials en dur dans le code | Fuite de secrets (déjà arrivé sur ce projet — voir README) | Session injectée depuis l'extérieur, jamais construite avec des clés en dur |
| Un seul essai sur throttling transitoire | Scan incomplet sur un compte actif | `max_retries` configurable, 5 par défaut |

## 3.8 Conseils professionnels

- En production, le rôle IAM du scanner devrait avoir une **politique
  explicite listant chaque action nécessaire** (`iam:ListUsers`,
  `rds:DescribeDBInstances`...) plutôt qu'une politique managée générique
  type `ReadOnlyAccess` — principe de moindre privilège strict.
- Le paramètre `AWS_COLLECTOR_MAX_RETRIES` mérite d'être plus bas en CI
  (échec rapide) et plus haut en scan de production planifié (résilience).

---

## Résumé du chapitre

- Le collector transforme l'état réel du cloud (via boto3) en `FindingDict`
  normalisé, sans jamais faire confiance à ce que Terraform *devrait* avoir
  créé.
- Trois mécanismes défensifs structurent tout le code : pagination
  systématique, retry à backoff exponentiel limité au throttling, et la
  règle absolue "erreur de permission ≠ non-conformité".
- Ajouter un nouveau domaine de ressource (comme `collect_rds` aujourd'hui)
  ne nécessite aucune modification du code d'orchestration — Strategy +
  Open/Closed.

## Points clés

- La distinction erreur/non-conformité est LE point à défendre en priorité
  en soutenance — c'est ce qui rend l'outil digne de confiance.

## Erreurs fréquentes à éviter en soutenance

- Décrire le connecteur comme "un simple wrapper boto3" — c'est réducteur,
  la gestion d'erreur et le retry sont le vrai travail d'ingénierie ici.

## Questions possibles du jury

1. *"Que se passe-t-il si le scanner n'a pas la permission de lire une
   configuration S3 ?"*
   → Réponse : aucun finding n'est généré pour cette vérification précise,
   un warning est loggé indiquant un scan incomplet — jamais une
   non-conformité déduite par défaut.
2. *"Pourquoi un backoff exponentiel plutôt qu'un délai fixe entre les
   tentatives ?"*
   → Réponse : éviter l'effet "thundering herd" où plusieurs tentatives
   simultanées se re-percutent au même instant.
3. *"Comment ajouteriez-vous un collecteur Azure sans casser l'existant ?"*
   → Réponse : écrire une fonction avec la même signature
   `(session, config) -> list[FindingDict]`, l'ajouter au tuple équivalent
   à `COLLECTORS` — aucune modification de l'orchestrateur (`run_all`).
4. *"Pourquoi ne pas utiliser directement les objets retournés par boto3
   dans le reste du pipeline ?"*
   → Réponse : réponse développée au Chapitre 4 (NormalizedResource/Finding)
   — coupler tout le pipeline à la forme exacte de l'API AWS le rendrait
   fragile à chaque changement d'API et impossible à étendre à d'autres
   clouds.

## Glossaire du chapitre

- **Pagination** : mécanisme par lequel une API renvoie de grands
  ensembles de résultats en plusieurs pages successives plutôt qu'en un
  seul appel.
- **Backoff exponentiel** : stratégie de nouvelle tentative où le délai
  d'attente double à chaque échec successif.
- **Throttling** : limitation de débit imposée par un fournisseur cloud
  pour protéger ses API d'une surcharge.
- **Moindre privilège (least privilege)** : principe de sécurité selon
  lequel un acteur ne doit avoir que les permissions strictement
  nécessaires à sa tâche.

## Références

- AWS Boto3 — Paginators : https://boto3.amazonaws.com/v1/documentation/api/latest/guide/paginators.html
- AWS — Error Retries and Exponential Backoff :
  https://docs.aws.amazon.com/general/latest/gr/api-retries.html
- AWS IAM — Least Privilege : https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html
- OWASP — Least Privilege Principle

---

# Chapitre 4 — Le schéma partagé : `NormalizedResource` et `Finding`

## 4.1 Définition

`scanner/schema.py` définit, via **Pydantic**, la forme exacte de chaque
donnée qui circule dans le système. Deux objets structurent ce chapitre :

- **`NormalizedResource`** : une ressource cloud normalisée, *avant*
  évaluation par un moteur de règles — pensée pour être **cloud-agnostique**
  (un `s3_bucket` AWS et un `storage_bucket` GCP partagent la même forme
  d'enveloppe, seul le contenu de `attributes` diffère).
- **`Finding`** : un problème de conformité détecté sur une ressource —
  le contrat central, produit aujourd'hui directement par les collecteurs
  (voir la nuance de la section 4.5).

## 4.2 Pourquoi normaliser — et pourquoi ne jamais faire circuler les objets bruts d'AWS

Un appel `describe_db_instances()` de boto3 renvoie un dictionnaire avec des
clés comme `DBInstanceIdentifier`, `StorageEncrypted`, `PubliclyAccessible`
— la forme exacte que l'API AWS a choisie, avec ses conventions de nommage
(`PascalCase`), ses champs optionnels, ses versions qui évoluent avec le SDK.

Si le reste du pipeline (scoring, RAG, dashboard) consommait directement ces
dictionnaires bruts :

```
┌───────────────────────────────────────────────────────────────┐
│  Sans normalisation :                                          │
│                                                                  │
│   scoring.py doit savoir que RDS utilise "PubliclyAccessible"  │
│   et que S3 utilise une autre clé pour le même concept.        │
│                                                                  │
│   Un jour, AWS renomme un champ dans une nouvelle version du    │
│   SDK → tout le pipeline qui lit ce champ casse.                │
│                                                                  │
│   Ajouter GCP/Azure = dupliquer toute la logique en aval pour   │
│   chaque forme différente d'API.                                │
└───────────────────────────────────────────────────────────────┘
```

C'est le principe **Contract-First** : on définit d'abord la forme
attendue (le contrat), et chaque collecteur a la responsabilité de
transformer sa source vers cette forme — jamais l'inverse.

## 4.3 `NormalizedResource` — anatomie

```python
class NormalizedResource(BaseModel):
    cloud_provider: CloudProvider
    resource_id: str
    resource_type: str          # ex: s3_bucket, security_group, rds_instance
    region: Optional[str] = None
    tags: dict[str, str] = Field(default_factory=dict)
    attributes: dict = Field(default_factory=dict)   # volontairement flexible
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
```

**Le choix le plus important ici est `attributes: dict`** — volontairement
non typé. C'est un compromis assumé : on aurait pu créer une classe Pydantic
stricte par type de ressource (`S3BucketAttributes`, `RdsInstanceAttributes`,
...), ce qui donnerait une validation plus forte, mais multiplierait le
nombre de classes à maintenir à chaque nouveau type de ressource — pour un
projet qui ajoute des types de ressources chaque semaine (S3 → SG →
CloudTrail → RDS...), la flexibilité l'emporte sur l'exhaustivité du
typage. C'est un arbitrage **DTO générique vs DTO strict par type**, à
assumer explicitement en soutenance plutôt qu'à présenter comme un oubli.

## 4.4 `Finding` — le contrat central, anatomie et validation

```python
class Finding(BaseModel):
    id: Optional[str] = None
    cloud_provider: CloudProvider
    resource_id: str
    resource_type: str
    rule_id: str
    domain: Domain                      # OBLIGATOIRE depuis v1.2.0
    severity: Severity
    description: str = Field(..., max_length=2000)
    status: FindingStatus = Field(default=FindingStatus.OPEN)
    detected_at: str = Field(default_factory=...)
    simulated: bool = Field(default=False)
    correlation_id: Optional[str] = None

    @field_validator("resource_id", "rule_id")
    @classmethod
    def not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("ne peut pas être vide")
        return v
```

### Ce que Pydantic apporte concrètement ici

- **Validation à la construction** : un `Finding` avec `severity="urgent"`
  (valeur hors de l'`Enum Severity`) lève une erreur **immédiatement**, à
  l'endroit où l'objet est créé — pas trois modules plus loin quand le
  dashboard essaie d'afficher une couleur inconnue pour cette sévérité.
- **`field_validator` personnalisé** : empêche un `rule_id` ou
  `resource_id` vide de se propager silencieusement — un bug qui serait
  autrement très difficile à tracer une fois le finding stocké.
- **`max_length=2000` sur `description`** : protection simple contre un
  message d'erreur mal formé qui grossirait indéfiniment (ex. une exception
  Python entière collée dans le champ par erreur).

### Pourquoi `domain` est devenu obligatoire en v1.2.0 (et pas optionnel)

Le changelog du fichier l'explique : *"reflète l'usage réel : toutes les
règles écrites à ce jour assignent un domaine."* C'est un exemple concret
de **schéma qui suit l'usage réel plutôt que l'inverse** — au lieu de
deviner à l'avance tous les cas possibles et rendre tout optionnel "au cas
où", le schéma se resserre progressivement à mesure que l'usage démontre
qu'un champ est en réalité toujours renseigné. `domain` sert directement
au filtrage du dashboard par onglet (IAM/Network pour toi,
Encryption/Logging/Storage pour ton teammate) — le rendre obligatoire évite
un finding "orphelin" qui n'apparaîtrait dans aucun onglet.

## 4.5 Nuance importante à assumer : le lien réel entre `NormalizedResource` et `Finding` aujourd'hui

**Ce que le schéma suggère** : un collecteur produit des
`NormalizedResource`, qu'un Rule Engine évalue pour produire des `Finding`.

**Ce qui se passe réellement dans `aws.py`** : les collecteurs produisent
un `FindingDict` (forme proche de `Finding` mais en `TypedDict`, pas en
`BaseModel` Pydantic) **directement**, sans jamais construire de
`NormalizedResource` intermédiaire ni appeler de Rule Engine. La logique de
détection (ex. "si `StorageEncrypted` est faux, c'est une non-conformité")
est écrite en dur dans le collecteur.

```
CE QUE LE SCHÉMA DÉCRIT (théorie / roadmap) :

  Collecteur → NormalizedResource → Rule Engine (YAML) → Finding (Pydantic)


CE QUI EXISTE RÉELLEMENT AUJOURD'HUI :

  Collecteur → FindingDict (TypedDict, logique en dur) → JSON
```

**Pourquoi assumer ce décalage plutôt que le cacher** : le schéma
`NormalizedResource` + le catalogue YAML représentent un vrai travail de
conception (110+ règles réparties par domaine, avec `framework_refs`) —
c'est une preuve de réflexion produit, présentable en soutenance comme
telle. Mais prétendre que ce chemin tourne réellement en scan serait
vérifiable en quelques secondes par un jury qui demande à voir le code de
`rule_engine.py` appelé depuis `aws.py`. Le Chapitre 5 détaille cette
décision et ce qu'impliquerait de vraiment relier les deux.

## 4.6 La section EXTENDED — vision produit, jamais câblée

Le README l'indique explicitement : 19 modèles roadmap (RBAC complet,
audit, workflow...) existent dans une section documentée mais non utilisée
du schéma. C'est un pattern sain : **documenter une vision sans
l'implémenter prématurément**, à condition de la présenter comme telle en
soutenance ("voici où on a réfléchi à l'extensibilité future") plutôt que
comme fonctionnalité livrée.

## 4.7 Bonnes pratiques illustrées

- **Un seul fichier source de vérité** pour tous les contrats de données,
  versionné explicitement (`v1.2.0`), avec changelog en tête de fichier.
- **Enums fermés** (`Severity`, `Domain`, `FindingStatus`) plutôt que des
  chaînes libres — empêche `severity="Haute"` de se glisser à côté de
  `severity="high"`.
- **`Optional` utilisé avec parcimonie** : seuls les champs réellement
  absents à un stade donné du pipeline (`id` avant persistance,
  `correlation_id` avant corrélation) sont optionnels — pas par confort.

## 4.8 Pièges fréquents

| Piège | Conséquence | Comment ce schéma l'évite |
|---|---|---|
| Champ `severity` en chaîne libre | Valeurs incohérentes en base (`"High"` vs `"high"`) | `Enum Severity` fermé |
| Valider les données trop tard (en base, à l'affichage) | Bug détecté loin de sa cause | Validation Pydantic à la construction de l'objet |
| Rendre tout optionnel "au cas où" | Le code consommateur doit vérifier `None` partout | `domain` rendu obligatoire dès que l'usage l'a confirmé |
| Modifier le schéma en solo | Rupture de contrat côté teammate/API | Règle de gouvernance explicite dans le README |

## 4.9 Conseils professionnels

- Le couple `Optional[str] = None` pour `id` (absent à la détection, généré
  en base) est un pattern courant et sain : **ne jamais faire porter à
  l'objet applicatif une responsabilité (générer un UUID) qui appartient à
  la couche de persistance.**
- Versionner un schéma partagé (`v1.2.0` en commentaire de tête, changelog
  explicite) coûte une ligne de commentaire et évite des heures de
  confusion sur "quelle version de quel champ on utilise".

---

## Résumé du chapitre

- `NormalizedResource` normalise l'entrée du pipeline pour rester
  cloud-agnostique ; `Finding` est le contrat central de sortie, validé par
  Pydantic.
- `domain` obligatoire depuis v1.2.0 illustre un schéma qui se resserre en
  suivant l'usage réel, pas l'inverse.
- Le chemin `NormalizedResource → Rule Engine → Finding` existe en théorie
  dans le schéma mais n'est pas ce que produisent réellement les
  collecteurs aujourd'hui (ils produisent un `FindingDict` directement) —
  point à assumer clairement, développé au Chapitre 5.

## Points clés

- Pydantic valide **à la construction**, pas en aval — c'est ce qui rend
  les bugs de données faciles à localiser.
- `attributes: dict` non typé dans `NormalizedResource` est un arbitrage
  assumé (flexibilité vs exhaustivité du typage), pas un oubli.

## Erreurs fréquentes à éviter en soutenance

- Affirmer que les collecteurs produisent des `NormalizedResource` — le
  code montre le contraire ; mieux vaut assumer l'écart que se faire
  prendre en flagrant délit devant le jury.

## Questions possibles du jury

1. *"Pourquoi `attributes` est-il un simple dict et pas un modèle Pydantic
   typé par ressource ?"*
   → Réponse : arbitrage entre validation stricte et vitesse d'ajout de
   nouveaux types de ressources sur un projet à 6 semaines ; le rule engine
   (déclaratif) sait quels attributs lire selon `resource_type`.
2. *"Que se passe-t-il si on construit un `Finding` avec un `rule_id`
   vide ?"*
   → Réponse : `field_validator("resource_id", "rule_id")` lève une
   `ValueError` immédiatement à la construction.
3. *"Vos collecteurs produisent-ils vraiment des `NormalizedResource` ?"*
   → Réponse honnête : non, ils produisent un `FindingDict` directement
   aujourd'hui ; `NormalizedResource` est le contrat prévu pour le Rule
   Engine, qui n'est pas encore branché sur le scan réel (voir Ch. 5).
4. *"Pourquoi la section EXTENDED du schéma existe si elle n'est jamais
   utilisée ?"*
   → Réponse : documenter une direction produit (RBAC, audit, workflow)
   sans l'implémenter prématurément — vision assumée comme roadmap, pas
   comme fonctionnalité livrée.

## Glossaire du chapitre

- **DTO (Data Transfer Object)** : objet dont le seul rôle est de porter
  des données entre deux couches, sans logique métier.
- **Contract-First** : approche où le contrat de données (ou d'API) est
  défini avant l'implémentation qui le respecte.
- **Enum fermé** : ensemble fini et explicite de valeurs valides,
  empêchant toute valeur hors catalogue.

## Références

- Pydantic — Validators : https://docs.pydantic.dev/latest/concepts/validators/
- Martin Fowler — *Data Transfer Object* :
  https://martinfowler.com/eaaCatalog/dataTransferObject.html
- ISO/IEC 27001:2022 — cohérence des enregistrements d'audit (Annexe A.5.28)

---

# Chapitre 5 — Rule Engine & catalogue YAML (Policy-as-Code)

## 5.1 Définition

Un **Rule Engine** (moteur de règles) est un composant qui évalue des
données contre un ensemble de règles **externalisées** (ici, des fichiers
YAML), plutôt que d'avoir la logique de décision codée en dur dans le
programme. Le principe général s'appelle **Policy-as-Code** : la politique
de conformité (ce qui est acceptable ou non) devient un artefact versionné,
relisable, modifiable sans toucher au code Python.

Dans ce projet, ce composant existe à deux niveaux bien distincts qu'il
faut absolument ne pas confondre :

1. **Le catalogue** (`rules/*.yaml`) — 111 règles réparties en 5 fichiers
   par domaine (`iam.yaml`, `network.yaml`, `storage.yaml`, `logging.yaml`,
   `encryption.yaml`), chacune avec `rule_id`, `domain`, `severity`,
   `resource_types`, `description`, `condition`.
2. **L'évaluateur** (`rule_engine.py`) — le code qui est censé lire ce
   catalogue et l'appliquer à des `NormalizedResource` (Chapitre 4) pour
   produire des `Finding`.

## 5.2 Anatomie d'une règle YAML

```yaml
- rule_id: encryption.s3_bucket_unencrypted
  domain: encryption
  severity: high
  resource_types: [s3_bucket]
  description: "Bucket {resource_id} has no default encryption configured."
  condition:
    attribute: encrypted
    operator: equals
    value: false
```

Chaque champ a un rôle précis :

| Champ | Rôle |
|---|---|
| `rule_id` | Identifiant stable, utilisé pour tracer un finding jusqu'à sa règle d'origine et pour le lookup `framework_refs` (voir 5.6) |
| `domain` | Filtrage par onglet dashboard (`iam`/`network` pour toi, `encryption`/`logging`/`storage` pour ton teammate) |
| `resource_types` | Types de ressources auxquels la règle s'applique — permet à un moteur de ne l'évaluer que sur les ressources pertinentes |
| `condition` | Structure fermée `{attribute, operator, value}` — **jamais de code exécutable** |
| `description` | Template avec `{resource_id}` interpolé au moment de la génération du finding |

## 5.3 Pourquoi `condition` est structuré et jamais `eval()`

C'est une règle non négociable du projet. La tentation naturelle, en Python,
serait d'écrire la condition comme une chaîne évaluable :

```python
# JAMAIS FAIT DANS CE PROJET — exemple de ce qu'il ne faut pas faire
condition = "resource.attributes['encrypted'] == False"
eval(condition)   # DANGER
```

**Pourquoi c'est dangereux** : si un fichier YAML de règles provient d'une
source externe (un template partagé, un contributeur, une fuite de
configuration), `eval()` exécute **n'importe quel code Python** contenu
dans la chaîne — c'est une porte ouverte à l'exécution de code arbitraire
(RCE — Remote Code Execution) simplement en modifiant un fichier de
configuration. C'est répertorié dans OWASP comme un cas de **Injection de
code**.

La structure `{attribute, operator, value}` limite radicalement ce qui peut
être exprimé : un évaluateur qui lit ce format ne peut faire que des
comparaisons prédéfinies (`equals`, `not_equals`, `greater_than`,
`less_than`), jamais exécuter de code. C'est un principe de sécurité
appelé **surface d'attaque minimale** : on retire la capacité de nuire en
ne l'implémentant jamais, plutôt que d'essayer de la sécuriser après coup
(sandboxing d'`eval()`, notoirement difficile à faire sans faille).

## 5.4 Workflow théorique complet (tel que le catalogue est conçu pour fonctionner)

```
1. Chargement des fichiers rules/*.yaml au démarrage
2. Pour chaque NormalizedResource produit par un collecteur :
     a. Filtrer les règles dont resource_types contient resource.resource_type
     b. Pour chaque règle filtrée :
          - lire resource.attributes[condition.attribute]
          - appliquer condition.operator contre condition.value
          - si vrai → construire un Finding
              (rule_id, domain, severity, description interpolée)
3. Retourner list[Finding]
```

## 5.5 Ce qui existe réellement aujourd'hui — le décalage assumé

**Constat factuel** (déjà établi aux Chapitres 3 et 4) :
`scanner/collectors/aws.py` ne construit jamais de `NormalizedResource` et
n'appelle jamais `rule_engine.py`. La détection réelle
(`s3.encryption_disabled`, `rds.publicly_accessible`, etc.) est codée en
dur dans chaque fonction `collect_*`.

**Deuxième constat, découvert en cours de projet** : le catalogue YAML
contient **111 règles**, très au-delà des "22 règles réparties sur 5
domaines" documentées à l'origine dans le README du projet — et une bonne
partie couvre des types de ressources qui n'existent dans aucun module
Terraform déployé ni dans aucun collecteur réel (`redshift_cluster`,
`cloudfront_distribution`, `api_gateway`, `load_balancer`, `network_acl`,
`vpc_peering`, `elastic_ip`).

**Décision d'architecture prise pour ce projet** (documentée ici pour être
défendable en soutenance) : **ne pas router les collecteurs à travers
`rule_engine.py`+YAML dans le temps imparti.** Raisons :

| Argument | Détail |
|---|---|
| Coût de migration | Il faudrait réécrire les 5 collecteurs pour produire des `NormalizedResource`, retester chaque vérification déjà validée (20 findings réels) |
| Bénéfice marginal | Le comportement observable (quels findings sortent) resterait strictement identique — le YAML n'ajoute aucune détection nouvelle tant que 90 des 111 règles portent sur des ressources non collectées |
| Risque de régression | Réécrire un chemin qui fonctionne et est testé, à 3 semaines de la soutenance, pour un gain non fonctionnel |
| Valeur du catalogue telle quelle | Reste démontrable comme travail de conception Policy-as-Code sérieux, si présenté honnêtement comme non branché |

**Ce que cette décision implique concrètement** : le catalogue YAML est
traité comme un **artefact de conception** (comme un diagramme
d'architecture ou une spécification), pas comme du code en production. Un
jury peut tout à fait valoriser les deux — un catalogue de 111 règles bien
structuré démontre une compréhension du domaine (ISO 27001, DNSSI) même
sans moteur d'exécution, à condition de ne jamais prétendre le contraire.

## 5.6 Récupérer `framework_refs` sans réintégrer tout le moteur

Le vrai besoin opérationnel derrière le Rule Engine, pour ce projet, n'est
pas l'évaluation (déjà faite en Python dans les collecteurs) mais la
**citation normative** : relier un `rule_id` à sa référence ISO
27001/DNSSI, pour que le teammate (finding→article linker, RAG) puisse
construire un `EnrichedFinding` avec `RegulatoryCitation`.

Solution découplée, sans dépendance à `rule_engine.py` :

```
rule_id (ex: "rds.publicly_accessible")
        │
        ▼
  Lookup direct dans les fichiers YAML
  (chargés une fois, indexés par rule_id)
        │
        ▼
  framework_refs correspondants
  (ex: ISO 27001 Annexe A.8.3)
```

Une simple fonction utilitaire (chargement des YAML + dictionnaire indexé
par `rule_id`) suffit — elle réutilise le catalogue existant comme **base
de connaissance statique**, sans avoir besoin d'évaluer quoi que ce soit
dynamiquement. C'est un découplage net entre "qui détecte" (les
collecteurs) et "qui documente/cite" (ce lookup + le RAG côté teammate).

## 5.7 Un doublon repéré dans le catalogue (à corriger, sans urgence)

`network.yaml` et `storage.yaml` définissent chacun une règle
`rds_no_deletion_protection` quasi identique (même sévérité `medium`,
même condition). C'est un signe que le catalogue a été enrichi sans
relecture croisée entre domaines — mineur, mais à nettoyer avant la
soutenance pour éviter une double citation d'un même problème réel.

## 5.8 Bonnes pratiques illustrées

- **Format déclaratif fermé** (`attribute/operator/value`) plutôt
  qu'exécutable — sécurité par construction, pas par validation a
  posteriori.
- **Un fichier YAML par domaine** plutôt qu'un unique fichier monolithique
  — limite les conflits d'édition entre les deux étudiants (toi sur
  `iam.yaml`/`network.yaml`, ton teammate sur
  `encryption.yaml`/`logging.yaml`/`storage.yaml`).
- **`enabled` par règle** (mentionné dans le README) : permet de désactiver
  une règle bruyante ou non fiable sans la supprimer du catalogue — utile
  en phase de calibrage.

## 5.9 Pièges fréquents

| Piège | Conséquence | Comment ce projet l'évite (ou devrait l'éviter) |
|---|---|---|
| `eval()` sur des conditions | RCE via un fichier YAML modifié | Format `{attribute, operator, value}` fermé |
| Prétendre qu'un catalogue de règles est "branché" sans vérifier | Crédibilité détruite devant un jury technique | Assumer explicitement le décalage (5.5) |
| Dupliquer une règle dans deux domaines | Double comptage d'un même risque dans le score de conformité | Repérer et fusionner (5.7) |
| Écrire des règles pour des ressources jamais collectées | Catalogue qui gonfle sans valeur opérationnelle | Distinguer clairement règles actives / règles roadmap |

## 5.10 Conseils professionnels

- Si ce projet devait un jour réellement brancher `rule_engine.py`, l'étape
  raisonnable ne serait pas "tout migrer d'un coup" mais migrer **un seul
  collecteur** (ex. RDS, le plus récent) vers `NormalizedResource` en
  parallèle de l'existant, pour valider l'approche avant de généraliser —
  principe de **migration incrémentale** (Strangler Fig Pattern).
- Ajouter un domaine complet (ex. un futur domaine "Kubernetes") suit un
  chemin déjà balisé par la conception actuelle : nouveau fichier
  `rules/kubernetes.yaml`, nouveau `resource_type`, sans toucher aux
  fichiers existants.

---

## Résumé du chapitre

- Le catalogue YAML (111 règles, Policy-as-Code, format déclaratif fermé)
  et l'évaluateur théorique (`rule_engine.py`) sont deux choses distinctes ;
  seul le premier existe comme artefact de conception solide.
- La détection réelle passe aujourd'hui par du code Python en dur dans les
  collecteurs — décision assumée, pas subie, justifiée par le rapport
  coût/bénéfice à l'échelle du projet.
- `framework_refs` peut être récupéré par un simple lookup statique sur le
  YAML, sans réintégrer tout le moteur — c'est la voie recommandée pour ce
  projet.

## Points clés

- Ne jamais utiliser `eval()` sur des conditions de règles — c'est une
  règle de sécurité, pas une préférence de style.
- Un catalogue de règles non branché a de la valeur en soutenance **si et
  seulement si** il est présenté honnêtement comme tel.

## Erreurs fréquentes à éviter en soutenance

- Dire "notre moteur de règles évalue 111 politiques" sans préciser
  qu'aucune n'est actuellement évaluée par un moteur — c'est l'écart le
  plus risqué de tout le projet face à un jury qui demande une démo live.

## Questions possibles du jury

1. *"Montrez-moi le moment où `rule_engine.py` est appelé dans votre
   scan."*
   → Réponse honnête : il ne l'est pas encore ; la détection est câblée
   directement dans les collecteurs. Le rule engine + catalogue YAML est
   un travail de conception livré séparément, présenté comme tel.
2. *"Pourquoi structurer une condition en `{attribute, operator, value}`
   plutôt que d'accepter une expression Python directe ?"*
   → Réponse : élimine par construction tout risque d'exécution de code
   arbitraire (`eval()`) si le fichier de règles provient d'une source
   externe ou est modifié par erreur.
3. *"Vous avez 111 règles mais seulement quelques dizaines de ressources
   déployées — n'est-ce pas contradictoire ?"*
   → Réponse : le catalogue documente une couverture cible plus large que
   le périmètre de test réel de 6 semaines ; seules les règles couvrant des
   `resource_types` réellement collectés sont opérationnelles aujourd'hui.
4. *"Comment récupérez-vous la référence ISO 27001 d'un finding sans
   moteur de règles ?"*
   → Réponse : un lookup direct par `rule_id` dans les fichiers YAML
   chargés en mémoire, indépendant de toute logique d'évaluation.

## Glossaire du chapitre

- **Policy-as-Code** : pratique consistant à exprimer des règles de
  conformité/sécurité sous forme de fichiers de configuration versionnés,
  plutôt qu'en code impératif dispersé.
- **RCE (Remote Code Execution)** : classe de vulnérabilité permettant à un
  attaquant d'exécuter du code arbitraire sur un système.
- **Strangler Fig Pattern** : stratégie de migration progressive d'un
  ancien système vers un nouveau, module par module, sans "big bang".

## Références

- OWASP — Code Injection : https://owasp.org/www-community/attacks/Code_Injection
- Open Policy Agent (OPA) — référence industrielle du Policy-as-Code :
  https://www.openpolicyagent.org/
- Martin Fowler — *StranglerFigApplication* :
  https://martinfowler.com/bliki/StranglerFigApplication.html
- ISO/IEC 27001:2022 — Annexe A (contrôles cités dans le catalogue)

---

# Chapitre 6 — Les Findings (le cœur du produit)

## 6.1 Définition

Un **Finding** est l'unité atomique de tout le produit : une non-conformité
détectée, sur une ressource précise, à un instant précis, reliée à une
règle précise. Tout ce que fait ComplianceIQ en aval — citation normative,
traduction financière, remédiation, score, dashboard — **consomme des
Finding**. Rien d'autre n'est produit directement par le scan.

```
                    ┌─────────────┐
                    │   Finding   │  ← tout part d'ici
                    └──────┬──────┘
           ┌───────────────┼───────────────┬───────────────┐
           ▼               ▼               ▼               ▼
   EnrichedFinding  FinancialRisk   RemediationProp   ComplianceScore
   (citation ISO)   Assessment      osal (Terraform)  (agrégation)
```

## 6.2 Pourquoi le Finding est "le cœur du produit" et pas la ressource cloud

Une ressource cloud (`rds_instance`, `s3_bucket`) est un fait neutre — elle
existe, point. Le Finding, lui, porte un **jugement** : "cette
configuration précise viole telle règle, avec telle sévérité". C'est ce
jugement qui a de la valeur commerciale et normative — un dashboard qui
listerait "voici vos 65 ressources AWS" n'intéresse personne ; un dashboard
qui dit "voici vos 12 non-conformités critiques, avec leur coût estimé"
est vendable. Le Finding est donc conçu comme **le contrat de plus haute
importance** du schéma (Chapitre 4), avec la règle de gouvernance la plus
stricte du README ("jamais un edit solo").

## 6.3 Cycle de vie d'un Finding

```
        ┌────────┐
        │  OPEN   │  ← état initial, à la détection
        └────┬────┘
             │
    ┌────────┼────────┐
    ▼                  ▼
┌─────────┐      ┌───────────┐
│ RESOLVED │      │ DISMISSED │
└─────────┘      └───────────┘
  la ressource       jugé faux positif
  a été corrigée     ou accepté comme
  (re-scan confirme) risque assumé
```

- **`OPEN`** : état par défaut (`FindingStatus.OPEN`), tant qu'un scan
  ultérieur ne l'a pas invalidé.
- **`RESOLVED`** : la non-conformité n'est plus détectée à un scan
  suivant — implique une logique de **réconciliation** entre deux scans
  successifs (non détaillée dans le code vu jusqu'ici, mais c'est la
  sémantique attendue du champ).
- **`DISMISSED`** : décision humaine explicite de ne pas traiter ce
  finding (ex. risque accepté par la direction) — **jamais automatique**,
  cohérent avec le principe de validation humaine du projet (voir
  `RemediationProposal.approved`, Chapitre 8).

## 6.4 Classification — `Severity` et `Domain`

```python
class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

Une échelle à 4 niveaux, volontairement **simple et fermée** — pas un score
numérique continu (0-100) qui donnerait une fausse précision à un jugement
qui reste largement qualitatif ("un bucket public en écriture est
`critical`" est un jugement métier, pas un calcul).

`Domain` (`iam`, `network`, `encryption`, `logging`, `storage`) sert une
deuxième fonction, orthogonale à la sévérité : **le découpage de
responsabilité entre les deux étudiants** et le filtrage du dashboard par
onglet. Un même Finding a donc toujours deux axes de lecture indépendants :
*"à quel point c'est grave"* (`severity`) et *"de quoi ça relève"*
(`domain`).

## 6.5 Métadonnées de traçabilité

| Champ | Rôle dans la traçabilité |
|---|---|
| `rule_id` | Relie le finding à sa règle d'origine — indispensable pour la citation normative (Ch. 5.6) et pour qu'un correctif futur de la règle puisse être audité |
| `detected_at` | Horodatage ISO 8601 UTC — permet de reconstituer une chronologie de scans, essentiel en cas d'incident (savoir depuis quand une ressource est mal configurée) |
| `resource_id` | Identifiant unique de la ressource concernée (nom de bucket, ID de security group...) — permet de retrouver la ressource exacte dans la console cloud |
| `simulated` | Distingue un finding issu d'un vrai scan d'un finding issu d'une simulation Terraform plan (`CloudProvider.TERRAFORM_PLAN`, roadmap "Compliance Simulation") — évite de confondre un risque réel et un risque hypothétique dans le score |
| `correlation_id` | Référence optionnelle vers un `CorrelatedRisk` — voir 6.6 |

## 6.6 `CorrelatedRisk` — quand plusieurs Findings valent plus que la somme de leurs parties

```python
class CorrelatedRisk(BaseModel):
    correlation_id: str
    finding_ids: list[str] = Field(..., min_length=2)
    combined_severity: Severity
    narrative: str
```

L'idée : un bucket S3 public **et** un rôle IAM sur-permissif **et** un
security group ouvert à Internet, pris séparément, sont chacun un finding
`medium`/`high`. **Combinés**, ils décrivent un chemin d'attaque complet
(*attack path*) — un attaquant externe qui atteint la ressource, avec les
permissions pour l'exploiter, et une porte d'entrée ouverte. La sévérité
combinée peut légitimement dépasser celle de n'importe quel finding pris
isolément. `min_length=2` sur `finding_ids` impose qu'une corrélation
implique toujours au moins deux findings — un `CorrelatedRisk` à un seul
élément n'aurait pas de sens (ce serait juste... un `Finding`).

**Statut réel** : ce mécanisme est modélisé dans le schéma mais je n'ai vu
aucun code qui le produit dans ce qui m'a été partagé — à vérifier avant de
le présenter comme fonctionnel en soutenance (probablement roadmap S8
selon la nomenclature du schéma).

## 6.7 Bonnes pratiques illustrées

- **Séparer le jugement (`severity`) de la classification (`domain`)** —
  deux axes orthogonaux plutôt qu'un seul champ fourre-tout.
- **Statuts fermés et explicites** (`OPEN`/`RESOLVED`/`DISMISSED`) plutôt
  qu'un simple booléen `is_open` — un booléen ne pourrait jamais distinguer
  "corrigé" de "accepté comme risque", deux réalités très différentes pour
  un audit.
- **Horodatage systématique en UTC, format ISO 8601** — évite toute
  ambiguïté de fuseau horaire dans un contexte d'audit multi-région.

## 6.8 Pièges fréquents

| Piège | Conséquence | Comment le schéma l'évite |
|---|---|---|
| Un score de sévérité continu (0-100) sans référentiel clair | Faux sentiment de précision sur un jugement qualitatif | Échelle fermée à 4 niveaux |
| Booléen unique pour le statut | Impossible de distinguer "corrigé" de "accepté" | Enum `FindingStatus` à 3 valeurs |
| Horodatage en heure locale | Ambiguïté lors d'un audit multi-région/multi-fuseau | ISO 8601 UTC systématique |
| Mélanger findings réels et simulés dans le même score | Score de conformité qui ment sur l'état réel du cloud | Champ `simulated` explicite |

## 6.9 Conseils professionnels

- Si `RESOLVED` doit un jour être posé automatiquement (comparaison entre
  deux scans), la logique de réconciliation doit être **idempotente** : un
  même scan rejoué ne doit jamais faire "flapper" un finding entre `OPEN`
  et `RESOLVED` à cause d'un bruit transitoire (ex. `AccessDenied`
  temporaire — voir Ch. 3.3.4, le même principe de prudence s'applique ici).

---

## Résumé du chapitre

- Le Finding est l'unique unité produite par le scan et consommée par tout
  le reste du système — c'est le contrat le plus critique du projet.
- Son cycle de vie (`OPEN`/`RESOLVED`/`DISMISSED`) distingue explicitement
  correction et acceptation de risque, jamais automatique pour ce dernier.
- `severity` et `domain` sont deux axes orthogonaux ; `CorrelatedRisk`
  modélise la composition de plusieurs findings en un risque combiné, mais
  reste à confirmer comme réellement implémenté.

## Points clés

- Toujours pouvoir répondre : "qui peut faire passer un finding à
  `DISMISSED`, et est-ce tracé ?" — question quasi certaine en revue de
  sécurité.

## Erreurs fréquentes à éviter en soutenance

- Présenter `CorrelatedRisk` comme fonctionnel sans avoir vérifié qu'un
  module le produit réellement.

## Questions possibles du jury

1. *"Quelle différence entre un finding `RESOLVED` et un finding
   `DISMISSED` ?"*
   → Réponse : `RESOLVED` signifie que la ressource a été corrigée et
   qu'un scan ultérieur ne détecte plus le problème ; `DISMISSED` est une
   décision humaine explicite de ne pas traiter un risque accepté — la
   ressource reste potentiellement non conforme.
2. *"Pourquoi un statut `dismissed` peut-il exister sans que la
   remédiation soit appliquée ?"*
   → Réponse : cohérent avec le principe général du projet — aucune action
   automatique, l'humain reste décisionnaire, y compris pour accepter un
   risque en connaissance de cause.
3. *"Comment un `CorrelatedRisk` change-t-il le score de conformité par
   rapport à des findings isolés ?"*
   → Réponse attendue selon la conception : la sévérité combinée peut
   dépasser la sévérité individuelle maximale, reflétant un chemin
   d'attaque réel — à confirmer/nuancer si le mécanisme n'est pas encore
   implémenté.

## Glossaire du chapitre

- **Attack path (chemin d'attaque)** : séquence de faiblesses combinées
  qu'un attaquant peut enchaîner pour atteindre un objectif, même si
  chaque faiblesse prise isolément semble mineure.
- **Idempotence** : propriété d'une opération dont le résultat est
  identique qu'elle soit exécutée une ou plusieurs fois avec les mêmes
  entrées.
- **Réconciliation** : processus de comparaison entre deux états successifs
  (ici, deux scans) pour déterminer ce qui a changé.

## Références

- MITRE ATT&CK — modélisation des chaînes d'attaque :
  https://attack.mitre.org/
- ISO/IEC 27001:2022 — Annexe A.5.24 (gestion des incidents, statuts de
  traitement)
