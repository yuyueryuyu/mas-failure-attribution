"""Middleware for recording inter-role communication topology edges."""

from adapter.MetaGPT.utils import get_profile
from adapter.middleware import Middleware
from monitor.base_monitor import BaseMonitor


class ObserveMiddleware(Middleware):
    """Capture message-flow edges from role observation results."""

    def __init__(self, monitor: BaseMonitor):
        """Initialize with monitor that stores topology updates."""
        self.monitor = monitor
    
    def after(self, ctx, result):
        """Record relevant sender->receiver links after observe call."""
        news = ctx.instance.rc.news
        for n in news:
            if (n.cause_by in ctx.instance.rc.watch or 
                ctx.instance.name in n.send_to) and n.sent_from != '' and self.monitor is not None:
                self.monitor.record_topology(get_profile(n.sent_from), ctx.instance.profile)

        return result