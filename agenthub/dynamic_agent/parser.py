from opendevin.action import (
    Action,
    AgentFinishAction,
    CmdRunAction,
    FileReadAction,
    FileWriteAction,
    BrowseURLAction,
    AgentEchoAction,
    AgentThinkAction,
)

from .prompts.util import get_yaml, get_docs_for

import re
import shutil

docs = get_yaml('docs')

NIFE = AgentEchoAction(docs['not_in_file_error'])


def invalid_error(cmd, cmd_name):
    return docs['command_invalid_error'].format(
        cmd,
        get_docs_for(cmd_name)
    )


VALIDATION = {
    'goto': r'^goto\s+(\d+)$',
    'edit': r'^edit\s+(\d+)\s+(-?\d+)\s+(\S.*)$',
    'write': r'^write\s+(\S+)\s+(.*?)\s*(\d+)?\s*(-?\d+)?$',
    'read': r'^read\s+(\S+)(?:\s+(\d+))?(?:\s+(-?\d+))?$',
    'search_file': r'^search_file\s+(\S+)(?:\s+(\S+))?$',
    'search_dir': r'^search_dir\s+(\S+)(?:\s+(\S+))?$',
    'find_file': r'^find_file\s+(\S+)(?:\s+(\S+))?$',
}

CHECK_PATH = ['scroll_up', 'scroll_down', 'goto', 'edit']


def validate(cmd: str, path, cmd_str):
    if cmd in CHECK_PATH and not path:
        return NIFE

    if cmd in VALIDATION.keys():
        valid = re.match(VALIDATION[cmd], cmd_str, re.DOTALL)
        if valid:
            return valid
        else:
            return AgentEchoAction(invalid_error(cmd_str, cmd))

    return None


def is_valid_command(cmd):
    if shutil.which(cmd):
        return True
    else:
        return False


def get_action_from_string(command_string: str, path: str, line: int, thoughts: str = '') -> Action | None:
    """
    Parses the command string to find which command the agent wants to run
    Converts the command into a proper Action and returns
    """
    vars = command_string.split(' ')
    cmd = vars[0]
    args = [] if len(vars) == 1 else vars[1:]
    valid = validate(cmd, path, command_string)

    if isinstance(valid, AgentEchoAction):
        return valid

    if 'exit' == cmd:
        return AgentFinishAction()

    elif 'think' == cmd:
        return AgentThinkAction(' '.join(args))

    elif 'scroll_up' == cmd:
        return FileReadAction(path, line + 100, line + 200, thoughts)

    elif 'scroll_down' == cmd:
        return FileReadAction(path, line - 100, line, thoughts)

    elif 'goto' == cmd:
        start = int(valid.group(1))
        end = start + 100
        return FileReadAction(path, start, end, thoughts)

    elif 'edit' == cmd:
        start = int(valid.group(1))
        end = int(valid.group(2))
        change = valid.group(3)
        if '"' == change[-1] and '"' == change[0]:
            change = change[1:-1]
        return FileWriteAction(path, change, start, end, thoughts)

    elif 'read' == cmd:
        file = valid.group(1)
        start_str = valid.group(2)
        end_str = valid.group(3)
        start = 0 if not start_str else int(start_str)
        end = -1 if not end_str else int(end_str)
        return FileReadAction(file, start, end, thoughts)

    elif 'write' == cmd:
        file = valid.group(1)
        content = valid.group(2)
        start_str = valid.group(3)
        end_str = valid.group(4)
        start = 0 if not start_str else int(start_str)
        end = -1 if not end_str else int(end_str)
        if '"' == content[-1] and '"' == content[0]:
            content = content[1:-1]
        return FileWriteAction(file, content, start, end, thoughts)

    elif 'browse' == cmd:
        return BrowseURLAction(args[0].strip())

    elif cmd in ['search_file', 'search_dir', 'find_file']:
        return CmdRunAction(command_string)

    else:
        # check bash command
        valid = is_valid_command(cmd)
        if not valid:
            # echo not found error for llm
            return AgentEchoAction(docs['command_does_not_exist_error'].format(command_string))
        else:
            # run valid command
            return CmdRunAction(command_string)


def parse_command(input_str: str, path: str, line: int) -> tuple[Action | None, str]:
    """
    Parses a given string and separates the command (enclosed in triple backticks) from any accompanying text.

    Args:
        input_str (str): The input string to be parsed.

    Returns:
        tuple: A tuple containing the command and the accompanying text (if any).
    """
    input_str = input_str.strip()
    if '```' in input_str:
        parts = input_str.split('```')
        command_str = parts[1].strip()
        ind = 2 if len(parts) > 2 else 1
        accompanying_text = ''.join(parts[:-ind]).strip()
        action = get_action_from_string(
            command_str, path, line, accompanying_text)
        if action:
            return action, accompanying_text
    return None, input_str  # used for retry


def parse_prompt(raw: str, key='PROMPT:') -> str:
    if key in raw:
        idx = raw.index(key) + len(key)
        return raw[idx:].strip()
    else:
        return raw
