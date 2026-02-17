"""
Rate limiter for bot commands to prevent abuse
"""
import time
from typing import Dict, List
from utils.logger import logger

class RateLimiter:
    """Simple sliding window rate limiter"""
    
    def __init__(self, rate: int, per: int):
        """
        Initialize rate limiter
        
        Args:
            rate: Maximum number of requests allowed
            per: Time period in seconds
        """
        self.rate = rate
        self.per = per
        self.requests: Dict[int, List[float]] = {}
    
    def check(self, user_id: int) -> bool:
        """
        Check if user is within rate limit
        
        Args:
            user_id: User ID to check
            
        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()
        
        # Initialize user history if needed
        if user_id not in self.requests:
            self.requests[user_id] = []
        
        # Remove old requests outside the window
        self.requests[user_id] = [
            t for t in self.requests[user_id] 
            if now - t < self.per
        ]
        
        # Check against limit
        if len(self.requests[user_id]) >= self.rate:
            logger.warning(f"Rate limit exceeded for user {user_id}")
            return False
        
        # Record new request
        self.requests[user_id].append(now)
        return True

# Pre-configured limiters
# 5 play commands per minute per user
play_limiter = RateLimiter(rate=5, per=60)

# 10 control commands (skip, stop, etc) per minute
control_limiter = RateLimiter(rate=10, per=60)
