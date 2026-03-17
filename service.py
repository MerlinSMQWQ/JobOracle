try:
    from .src.JobOracle.service import *  # type: ignore
except ImportError:
    from src.JobOracle.service import *  # type: ignore
