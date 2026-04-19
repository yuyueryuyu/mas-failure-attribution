from adapter.middleware import Middleware
from monitor.base_monitor import RoleType


class EngineerMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def after(self, ctx, result):
        name = ctx.instance.profile
        if self.monitor is not None:
            coding_content = f"{name} coding : {result}"
            self.monitor.record_step(coding_content, name, RoleType.ASSISTANT)
        return result