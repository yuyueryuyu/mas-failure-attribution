from adapter.middleware import Middleware
from monitor.base_monitor import RoleType


class TerminalMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    # Terminal response should be merged into previous step, so no injection
    def after(self, ctx, result):
        cmd = ctx.args[0]
        terminal_content = f"Terminal output: [command]: {cmd} \n[command output] : {result}"
        if self.monitor is not None:
            self.monitor.record_step(terminal_content, "Terminal", RoleType.TERMINAL)
        return result