"""
Test runner script for the handyman platform.
Provides a cross-platform way to run tests.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def run_command(cmd, description):
    """Run a command and report status."""
    print(f"\n{'='*60}")
    print(f"Running: {description}")
    print(f"{'='*60}\n")
    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"\n❌ FAILED: {description}")
        return False
    print(f"\n✅ PASSED: {description}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Test runner for handyman platform",
    )
    
    parser.add_argument(
        "command",
        choices=[
            "all",
            "unit",
            "integration",
            "failure",
            "intervals",
            "idempotency",
            "rabbit",
            "booking",
            "coverage",
            "coverage-html",
            "watch",
        ],
        help="Test command to run",
    )
    
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    
    args = parser.parse_args()

    pytest_base = "pytest"
    if args.verbose:
        pytest_base += " -vv -s"
    else:
        pytest_base += " -v"
    
    commands = {
        "all": (f"{pytest_base} tests/", "All tests"),
        "unit": (f"{pytest_base} tests/unit/", "Unit tests"),
        "integration": (f"{pytest_base} tests/integration/", "Integration tests"),
        "failure": (f"{pytest_base} tests/failure_mode/", "Failure-mode tests"),
        "intervals": (f"{pytest_base} -m intervals", "Interval overlap tests"),
        "idempotency": (f"{pytest_base} -m idempotency", "Idempotency tests"),
        "rabbit": (f"{pytest_base} -m rabbit", "RabbitMQ consumer tests"),
        "booking": (f"{pytest_base} -m booking_lifecycle", "Booking lifecycle tests"),
        "coverage": (
            f"{pytest_base} tests/ --cov=services --cov=shared --cov-report=term-missing",
            "Tests with coverage",
        ),
        "coverage-html": (
            f"{pytest_base} tests/ --cov=services --cov=shared --cov-report=html --cov-report=term",
            "Tests with HTML coverage report",
        ),
        "watch": ("ptw tests/ -- -v", "Tests in watch mode"),
    }
    
    cmd, description = commands[args.command]
    
    success = run_command(cmd, description)
    
    if args.command == "coverage-html":
        print("\n📊 Coverage report generated in htmlcov/index.html")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
