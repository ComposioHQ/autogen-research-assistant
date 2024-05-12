# main.py

import asyncio
import logging
import os
import traceback

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from autogen_agents import AgentManager

logging.basicConfig(level=logging.INFO)

load_dotenv()

app = FastAPI()

TRIGGER_ID = os.environ.get("TRIGGER_ID", None)
CHANNEL_ID = os.environ.get("CHANNEL_ID", None)


if TRIGGER_ID is None or TRIGGER_ID == "" or CHANNEL_ID is None or CHANNEL_ID == "":
    logging.error(
        "Please set TRIGGER_ID and CHANNEL_ID environment variables in the .env file"
    )
    exit(1)

TRIGGER_ID = TRIGGER_ID.strip()
CHANNEL_ID = CHANNEL_ID.strip()


def run_agents(topic: str):
    logging.info(f"Running agents for topic: {topic}")
    agents = AgentManager(topic=topic)
    logging.info("Initialisation done")
    agents.execute()


async def async_run_agents(topic, user):
    try:
        run_agents(topic=topic)
    except Exception as e:
        logging.error(f"Error in background task: {str(e)}\n{traceback.format_exc()}")
    return JSONResponse(
        content={"message": f"Autogen run initiated for user's {user} message {topic}"},
        status_code=200,
    )


@app.get("/")
async def health():
    logging.info("Health check endpoint accessed")
    return JSONResponse(content={"status": "ok"}, status_code=200)


@app.post("/")
async def webhook(request: Request):
    payload = await request.json()
    logging.info(f"Webhook received payload: {payload}")

    message_payload = payload.get("payload", {})
    channel = message_payload.get("channel", "")

    if channel == CHANNEL_ID:
        logging.info("Payload received for this channel", message_payload)
    else:
        logging.info("Message received but not for this channel")

    text = message_payload.get("text", "")
    user = message_payload.get("user", "")

    asyncio.create_task(async_run_agents(text, user))
    return JSONResponse(content={}, status_code=200)


# async def main():
#     logging.info("Starting server on host 0.0.0.0 at port 2000")
#     config = uvicorn.Config(app=app, host="0.0.0.0", port=2000)
#     server = uvicorn.Server(config)
#     await server.serve()


# if __name__ == "__main__":
#     asyncio.run(main())

asyncio.run(async_run_agents("superman", "test"))

print("Done")
