"""Compatibility wrapper for the src-based JobOracle package."""

try:
    from .src.JobOracle import EmploymentAdvisor, EmploymentReport, EmploymentRequest
except ImportError:
    from src.JobOracle import EmploymentAdvisor, EmploymentReport, EmploymentRequest

__all__ = ["EmploymentAdvisor", "EmploymentReport", "EmploymentRequest"]
