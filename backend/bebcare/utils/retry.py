import time
import functools
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple = (Exception,),
    logger_name: str = None
):
    """
    带指数退避的重试装饰器
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        exceptions: 需要重试的异常类型
        logger_name: 日志记录器名称
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    log = logging.getLogger(logger_name) if logger_name else logger
                    log.warning(f"Attempt {attempt + 1}/{max_retries} failed: {str(e)[:100]}...")
                    
                    if attempt < max_retries - 1:
                        log.info(f"Retrying in {delay:.2f} seconds...")
                        time.sleep(delay)
                        delay *= backoff_factor
            
            log.error(f"All {max_retries} attempts failed. Last error: {str(last_exception)[:200]}")
            raise last_exception
        
        return wrapper
    return decorator
