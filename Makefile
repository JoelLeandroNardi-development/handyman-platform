.PHONY: help test test-unit test-integration test-failure test-cov test-cov-html test-watch install-test-deps

help:

install-test-deps:
	pip install -r requirements-test.txt

test:
	pytest tests/ -v

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

test-failure:
	pytest tests/failure_mode/ -v --tb=short

test-intervals:
	pytest -m intervals -v

test-idempotency:
	pytest -m idempotency -v

test-rabbit:
	pytest -m rabbit -v

test-booking:
	pytest -m booking_lifecycle -v

test-cov:
	pytest tests/ --cov=services --cov=shared --cov-report=term-missing -v

test-cov-html:
	pytest tests/ --cov=services --cov=shared --cov-report=html --cov-report=term -v
	@if command -v xdg-open > /dev/null; then \
		xdg-open htmlcov/index.html; \
	elif command -v open > /dev/null; then \
		open htmlcov/index.html; \
	fi

test-watch:
	ptw tests/ -- -v

test-verbose:
	pytest tests/ -vv -s

test-fast:
	pytest tests/ -m "not slow" -v

test-specific:
	@echo "Usage: make test-specific TEST=tests/unit/test_intervals.py::TestOverlaps::test_overlaps_partial_overlap"
	pytest $(TEST) -v

install-all-deps:
	pip install -r requirements-test.txt
	cd services/auth-service && pip install -r requirements.txt && cd ../..
	cd services/booking-service && pip install -r requirements.txt && cd ../..
	cd services/availability-service && pip install -r requirements.txt && cd ../..
	cd services/handyman-service && pip install -r requirements.txt && cd ../..
	cd services/match-service && pip install -r requirements.txt && cd ../..
	cd services/user-service && pip install -r requirements.txt && cd ../..
	cd services/gateway-service && pip install -r requirements.txt && cd ../..
	cd shared && pip install -e ".[test]" && cd ..
	@echo "All dependencies installed!"

test-docker:
	docker-compose up -d postgres redis rabbitmq
	sleep 5
	pytest tests/ -v
	docker-compose down

quality: test-cov
	@echo "Running linting (if configured)..."
	@echo "Test quality check complete!"
