from adapter.middleware import Middleware
from monitor.base_monitor import RoleType
from utils.logging import logger

class TeamLeaderMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def before(self, ctx):
        name = ctx.instance.profile
        dst = ctx.args[1]
        msg = ctx.args[0]
        if self.monitor is not None:
            content = f"{name} sends to {dst}: {msg}"
            if self.monitor.should_inject():
                logger.info(f'Injection step detected, injecting...')
                content = self.monitor.get_injection_content()
                ctx.args[0] = content
            self.monitor.record_step(content, name, RoleType.ASSISTANT)