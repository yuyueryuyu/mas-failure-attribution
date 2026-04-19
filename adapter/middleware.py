import types
import inspect

class Context:
    def __init__(self, instance, args, kwargs):
        self.instance = instance
        self.args = args
        self.kwargs = kwargs


class Middleware:
    """
    Middleware class for handling function processing.

    This class provides a hook-based middleware pattern with before and after
    processing stages. Subclasses can override these methods to implement
    custom logic for intercepting and modifying function handling.

    Methods:
        before(ctx): Called before the main operation. Receives the context object.
        after(ctx, result): Called after the main operation. Receives the context 
                           object and the result, returning the (possibly modified) result.
    """
    def before(self, ctx):
        pass

    def after(self, ctx, result):
        return result

def build_llm_wrapper(func, middlewares):
    if inspect.iscoroutinefunction(func):

        async def async_wrapper(self, *args, **kwargs):
            ctx = Context(self, args, kwargs)

            for m in middlewares:
                m.before(ctx)

            result = await func(self, *ctx.args, **ctx.kwargs)

            for m in reversed(middlewares):
                result = m.after(ctx, result)

            return result

        return async_wrapper

    else:

        def sync_wrapper(self, *args, **kwargs):
            ctx = Context(self, args, kwargs)

            for m in middlewares:
                m.before(ctx)

            result = func(self, *ctx.args, **ctx.kwargs)

            for m in reversed(middlewares):
                result = m.after(ctx, result)

            return result

        return sync_wrapper

def patch_with_middlewares(instance, method_name, middlewares):
    """
    patch target instance with middlewares
    Args:
        instance: The instance that will be patched
        method_name: The method that will be monitored
        middlewares: A list that containing all middlewares you want to inject 
    """
    method = getattr(instance, method_name)

    if inspect.ismethod(method):
        func = method.__func__
    else:
        func = method
    
    wrapped = build_llm_wrapper(func, middlewares)
    setattr(instance, method_name, types.MethodType(wrapped, instance))