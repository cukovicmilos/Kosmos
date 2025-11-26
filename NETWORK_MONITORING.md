# Network Monitoring & Timeout Configuration

## Overview

This document describes the network monitoring and timeout configuration features implemented to improve bot reliability and detect network issues with Telegram API.

## Features Implemented

### 1. Enhanced Timeout Configuration

**File:** `config.py`

Added configurable timeout parameters for Telegram API connections:

```python
TELEGRAM_CONNECT_TIMEOUT = 20.0s  # Connection establishment timeout (increased from default 5.0s)
TELEGRAM_READ_TIMEOUT = 30.0s     # Read timeout (increased from default 5.0s)
TELEGRAM_WRITE_TIMEOUT = 30.0s    # Write timeout (increased from default 5.0s)
TELEGRAM_POOL_TIMEOUT = 10.0s     # Connection pool timeout
```

**Benefits:**
- Reduced timeout errors on slow/unstable networks
- More tolerance for network latency spikes
- Configurable via environment variables

**Configuration:**

Add to your `.env` file:
```bash
TELEGRAM_CONNECT_TIMEOUT=20.0
TELEGRAM_READ_TIMEOUT=30.0
TELEGRAM_WRITE_TIMEOUT=30.0
TELEGRAM_POOL_TIMEOUT=10.0
```

### 2. Network Monitoring System

**File:** `network_monitor.py`

Implements real-time network health monitoring:

**Key Features:**
- Tracks successful and failed network operations
- Counts consecutive timeout errors
- Automatic alerting when threshold exceeded
- Maintains history of last 100 network events
- Calculates success rate statistics

**Usage Example:**
```python
from network_monitor import record_network_timeout, record_network_success

# Record a timeout
record_network_timeout("send_reminder_123", "Connection timed out")

# Record a success
record_network_success("send_reminder_123")

# Get statistics
stats = get_network_stats()
print(f"Success rate: {stats['success_rate']:.1%}")
```

**Alert Threshold:**

Default: 3 consecutive timeouts trigger a CRITICAL log alert.

Configure via environment variable:
```bash
MAX_CONSECUTIVE_TIMEOUTS=3
```

### 3. Network Statistics Command

**File:** `handlers/netstats.py`

New `/netstats` command for users to check network health:

**Features:**
- Shows overall success rate
- Displays total successes and timeouts
- Current consecutive timeout count
- Alert status indicator
- Last 5 network events with timestamps

**Example Output:**
```
📊 Network Statistics

Success Rate: 98.5%
Total Successes: 1247
Total Timeouts: 19
Consecutive Timeouts: 0

✅ Network Status: OK
Last Timeout: 2025-11-23 20:21:17

Recent Events (last 5):
✅ 21:22:13 - send_reminder_93
✅ 21:21:42 - pending_message_8
❌ 21:21:17 - send_reminder_93
❌ 21:20:17 - send_reminder_93
✅ 21:19:45 - send_reminder_91
```

### 4. Integration Points

**Scheduler (`scheduler.py`):**
- Records timeouts and successes when sending reminders
- Automatically tracks network health during reminder delivery

**Message Queue (`message_queue.py`):**
- Monitors retry message delivery attempts
- Records timeout events during message queue processing

## Monitoring in Action

### Normal Operation
```
[INFO] Reminder 93 sent to user 430937625
[INFO] Network recovered after 2 consecutive timeouts
```

### Alert Triggered
```
[CRITICAL] ⚠️ NETWORK ALERT: 3 consecutive timeouts detected!
Last timeout at 2025-11-23 20:21:17.
Total stats: 19 timeouts, 1247 successes.
Check network connectivity to Telegram API servers.
```

## Benefits

1. **Improved Reliability:** Longer timeouts reduce false failures on slow networks
2. **Proactive Monitoring:** Alerts administrators to network issues before they become critical
3. **Visibility:** `/netstats` command gives real-time insight into bot health
4. **Automatic Recovery:** Bot tracks when network recovers after issues
5. **Historical Tracking:** Maintains event history for debugging

## Testing

### Test Network Monitor
```bash
cd /var/www/html/kosmos
source venv/bin/activate
python3 -c "import network_monitor; print('✅ Network monitor OK')"
```

### Test Configuration
```bash
python3 -c "from config import TELEGRAM_CONNECT_TIMEOUT; print(f'Connect timeout: {TELEGRAM_CONNECT_TIMEOUT}s')"
```

### Test in Production
1. Use `/netstats` command in bot
2. Check logs for "Bot configured with timeouts" message
3. Monitor for NETWORK ALERT messages during network issues

## Log Analysis

### View Network Errors
```bash
grep -E "Network|timeout|Timed out" log/app.log | tail -50
```

### Check Alert History
```bash
grep "NETWORK ALERT" log/app.log
```

### View Success Rate
```bash
# Use /netstats command in bot for real-time stats
```

## Troubleshooting

### High Timeout Rate (>5%)
1. Check network connectivity: `ping api.telegram.org`
2. Verify DNS resolution
3. Check firewall/proxy settings
4. Consider increasing timeout values further

### False Alerts
1. Increase `MAX_CONSECUTIVE_TIMEOUTS` in `.env`
2. Check if timeouts happen during known network maintenance
3. Review timeout duration settings

### No Statistics Showing
1. Ensure bot was restarted after changes
2. Check that handlers are registered: logs should show "Network statistics handlers registered"
3. Verify `/netstats` command is available in bot menu

## Future Enhancements

Potential improvements:
- Send admin notifications via Telegram when alerts triggered
- Export statistics to external monitoring system (Prometheus, Grafana)
- Automatic timeout adjustment based on historical success rate
- Detailed per-operation timeout tracking
- Network latency measurements

## Changelog

**2025-11-23:**
- Initial implementation
- Added configurable timeouts (connect: 20s, read/write: 30s)
- Implemented network monitoring system
- Added `/netstats` command
- Integrated monitoring into scheduler and message queue
- Alert threshold: 3 consecutive timeouts

---

For questions or issues, check the main project README or review the implementation in:
- `network_monitor.py`
- `handlers/netstats.py`
- `config.py` (timeout configuration)
