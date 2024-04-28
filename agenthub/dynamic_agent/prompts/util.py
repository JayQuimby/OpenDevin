import yaml

BASE = './agenthub/dynamic_agent/prompts/'


def msg_format(content: str, entity: str = 'user') -> dict:
    return {'content': content, 'role': entity}


def dict_to_str(data, indent=0):
    '''recursively returns a dict formatted as a string with indentation'''
    res = ''
    for key, value in data.items():
        res += '\n' + '\t' * indent + str(key) + ': '
        if isinstance(value, dict):
            res += '\n'
            res += dict_to_str(value, indent + 1)
        elif isinstance(value, list):
            res += '\n'
            for item in value:
                res += '\t' * (indent + 1)
                if isinstance(item, (dict, list)):
                    res += '\n'
                    res += dict_to_str(item, indent + 1)
                else:
                    res += '- ' + str(item) + '\n'
        else:
            starter = '\n' + '\t' * (indent + 1)
            res += starter + starter.join(str(value).split('\n'))
    return res


def get_yaml(name: str):
    '''returns the contents of a yaml file as a dict'''
    with open(BASE + name + '.yml', 'r') as file:
        data = yaml.safe_load(file)
    return data


ALL = {
    'act': get_yaml('action'),
    'think': get_yaml('think'),
    'docs': get_yaml('docs'),
    'system': get_yaml('system')
}

SYS_MSG = msg_format(
    dict_to_str(ALL['system']['outline']),
    'system'
)


def format_memory(act, obs):
    return ALL['system']['memory'].format(
        act, obs
    )


def get_docs_for(command: str) -> str:
    doc_dict = ALL['docs']['usage'][command]
    res = f'Documentation for {command}:\n'
    args = '\n' if doc_dict['args'] == 'None' else f' {doc_dict["args"]}\n'
    res += f'Format: {command}' + args
    res += f'Description: {doc_dict["docstr"]}\n'
    res += 'Use cases with examples:\n'
    for use, example in zip(doc_dict['use'], doc_dict['example']):
        res += f'\t{use}\n\t{example}\n'
    return res


def get_docs(lite=False) -> str:
    res = '\nThis is the documentation for the custom commands you have access to:\n'
    for k, v in ALL['docs']['usage'].items():
        res += f'{k}:\n'
        res += f'\tDescription: {v["docstr"]}\n'
        res += f'\tArgs: {v["args"]}\n'
        if not lite:
            uses = '\n\t\t'.join(v['use'])
            res += '\tUsage:\n\t\t' + uses + '\n'
    return res


TECH_DOCS = get_docs()
LITE_DOCS = get_docs(lite=True)


def get_prompt(toggle: str, memory: list[str], **kwargs):
    messages = [SYS_MSG]
    num_mems = len(memory)
    if num_mems > 0:
        mems = memory if toggle == 'think' else memory[-min(num_mems, 5):]
        mem_prompt = ALL['system']['all_memories'].format('\n\n'.join(mems))
        messages.append(msg_format(mem_prompt))

    data = ALL.get(toggle, f'{toggle} is not a valid mode for (think | act)')

    if isinstance(data, str):
        return data
    else:
        prompt = dict_to_str(data['prompt'])
        docs = LITE_DOCS if toggle == 'think' else TECH_DOCS
        formatted = prompt.format(docs=docs, **kwargs)
        messages.append(msg_format(formatted))
        return messages
