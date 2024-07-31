COVERAGE=poetry run pytest --cov=src/audit_alembic tests/ --cov-branch --cov-report=

.PHONY: help

help: ## Display the available options
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST)  | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

test: ## Run the tests
	poetry run pytest -vv
cov: ## Run unit tests with human-readable HMTL coverage report
	${COVERAGE}html

cov-json: ## Report coverage as json for validation in pipeline
	${COVERAGE}json

lint: ## Run linting
	ruff format
	ruff check --fix

all: help
