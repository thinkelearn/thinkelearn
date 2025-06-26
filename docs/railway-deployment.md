# Railway Deployment Guide

## Required Environment Variables

Set these environment variables in your Railway project dashboard:

### Required Variables

```bash
SECRET_KEY=your-secret-key-here-make-it-long-and-random
DATABASE_URL=postgresql://... (Railway will provide this automatically)
DJANGO_SETTINGS_MODULE=thinkelearn.settings.production
```

### Optional Variables (for email functionality)

```bash
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=hello@thinkelearn.com
WAGTAILADMIN_BASE_URL=https://your-app.railway.app
```

## Deployment Steps

1. **Push your code to GitHub**:

   ```bash
   git push origin main
   ```

2. **Add PostgreSQL to Railway**:
   - Go to your Railway project dashboard
   - Click "New" → "Database" → "Add PostgreSQL"
   - Railway will automatically set DATABASE_URL

3. **Set Environment Variables**:
   - In Railway dashboard, go to your service
   - Click "Variables" tab
   - Add the required environment variables above

4. **Deploy**:
   - Railway will automatically deploy when you push to main
   - Or trigger manual deployment from the Railway dashboard

5. **Run Initial Setup** (after first deployment):

   ```bash
   # Create superuser via Railway CLI or web terminal
   python manage.py createsuperuser
   ```

## Domain Setup

To use a custom domain (thinkelearn.com):

1. In Railway dashboard, go to Settings → Domains
2. Add your custom domain
3. Update your DNS records as instructed
4. Railway will automatically provision SSL certificates

## Monitoring

- Check deployment logs in Railway dashboard
- Monitor application performance
- Set up error tracking if needed

## Database Management

- Backups are handled automatically by Railway
- Use Railway's database dashboard for monitoring
- Connect to database via Railway CLI for manual operations

## Static Files

- Static files are served by Whitenoise
- CSS is built during Docker build process
- No separate CDN needed for basic deployment
