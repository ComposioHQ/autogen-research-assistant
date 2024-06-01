import logging
import os
import yaml
from autogen import AssistantAgent, UserProxyAgent, ConversableAgent
from composio_autogen import App, ComposioToolSet

# Set up logging configuration
logging.basicConfig(level=logging.INFO)

# Load the OPENAI_API_KEY from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY environment variable is not set in the .env file")
    exit(1)

# Define configuration for the language model
language_model_config = {
    "model": "gpt-4-turbo",
    "api_key": OPENAI_API_KEY,
}


# Define a function to load YAML configuration files
def load_yaml_config(file_path):
    with open(file_path, "r") as file:
        return yaml.safe_load(file)


# Load agent and task configurations from YAML files
agents_config = load_yaml_config("config/agents.yaml")
tasks_config = load_yaml_config("config/tasks.yaml")

# Map agent types to their respective system prompts from the configuration
agent_prompts = {
    "research": agents_config["researcher"]["system_prompt"],
    "notion": agents_config["notion_agent"]["system_prompt"],
    "slack": agents_config["slack_agent"]["system_prompt"],
}

# Map task types to their descriptions from the configuration
task_details = {
    "research": tasks_config["research_task"]["description"],
    "notion": tasks_config["notion_task"]["description"],
    "slack": tasks_config["slack_task"]["description"],
}


# Function to create an agent with dynamic system messages based on the topic
def create_agent(agent_type, topic):
    system_message = f"{agent_prompts[agent_type].replace('{topic}', topic)}\n{task_details[agent_type].replace('{topic}', topic)}"
    return AssistantAgent(
        name=f"{agent_type}_agent",
        system_message=system_message,
        description=system_message,
        llm_config=language_model_config,
        human_input_mode="NEVER",
    )


# Function to initialize a toolset for an agent
def init_toolset(user_proxy, app, agent):
    toolset = ComposioToolSet()
    toolset.get_tools(tools=[App.app], caller=agent, executor=user_proxy)
    logging.info(f"Toolset for {app} initialized")


# Description for the user proxy agent
user_proxy_description = """Your job is to act as a user and ensure the task is completed. 
You will receive the output of the tasks, then verify if the task was completed. 
If the task was completed, send a "TERMINATE" message to the group chat. 
Ensure not to send empty outputs."""


# New summary method that passes on complete conversations.
def my_summary_method(
    sender: ConversableAgent, recipient: ConversableAgent, summary_args: dict
):
    last_msg = recipient.chat_messages[sender]
    return str(last_msg)


# Class to manage different agents and their interactions
class AgentManager:
    def __init__(self, topic):
        logging.info(f"Initializing AgentManager for topic: {topic}")
        self.topic = topic

        # Create agents with dynamic system messages based on the topic
        self.researcher_agent = create_agent("research", topic)
        self.notion_agent = create_agent("notion", topic)
        self.slack_agent = create_agent("slack", topic)

        # Initialize the user proxy agent
        self.user_proxy = UserProxyAgent(
            "user",
            system_message=user_proxy_description,
            description=user_proxy_description,
            is_termination_msg=lambda x: (x.get("content") or "")
            .rstrip()
            .endswith("TERMINATE"),
            human_input_mode="NEVER",
            llm_config=language_model_config,
            code_execution_config={"use_docker": False},
        )

        # Initialize toolsets for Notion and Slack agents
        self.init_toolsets()

    def init_toolsets(self):
        logging.info("Initializing toolsets for Notion and Slack agents")
        init_toolset(self.user_proxy, App.NOTION, self.notion_agent)
        init_toolset(self.user_proxy, App.SLACK, self.slack_agent)

    def execute(self):
        logging.info(f"Executing tasks for the topic: {self.topic}")
        chat_results = self.user_proxy.initiate_chats(
            [
                {
                    "recipient": self.researcher_agent,
                    "message": task_details["research"].replace("{topic}", self.topic),
                    "max_turns": 10,
                    "clear_history": True,
                    "silent": False,
                    "summary_method": my_summary_method,
                },
                {
                    "recipient": self.notion_agent,
                    "message": task_details["notion"].replace("{topic}", self.topic),
                    "max_turns": 10,
                    "summary_method": my_summary_method,
                },
                {
                    "recipient": self.slack_agent,
                    "message": task_details["slack"].replace("{topic}", self.topic),
                    "max_turns": 10,
                    "summary_method": my_summary_method,
                },
            ],
        )
        logging.info(f"Tasks initiated for the topic: {self.topic}")
        print("First Chat Summary: ", chat_results[0].summary)
