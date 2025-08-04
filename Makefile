.PHONY: start setup stop reset clean rebuild status logs help

# Default target
.DEFAULT_GOAL := start

# Start all development containers (default)
start:
	@./start.sh start

# Start containers and run full initial setup (admin + pages)
setup:
	@./start.sh setup

# Stop all running containers
stop:
	@./start.sh stop

# Stop containers and clean up Docker resources (preserves database)
reset:
	@./start.sh reset

# Stop containers and clean up everything (⚠️  REMOVES DATABASE)
clean:
	@./start.sh clean

# Stop containers, clean up, and rebuild from scratch
rebuild:
	@./start.sh rebuild

# Show status of all containers
status:
	@./start.sh status

# Show logs from all containers
logs:
	@./start.sh logs

# Show help message
help:
	@./start.sh help
