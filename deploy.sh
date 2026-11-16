#!/bin/bash
set -e

echo "🚀 Starting Logforge Deployment..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[$(date +'%H:%M:%S')]${NC} $1"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# Function to check if a service is healthy
wait_for_service() {
    local service_name=$1
    local max_attempts=${2:-30}
    local attempt=1
    
    print_status "Waiting for $service_name to be healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        if docker compose -f infra/docker/compose.yml ps $service_name | grep -q "healthy"; then
            print_success "$service_name is healthy!"
            return 0
        fi
        
        echo "   Attempt $attempt/$max_attempts - $service_name not ready yet, waiting 5 seconds..."
        sleep 5
        ((attempt++))
    done
    
    print_error "$service_name failed to become healthy after $max_attempts attempts"
    return 1
}

# Function to setup Kafka topics
setup_topics() {
    print_status "Setting up Kafka topics..."
    
    # Check if Python script exists
    if [ ! -f "infra/setup_kafka_topics.py" ]; then
        print_error "Topic setup script not found: infra/setup_kafka_topics.py"
        exit 1
    fi
    
    # Run the topic setup script
    if python infra/setup_kafka_topics.py --environment development --force-recreate; then
        print_success "All topics created successfully!"
    else
        print_error "Topic setup failed!"
        exit 1
    fi
}

# Function to verify topic setup
verify_topics() {
    print_status "Verifying topic setup..."
    
    # List all topics
    echo "Current topics:"
    docker exec logforge-redpanda rpk topic list
    
    # Validate with our script
    if python infra/setup_kafka_topics.py --environment development --validate-only; then
        print_success "Topic validation passed!"
    else
        print_error "Topic validation failed!"
        exit 1
    fi
}

# Function to check prerequisites
check_prerequisites() {
    print_status "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker compose > /dev/null 2>&1; then
        print_error "Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    # Check if Python is available
    if ! command -v python > /dev/null 2>&1; then
        print_error "Python is not available. Please install Python."
        exit 1
    fi
    
    # Check if required files exist
    if [ ! -f "infra/docker/compose.yml" ]; then
        print_error "Docker Compose file not found: infra/docker/compose.yml"
        exit 1
    fi
    
    print_success "All prerequisites met!"
}

# Function to cleanup existing containers
cleanup() {
    print_status "Cleaning up existing containers..."
    docker compose -f infra/docker/compose.yml down --remove-orphans > /dev/null 2>&1 || true
    print_success "Cleanup completed!"
}

# Function to show service status
show_status() {
    print_status "Service Status:"
    docker compose -f infra/docker/compose.yml ps
}

# Function to show service URLs
show_urls() {
    echo ""
    print_success "Deployment completed successfully!"
    echo ""
    echo -e "${BLUE}🌐 Services available at:${NC}"
    echo "   API:        http://localhost:7080"
    echo "   UI:         http://localhost:3001"
    echo "   ClickHouse: http://localhost:8124"
    echo "   MinIO:      http://localhost:9004 (minio/minio123)"
    echo "   RedPanda:   http://localhost:18081"
    echo ""
    echo -e "${BLUE}📋 Created Topics:${NC}"
    docker exec logforge-redpanda rpk topic list
}

# Main deployment function
main() {
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                    🚀 LOGFORGE DEPLOYMENT                    ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
    echo ""
    
    # Check prerequisites
    check_prerequisites
    
    # Cleanup any existing containers
    cleanup
    
    # Step 1: Start infrastructure services
    print_status "Starting infrastructure services..."
    docker compose -f infra/docker/compose.yml up -d clickhouse minio redpanda
    
    # Step 2: Wait for services to be healthy
    wait_for_service "clickhouse" 60
    wait_for_service "minio" 60  
    wait_for_service "redpanda" 60
    
    # Step 3: Setup Kafka topics
    setup_topics
    
    # Step 4: Verify topics
    verify_topics
    
    # Step 5: Start application services
    print_status "Starting application services..."
    docker compose -f infra/docker/compose.yml up -d api ui
    
    # Step 6: Wait for application services
    print_status "Waiting for application services to start..."
    sleep 10
    
    # Show final status
    show_status
    show_urls
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "cleanup")
        print_status "Cleaning up all containers..."
        docker compose -f infra/docker/compose.yml down --remove-orphans -v
        print_success "Cleanup completed!"
        ;;
    "status")
        show_status
        ;;
    "topics")
        if docker ps --filter name=logforge-redpanda --filter status=running | grep -q logforge-redpanda; then
            print_status "Current topics:"
            docker exec logforge-redpanda rpk topic list
        else
            print_error "RedPanda container is not running"
        fi
        ;;
    "logs")
        service_name=${2:-api}
        print_status "Showing logs for $service_name..."
        docker compose -f infra/docker/compose.yml logs -f $service_name
        ;;
    *)
        echo "Usage: $0 [deploy|cleanup|status|topics|logs]"
        echo ""
        echo "Commands:"
        echo "  deploy   - Deploy all services (default)"
        echo "  cleanup  - Stop and remove all containers and volumes"
        echo "  status   - Show service status"
        echo "  topics   - List Kafka topics"
        echo "  logs     - Show logs for a service (default: api)"
        exit 1
        ;;
esac