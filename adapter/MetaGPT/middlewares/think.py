from adapter.middleware import Middleware
from monitor.base_monitor import RoleType
from utils.logging import logger

EDITOR_COMMANDS_DOC = """
    You can use the following Editor commands (use exact parameter names!):

    - Editor.create_file(filename: str)
    - Editor.insert_content_at_line(file_name: str, line_number: int, insert_content: str)
    - Editor.edit_file_by_replace(file_name: str,
        first_replaced_line_number: int,
        first_replaced_line_content: str,
        last_replaced_line_number: int,
        last_replaced_line_content: str,
        new_content: str)
    - Editor.open_file(path: str)

    Do NOT use parameters like 'line', 'content', 'file_path', or 'file_name' unless specified above. Always use the exact parameter names and types as listed.

    When generating code to insert, always:
    - Output a complete, standalone Python file (including function definition, test cases, and necessary imports).
    - Start the file with a comment or an empty line before any function/class definition.
    - Ensure the code is properly indented and syntactically correct.
    - Do not insert only a function body; always include the full context.
    """

class ThinkMiddleware(Middleware):
    def __init__(self, monitor):
        self.monitor = monitor
    
    def before(self, ctx):
        system_msgs = ctx.kwargs.get('system_msgs')
        system_msgs[0] = (
            EDITOR_COMMANDS_DOC
            + "\n"
            + system_msgs[0]
        )
        ctx.kwargs['system_msgs'] = system_msgs

    def after(self, ctx, result):
        name = ctx.instance.profile
        if self.monitor is not None and result != '':
            if self.monitor.should_inject():
                logger.info(f'Injection step detected, injecting...')
                step_content = self.monitor.get_injection_content()
                result = step_content
            else:
                step_content = f'{name} thinking: {result}'
            self.monitor.record_step(step_content, name, RoleType.ASSISTANT)
        return result