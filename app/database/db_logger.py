"""Database logging service for detailed interaction tracking."""

import logging
import functools
from pathlib import Path
from datetime import datetime
from typing import Any, Callable, Optional


def get_database_log_config():
    """Get database logging configuration from settings."""
    try:
        from ..settings import Settings
        settings = Settings.load_from_yaml()
        return {
            'enabled': getattr(settings, 'enable_database_logging', True),
            'log_dir': getattr(settings, 'database_log_dir', '/app/logs'),
            'log_level': getattr(settings, 'database_log_level', 'INFO')
        }
    except Exception:
        # Fallback to defaults if settings not available
        return {
            'enabled': True,
            'log_dir': '/app/logs',
            'log_level': 'INFO'
        }


class DatabaseLogger:
    """Handles database interaction logging with daily rotation."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        # Get configuration
        config = get_database_log_config()
        
        self.enabled = config['enabled']
        self.log_dir = Path(log_dir) if log_dir else Path(config['log_dir'])
        self.log_level = getattr(logging, config['log_level'].upper(), logging.INFO)
        self.logger_name = "database_interactions"
        self._current_logger: Optional[logging.Logger] = None
        self._current_date: Optional[str] = None
        
        if self.enabled:
            # Ensure log directory exists
            self._ensure_log_directory()
    
    def _ensure_log_directory(self) -> None:
        """Create log directory if it doesn't exist."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to user home directory if we can't write to /app/logs
            fallback_dir = Path.home() / ".media_scoring" / "database_logs"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            self.log_dir = fallback_dir
            logging.getLogger(__name__).warning(
                f"Cannot write to {self.log_dir}, using fallback: {fallback_dir}"
            )
    
    def _get_current_date(self) -> str:
        """Get current date in YYYY-MM-DD format."""
        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_log_file_path(self, date: str) -> Path:
        """Get log file path for a specific date."""
        return self.log_dir / f"database_interactions_{date}.log"
    
    def _setup_daily_logger(self) -> logging.Logger:
        """Setup or get logger for current day."""
        if not self.enabled:
            return logging.getLogger('null')  # Return a null logger
            
        current_date = self._get_current_date()
        
        # If date changed, create new logger
        if self._current_date != current_date or self._current_logger is None:
            # Remove old handlers if they exist
            if self._current_logger:
                for handler in list(self._current_logger.handlers):
                    self._current_logger.removeHandler(handler)
                    handler.close()
            
            # Create new logger for current date
            logger = logging.getLogger(f"{self.logger_name}_{current_date}")
            logger.setLevel(self.log_level)
            
            # Remove any existing handlers
            for handler in list(logger.handlers):
                logger.removeHandler(handler)
                handler.close()
            
            # Create file handler for current date
            log_file = self._get_log_file_path(current_date)
            file_handler = logging.FileHandler(log_file, encoding="utf-8")
            file_handler.setLevel(self.log_level)
            
            # Create formatter with detailed information
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-5s | %(funcName)-25s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(formatter)
            
            logger.addHandler(file_handler)
            
            # Prevent propagation to root logger
            logger.propagate = False
            
            self._current_logger = logger
            self._current_date = current_date
            
            # Log the initialization
            logger.info(f"Database logger initialized for date: {current_date}")
        
        return self._current_logger
    
    def log_operation(self, operation: str, details: str = "", level: str = "INFO") -> None:
        """Log a database operation."""
        if not self.enabled:
            return
            
        logger = self._setup_daily_logger()
        log_level = getattr(logging, level.upper(), logging.INFO)
        
        message = f"DB_OP: {operation}"
        if details:
            message += f" | {details}"
        
        logger.log(log_level, message)
    
    def log_query(self, query_type: str, table: str = "", params: str = "", result_count: Optional[int] = None) -> None:
        """Log a database query."""
        if not self.enabled:
            return
            
        logger = self._setup_daily_logger()
        
        message = f"DB_QUERY: {query_type}"
        if table:
            message += f" | table={table}"
        if params:
            message += f" | params={params}"
        if result_count is not None:
            message += f" | results={result_count}"
        
        logger.info(message)
    
    def log_transaction(self, action: str, details: str = "") -> None:
        """Log database transaction actions."""
        if not self.enabled:
            return
            
        logger = self._setup_daily_logger()
        
        message = f"DB_TRANSACTION: {action}"
        if details:
            message += f" | {details}"
        
        logger.info(message)
    
    def log_error(self, operation: str, error: str) -> None:
        """Log database errors."""
        if not self.enabled:
            return
            
        logger = self._setup_daily_logger()
        logger.error(f"DB_ERROR: {operation} | error={error}")


# Global database logger instance
_db_logger = DatabaseLogger()


def log_db_operation(operation_name: str = None, log_params: bool = True, log_result: bool = True):
    """Decorator to log database operations."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Skip logging if disabled
            if not _db_logger.enabled:
                return func(*args, **kwargs)
                
            # Get operation name (use function name if not provided)
            op_name = operation_name or func.__name__
            
            # Build parameter info
            param_info = ""
            if log_params and (args or kwargs):
                param_parts = []
                # Log non-self arguments
                if args and len(args) > 1:  # Skip 'self' parameter
                    param_parts.append(f"args={args[1:]}")
                if kwargs:
                    param_parts.append(f"kwargs={kwargs}")
                param_info = " | ".join(param_parts)
            
            # Log operation start
            _db_logger.log_operation(f"START_{op_name}", param_info)
            
            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log successful completion
                result_info = ""
                if log_result and result is not None:
                    if hasattr(result, '__len__') and not isinstance(result, str):
                        result_info = f"count={len(result)}"
                    elif hasattr(result, 'id'):
                        result_info = f"id={result.id}"
                    elif isinstance(result, bool):
                        result_info = f"success={result}"
                
                _db_logger.log_operation(f"SUCCESS_{op_name}", result_info)
                return result
                
            except Exception as e:
                # Log error
                _db_logger.log_error(op_name, str(e))
                raise  # Re-raise the exception
                
        return wrapper
    return decorator