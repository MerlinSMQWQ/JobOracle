try:
    from .src.JobOracle.main import main
except ImportError:
    from src.JobOracle.main import main


if __name__ == "__main__":
    main()
