try:
    from .src.JobOracle.cli import main
except ImportError:
    from src.JobOracle.cli import main


if __name__ == "__main__":
    main()
