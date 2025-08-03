# Paperflow Makefile
# Simple commands for easy interaction with Paperflow

.PHONY: help install dev setup clean test run api web cli build deploy

# Default target
help:
	@echo "Paperflow - Academic Paper Website Generator"
	@echo "===========================================" 
	@echo ""
	@echo "Available commands:"
	@echo "  make install     - Install Paperflow and dependencies"
	@echo "  make dev         - Install development dependencies"
	@echo "  make setup       - Setup development environment"
	@echo "  make clean       - Clean build artifacts and cache"
	@echo ""
	@echo "Running Paperflow:"
	@echo "  make run         - Launch web configurator (port 8113)"
	@echo "  make api         - Start FastAPI backend (port 8000)" 
	@echo "  make web         - Start web configurator only"
	@echo "  make cli         - Show CLI help"
	@echo ""
	@echo "Development:"
	@echo "  make test        - Run test suite"
	@echo "  make lint        - Run code linting"
	@echo "  make format      - Format code with black"
	@echo ""
	@echo "Project commands:"
	@echo "  make init NAME=my-paper    - Create new project"
	@echo "  make build                 - Build current project"
	@echo "  make sync                  - Sync current project"
	@echo "  make deploy                - Deploy current project"
	@echo ""
	@echo "Quick start:"
	@echo "  make install && make run"

# Installation
install:
	@echo "📦 Installing Paperflow..."
	pip install -e .

dev:
	@echo "🔧 Installing development dependencies..."
	pip install -r requirements-dev.txt

setup: install dev
	@echo "🚀 Setting up development environment..."
	mkdir -p data temp uploads
	@echo "✅ Setup complete!"

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .pytest_cache/ .coverage htmlcov/
	@echo "✅ Cleanup complete!"

# Running services
run:
	@echo "🌐 Starting Paperflow web configurator..."
	@echo "Opening http://localhost:8113"
	python launch.py

api:
	@echo "🚀 Starting FastAPI backend..."
	@echo "API docs: http://localhost:8000/docs"
	cd paperflow && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

web:
	@echo "🌐 Starting web configurator..."
	cd web-configurator && python server.py

cli:
	@echo "💻 Paperflow CLI:"
	python -m paperflow.cli.main --help

# Development
test:
	@echo "🧪 Running test suite..."
	python -m pytest tests/ -v

lint:
	@echo "🔍 Running linting..."
	python -m flake8 paperflow/
	python -m mypy paperflow/

format:
	@echo "✨ Formatting code..."
	python -m black paperflow/ tests/
	python -m isort paperflow/ tests/

# Project operations
init:
	@if [ -z "$(NAME)" ]; then \
		echo "❌ Usage: make init NAME=my-paper"; \
		exit 1; \
	fi
	@echo "📝 Creating new project: $(NAME)"
	python -m paperflow.cli.main init $(NAME)

build:
	@echo "🔨 Building current project..."
	python -m paperflow.cli.main build

sync:
	@echo "🔄 Syncing current project..."
	python -m paperflow.cli.main sync

deploy:
	@echo "🚀 Deploying current project..."
	python -m paperflow.cli.main deploy

status:
	@echo "📊 Project status:"
	python -m paperflow.cli.main status

validate:
	@echo "✅ Validating current project..."
	python -m paperflow.cli.main validate

# Quick examples
example:
	@echo "📋 Creating example project..."
	make init NAME=example-paper
	cd example-paper && echo "title: My Research Paper\nabstract: This is an example abstract" > config.yaml

demo: setup example
	@echo "🎬 Running demo..."
	cd example-paper && make build && make run

# Development server with hot reload
dev-server:
	@echo "🔄 Starting development server with hot reload..."
	python -m uvicorn paperflow.api.main:app --reload --host 0.0.0.0 --port 8000 &
	cd web-configurator && python server.py &
	@echo "🌐 API: http://localhost:8000"
	@echo "🌐 Web: http://localhost:8113"

# Installation verification
verify:
	@echo "🔍 Verifying Paperflow installation..."
	@python -c "import paperflow; print('✅ Paperflow package imported successfully')"
	@python -c "from paperflow.config.settings import Settings; print('✅ Settings module working')"
	@python -c "from paperflow.services.project_service import ProjectService; print('✅ Services module working')"
	@echo "✅ Paperflow is ready to use!"

# Show current configuration
config:
	@echo "⚙️  Current Paperflow configuration:"
	@python -c "from paperflow.config.settings import Settings; s = Settings(); print(f'Project path: {s.project_path}'); print(f'Theme: {s.website_theme}'); print(f'Build engine: {s.build_latex_engine}')"

# Quick health check
health:
	@echo "🏥 Paperflow health check..."
	@python -c "import sys; print(f'Python: {sys.version}')"
	@python -c "import paperflow; print('✅ Paperflow: OK')"
	@which git > /dev/null && echo "✅ Git: OK" || echo "❌ Git: Not found"
	@which pdflatex > /dev/null && echo "✅ LaTeX: OK" || echo "⚠️  LaTeX: Not found (optional)"