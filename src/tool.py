import logging
from langchain.tools import tool
from .utilities import ListGoogleCalendarEvents, CreateGoogleCalendarEvent, DeleteGoogleCalendarEvent, PostponeGoogleCalendarEvent
from .utilities import api_resource
from typing import TypedDict, cast
from langchain_together import ChatTogether


from dotenv import load_dotenv
load_dotenv()  # this will load variables from .env into environment

import os
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
print("TOGETHER_API_KEY:", TOGETHER_API_KEY[:10], "...")  # for debug

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

llm = ChatTogether(
    model="meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
    together_api_key=TOGETHER_API_KEY
)

@tool
def create_event_tool(start_datetime, end_datetime, summary, location="", description="", ):
    """
    Create a Google Calendar event.

    Args:
        start_datetime (str): Start datetime (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime (YYYY-MM-DDTHH:MM:SS).
        summary (str): Event title.
        location (str, optional): Event location.
        description (str, optional): Event description.
        timezone (str): Timezone.

    Returns:
        str: Confirmation message with event link.
    """
    timezone="Asia/Kolkata"
    try:
        tool = CreateGoogleCalendarEvent(api_resource)
        result = tool._run(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            summary=summary,
            location=location,
            description=description,
            timezone=timezone
        )
        logger.info(f"Created event: {summary} from {start_datetime} to {end_datetime}")
        return result
    except Exception as e:
        logger.error(f"Error creating event: {e}")
        return f"❌ Error creating event: {e}"

@tool
def list_events_tool(start_datetime, end_datetime, max_results=10,):
    """
    List Google Calendar events in a date range.

    Args:
        start_datetime (str): Start datetime (YYYY-MM-DDTHH:MM:SS).
        end_datetime (str): End datetime (YYYY-MM-DDTHH:MM:SS).
        max_results (int): Maximum results to return.
        timezone (str): Timezone.

    Returns:
        list: List of event dicts (each includes event ID, summary, times, etc.).
    """
    timezone="Asia/Kolkata"
    try:
        tool = ListGoogleCalendarEvents(api_resource)
        events = tool._run(
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            max_results=max_results,
            timezone=timezone
        )
        logger.info(f"Listed {len(events)} events from {start_datetime} to {end_datetime}")
        return events
    except Exception as e:
        logger.error(f"Error listing events: {e}")
        return []

@tool
def postpone_event_tool(
    start_datetime: str,
    end_datetime: str,
    user_query: str,
    new_start_datetime: str,
    new_end_datetime: str,
) -> str:
    """
    Postpone one or more Google Calendar events based on a natural language user query.
    Uses an LLM to select the correct event(s) if the reference is ambiguous.

    Args:
        start_datetime (str): Start datetime for search window.
        end_datetime (str): End datetime for search window.
        user_query (str): The user's original query or meeting description.
        new_start_datetime (str): New start datetime for the event(s).
        new_end_datetime (str): New end datetime for the event(s).

    Returns:
        str: Confirmation message(s) or clarification prompt.
    """
    timezone = "Asia/Kolkata"
    args = {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }

    logger.info(f"Postpone tool called with args: {args}")
    events = list_events_tool.invoke(args)
    logger.info(f"Events found: {events}")
    if not events:
        return "No events found in the specified time window."

    # Prepare event options for the LLM
    event_options = [
        f"{idx+1}. {e.get('summary', 'No Title')} at {e.get('start')} (ID: {e.get('id')})"
        for idx, e in enumerate(events)
    ]
    options_text = "\n".join(event_options)

    # Compose LLM prompt
    prompt = (
        f"User query: '{user_query}'\n"
        f"Here are the events found:\n{options_text}\n"
        "Based on the user's query, which event ID(s) best match the intent for postponement? "
        "Just reply with the event ID(s) as a list."
    )

    # Call the LLM to select the best event(s)
    class output(TypedDict):
        event_id: list[str]  # Use the same key as in your delete_event_tool

    llm_response = cast(output, llm.with_structured_output(output).invoke(prompt))
    selected_event_ids = llm_response.get('event_id')
    logger.info(f"Selected event IDs for postponement: {selected_event_ids}")

    postponed_events = []

    for event_id in selected_event_ids:
        event = next((e for e in events if e.get('id') == event_id), None)
        if not event:
            msg = f"❌ Event ID `{event_id}` not found."
            logger.warning(msg)
            postponed_events.append(msg)
            continue

        try:
            tool = PostponeGoogleCalendarEvent(api_resource)
            result = tool._run(
                event_id=str(event.get('id')),
                new_start_datetime=new_start_datetime,
                new_end_datetime=new_end_datetime,
                timezone=timezone
            )
            msg = f"✅ Postponed event: **{event.get('summary', 'No Title')}** (`{event_id}`) → {result}"
            logger.info(msg)
            postponed_events.append(msg)
        except Exception as e:
            msg = f"❌ Error postponing event `{event_id}`: {e}"
            logger.error(msg)
            postponed_events.append(msg)

    return "\n".join(postponed_events)

