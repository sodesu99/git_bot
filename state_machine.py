#!/usr/bin/env python3
"""
State machine for Git-Telegram bot.
Uses transitions library to manage state transitions.
"""

import logging
from typing import Optional, Dict, Any
from transitions import Machine

logger = logging.getLogger(__name__)


class BotStateMachine:
    """State machine for Git-Telegram bot operations."""

    states = [
        'idle',           # Waiting for commands
        'fetching',       # Fetching from remote
        'diffing',        # Calculating differences
        'sending',        # Sending results to user
        'error',          # Error state
    ]

    transitions = [
        # Trigger: check_requested, source: idle, dest: fetching
        {'trigger': 'check_requested', 'source': 'idle', 'dest': 'fetching'},
        # Trigger: fetch_completed, source: fetching, dest: diffing
        {'trigger': 'fetch_completed', 'source': 'fetching', 'dest': 'diffing'},
        # Trigger: diff_completed, source: diffing, dest: sending
        {'trigger': 'diff_completed', 'source': 'diffing', 'dest': 'sending'},
        # Trigger: send_completed, source: sending, dest: idle
        {'trigger': 'send_completed', 'source': 'sending', 'dest': 'idle'},
        # Trigger: error_occurred, source: '*', dest: error
        {'trigger': 'error_occurred', 'source': '*', 'dest': 'error'},
        # Trigger: retry, source: error, dest: idle
        {'trigger': 'retry', 'source': 'error', 'dest': 'idle'},
    ]

    def __init__(self, context: Optional[Dict[str, Any]] = None):
        self.context = context or {}
        self.machine = Machine(
            model=self,
            states=BotStateMachine.states,
            transitions=BotStateMachine.transitions,
            initial='idle',
            ignore_invalid_triggers=True  # ignore triggers that aren't valid in current state
        )
        self.error_message = None

    def on_enter_fetching(self):
        """Called when entering fetching state."""
        logger.debug("Entering fetching state")
        self.context['fetch_result'] = None

    def on_enter_diffing(self):
        """Called when entering diffing state."""
        logger.debug("Entering diffing state")
        self.context['diff_result'] = None

    def on_enter_sending(self):
        """Called when entering sending state."""
        logger.debug("Entering sending state")
        self.context['send_result'] = None

    def on_enter_error(self):
        """Called when entering error state."""
        logger.error(f"Entered error state: {self.error_message}")

    def on_exit_error(self):
        """Called when exiting error state."""
        self.error_message = None

    def set_error(self, message: str):
        """Set error message and transition to error state."""
        self.error_message = message
        self.error_occurred()

    def get_state(self) -> str:
        """Return current state."""
        return self.state

    def is_idle(self) -> bool:
        """Check if machine is idle."""
        return self.state == 'idle'

    def is_error(self) -> bool:
        """Check if machine is in error state."""
        return self.state == 'error'

    def set_state(self, state: str):
        """Set state directly (for reset and deserialization)."""
        if state in self.states:
            self.state = state
        else:
            logger.warning(f"Attempted to set invalid state: {state}")

    def reset(self):
        """Reset machine to idle state."""
        self.set_state('idle')
        self.error_message = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize state machine to dict."""
        return {
            'state': self.state,
            'error_message': self.error_message,
            'context': self.context,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BotStateMachine':
        """Deserialize state machine from dict."""
        obj = cls(data.get('context', {}))
        obj.set_state(data.get('state', 'idle'))
        obj.error_message = data.get('error_message')
        return obj


if __name__ == '__main__':
    # Example usage
    sm = BotStateMachine()
    print(f"Initial state: {sm.state}")
    sm.check_requested()
    print(f"After check_requested: {sm.state}")
    sm.fetch_completed()
    print(f"After fetch_completed: {sm.state}")
    sm.diff_completed()
    print(f"After diff_completed: {sm.state}")
    sm.send_completed()
    print(f"After send_completed: {sm.state}")
    sm.error_occurred()
    print(f"After error_occurred: {sm.state}")
    sm.retry()
    print(f"After retry: {sm.state}")