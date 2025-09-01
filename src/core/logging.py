"""Logging utilities for Media Scorer"""
import logging
from pathlib import Path
from .scoring import scores_dir_for


def setup_logging(directory: Path, logger_name: str = "video_scorer_fastapi") -> logging.Logger:
    """Setup file logging for the application"""
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    
    # Setup file handler
    log_dir = scores_dir_for(directory) / ".log"
    log_file = log_dir / "video_scorer.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.info(f"Logger initialized. dir={directory}")
    
    return logger