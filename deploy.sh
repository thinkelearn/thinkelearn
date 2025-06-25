#!/bin/bash

# Railway Deployment Script for THINK eLearn
# Based on Railway's Django deployment guide: https://docs.railway.com/guides/django

echo "🚀 Deploying THINK eLearn to Railway..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed. Please install it first:"
    echo "npm install -g @railway/cli"
    exit 1
fi

# Check if logged in
if ! railway whoami &> /dev/null; then
    echo "❌ Please login to Railway first:"
    echo "railway login"
    exit 1
fi

echo "📝 Current project status:"
railway status

echo ""
echo "🗄️  Since you already have a PostgreSQL database, we'll deploy the Django app as a new service."

echo ""
echo "📝 To deploy your Django app, run these commands interactively:"
echo ""
echo "1. railway login  # (if not already logged in)"
echo "2. railway link   # Link to your existing project"
echo "3. railway up     # Deploy the Django application"
echo ""
echo "4. After deployment, set environment variables:"
echo "   railway variables --set SECRET_KEY=YUvf_Gn1m-3y4aTtPqElbH_RwlaykFvmDepV_vG8-njQZ_mFt9s8AViElVQpoWl6YWc"
echo ""
echo "5. Create a superuser:"
echo "   railway run python manage.py createsuperuser"
echo ""
echo "📱 The DATABASE_URL will be automatically provided by your PostgreSQL service"
echo "🔧 Your app will be available at the Railway-provided URL"

echo ""
echo "🚀 Attempting to deploy now..."
railway up