# Railway CLI Commands Reference

## Quick Start: SSH into Deployed Service

**IMPORTANT**: Use this workflow to run Django management commands in the deployed Railway environment.

```bash
# 1. Link to your project (only need to do this once)
railway link -p thinkelearn -s web -e production
# OR use interactive mode:
railway link

# 2. SSH into the deployed service
railway ssh

# 3. Inside the Railway SSH session, run Django commands with uv:
uv run python manage.py createsuperuser
uv run python manage.py setup_lms --with-categories --with-tags
uv run python manage.py setup_portfolio
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput

# 4. Exit SSH session
exit
```

**Why `uv run`?** Railway uses `uv` to manage dependencies in a virtual environment. You MUST prefix Python commands with `uv run` to access installed packages.

**Common Mistake**: Don't use `railway run python manage.py <command>` - this runs on your LOCAL machine and can't connect to Railway's internal database (`postgres.railway.internal`). Always use `railway ssh` first, THEN run commands inside the SSH session.

## Project Management

```bash
# Login to Railway
railway login

# Link to existing project (interactive)
railway link
# OR link with specific parameters
railway link -p thinkelearn -s web -e production

# Initialize new project
railway init

# Show project status
railway status
railway status --json  # JSON output

# Deploy current directory
railway up
railway up --detach  # Deploy in background
```

## Service Management

```bash
# List all services (interactive)
railway service

# Switch to specific service
railway service <service-name>
railway service web
railway service Postgres

# Check current service context
railway status
```

## Database Management

```bash
# Add new database
railway add --database postgres
railway add --database mysql
railway add --database redis
railway add --database mongo

# Connect to database (opens shell)
railway connect

# Run database commands
railway run psql  # PostgreSQL
railway run mysql  # MySQL
```

## Environment Variables

```bash
# View all variables for current service
railway variables

# Set variable
railway variables --set "KEY=value"
railway variables --set "DATABASE_URL=postgresql://user:pass@host:port/db"
railway variables --set "REDIS_URL=redis://:password@host:port/0"

# Remove variable
railway variables --remove KEY
```

## Deployments

```bash
# View deployment logs
railway logs
railway logs --tail  # Follow logs

# Redeploy service
railway redeploy

# Open service in browser
railway open
```

## SSH Access (Recommended for Django Commands)

```bash
# SSH into deployed service
railway ssh

# SSH with specific service/environment
railway ssh -s web -e production

# SSH into a specific deployment instance
railway ssh -d <deployment-instance-id>

# SSH with tmux session (persists across disconnections)
railway ssh --session

# Run a single command and exit
railway ssh "uv run python manage.py check"
```

**Use SSH for**:

- Running Django management commands
- Debugging production issues
- Checking logs in real-time
- Inspecting the deployed environment

## Local Development

```bash
# ⚠️  CAUTION: railway run downloads Railway env vars but runs LOCALLY
# This ONLY works for commands that don't need database access
railway run <command>
railway run npm start

# Shell with Railway environment variables (still local)
railway shell

# ❌ DON'T USE for Django commands (database won't be accessible):
# railway run python manage.py migrate  # FAILS - can't reach Railway's internal DB

# ✅ DO USE railway ssh instead:
railway ssh
uv run python manage.py migrate  # Works - runs in Railway environment
```

## Volume Management

```bash
# List volumes
railway volumes

# Create volume
railway volumes create --name <name> --mount-path <path>
```

## Common Django + Railway Workflows

### Initial Setup

```bash
# 1. Link project
railway link

# 2. Add PostgreSQL database
railway add --database postgres

# 3. Add Redis
railway add --database redis

# 4. Set environment variables
railway variables --set "SECRET_KEY=your-secret-key"
railway variables --set "DEBUG=False"
railway variables --set "REDIS_URL=redis://:password@host:port/0"

# 4. Deploy
railway up
```

### Celery Worker Service

Use a separate Railway service for background tasks:

1. Duplicate the web service in Railway and name it `worker`.
2. Set the start command to: `celery -A thinkelearn worker -l info`.
3. Ensure the worker has the same env vars as web, including `REDIS_URL`.

### Database Setup

```bash
# 1. Link to your project
railway link -p thinkelearn -s web -e production

# 2. SSH into the web service
railway ssh

# 3. Inside SSH session, run migrations and setup
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py setup_lms --with-categories --with-tags
```

**Note**: DATABASE_URL is automatically set by Railway when you add a PostgreSQL database service. You don't need to manually configure it.

### Troubleshooting

```bash
# Check deployment logs
railway logs

# Check service status
railway status

# Redeploy if needed
railway redeploy

# Connect to database directly
railway service Postgres
railway connect
```

### Environment Management

```bash
# Switch environments
railway environment production
railway environment staging

# Create new environment
railway environment create <name>
```

## Tips

1. **Service Context**: Always check `railway status` to see which service you're currently connected to
2. **Variables**: Database variables are automatically created when adding a database service
3. **Linking**: Railway automatically links services in the same project
4. **Logs**: Use `railway logs --tail` during deployments to watch for issues
5. **JSON Output**: Add `--json` to most commands for programmatic usage

## Common Issues

### Database Connection

- Ensure DATABASE_URL is set in the web service, not just the database service
- Wait for database service to fully deploy before running migrations
- Use `postgres.railway.internal` hostname for internal connections

### Environment Variables

- Variables are service-specific, not project-wide
- Switch to correct service before setting variables
- Railway automatically generates database connection variables

### Deployments

- Use `railway up --detach` for background deployments
- Check logs with `railway logs` if deployment fails
- Database services can take 2-3 minutes to fully initialize
