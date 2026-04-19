from adapter.MetaGPT.utils import get_profile
from adapter.middleware import Middleware
from monitor.base_monitor import BaseMonitor


class ObserveMiddleware(Middleware):
    def __init__(self, monitor: BaseMonitor):
        self.monitor = monitor
    
    def after(self, ctx, result):
        news = ctx.instance.rc.news
        for n in news:
            if (n.cause_by in ctx.instance.rc.watch or 
                ctx.instance.name in n.send_to) and n.sent_from != '':
                self.monitor.record_topology(get_profile(n.sent_from), ctx.instance.profile)

        return result