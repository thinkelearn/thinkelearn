# Docker Development Guide

## Container Management Script

The project includes a comprehensive `start.sh` script for easy container management:

```bash
# Start development environment (containers + migrations)
./start.sh

# Complete setup (containers + migrations + admin + pages)
./start.sh setup

# Stop all containers
./start.sh stop

# Stop containers and clean up resources (preserves database)
./start.sh reset

# Stop containers and clean up everything (⚠️ REMOVES DATABASE)
./start.sh clean

# Full rebuild and restart (includes automatic migrations)
./start.sh rebuild

# Show container status
./start.sh status

# View logs from all containers
./start.sh logs

# Show help
./start.sh help
```

## Docker Commands

```bash
# Start/stop services
docker-compose up -d                    # Start in background
docker-compose down                     # Stop services
docker-compose down -v                  # Stop and remove volumes

# Django management
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py makemigrations
docker-compose exec web python manage.py collectstatic
docker-compose exec web python manage.py shell

# Database access
docker-compose exec db psql -U postgres -d thinkelearn

# View logs
docker-compose logs -f web              # Django logs
docker-compose logs -f db               # Database logs
docker-compose logs -f pgadmin          # PgAdmin logs
```

## pgAdmin Setup

pgAdmin is included in the Docker setup for easy database management and inspection.

### Accessing pgAdmin

1. **Start the services**: `docker-compose up`
2. **Open pgAdmin**: Navigate to http://localhost:5050
3. **Login credentials**:
   - Email: `admin@thinkelearn.com`
   - Password: `admin`

### Connecting to PostgreSQL Database

Once logged into pgAdmin:

1. **Add New Server**:
   - Right-click "Servers" → "Register" → "Server..."

2. **General Tab**:
   - Name: `THINK eLearn Dev` (or any descriptive name)

3. **Connection Tab**:
   - Host name/address: `db`
   - Port: `5432`
   - Maintenance database: `thinkelearn`
   - Username: `postgres`
   - Password: `postgres`

4. **Save**: Click "Save" to establish the connection

### Common pgAdmin Tasks

```sql
-- View all tables
SELECT table_name FROM information_schema.tables
WHERE table_schema = 'public';

-- Check Django migrations
SELECT * FROM django_migrations ORDER BY applied DESC;

-- View Wagtail pages
SELECT id, title, slug, path FROM wagtailcore_page;

-- Check user accounts
SELECT id, username, email, is_active, is_superuser, date_joined
FROM auth_user;
```

### Troubleshooting pgAdmin

- **Connection refused**: Ensure database service is running (`docker-compose up db`)
- **Login issues**: Use exact credentials: `admin@thinkelearn.com` / `admin`
- **Host not found**: Use `db` as hostname (Docker service name), not `localhost`
- **Port conflicts**: If port 5050 is in use, modify docker-compose.yml ports mapping
