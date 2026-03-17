try:
    from .src.JobOracle.report_writer import *  # type: ignore
except ImportError:
    from src.JobOracle.report_writer import *  # type: ignore
