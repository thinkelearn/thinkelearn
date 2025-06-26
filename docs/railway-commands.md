# Railway CLI Commands Reference

## Project Management

```bash
# Login to Railway
railway login

# Link to existing project
railway link

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

## Local Development

```bash
# Run command with Railway environment
railway run <command>
railway run python manage.py migrate
railway run npm start

# Shell with Railway environment
railway shell
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

# 3. Set environment variables
railway variables --set "SECRET_KEY=your-secret-key"
railway variables --set "DEBUG=False"

# 4. Deploy
railway up
```

### Database Setup

```bash
# 1. Switch to database service to get connection details
railway service Postgres
railway variables  # Copy DATABASE_URL

# 2. Switch to web service and set DATABASE_URL
railway service web
railway variables --set "DATABASE_URL=postgresql://..."

# 3. Run migrations
railway run python manage.py migrate
railway run python manage.py createsuperuser
```

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
