import os
import yaml
import logging

from autogen import (
    UserProxyAgent,
    AssistantAgent,
    GroupChat,
    GroupChatManager,
)
from composio_autogen import ComposioToolset, App


logging.basicConfig(level=logging.INFO)

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

if OPENAI_API_KEY is None:
    logging.error("Please set OPENAI_API_KEY environment variable in the .env file")
    exit(1)

llm_config = {
    "model": "gpt-4-turbo",
    "api_key": OPENAI_API_KEY,
}

with open("config/agents.yaml", "r") as file:
    agents_config = yaml.safe_load(file)

with open("config/tasks.yaml", "r") as file:
    tasks_config = yaml.safe_load(file)

research_agent_description = agents_config["researcher"]["system_prompt"]
reporting_agent_description = agents_config["reporting_analyst"]["system_prompt"]
notion_agent_description = agents_config["notion_agent"]["system_prompt"]
slack_agent_description = agents_config["slack_agent"]["system_prompt"]

research_task_description = tasks_config["research_task"]["description"]
reporting_task_description = tasks_config["reporting_task"]["description"]
notion_task_description = tasks_config["notion_task"]["description"]
slack_task_description = tasks_config["slack_task"]["description"]


### Autogen class
class AgentManager:
    def __init__(self, topic):
        logging.info("Initializing AgentManager with topic: %s", topic)
        self.topic = topic
        self.researcher_agent = AssistantAgent(
            "researcher",
            description=research_agent_description.replace("{topic}", topic),
            llm_config=llm_config,
        )

        self.reporting_analyst_agent = AssistantAgent(
            "reporting_analyst",
            description=reporting_agent_description.replace("{topic}", topic),
            llm_config=llm_config,
        )

        self.notion_agent = AssistantAgent(
            "notion_agent",
            description=notion_agent_description.replace("{topic}", topic),
            llm_config=llm_config,
        )

        self.slack_agent = AssistantAgent(
            "slack_agent",
            description=slack_agent_description.replace("{topic}", topic),
            llm_config=llm_config,
        )

        self.user_proxy = UserProxyAgent(
            "user_proxy",
            is_termination_msg=lambda x: x.get("content", "")
            and "TERMINATE" in x.get("content", ""),
            human_input_mode="NEVER",  # Don't take input from User
            code_execution_config={"use_docker": False},
        )

        logging.info("Initializing Composio Toolsets for Notion and Slack")
        # Initialise the Composio Notion Tool Set
        notion_composio_tools = ComposioToolset()

        notion_composio_tools.register_tools(
            tools=[App.NOTION], caller=self.notion_agent, executor=self.user_proxy
        )

        # Initialise the Composio Slack Tool Set
        slack_composio_tools = ComposioToolset()

        slack_composio_tools.register_tools(
            tools=[App.SLACK], caller=self.slack_agent, executor=self.user_proxy
        )

        groupchat = GroupChat(
            agents=[
                self.user_proxy,
                self.researcher_agent,
                self.reporting_analyst_agent,
                self.slack_agent,
                self.notion_agent,
            ],
            messages=[],
            max_round=50,
        )

        self.manager = GroupChatManager(groupchat=groupchat, llm_config=llm_config)
        logging.info("AgentManager initialized successfully")

    def execute(self):
        logging.info("Executing tasks for topic: %s", self.topic)
        self.user_proxy.initiate_chat(
            self.manager,
            message="Please complete the following tasks:"
            + research_task_description.replace("{topic}", self.topic)
            + reporting_task_description.replace("{topic}", self.topic)
            + notion_task_description.replace("{topic}", self.topic)
            + slack_task_description.replace("{topic}", self.topic),
        )
        logging.info("Tasks initiated for topic: %s", self.topic)
