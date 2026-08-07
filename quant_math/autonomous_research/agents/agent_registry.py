"""
Agent Registry for managing specialized research agents.

The registry maintains a collection of specialized agents that can be
deployed to perform specific research tasks. Supports dynamic registration
and agent communication.
"""

import uuid
from typing import Dict, List, Optional, Type
from datetime import datetime

from ..interfaces import Agent, AgentMessage


class AgentRegistry:
    """
    Registry for managing specialized research agents.

    Maintains a registry of available agents and handles communication
    between agents.
    """

    def __init__(self):
        """Initialize the agent registry"""
        self._agents: Dict[str, Agent] = {}
        self._capabilities: Dict[str, List[str]] = {}
        self._agent_messages: List[AgentMessage] = []

    def register_agent(self, agent: Agent) -> str:
        """
        Register a new agent.

        Args:
            agent: Agent instance to register

        Returns:
            Agent ID assigned to the agent
        """
        agent_id = agent.agent_id

        if agent_id not in self._agents:
            self._agents[agent_id] = agent
            self._capabilities[agent_id] = agent.get_capabilities()
            print(f"[AgentRegistry] Registered agent: {agent.name} ({agent_id})")
        else:
            print(f"[AgentRegistry] Agent already registered: {agent.name} ({agent_id})")

        return agent_id

    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.

        Args:
            agent_id: ID of agent to unregister

        Returns:
            True if unregistered, False if agent not found
        """
        if agent_id in self._agents:
            del self._agents[agent_id]
            del self._capabilities[agent_id]
            print(f"[AgentRegistry] Unregistered agent: {agent_id}")
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get agent by ID"""
        return self._agents.get(agent_id)

    def get_agents_by_capability(self, capability: str) -> List[Agent]:
        """
        Get all agents that have a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agents with the capability
        """
        agents = []
        for agent_id, capabilities in self._capabilities.items():
            if capability in capabilities:
                agents.append(self._agents[agent_id])
        return agents

    def broadcast(self, message: AgentMessage):
        """
        Broadcast a message to all registered agents.

        Args:
            message: Message to broadcast
        """
        message_id = message.message_id
        self._agent_messages.append(message)

        print(f"[AgentRegistry] Broadcasting message: {message.sender}→*")

        for agent_id, agent in self._agents.items():
            try:
                agent.communicate(message)
            except Exception as e:
                print(f"[AgentRegistry] Failed to send to {agent_id}: {e}")

    def send_message(self, sender: Agent, receiver_id: str, content: Any,
                     priority: str = "normal") -> AgentMessage:
        """
        Send a message to a specific agent.

        Args:
            sender: Sending agent
            receiver_id: Target agent ID
            content: Message content
            priority: Message priority

        Returns:
            Created AgentMessage
        """
        message_id = str(uuid.uuid4())
        message = AgentMessage(
            message_id=message_id,
            sender=sender.agent_id,
            receiver=receiver_id,
            content=content,
            priority=priority
        )

        self._agent_messages.append(message)
        print(f"[AgentRegistry] Sending message: {sender.agent_id}→{receiver_id}")

        receiver = self.get_agent(receiver_id)
        if receiver:
            receiver.communicate(message)
        else:
            print(f"[AgentRegistry] Receiver not found: {receiver_id}")

        return message

    def get_message_history(self, agent_id: Optional[str] = None,
                           limit: int = 100) -> List[AgentMessage]:
        """
        Get message history.

        Args:
            agent_id: Filter by sender/receiver ID (optional)
            limit: Maximum number of messages to return

        Returns:
            List of AgentMessage objects
        """
        messages = self._agent_messages

        if agent_id:
            messages = [m for m in messages if m.sender == agent_id or m.receiver == agent_id]

        return messages[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get registry statistics.

        Returns:
            Dictionary with statistics about registered agents and messages
        """
        return {
            "total_agents": len(self._agents),
            "total_messages": len(self._agent_messages),
            "capabilities": list(self._capabilities.keys()),
            "agents": list(self._agents.keys())
        }

    def list_agents(self) -> List[Dict[str, Any]]:
        """
        Get list of all registered agents with details.

        Returns:
            List of agent information dictionaries
        """
        agents_info = []
        for agent_id, agent in self._agents.items():
            agents_info.append({
                "agent_id": agent_id,
                "name": agent.name,
                "capabilities": agent.get_capabilities()
            })
        return agents_info

    def clear_messages(self):
        """Clear all message history"""
        self._agent_messages = []
        print("[AgentRegistry] Cleared message history")
