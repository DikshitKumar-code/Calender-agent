from langgraph.graph import END
from datetime import datetime
import pytz
from langchain_core.messages import ToolMessage, HumanMessage,AnyMessage
from typing import Annotated
from langgraph.graph.message import add_messages
from typing import TypedDict
from .tool import calendar_tools,create_event_tool,list_events_tool,delete_event_tool,postpone_event_tool
from langgraph.graph import StateGraph,MessagesState, START
from langchain_together import ChatTogether
from dotenv import load_dotenv
load_dotenv()  # this will load variables from .env into environment

import os
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
print("TOGETHER_API_KEY:", TOGETHER_API_KEY[:10], "...")  # for debug
llm = ChatTogether(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    together_api_key=TOGETHER_API_KEY
)



import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

llm 

model_with_tools = llm.bind_tools(calendar_tools)


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

def should_continue(state):
    try:
        messages = state["messages"]
        last_message = messages[-1]
        if getattr(last_message, "tool_calls", None):
            logger.info("Tool calls detected, continuing to tools node.")
            return "tools"
        logger.info("No tool calls detected, ending graph.")
        return END
    except Exception as e:
        logger.error(f"Error in should_continue: {e}")
        return END


def call_model(state):
    try:
        messages = state["messages"]
        logger.info(f"Received {len(messages)} messages.")

        # Find the latest ToolMessage
        latest_tool_message = next((msg for msg in reversed(messages) if isinstance(msg, ToolMessage)), None)
        latest_human_message = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)

        if latest_tool_message:
            logger.info("Latest message is a ToolMessage, invoking LLM for final response.")
            prompt = (
                f"Give final response based on this tool message: {latest_tool_message}. "
                f"And also consider the user's original message: {latest_human_message}. "
                "This response created by you will be final and will be prompted to user."
            )
            response = llm.invoke(prompt)
            logger.info("LLM response received for tool message.")
            return {"messages": [response]}

        # Add current time information for the LLM
        timezone = pytz.timezone('Asia/Kolkata')
        current_time = datetime.now(timezone)
        current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S %Z')
        time_prompt = (
            f"The current date and time is {current_time_str}. "
            "Please consider this information when generating your response."
        )

        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "content") and isinstance(last_message.content, str):
                logger.info("Prepending current time info to the last user message.")
                last_message.content = f"{time_prompt}\n\n{last_message.content}"

        response = model_with_tools.invoke(messages)
        logger.info("Model with tools invoked successfully.")
        return {"messages": [response]}

    except Exception as e:
        logger.error(f"Error in call_model: {e}")
        error_message = {
            "role": "assistant",
            "content": "Sorry, an error occurred while processing your request. Please try again later."
        }
        return {"messages": [error_message]}


def tool_dispatch_node(state):
    try:
        messages = state["messages"]
        last_message = messages[-1]
        tool_calls = getattr(last_message, "tool_calls", [])
        new_messages = []

        tool_map = {
            "create_event_tool": create_event_tool,
            "list_events_tool": list_events_tool,
            "postpone_event_tool": postpone_event_tool,
            "delete_event_tool": delete_event_tool,
        }

        for call in tool_calls:
            tool_name = call["name"]
            args = call["args"]
            logger.info(f"Invoking tool: {tool_name} with args: {args}")
            tool_func = tool_map.get(tool_name)
            if not tool_func:
                logger.warning(f"Tool {tool_name} not found in tool_map.")
                continue
            try:
                result = tool_func.invoke(args)
                new_messages.append(
                    ToolMessage(content=result, name=tool_name, tool_call_id=call["id"])
                )
                logger.info(f"Tool {tool_name} executed successfully.")
            except Exception as tool_error:
                logger.error(f"Error executing tool {tool_name}: {tool_error}")
                error_msg = ToolMessage(
                    content=f"Error executing tool {tool_name}: {tool_error}",
                    name=tool_name,
                    tool_call_id=call["id"]
                )
                new_messages.append(error_msg)

        logger.info(f"Tool dispatch node returning {len(new_messages)} messages.")
        return {"messages": new_messages}

    except Exception as e:
        logger.error(f"Error in tool_dispatch_node: {e}")
        error_msg = ToolMessage(
            content="An error occurred while dispatching tools.",
            name="tool_dispatch_node",
            tool_call_id=None
        )
        return {"messages": [error_msg]}




builder = StateGraph(MessagesState)
builder.add_node("call_model", call_model)
builder.add_node("tools", tool_dispatch_node)
builder.add_edge(START, "call_model")
builder.add_conditional_edges("call_model", should_continue, ["tools", END])
builder.add_edge("tools", "call_model")
graph = builder.compile()


if __name__ == "__main__":
    try:
        logger.info("Starting graph invocation with test message.")
        result = graph.invoke({
            "messages": [
                {"role": "user", "content": "book a meeting tommorow 9 am"}
            ]
        })
        logger.info(f"Graph invocation result: {result}")
        print(result)
    except Exception as e:
        logger.error(f"Error during graph invocation: {e}")
        print(f"Error during graph invocation: {e}")
