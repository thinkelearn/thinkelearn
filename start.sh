#!/bin/bash

# THINK eLearn Development Container Manager
# Manages Docker containers for the Django/Wagtail eLearning platform

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

# Core Docker services used throughout this script
CORE_SERVICES=(web db redis celery pgadmin mailpit minio)

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."

    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        print_error "Please install Docker: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check for Docker Compose (support both V1 `docker-compose` and V2 `docker compose`)
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed or not available via Docker CLI"
        print_error "Please install Docker Compose: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Check if Docker daemon is running
    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running"
        print_error "Please start Docker and try again"
        exit 1
    fi

    print_success "All dependencies are available"
}

# Function to show usage
show_usage() {
    echo "THINK eLearn Development Container Manager"
    echo ""
    echo "Usage: $0 [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  start     Start all development containers (default)"
    echo "  setup     Start containers and run full initial setup (admin + pages)"
    echo "  stop      Stop all running containers"
    echo "  reset     Stop containers and clean up Docker resources (preserves database)"
    echo "  clean     Stop containers and clean up everything (⚠️  REMOVES DATABASE)"
    echo "  rebuild   Stop containers, clean up, and rebuild from scratch"
    echo "  status    Show status of all containers"
    echo "  logs      Show logs from all containers"
    echo "  help      Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                # Start development environment"
    echo "  $0 start          # Start development environment"
    echo "  $0 setup          # Start + create admin user + setup pages"
    echo "  $0 stop           # Stop all containers"
    echo "  $0 reset          # Clean up Docker issues, keep database"
    echo "  $0 clean          # ⚠️  DANGER: Removes all data including database"
    echo "  $0 rebuild        # Full rebuild and restart"
}

# Function to start containers
start_containers() {
    print_status "Starting THINK eLearn development environment..."
    echo ""
    echo -e "${BLUE}████████╗██╗  ██╗██╗███╗   ██╗██╗  ██╗    ███████╗██╗     ███████╗ █████╗ ██████╗ ███╗   ██╗${NC}"
    echo -e "${BLUE}╚══██╔══╝██║  ██║██║████╗  ██║██║ ██╔╝    ██╔════╝██║     ██╔════╝██╔══██╗██╔══██╗████╗  ██║${NC}"
    echo -e "${BLUE}   ██║   ███████║██║██╔██╗ ██║█████╔╝     █████╗  ██║     █████╗  ███████║██████╔╝██╔██╗ ██║${NC}"
    echo -e "${BLUE}   ██║   ██╔══██║██║██║╚██╗██║██╔═██╗     ██╔══╝  ██║     ██╔══╝  ██╔══██║██╔══██╗██║╚██╗██║${NC}"
    echo -e "${BLUE}   ██║   ██║  ██║██║██║ ╚████║██║  ██╗    ███████╗███████╗███████╗██║  ██║██║  ██║██║ ╚████║${NC}"
    echo -e "${BLUE}   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝    ╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝${NC}"
    echo ""

    # Clean up any orphaned networks first
    print_status "Cleaning up any orphaned Docker networks..."
    docker network prune -f > /dev/null 2>&1 || true

    # Start main services
    print_status "Starting web server, database, Redis, Celery, pgAdmin, Mailpit, and MinIO..."
    docker-compose up -d "${CORE_SERVICES[@]}"

    # Resolve STRIPE_SECRET_KEY the same way docker-compose does (.env + env).
    local stripe_key
    stripe_key="$(docker-compose config 2>/dev/null | grep -m1 '^ *STRIPE_SECRET_KEY:' | cut -d':' -f2-)"
    stripe_key="${stripe_key//\"/}"
    stripe_key="$(echo "${stripe_key}" | tr -d '[:space:]')"

    if [[ -n "${stripe_key}" ]]; then
        print_status "Starting Stripe CLI webhook forwarder..."
        docker-compose --profile stripe up -d stripe
        print_success "Stripe CLI container started"
    else
        print_warning "Stripe container skipped (set STRIPE_SECRET_KEY to enable Stripe testing)"
    fi

    # Start CSS build process
    print_status "Starting Tailwind CSS build process..."
    docker-compose up -d css

    print_success "All containers started successfully!"

    # Run initial database setup
    print_status "Running initial database setup..."
    docker-compose exec -T web python manage.py migrate

    echo ""
    print_status "Development environment is ready:"
    echo "  🌐 Web application: http://localhost:8000"
    echo "  📝 Wagtail Admin (CMS): http://localhost:8000/admin/"
    echo "  ⚙️  Django Admin (System): http://localhost:8000/django-admin/"
    echo "  📧 Mailpit (email testing): http://localhost:8025"
    echo "  🗄️  pgAdmin (database): http://localhost:5050"
    echo "  📊 Database: postgres://postgres:postgres@localhost:5432/thinkelearn"
    echo "  🧰 Redis: redis://localhost:6379/0"
    echo "  🪣 MinIO (S3 storage): http://localhost:9001"
    echo "  🎨 CSS: Tailwind is watching for changes"
    if [[ -n "${stripe_key}" ]]; then
        echo "  💳 Stripe webhook forwarder: docker-compose logs -f stripe"
    fi
    echo ""
    print_status "Admin interfaces:"
    echo "  📝 Wagtail Admin - Content management, pages, media"
    echo "  ⚙️  Django Admin - User management, communications, system data"
    echo ""
    print_status "Credentials for pgAdmin:"
    echo "  Email: admin@thinkelearn.com"
    echo "  Password: admin"
    echo ""
    print_status "Credentials for MinIO:"
    echo "  Username: minioadmin"
    echo "  Password: minioadmin"
    echo ""
    print_status "Use 'docker-compose logs -f' to view logs"
    print_status "Use '$0 stop' to stop all containers"
}

