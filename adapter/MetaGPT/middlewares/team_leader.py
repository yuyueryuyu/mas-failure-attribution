from adapter.middleware import Middleware
from monitor.base_monitor import RoleType


class TeamLeaderMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def before(self, ctx):
        name = ctx.instance.profile
        dst = ctx.args[1]
        msg = ctx.args[0]
        if self.monitor is not None:
            coding_content = f"{name} sends to {dst}: {msg}"
            self.monitor.record_step(coding_content, name, RoleType.ASSISTANT)