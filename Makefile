# Logforge Makefile
.PHONY: help up down logs build clean seed-demo test-log health

# Default target
help:
	@echo "Logforge Development Commands:"
	@echo "  make up          - Start all services"
	@echo "  make down        - Stop all services"
	@echo "  make logs        - Show service logs"
	@echo "  make build       - Build all containers"
	@echo "  make clean       - Clean up containers and volumes"
	@echo "  make seed-demo   - Seed demo data"
	@echo "  make test-log    - Send a test log entry"
	@echo "  make health      - Check system health"

# Start all services
up:
	@echo "🚀 Starting Logforge services..."
	docker compose -f infra/docker/compose.yml up -d
	@echo "✅ Services started! Access UI at http://localhost:3001"

# Stop all services
down:
	@echo "🛑 Stopping Logforge services..."
	docker compose -f infra/docker/compose.yml down

# Show logs
logs:
	docker compose -f infra/docker/compose.yml logs -f

# Build containers
build:
	@echo "🔨 Building Logforge containers..."
	docker compose -f infra/docker/compose.yml build

# Clean up
clean:
	@echo "🧹 Cleaning up containers and volumes..."
	docker compose -f infra/docker/compose.yml down -v
	docker system prune -f

# Seed demo data
seed-demo:
	@echo "🌱 Seeding demo data..."
	@for i in $$(seq 1 10); do \
		curl -X POST http://localhost:7080/v1/ingest/logs \
			-H 'Content-Type: application/json' \
			-d "{\"service\":\"demo-app\",\"level\":\"info\",\"msg\":\"Demo log entry $$i\",\"trace_id\":\"demo-$$i\",\"attrs\":{\"iteration\":$$i}}"; \
		sleep 0.5; \
	done
	@echo "\n✅ Demo data seeded!"

# Send a test log
test-log:
	@echo "📝 Sending test log..."
	curl -X POST http://localhost:7080/v1/ingest/logs \
		-H 'Content-Type: application/json' \
		-d '{"service":"test","level":"info","msg":"Test log from Makefile","trace_id":"test-'$$(date +%s)'","attrs":{"source":"makefile"}}'
	@echo "\n✅ Test log sent!"

# Check system health
health:
	@echo "🏥 Checking system health..."
	curl -s http://localhost:7080/health | python3 -m json.tool || echo "API not responding"