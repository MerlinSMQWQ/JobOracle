try:
    from .src.JobOracle.llm_client import *  # type: ignore
except ImportError:
    from src.JobOracle.llm_client import *  # type: ignore
