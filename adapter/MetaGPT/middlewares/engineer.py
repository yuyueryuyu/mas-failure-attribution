from adapter.middleware import Middleware
from monitor.base_monitor import RoleType
from utils.logging import logger

class EngineerMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def after(self, ctx, result):
        name = ctx.instance.profile
        if self.monitor is not None:
            coding_content = f"{name} coding : {result}"
            if self.monitor.should_inject():
                logger.info(f'Injection step detected, injecting...')
                coding_content = self.monitor.get_injection_content()
                result = coding_content
            self.monitor.record_step(coding_content, name, RoleType.ASSISTANT)
        return result