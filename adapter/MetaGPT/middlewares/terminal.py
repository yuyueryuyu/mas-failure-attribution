"""Middleware for folding terminal output into monitor step history."""

from adapter.middleware import Middleware
from monitor.base_monitor import RoleType


class TerminalMiddleware(Middleware):
    """Capture terminal command outputs as terminal-role history entries."""

    def __init__(self, monitor):
        """Initialize middleware with a monitor instance."""
        self.monitor = monitor
    
    # Terminal response should be merged into previous step, so no injection
    def after(self, ctx, result):
        """Record terminal output and return unmodified terminal result."""
        cmd = ctx.args[0]
        terminal_content = f"Terminal output: [command]: {cmd} \n[command output] : {result}"
        if self.monitor is not None:
            self.monitor.record_step(terminal_content, "Terminal", RoleType.TERMINAL)
        return result