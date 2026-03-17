try:
    from .src.JobOracle.models import *  # type: ignore
except ImportError:
    from src.JobOracle.models import *  # type: ignore
