
import time
import asyncio
from functools import wraps
from utils.logger import logger

class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    async def call(self, func, *args, **kwargs):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise CircuitBreakerOpen("Circuit breaker is OPEN. API requests are paused.")
        
        try:
            result = await func(*args, **kwargs)
            
            if self.state == "HALF_OPEN":
                self.state = "CLOSED"
                self.failures = 0
                logger.info("Circuit breaker closed (recovered)")
            elif self.state == "CLOSED" and self.failures > 0:
                self.failures = 0
                
            return result
            
        except Exception as e:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                self.state = "OPEN"
                logger.warning(f"Circuit breaker opened after {self.failures} failures. Pausing requests for {self.recovery_timeout}s")
            
            raise e

# Decorator for easy usage
def circuit_breaker(cb_instance):
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await cb_instance.call(func, *args, **kwargs)
        return wrapper
    return decorator

# Global instance for YouTube API
youtube_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
