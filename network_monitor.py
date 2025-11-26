"""
Network monitoring module for Kosmos Telegram Bot.
Tracks network timeouts and alerts when threshold is exceeded.
"""

import logging
from datetime import datetime
from collections import deque
from typing import Optional

from config import MAX_CONSECUTIVE_TIMEOUTS

logger = logging.getLogger(__name__)


class NetworkMonitor:
    """
    Monitors network connectivity and tracks consecutive timeout errors.
    """
    
    def __init__(self, max_consecutive_timeouts: int = MAX_CONSECUTIVE_TIMEOUTS):
        """
        Initialize network monitor.
        
        Args:
            max_consecutive_timeouts: Number of consecutive timeouts before alerting
        """
        self.max_consecutive_timeouts = max_consecutive_timeouts
        self.consecutive_timeouts = 0
        self.total_timeouts = 0
        self.total_successes = 0
        self.last_timeout_time: Optional[datetime] = None
        self.timeout_history = deque(maxlen=100)  # Keep last 100 events
        self.alert_sent = False
        
    def record_timeout(self, operation: str, error_msg: str = "") -> None:
        """
        Record a network timeout event.
        
        Args:
            operation: Name of the operation that timed out
            error_msg: Optional error message
        """
        self.consecutive_timeouts += 1
        self.total_timeouts += 1
        self.last_timeout_time = datetime.now()
        
        # Record in history
        self.timeout_history.append({
            'timestamp': self.last_timeout_time,
            'type': 'timeout',
            'operation': operation,
            'error': error_msg
        })
        
        logger.warning(
            f"Network timeout #{self.consecutive_timeouts} for '{operation}': {error_msg}"
        )
        
        # Check if we've exceeded the threshold
        if self.consecutive_timeouts >= self.max_consecutive_timeouts and not self.alert_sent:
            self._send_alert()
            
    def record_success(self, operation: str = "") -> None:
        """
        Record a successful network operation.
        
        Args:
            operation: Name of the successful operation
        """
        # If we had consecutive timeouts and now success, log recovery
        if self.consecutive_timeouts > 0:
            logger.info(
                f"Network recovered after {self.consecutive_timeouts} consecutive timeouts"
            )
            self.alert_sent = False  # Reset alert flag
            
        self.consecutive_timeouts = 0
        self.total_successes += 1
        
        # Record in history
        self.timeout_history.append({
            'timestamp': datetime.now(),
            'type': 'success',
            'operation': operation
        })
        
    def _send_alert(self) -> None:
        """
        Send an alert when consecutive timeout threshold is exceeded.
        """
        logger.critical(
            f"⚠️ NETWORK ALERT: {self.consecutive_timeouts} consecutive timeouts detected! "
            f"Last timeout at {self.last_timeout_time}. "
            f"Total stats: {self.total_timeouts} timeouts, {self.total_successes} successes. "
            f"Check network connectivity to Telegram API servers."
        )
        self.alert_sent = True
        
    def get_stats(self) -> dict:
        """
        Get current network statistics.
        
        Returns:
            Dictionary with network statistics
        """
        return {
            'consecutive_timeouts': self.consecutive_timeouts,
            'total_timeouts': self.total_timeouts,
            'total_successes': self.total_successes,
            'last_timeout_time': self.last_timeout_time,
            'alert_active': self.alert_sent,
            'success_rate': (
                self.total_successes / (self.total_successes + self.total_timeouts)
                if (self.total_successes + self.total_timeouts) > 0
                else 0.0
            )
        }
        
    def get_recent_history(self, count: int = 10) -> list:
        """
        Get recent network events.
        
        Args:
            count: Number of recent events to return
            
        Returns:
            List of recent events
        """
        history_list = list(self.timeout_history)
        return history_list[-count:] if len(history_list) > count else history_list


# Global monitor instance
_network_monitor = NetworkMonitor()


def get_network_monitor() -> NetworkMonitor:
    """
    Get the global network monitor instance.
    
    Returns:
        NetworkMonitor instance
    """
    return _network_monitor


def record_network_timeout(operation: str, error_msg: str = "") -> None:
    """
    Convenience function to record a timeout.
    
    Args:
        operation: Name of the operation that timed out
        error_msg: Optional error message
    """
    _network_monitor.record_timeout(operation, error_msg)


def record_network_success(operation: str = "") -> None:
    """
    Convenience function to record a success.
    
    Args:
        operation: Name of the successful operation
    """
    _network_monitor.record_success(operation)


def get_network_stats() -> dict:
    """
    Convenience function to get network statistics.
    
    Returns:
        Dictionary with network statistics
    """
    return _network_monitor.get_stats()