# Function to run full setup (start + admin + pages)
setup_environment() {
    print_status "Setting up complete THINK eLearn development environment..."

    # Start containers first
    start_containers

    # Create admin user
    print_status "Creating admin user..."
    print_status "Using defaults: admin / admin@thinkelearn.com / defaultpassword123"
    docker-compose exec -T web python manage.py create_admin --reset

    # Setup initial pages
    print_status "Setting up core pages (About, Contact, Blog, Portfolio, LMS)..."
    docker-compose exec -T web python manage.py setup_pages
    docker-compose exec -T web python manage.py setup_portfolio
    docker-compose exec -T web python manage.py setup_lms

    echo ""
    print_success "🎉 Complete setup finished!"
    print_status "You can now log in to both admin interfaces with:"
    echo "  👤 Username: admin"
    echo "  🔒 Password: defaultpassword123"
    echo ""
    print_status "Admin interfaces:"
    echo "  📝 Wagtail Admin (CMS): http://localhost:8000/admin/"
    echo "  ⚙️  Django Admin (System): http://localhost:8000/django-admin/"
    echo ""
    print_status "💡 Tip: Change the admin password after first login!"
}

# Function to stop containers
stop_containers() {
    print_status "Stopping all containers..."
    # Remove profile-started services (e.g., Stripe) as orphans too.
    docker-compose down --remove-orphans
    print_success "All containers stopped"
}

# Function to reset (clean without removing volumes)
reset_containers() {
    print_status "Resetting containers (preserving database)..."

    # Stop all services but keep volumes
    docker-compose down --remove-orphans

    print_status "Cleaning up Docker networks..."
    docker network prune -f

    print_status "Pruning unused Docker resources..."
    docker system prune -f

    print_success "Reset completed - database preserved"
}

# Function to clean up (including volumes)
clean_containers() {
    print_warning "⚠️  WARNING: This will permanently delete your database and all data!"
    print_status "Stopping and cleaning up containers..."

    # Stop all services AND remove volumes
    docker-compose down --volumes --remove-orphans

    print_status "Cleaning up Docker networks..."
    docker network prune -f

    print_status "Pruning unused Docker resources..."
    docker system prune -f

    print_success "Full cleanup completed - database removed"
}

# Function to rebuild everything
rebuild_containers() {
    print_status "Rebuilding development environment from scratch..."

    # Stop everything
    print_status "Stopping all containers..."
    docker-compose down --volumes --remove-orphans

    # Remove images
    print_status "Removing existing images..."
    if ! docker-compose down --rmi all; then
        print_warning "Failed to remove Docker images during rebuild. Proceeding, but some old images may remain. Run 'docker images' to check and 'docker-compose down --rmi all' to clean up manually."
    fi

    # Rebuild and start
    print_status "Rebuilding images..."
    docker-compose build --no-cache

    print_status "Starting rebuilt containers..."
    start_containers
}

# Function to show container status
show_status() {
    print_status "Container status:"
    docker-compose ps
}

# Function to show logs
show_logs() {
    print_status "Showing logs from all containers (Ctrl+C to exit):"
    docker-compose logs -f
}

# Main script logic
case "${1:-start}" in
    "start")
        check_dependencies
        start_containers
        ;;
    "setup")
        check_dependencies
        setup_environment
        ;;
    "stop")
        stop_containers
        ;;
    "reset")
        reset_containers
        ;;
    "clean")
        clean_containers
        ;;
    "rebuild")
        check_dependencies
        rebuild_containers
        ;;
    "status")
        show_status
        ;;
    "logs")
        show_logs
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        print_error "Unknown command: $1"
        echo ""
        show_usage
        exit 1
        ;;
esac
