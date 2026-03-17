try:
    from .src.JobOracle.agents import *  # type: ignore
except ImportError:
    from src.JobOracle.agents import *  # type: ignore
