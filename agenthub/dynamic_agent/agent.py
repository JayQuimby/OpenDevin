from typing import List
from opendevin.agent import Agent
from opendevin.llm.llm import LLM
from opendevin.state import State
from opendevin.observation import Observation
from opendevin.action import (
    Action,
    AgentThinkAction,
    FileReadAction,
    FileWriteAction,
)

from .prompts.util import (
    get_prompt,
    format_memory
)

from .parser import (
    parse_command,
    parse_prompt
)


class DynamicAgent(Agent):
    """
    The Dynamic Agent aims to dynamically prompt the actor agent using a thinker agent.
    The thinker agent will create a prompt at each step to give the actor a dynamic prompt structure.
    The actor agent will then use the dynamic prompt to complete the next step
    **Optional** Critic: an additional pass through the thinker agent to ensure the actions does what was asked.
    """

    def __init__(self, llm: LLM):
        super().__init__(llm)
        self.cur_file: str = ''
        self.cur_line: int = 0
        self.cur_thought: str = ''
        self.memory: list[str] = []

    def search_memory(self, query: str) -> List[str]:
        """Return any exact matches for query in agent memories"""
        return [item for item in self.memory if query in item]

    def _remember(self, action: Action, observation: Observation) -> None:
        """Agent has a limited memory of the few steps implemented as a queue"""
        memory = format_memory(
            action.to_memory(),
            observation.to_memory()
        )
        self.memory.append(memory)

    def _update(self, action: Action) -> None:
        """Update the current path and line if they are changed"""
        if isinstance(action, (FileReadAction, FileWriteAction)):
            self.cur_file = action.path
            self.cur_line = action.start

    def _completion(self, messages: list[dict]):
        """LLM completion given messages"""
        resp = self.llm.completion(
            messages=messages,
            temperature=0.05,
        )
        return resp['choices'][0]['message']['content']

    def _think(self, state: State) -> str:
        msgs = get_prompt(
            'think',
            self.memory,
            goal=state.plan.main_goal
        )
        raw_output = self._completion(msgs)
        print(f'\033[0;36mThinking:\n{raw_output}')
        return parse_prompt(raw_output)

    def _act(self, state: State):
        msgs = get_prompt(
            'act',
            self.memory,
            goal=state.plan.main_goal,
            task=self.cur_thought,
            file=self.cur_file,
            line=self.cur_line
        )
        raw_output = self._completion(msgs)
        print(f'\033[1;35mAction:\n{raw_output}')
        return parse_command(
            raw_output,
            self.cur_file,
            self.cur_line
        )

    def step(self, state: State) -> Action:
        for prev_action, obs in state.updated_info:
            self._remember(prev_action, obs)

        self.cur_thought = self._think(state)
        action, thought = self._act(state)

        if not action:
            action = AgentThinkAction(thought)

        self._update(action)
        self.latest_action = action
        return action
