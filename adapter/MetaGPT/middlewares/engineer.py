"""Middleware hooks for capturing and optionally injecting engineer outputs."""

from adapter.middleware import Middleware
from monitor.base_monitor import RoleType
from utils.logging import logger

class EngineerMiddleware(Middleware):
    """Record engineer coding outputs and apply injection at target step."""

    def __init__(self, monitor):
        """Bind monitor used for step recording and injection checks."""
        self.monitor = monitor
    
    def after(self, ctx, result):
        """Post-process engineer output before it is returned to caller."""
        name = ctx.instance.profile
        if self.monitor is not None:
            coding_content = f"{name} coding : {result}"
            if self.monitor.should_inject():
                logger.info(f'Injection step detected, injecting...')
                coding_content = self.monitor.get_injection_content()
                result = coding_content
            self.monitor.record_step(coding_content, name, RoleType.ASSISTANT)
        return result