@tool
def delete_event_tool(
    start_datetime: str,
    end_datetime: str,
    user_query: str,
) -> str:
    """
    Delete a Google Calendar event based on a natural language user query.
    Uses an LLM to select the correct event if the reference is ambiguous.
    """
    args = {
        "start_datetime": start_datetime,
        "end_datetime": end_datetime
    }
    logger.info(f"Delete tool called with args: {args}")
    events = list_events_tool.invoke(args)
    if not events:
        return "No events found in the specified time window."

    # Prepare event options for the LLM
    event_options = [
        f"{idx+1}. {e.get('summary', 'No Title')} at {e.get('start')} (ID: {e.get('id')})"
        for idx, e in enumerate(events)
    ]
    options_text = "\n".join(event_options)

    # Compose LLM prompt
    prompt = (
        f"User query: '{user_query}'\n"
        f"Here are the events found:\n{options_text}\n"
        "Based on the user's query, which event ID(s) best match the intent for deletion? "
        "Just reply with the event ID(s) as a list."
    )

    # Call the LLM to select the best event
    class output(TypedDict):
        event_id: list[str]  

    llm_response = cast(output, llm.with_structured_output(output).invoke(prompt))
    selected_event_ids = llm_response.get('event_id')
    logger.info(f"Selected event IDs for deletion: {selected_event_ids}")

    # Loop through all selected event IDs and delete each
    deleted_events = []

    for event_id in selected_event_ids:  # This is now a list
        # Find the event by exact match of ID
        event = next((e for e in events if e.get('id') == event_id), None)
        if not event:
            msg = f"❌ Event ID `{event_id}` not found."
            logger.warning(msg)
            deleted_events.append(msg)
            continue

        try:
            tool = DeleteGoogleCalendarEvent(api_resource)
            result = tool._run(
                event_id=str(event.get('id')),
                calendar_id=None  # Defaults to 'primary' or configured calendar
            )
            msg = f"✅ Deleted event: **{event.get('summary', 'No Title')}** (`{event_id}`) → {result}"
            logger.info(msg)
            deleted_events.append(msg)
        except Exception as e:
            msg = f"❌ Error deleting event `{event_id}`: {e}"
            logger.error(msg)
            deleted_events.append(msg)

    # Return summary of all deletions
    return "\n".join(deleted_events)

calendar_tools = [
    create_event_tool,
    list_events_tool,
    postpone_event_tool,
    delete_event_tool
]

if __name__ == '__main__':
    logger.info("Tool file")
    result = postpone_event_tool.invoke({
        "start_datetime": "2025-07-07T17:00:00",        # Today, 5:00 PM
        "end_datetime": "2025-07-07T18:00:00",          # Today, 6:00 PM (assuming 1-hour meeting)
        "user_query": "postpone today's 5 pm meeting to tomorrow 10 am",
        "new_start_datetime": "2025-07-08T10:00:00",    # Tomorrow, 10:00 AM
        "new_end_datetime": "2025-07-08T11:00:00"       # Tomorrow, 11:00 AM
    })
    print(result)
