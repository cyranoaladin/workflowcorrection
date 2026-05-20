# Runbook des Operations — Workflow Correction

## 1. Architecture deux stacks

### Stack workflowcorrection (5 containers)

| Container | Role | Port expose |
|-----------|------|-------------|
| `backend` | API FastAPI | 127.0.0.1:8010 |
| `frontend` | Interface Next.js | 127.0.0.1:3011 |
| `postgres` | Base de donnees PostgreSQL | — (interne) |
| `redis` | Broker Celery / cache | — (interne) |
| `worker` | Worker Celery (grading async) | — |

### Stack RAG colocalise (3+1 containers)

| Container | Role | Port expose |
|-----------|------|-------------|
| `compose-ingestor-1` | Service d'ingestion RAG | :8001 |
| `compose-chroma-1` | Base vectorielle ChromaDB | :8000 (interne) |
| `compose-ollama-1` | Modele d'embeddings local | :11434 (interne) |
| `compose-ui-1` | Interface d'administration RAG | :8080 |

### Reseau Docker

Les deux stacks communiquent via le reseau Docker `compose_rag_ui_net`.

- Le backend accede a l'ingestor par son alias DNS Docker : `compose-ingestor-1`
- Variable d'environnement cote backend : `RAG_HTTP_BASE_URL=http://compose-ingestor-1:8001`
- Le port `:8001` n'a pas besoin d'etre expose sur l'hote si les deux stacks partagent le meme reseau Docker

---

## 2. Commandes courantes

### Consulter les logs

```bash
# Logs du backend (100 dernieres lignes, mode follow)
docker logs math-correction-backend-1 --tail=100 -f

# Logs du worker Celery
docker logs math-correction-worker-1 --tail=100 -f

# Logs de l'ingestor RAG
docker logs compose-ingestor-1 --tail=100 -f
```

### Redemarrer des services

```bash
# Redemarrer backend et worker
docker compose -f docker-compose.labomaths.yml restart backend worker

# Redemarrer toute la stack
docker compose -f docker-compose.labomaths.yml restart
```

### Migration de base de donnees

```bash
# Appliquer les migrations Alembic
docker compose -f docker-compose.labomaths.yml exec backend alembic upgrade head

# Verifier l'etat des migrations
docker compose -f docker-compose.labomaths.yml exec backend alembic current
```

### Backup de la base de donnees

```bash
bash scripts/backup-db.sh
```

---

## 3. Diagnostic des problemes

### Le endpoint /health/ready retourne `rag: ok=false`

1. **Verifier la variable d'environnement** : `RAG_HTTP_BASE_URL` doit pointer vers `http://compose-ingestor-1:8001`
2. **Verifier la connectivite reseau interne** :
   ```bash
   docker compose -f docker-compose.labomaths.yml exec backend \
     python -c "import httpx; print(httpx.get('http://compose-ingestor-1:8001/health').status_code)"
   ```
3. **Verifier que la stack RAG tourne** :
   ```bash
   docker ps --filter "name=compose-ingestor" --filter "name=compose-chroma" --filter "name=compose-ollama"
   ```
4. **Verifier que les deux stacks partagent le reseau** :
   ```bash
   docker network inspect compose_rag_ui_net
   ```

### Grading lent

1. **Verifier la latence OpenAI** : les appels au LLM representent la majorite du temps de grading
2. **Consulter les logs du worker** pour identifier les etapes lentes :
   ```bash
   docker logs math-correction-worker-1 --tail=200 | grep -i "duration\|elapsed\|slow"
   ```
3. **Verifier la charge du worker** : si le nombre de taches en file d'attente augmente, envisager de scaler les workers

### OCR en echec

1. **Verifier les credits Mathpix** : se connecter au dashboard Mathpix et verifier le quota restant
2. **Verifier les credits Azure** (si utilise comme provider OCR)
3. **Fallback automatique** : le systeme bascule sur OpenAI Vision en cas d'echec des providers principaux. Verifier que la cle API OpenAI est valide et que le quota n'est pas epuise.
4. **Consulter les logs** :
   ```bash
   docker logs math-correction-backend-1 --tail=200 | grep -i "ocr\|mathpix\|vision"
   ```

---

## 4. Monitoring

### Logs structures

- Format : JSON structure
- Niveau par defaut : `LOG_LEVEL=INFO`
- Pour activer le mode debug temporairement, modifier la variable d'environnement et redemarrer :
  ```bash
  # Dans le fichier .env
  LOG_LEVEL=DEBUG
  docker compose -f docker-compose.labomaths.yml restart backend worker
  ```

### Metriques a surveiller

| Metrique | Description | Seuil d'alerte |
|----------|-------------|-----------------|
| Taux `audit_passed` | Pourcentage de corrections validees par l'audit | < 80% |
| Taux `needs_human_review` | Pourcentage de copies necessitant une relecture humaine | > 30% |
| Latence `/grade` | Temps de reponse du endpoint de correction | > 60s |

### Futur (non encore deploye)

- **Sentry** : capture des erreurs et exceptions en production
- **Prometheus** : collecte de metriques applicatives et infrastructure

---

## 5. Procedures de maintenance

### Rotation des logs

Les logs Docker s'accumulent sur le disque. Configurer la rotation dans `/etc/docker/daemon.json` :

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
```

Redemarrer le daemon Docker apres modification :

```bash
sudo systemctl restart docker
```

### Rotation des backups

- Les backups sont stockes dans `scripts/backups/` (ou le repertoire configure)
- Conserver les 7 derniers backups quotidiens et les 4 derniers backups hebdomadaires
- Automatiser la purge via cron :
  ```bash
  # Supprimer les backups de plus de 30 jours
  find /chemin/vers/backups -name "*.sql.gz" -mtime +30 -delete
  ```

### Mise a jour de l'application

```bash
# 1. Recuperer les derniers changements
git pull origin main

# 2. Deployer avec le script
bash scripts/deploy_server.sh
```

Le script `deploy_server.sh` gere :
- La reconstruction des images Docker
- L'application des migrations
- Le redemarrage des services
