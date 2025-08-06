# Docker Setup for Nagatha Assistant

This Docker Compose configuration sets up Redis and PostgreSQL with vector capabilities for the Nagatha Assistant project.

## Services

### PostgreSQL with pgvector
- **Image**: `pgvector/pgvector:pg16`
- **Port**: `5432`
- **Database**: `nagatha`
- **User**: `nagatha_user`
- **Password**: `nagatha_password`
- **Vector Extension**: Enabled with pgvector for storing and querying vector embeddings

### Redis
- **Image**: `redis:7-alpine`
- **Port**: `6379`
- **Persistence**: Enabled with AOF (Append Only File)
- **Use Case**: Caching, session storage, and real-time data

## Getting Started

1. **Start the services**:
   ```bash
   docker-compose up -d
   ```

2. **Check service status**:
   ```bash
   docker-compose ps
   ```

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

4. **Stop the services**:
   ```bash
   docker-compose down
   ```

## Environment Configuration

The Docker Compose setup uses environment variables from your `.env` file. Make sure your `.env` file includes these variables:

```bash
# Docker Compose Database Credentials
POSTGRES_DB=nagatha
POSTGRES_USER=nagatha_user
POSTGRES_PASSWORD=nagatha_password
POSTGRES_PORT=5432
REDIS_PORT=6379

# Application Database Configuration
DATABASE_URL=postgresql://nagatha_user:nagatha_password@localhost:5432/nagatha
REDIS_URL=redis://localhost:6379/0
```

The Docker Compose file will automatically use these environment variables, with sensible defaults if they're not set.

## Vector Database Features

The PostgreSQL setup includes:

- **pgvector extension** for vector operations
- **Sample embeddings table** with vector storage
- **Vector similarity search** with IVFFlat index
- **JSONB metadata** support for flexible data storage

### Example Vector Operations

```sql
-- Insert a vector embedding
INSERT INTO embeddings (content, embedding, metadata) 
VALUES ('sample text', '[0.1, 0.2, 0.3, ...]'::vector, '{"source": "example"}');

-- Find similar vectors using cosine similarity
SELECT content, embedding <=> '[0.1, 0.2, 0.3, ...]'::vector as distance
FROM embeddings 
ORDER BY embedding <=> '[0.1, 0.2, 0.3, ...]'::vector
LIMIT 5;
```

## Data Persistence

- **PostgreSQL data**: Stored in `postgres_data` volume
- **Redis data**: Stored in `redis_data` volume with AOF persistence

## Health Checks

Both services include health checks to ensure they're running properly:
- PostgreSQL: Uses `pg_isready`
- Redis: Uses `redis-cli ping`

## Troubleshooting

1. **Port conflicts**: If ports 5432 or 6379 are already in use, modify the `docker-compose.yml` file to use different ports.

2. **Permission issues**: Ensure Docker has proper permissions to create volumes.

3. **Vector extension not working**: Check the logs with `docker-compose logs postgres` to see if the initialization script ran successfully.

## Development

For development, you can also run individual services:

```bash
# Start only PostgreSQL
docker-compose up postgres -d

# Start only Redis
docker-compose up redis -d
``` 