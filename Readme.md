# ⚡ BrixHub OSINT Engine & API Platform

<p align="center">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/ClickHouse-FFCC01?style=for-the-badge&logo=clickhouse&logoColor=black" alt="ClickHouse" />
  <img src="https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white" alt="Redis" />
  <img src="https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white" alt="Docker" />
  <img src="https://img.shields.io/badge/Traefik_v3-24A1C1?style=for-the-badge&logo=traefikproxy&logoColor=white" alt="Traefik" />
  <img src="https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white" alt="Tailwind" />
  <img src="https://img.shields.io/badge/Debian_12%2F13-A81D33?style=for-the-badge&logo=debian&logoColor=white" alt="Debian" />
  <img src="https://img.shields.io/badge/Security-Strict_OTP_&_Rate_Limit-blueviolet?style=for-the-badge&logo=shield" alt="Security" />
</p>

---

## 📑 Sommaire
- [1. Présentation de l'Architecture](#1-présentation-de-larchitecture)
- [2. Prérequis & Dimensionnement](#2-prérequis--dimensionnement)
- [3. Guide de Déploiement Complet (Pas-à-pas)](#3-guide-de-déploiement-complet-pas-à-pas)
  - [Étape 1 : Préparation du Système d'Exploitation](#étape-1--préparation-du-système-dexploitation)
  - [Étape 2 : Installation du Moteur ClickHouse Natif](#étape-2--installation-du-moteur-clickhouse-natif)
  - [Étape 3 : Installation de Docker & Docker Compose](#étape-3--installation-de-docker--docker-compose)
  - [Étape 4 : Restauration et Indexation des Données](#étape-4--restauration-et-indexation-des-données)
  - [Étape 5 : Arborescence Applicative & Fichiers de Configuration](#étape-5--arborescence-applicative--fichiers-de-configuration)
  - [Étape 6 : Lancement de la Pile Docker](#étape-6--lancement-de-la-pile-docker)
- [4. Système d'Authentification & Sécurité OTP](#4-système-dauthentification--sécurité-otp)
- [5. Spécifications & Endpoints de l'API](#5-spécifications--endpoints-de-lapi)
- [6. Maintenance, Sauvegardes & Supervision](#6-maintenance-sauvegardes--supervision)

---

## 1. Présentation de l'Architecture

BrixHub OSINT est un moteur d'investigation et d'indexation haute performance conçu pour corréler des téraoctets de données en temps réel :
- **Moteur de stockage analytique** : **ClickHouse Server** installé en natif sur l'hôte Debian pour un accès direct aux threads CPU, RAM et I/O disque sans surcouche réseau Docker.
- **Cache & Rate-limiting** : **Redis 7** orchestré dans Docker pour contrôler les quotas stricts par IP (visiteurs non connectés : 2 requêtes/jour) et utilisateurs authentifiés (5 requêtes/jour, plans Standard à 1 000 req/jour, Pro à 50 000 req/jour).
- **Couche Applicative** : **FastAPI (Python 3.11)** avec tâches d'arrière-plan asynchrones (`BackgroundTasks`), modèles Pydantic stricts et hashing de sécurité.
- **Passerelle Emailing Sécurisée** : Notification SMTP (Google Workspace / Gmail App Password) expédiant des codes de validation OTP à 6 chiffres via templates dark glassmorphism.
- **Passerelle d'Entrée & SSL** : **Traefik v3** assurant le reverse-proxying, le re-routage des en-têtes IP réelles (`X-Forwarded-For`), et le renouvellement automatique des certificats SSL Let's Encrypt TLS-ALPN-01 / HTTP-01.


```

```
                          [ Internet ]
                               │
                       (Ports 80 & 443)
                               ▼
                  ┌─────────────────────────┐
                  │   Traefik v3 (SSL ACME) │
                  └────────────┬────────────┘
                               │
          ┌────────────────────┴────────────────────┐
          ▼                                         ▼

```

┌──────────────────────┐                  ┌──────────────────────┐
│    BrixHub WebApp    │                  │      n8n Engine      │
│   (FastAPI/Tailwind) │                  │ (Workflows Autom.)   │
└──────────┬───────────┘                  └──────────────────────┘
│
┌───────┴─────────────────┐
▼                         ▼
┌───────────┐       ┌────────────────────────┐
│  Redis 7  │       │ ClickHouse Server (OS) │
│ (OTP/RL)  │       │  ports 8123 / 9000     │
└───────────┘       └────────────────────────┘

```

---

## 2. Prérequis & Dimensionnement

| Composant | Configuration Minimale | Configuration Recommandée |
| :--- | :--- | :--- |
| **Système d'exploitation** | Debian 12 (Bookworm) / Debian 13 (Trixie) | Debian 12 x86_64 |
| **Processeur (CPU)** | 2 vCPU | 4 à 8 vCPU |
| **Mémoire Vive (RAM)** | 4 Go | 8 Go à 16 Go |
| **Stockage (SSD/NVMe)** | 40 Go libres | 100 Go+ NVMe |
| **Réseau** | IP Publique Statique | Ports 80, 443, 22 ouverts |
| **DNS (Enregistrements A)** | `brixhub.uned.live` & `n8n.uned.live` | Pointant vers l'IP publique du VPS |

---

## 3. Guide de Déploiement Complet (Pas-à-pas)

### Étape 1 : Préparation du Système d'Exploitation

Connectez-vous en SSH avec les droits `root` :

```bash
apt update && apt upgrade -y
apt install -y curl wget git unzip htop ufw ca-certificates gnupg lsb-release apt-transport-https dirmngr python3-pip python3-venv

```

Configuration du pare-feu applicatif (UFW) :

```bash
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

```

---

### Étape 2 : Installation du Moteur ClickHouse Natif

1. **Ajout du dépôt officiel ClickHouse :**

```bash
GNUPGHOME=$(mktemp -d)
GNUPGHOME="$GNUPGHOME" gpg --no-default-keyring --keyring /usr/share/keyrings/clickhouse-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys 8919F6BD2B48D754
rm -rf "$GNUPGHOME"
chmod +r /usr/share/keyrings/clickhouse-keyring.gpg

echo "deb [signed-by=/usr/share/keyrings/clickhouse-keyring.gpg] [https://packages.clickhouse.com/deb](https://packages.clickhouse.com/deb) stable main" | tee /etc/apt/sources.list.d/clickhouse.list
apt update

```

2. **Installation des paquets :**

```bash
DEBIAN_FRONTEND=noninteractive apt install -y clickhouse-server clickhouse-client

```

3. **Configuration réseau & accès Docker :**
Pour permettre au conteneur Docker `webapp` d'interroger ClickHouse via l'adresse passerelle `host.docker.internal:8123`, autorisez l'écoute sur toutes les interfaces :

```bash
cat << 'EOF' > /etc/clickhouse-server/config.d/listen.xml
<clickhouse>
    <listen_host>::</listen_host>
</clickhouse>
EOF

cat << 'EOF' > /etc/clickhouse-server/config.d/backups.xml
<clickhouse>
    <backups>
        <allowed_path>/var/lib/clickhouse/backups/</allowed_path>
    </backups>
</clickhouse>
EOF

mkdir -p /var/lib/clickhouse/backups
chown -R clickhouse:clickhouse /var/lib/clickhouse/backups

systemctl enable clickhouse-server
systemctl restart clickhouse-server

```

Vérification :

```bash
clickhouse-client --query="SELECT version();"

```

---

### Étape 3 : Installation de Docker & Docker Compose

```bash
install -m 0755 -d /etc/apt/keyrings
curl -fsSL [https://download.docker.com/linux/debian/gpg](https://download.docker.com/linux/debian/gpg) -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] [https://download.docker.com/linux/debian](https://download.docker.com/linux/debian) $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

```

---

### Étape 4 : Restauration et Indexation des Données

1. Téléchargez ou déplacez l'archive de sauvegarde dans le dossier ClickHouse :

```bash
cd /var/lib/clickhouse/backups/
# Exemple de rapatriement :
# wget -O backup_sports_db_20261020.zip "<LIEN_DU_BACKUP>"
chown -R clickhouse:clickhouse /var/lib/clickhouse/backups/
chmod 644 /var/lib/clickhouse/backups/*.zip

```

2. Restaurez la base de données :

```bash
clickhouse-client --query="RESTORE DATABASE sports_db FROM File('/var/lib/clickhouse/backups/backup_sports_db_20261020.zip');"

```

3. Contrôlez l'intégrité de la table restaurée (103M+ lignes attendues) :

```bash
clickhouse-client --query="
SELECT
    database,
    table,
    formatReadableSize(sum(bytes_on_disk)) AS taille_disque,
    sum(rows) AS total_enregistrements
FROM system.parts
WHERE database = 'sports_db' AND active = 1
GROUP BY database, table;
"

```

---

### Étape 5 : Arborescence Applicative & Fichiers de Configuration

Structure des dossiers :

```bash
mkdir -p /opt/search_app/app/api
mkdir -p /opt/search_app/app/core
mkdir -p /opt/search_app/app/db
mkdir -p /opt/search_app/app/repositories
mkdir -p /opt/search_app/app/services
mkdir -p /opt/search_app/static
mkdir -p /opt/search_app/traefik/letsencrypt

cd /opt/search_app
touch traefik/letsencrypt/acme.json
chmod 600 traefik/letsencrypt/acme.json

```

#### 1. Fichier d'environnement `/opt/search_app/.env`

```bash
cat << 'EOF' > /opt/search_app/.env
# Bases de données & Cache
CLICKHOUSE_HOST=host.docker.internal
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=
REDIS_URL=redis://redis:6379/0

# Sécurité & Tokens
ADMIN_TOKEN=sk_admin_secret_key_change_me_9921
JWT_SECRET=super_secret_jwt_token_entropy_brixhub_2026

# Passerelle SMTP Google (Envoi OTP Sécurisé)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=nathansroussi@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_application_16_caracteres
SMTP_FROM_NAME="BrixHub Security"
SMTP_FROM_EMAIL=nathansroussi@gmail.com

# Configuration des domaines
DOMAIN_WEB=brixhub.uned.live
DOMAIN_N8N=n8n.uned.live
LETSENCRYPT_EMAIL=nathansroussi@gmail.com
EOF

```

#### 2. Fichier d'orchestration `/opt/search_app/docker-compose.yml`

```bash
cat << 'EOF' > /opt/search_app/docker-compose.yml
services:
  traefik:
    image: traefik:v3.1
    container_name: traefik
    restart: always
    command:
      - "--api.dashboard=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.web.http.redirections.entrypoint.to=websecure"
      - "--entrypoints.web.http.redirections.entrypoint.scheme=https"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=${LETSENCRYPT_EMAIL}"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./traefik/letsencrypt:/letsencrypt"
    networks:
      - app_net

  redis:
    image: redis:7-alpine
    container_name: redis
    restart: always
    command: ["redis-server", "--appendonly", "yes"]
    volumes:
      - redis_data:/data
    networks:
      - app_net

  webapp:
    build: .
    container_name: web_search_app
    restart: always
    env_file: .env
    extra_hosts:
      - "host.docker.internal:host-gateway"
    volumes:
      - ./static:/app/static
      - ./.env:/app/.env
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.webapp.rule=Host(`${DOMAIN_WEB}`)"
      - "traefik.http.routers.webapp.entrypoints=websecure"
      - "traefik.http.routers.webapp.tls.certresolver=myresolver"
      - "traefik.http.services.webapp.loadbalancer.server.port=80"
    depends_on:
      - redis
    networks:
      - app_net

  n8n:
    image: docker.n8n.io/n8nio/n8n:latest
    container_name: n8n
    restart: always
    environment:
      - N8N_HOST=${DOMAIN_N8N}
      - N8N_PORT=5678
      - N8N_PROTOCOL=https
      - NODE_ENV=production
      - WEBHOOK_URL=https://${DOMAIN_N8N}/
    volumes:
      - n8n_data:/home/node/.n8n
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.n8n.rule=Host(`${DOMAIN_N8N}`)"
      - "traefik.http.routers.n8n.entrypoints=websecure"
      - "traefik.http.routers.n8n.tls.certresolver=myresolver"
      - "traefik.http.services.n8n.loadbalancer.server.port=5678"
    networks:
      - app_net

networks:
  app_net:
    driver: bridge

volumes:
  redis_data:
  n8n_data:
EOF

```

#### 3. Image Docker Applicative `/opt/search_app/Dockerfile`

```bash
cat << 'EOF' > /opt/search_app/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 80

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80", "--proxy-headers", "--forwarded-allow-ips=*"]
EOF

```

#### 4. Dépendances `/opt/search_app/requirements.txt`

```bash
cat << 'EOF' > /opt/search_app/requirements.txt
fastapi==0.110.0
uvicorn[standard]==0.28.0
pydantic==2.6.4
pydantic-settings==2.2.1
redis==5.0.3
clickhouse-connect==0.7.4
python-dotenv==1.0.1
passlib[bcrypt]==1.7.4
bcrypt==4.1.2
pyjwt==2.8.0
EOF

```

---

### Étape 6 : Lancement de la Pile Docker

```bash
cd /opt/search_app
docker compose build --no-cache webapp
docker compose up -d

```

Vérification des conteneurs :

```bash
docker compose ps

```

Tous les conteneurs (`traefik`, `web_search_app`, `redis`, `n8n`) doivent afficher le statut **Up**.

---

## 4. Système d'Authentification & Sécurité OTP

Pour garantir une protection maximale contre les abus et l'énumération de comptes :

1. **Fournisseurs officiels uniquement** : Seuls les domaines `@gmail.com`, `@hotmail.*`, `@yahoo.*`, `@outlook.*` et `@icloud.com` sont autorisés à l'inscription.
2. **Double facteur obligatoire (2-Step Verification)** :
* Inscription : L'utilisateur fournit son email et son mot de passe. Un code numérique de 6 chiffres est envoyé par email. Le compte n'est écrit dans la base de données qu'après validation de l'OTP.
* Mot de passe oublié : Aucun lien de réinitialisation n'est généré ni exposé dans l'API. L'utilisateur doit saisir le code à usage unique reçu dans sa boîte mail ainsi que son nouveau mot de passe.


3. **Persistance temporaire Redis** : Les sessions OTP expirent automatiquement après **10 minutes (600 secondes)** et sont détruites dès leur première utilisation (`One-Time Token`).
4. **Rate limiting prédictif** :
* Visiteurs anonymes (Guest) : **2 requêtes par adresse IP et par tranche de 24h**.
* Utilisateurs enregistrés : **5 requêtes par compte et par jour**.
* Développeurs API : Jusqu'à 50 000 req/jour selon licence.



---

## 5. Spécifications & Endpoints de l'API

Point d'accès de base : `https://brixhub.uned.live/v1`

### Authentification HTTP

Toute requête doit transmettre l'en-tête suivant :

```http
Authorization: Bearer <VOTRE_CLE_API>

```

### 1. Recherche Standard `/v1/search`

Méthode : `GET`

| Paramètre | Type | Format | Description |
| --- | --- | --- | --- |
| `q` | String | Texte libre | Recherche globale multi-colonnes. |
| `nom` | String | `DUPONT` | Recherche exacte ou floue par nom. |
| `prenom` | String | `Jean` | Recherche par prénom. |
| `tel` | String | `0612345678` | Recherche par numéro de téléphone. |
| `mail` | String | `jean@gmail.com` | Recherche par adresse email. |
| `code_postal` | String | `75008` | Recherche par code postal. |
| `ville` | String | `Paris` | Recherche par commune. |
| `limit` | Integer | `1` à `250` | Nombre maximum de résultats (défaut : 50). |

### 2. Pivots et Corrélations Multi-Sources `/v1/correlations`

Méthode : `GET` (Réservé aux plans PRO & ENTERPRISE)

| Paramètre | Type | Description |
| --- | --- | --- |
| `tel` | String | Déclenche un pivot automatique sur le numéro de téléphone. |
| `mail` | String | Déclenche un pivot automatique sur l'adresse email. |

### Codes d'Erreurs HTTP Standardisés

```json
{
  "error": true,
  "status_code": 429,
  "code": "DAILY_QUOTA_EXCEEDED",
  "detail": "Votre quota quotidien de requêtes est épuisé.",
  "reset_timestamp": 1774828800
}

```

* `200 OK` : Requête exécutée avec succès.
* `400 Bad Request` : Paramètres manquants ou syntaxe erronée.
* `401 Unauthorized` : Clé API absente ou format non conforme.
* `403 Forbidden` : Clé API suspendue ou niveau de licence insuffisant.
* `429 Too Many Requests` : Quota journalier ou rate-limit par seconde atteint.
* `500 Internal Error` : Erreur interne serveur / base de données.

---

## 6. Maintenance, Sauvegardes & Supervision

### Surveillance des conteneurs en temps réel

```bash
# Journaux Traefik et SSL
docker logs -f traefik

# Journaux applicatifs FastAPI & SMTP
docker logs -f --tail=50 web_search_app

# Métriques de ressources système
docker stats

```

### Redémarrage des services

```bash
cd /opt/search_app
docker compose restart webapp

```

### Sauvegarde à chaud de ClickHouse

```bash
clickhouse-client --query="BACKUP DATABASE sports_db TO File('/var/lib/clickhouse/backups/backup_auto_' || toString(today()) || '.zip');"

```

```

---

# Script d'Importation & Création de Vue sur ClickHouse

Ce script prêt à l'emploi configure la structure optimale, importe les fichiers bruts (CSV, TSV, Parquet ou dump SQL) et génère la **vue unifiée matérialisée** (`sports_db.vue_recherche_unifiee`) optimisée pour les recherches par trigrammes et index inversés.

Enregistrez et exécutez ce script sur votre VPS :

```bash
cat << 'EOF' > /opt/search_app/setup_clickhouse_views.sh
#!/usr/bin/env bash
# ==============================================================================
# BRIXHUB OSINT ENGINE - SCRIPT D'IMPORTATION & CREATION DE VUES UNIFIEES
# Moteur : ClickHouse Database Engine
# Base cible : sports_db
# ==============================================================================

set -euo pipefail

echo "=========================================================="
echo "⚡ INITIALISATION DE LA STRUCTURE ET DES VUES CLICKHOUSE"
echo "=========================================================="

# 1. Vérifier si ClickHouse est opérationnel
if ! systemctl is-active --quiet clickhouse-server; then
    echo "❌ Le service clickhouse-server n'est pas actif. Démarrage en cours..."
    systemctl start clickhouse-server
    sleep 2
fi

# 2. Création de la base de données
clickhouse-client --multiquery << 'SQL'
CREATE DATABASE IF NOT EXISTS sports_db;
CREATE DATABASE IF NOT EXISTS auth_db;
SQL

echo "✔ Bases 'sports_db' et 'auth_db' validées."

# 3. Création de la table principale optimisée (si non existante)
clickhouse-client --multiquery << 'SQL'
CREATE TABLE IF NOT EXISTS sports_db.membres
(
    id UUID DEFAULT generateUUIDv4(),
    nom LowCardinality(String),
    prenom String,
    date_naissance Nullable(Date),
    jour Nullable(UInt8),
    mois Nullable(UInt8),
    annee Nullable(UInt16),
    adresse String,
    code_postal LowCardinality(String),
    ville LowCardinality(String),
    tel LowCardinality(String),
    mail String,
    source LowCardinality(String) DEFAULT 'SPORTS_DB',
    date_import DateTime DEFAULT now()
)
ENGINE = MergeTree()
PARTITION BY toYYYYMM(date_import)
ORDER BY (nom, prenom, code_postal, tel)
SETTINGS index_granularity = 8192;
SQL

echo "✔ Table 'sports_db.membres' prête."

# 4. Création de la VUE UNIFIÉE OPTIMISÉE POUR LA RECHERCHE
# Cette vue nettoie, normalise et expose les champs clés pour l'API
clickhouse-client --multiquery << 'SQL'
DROP VIEW IF EXISTS sports_db.vue_recherche_unifiee;

CREATE VIEW sports_db.vue_recherche_unifiee AS
SELECT
    toString(id) AS id,
    upper(trim(nom)) AS nom,
    initcap(trim(prenom)) AS prenom,
    date_naissance,
    jour,
    mois,
    annee,
    upper(trim(adresse)) AS adresse,
    trim(code_postal) AS code_postal,
    upper(trim(ville)) AS ville,
    replaceAll(replaceAll(replaceAll(trim(tel), ' ', ''), '.', ''), '-', '') AS tel,
    lower(trim(mail)) AS mail,
    source,
    date_import
FROM sports_db.membres;
SQL

echo "✔ Vue standard 'sports_db.vue_recherche_unifiee' configurée."

# 5. Création de la table des utilisateurs & quotas API dans auth_db
clickhouse-client --multiquery << 'SQL'
CREATE TABLE IF NOT EXISTS auth_db.utilisateurs
(
    user_id UUID DEFAULT generateUUIDv4(),
    email String,
    password_hash String,
    plan LowCardinality(String) DEFAULT 'FREE',
    daily_quota UInt32 DEFAULT 5,
    api_key String,
    is_active UInt8 DEFAULT 1,
    created_at DateTime DEFAULT now()
)
ENGINE = ReplacingMergeTree()
ORDER BY (email, user_id);
SQL

echo "✔ Table d'authentification 'auth_db.utilisateurs' prête."

# 6. Affichage du résumé d'indexation
echo ""
echo "📊 État des tables et volumes actuels :"
clickhouse-client --query="
SELECT
    database,
    table,
    formatReadableSize(sum(bytes_on_disk)) AS taille,
    sum(rows) AS total_lignes
FROM system.parts
WHERE database IN ('sports_db', 'auth_db') AND active = 1
GROUP BY database, table
ORDER BY total_lignes DESC;
"

echo "=========================================================="
echo "✅ CONFIGURATION DES VUES CLICKHOUSE TERMINÉE AVEC SUCCÈS"
echo "=========================================================="
EOF

chmod +x /opt/search_app/setup_clickhouse_views.sh
/opt/search_app/setup_clickhouse_views.sh

```
