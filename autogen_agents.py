import logging
import os

import yaml
from autogen import AssistantAgent, GroupChat, GroupChatManager, UserProxyAgent
from composio_autogen import App, ComposioToolset

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

TERMINATION_MESSAGE = "TERMINATE ONCE YOU ARE DONE WITH YOUR JOB by saying TERMINATE"


### Autogen class
class AgentManager:
    def __init__(self, topic):
        logging.info("Initializing AgentManager with topic: %s", topic)
        self.topic = topic
        agent_system_message = (
            research_agent_description.replace("{topic}", topic)
            + "\n"
            + research_task_description.replace("{topic}", topic)
        )
        self.researcher_agent = AssistantAgent(
            name="researcher_agent",
            system_message=agent_system_message,
            description=agent_system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )
        agent_system_message = (
            reporting_agent_description.replace("{topic}", topic)
            + "\n"
            + reporting_task_description.replace("{topic}", topic)
        )
        self.reporting_analyst_agent = AssistantAgent(
            name="reporting_analyst_agent",
            system_message=agent_system_message,
            description=agent_system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )
        agent_system_message = (
            notion_agent_description.replace("{topic}", topic)
            + "\n"
            + notion_task_description.replace("{topic}", topic)
        )
        self.notion_agent = AssistantAgent(
            name="notion_agent",
            system_message=agent_system_message,
            description=agent_system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )
        agent_system_message = (
            slack_agent_description.replace("{topic}", topic)
            + "\n"
            + slack_task_description.replace("{topic}", topic)
        )
        self.slack_agent = AssistantAgent(
            name="slack_agent",
            system_message=agent_system_message,
            description=agent_system_message,
            llm_config=llm_config,
            human_input_mode="NEVER",
        )

        self.user_proxy = UserProxyAgent(
            "user",
            system_message="""Your job is to act as a user and make sure the task is completed. 
            You will get an output of the tasks in response, then check if task was completed. 
            If task was completed, you will send a message to the group chat with the following: 
            "TERMINATE"
            If you think output looks good, send "TERMINATE" message. Do not ever send empty output. 
            """,
            description="""Your job is to act as a user and make sure the task is completed. 
            You will get an output of the tasks in response, then check if task was completed. 
            If task was completed, you will send a message to the group chat with the following: 
            "TERMINATE"
            If you think output looks good, send "TERMINATE" message. Do not ever send empty output. 
            """,
            is_termination_msg=lambda x: x.get("content", "")
            and x.get("content", "").rstrip().endswith("TERMINATE"),
            # max_consecutive_auto_reply=1,  # terminate without auto-reply
            human_input_mode="NEVER",  # Don't take input from User
            llm_config=llm_config,
            code_execution_config={"use_docker": False},
        )

        logging.info("Initializing Composio Toolsets for Notion and Slack")
        # Initialise the Composio Notion Tool Set
        notion_composio_tools = ComposioToolset()

        notion_composio_tools.register_tools(
            tools=[App.NOTION],
            caller=self.notion_agent,
            executor=self.user_proxy,
        )

        logging.info("Notion Toolset initialized")
        # Initialise the Composio Slack Tool Set
        slack_composio_tools = ComposioToolset()

        slack_composio_tools.register_tools(
            tools=[App.SLACK],
            caller=self.slack_agent,
            executor=self.user_proxy,
        )

        logging.info("Slack Toolset initialized")

    def execute(self):
        logging.info("Executing tasks for topic: %s", self.topic)
        chat_results = self.user_proxy.initiate_chats(
            [
                {
                    "recipient": self.researcher_agent,
                    "message": research_task_description.replace("{topic}", self.topic),
                    "max_turns": 6,
                    "clear_history": True,
                    "silent": False,
                    "summary_method": "reflection_with_llm",
                },
                {
                    "recipient": self.reporting_analyst_agent,
                    "message": reporting_task_description.replace(
                        "{topic}", self.topic
                    ),
                    "max_turns": 6,
                    "summary_method": "reflection_with_llm",
                },
                {
                    "recipient": self.notion_agent,
                    "message": notion_task_description.replace("{topic}", self.topic),
                    "max_turns": 15,
                    "summary_method": "reflection_with_llm",
                },
                {
                    "recipient": self.slack_agent,
                    "message": slack_task_description.replace("{topic}", self.topic),
                    "max_turns": 15,
                    "summary_method": "reflection_with_llm",
                },
            ],
        )
        logging.info("Tasks initiated for topic: %s", self.topic)
        print("First Chat Summary: ", chat_results[0].summary)
        print("Second Chat Summary: ", chat_results[1].summary)
        print("Third Chat Summary: ", chat_results[2].summary)
