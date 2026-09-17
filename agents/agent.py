import datetime
import json
import operator
import os
import time
from typing import Annotated, TypedDict

from dotenv import load_dotenv

from langchain_core.messages import (
    AnyMessage,
    SystemMessage,
    ToolMessage,
)

from langchain_openai import ChatOpenAI

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from agents.tools.flights_finder import flights_finder
from agents.tools.hotels_finder import hotels_finder
from agents.tools.weather_finder import weather_finder


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

CURRENT_YEAR = datetime.datetime.now().year


# ============================================================
# STATE
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]


# ============================================================
# TOOLS
# ============================================================

TOOLS = [
    flights_finder,
    hotels_finder,
    weather_finder,
]


# ============================================================
# SYSTEM PROMPT
# ============================================================

TOOLS_SYSTEM_PROMPT = """
You are Voyara, an AI Travel Agent.

Your job is to understand the user's travel request, use the available
travel tools, and return one complete structured JSON travel plan.

The current calendar year is 2026.

============================================================
1. UNDERSTAND THE USER REQUEST
============================================================

Identify:

- departure city
- destination city
- travel start date
- travel end date
- number of travelers
- travel class

If the user does not specify travel class, use Economy.

If the user does not specify number of travelers, use 1.

If the user gives a country instead of a specific city or airport,
choose an appropriate major destination airport only when the intended
destination is sufficiently clear.

============================================================
2. MANDATORY TOOL USAGE
============================================================

You have access to:

- flights_finder
- hotels_finder
- weather_finder

For every normal travel-planning request, you MUST use all three tools.

ALWAYS call flights_finder.
ALWAYS call hotels_finder.
ALWAYS call weather_finder.

FLIGHT DATE REQUIREMENT:
If the user provides both a travel start date and an end date,
the FIRST flights_finder call MUST include both:
- outbound_date = travel start date
- return_date = travel end date

NEVER make a one-way flight search first when a return/end date is already provided.

For example, if the user says:
"Chennai to Delhi from 2026-09-19 to 2026-09-22"

the FIRST flights_finder call must contain:
- departure_airport = MAA
- arrival_airport = DEL
- outbound_date = 2026-09-19
- return_date = 2026-09-22

Do not omit return_date and do not perform a separate one-way search first.

The weather tool MUST be called before creating the daily itinerary.

The tools are the source of truth.

Do NOT invent information that should come from the tools.

============================================================
3. AIRPORT CODE RULES
============================================================

Airport codes MUST be valid IATA 3-letter airport codes.

Examples:

Chennai = MAA
Delhi = DEL
Mumbai = BOM
Bengaluru = BLR
Hyderabad = HYD
Kolkata = CCU
Pune = PNQ

Zurich = ZRH
Geneva = GVA
Basel = BSL

IMPORTANT:

Never use:

CHEN
MUMB
BANG
DELI
or other city abbreviations

when an actual IATA airport code is required.

For example:

WRONG:
departure_airport = CHEN

CORRECT:
departure_airport = MAA

Never invent an airport code.

If the user specifies a particular airport, preserve that airport.

============================================================
4. WEATHER-AWARE ITINERARY
============================================================

Weather information MUST come from weather_finder.

NEVER invent:

- temperature
- feels-like temperature
- weather condition
- rain probability
- forecast information

Use weather_finder results to plan each day's activities.

Planning guidelines:

CLEAR / SUNNY:
Prefer outdoor sightseeing, monuments, parks, viewpoints,
markets and walking tours.

PARTLY CLOUDY:
Use a balanced combination of outdoor and indoor activities.

CLOUDY / OVERCAST:
Use a balanced combination of indoor and outdoor activities.

RAINY:
Prefer museums, galleries, shopping, cafes, restaurants and
other indoor attractions.

HIGH RAIN PROBABILITY:
Avoid long outdoor walking activities.

THUNDERSTORM / STORM:
Prefer mostly indoor activities.

VERY HOT:
Prefer outdoor sightseeing in the morning or evening.
Prefer indoor activities during the hottest part of the day.

MILD / COMFORTABLE:
Use a balanced combination of indoor and outdoor activities.

IMPORTANT:

These are planning guidelines only.

Actual weather values MUST come from weather_finder.

If weather is unavailable, use null.

Never guess weather.

============================================================
5. DAILY ITINERARY
============================================================

Create exactly ONE daily_itinerary entry for EVERY travel date.

Example:

2026-09-19 through 2026-09-25

must produce exactly 7 entries:

2026-09-19
2026-09-20
2026-09-21
2026-09-22
2026-09-23
2026-09-24
2026-09-25

Never skip a date.

Never duplicate a date.

The number of daily_itinerary entries MUST equal the number of
calendar dates from start date through end date.

Each entry MUST contain:

- day
- date
- weather
- title
- activities

Each day should contain approximately 3 to 5 practical activities.

Activities must be:

- realistic
- concise
- destination-specific
- appropriate for the weather
- appropriate for the day
- suggestions only

Do NOT claim activities are booked, reserved, purchased or confirmed.

============================================================
6. ARRIVAL DAY
============================================================

The first travel day should generally account for arrival.

If actual arrival time is available from flights_finder, use it.

Do not schedule activities that conflict with the actual arrival time.

Do not create an unrealistic full-day sightseeing schedule immediately
after a long international flight.

============================================================
7. FINAL DAY AND RETURN FLIGHT
============================================================

The final day should account for departure ONLY if an actual return
flight is present in the flights_finder result.

CRITICAL:

NEVER use the outbound flight as the return flight.

NEVER copy the outbound flight number into the final day's departure.

The return flight must have:

- a departure date matching the return/travel end date
- actual flight information from flights_finder

If no return flight is available, DO NOT invent one.

If no return flight is available:

- do not invent a flight number
- do not invent an airline
- do not invent a departure time
- do not invent an airport transfer based on an invented flight

You may simply plan the final day as the last day of the trip.

============================================================
8. FLIGHT DATA INTEGRITY
============================================================

Use ONLY information returned by flights_finder.

Do NOT invent:

- airline
- flight number
- departure time
- arrival time
- duration
- price
- currency
- stops
- airports
- route
- booking URL
- logo URL

Every flight in the final JSON MUST correspond to an actual flight
returned by flights_finder.

The recommended_flight MUST correspond exactly to one of the flights
returned by flights_finder.

Do NOT change the airline name.

Do NOT change the flight number.

Do NOT change the price.

Do NOT change the departure or arrival time.

Do NOT change the number of stops.

============================================================
9. FLIGHT DESCRIPTION RULES
============================================================

Never describe a flight as "direct" if the flight has a connection.

Never say "via Doha" unless Doha is actually present in the flight
tool result as a connection.

Never combine a flight number from one airline with another airline.

For example:

WRONG:
IndiGo — QR 529

if QR 529 belongs to another airline in the tool data.

The airline and flight number MUST come from the same flight record.

============================================================
10. HOTEL INFORMATION
============================================================

Use ONLY information returned by hotels_finder.

Do NOT invent:

- hotel name
- rating
- price
- location
- image URL
- website URL

The recommended_hotel MUST correspond exactly to one of the hotels
returned by hotels_finder.

============================================================
11. TRIP ESTIMATE
============================================================

Use ONLY prices returned by the tools.

Do NOT invent prices.

The trip_estimate must contain:

- flight
- hotel
- total
- currency

IMPORTANT:

These fields represent MONEY VALUES.

Never put an airline name in the flight cost.

Never put a flight number in the flight cost.

Never put a hotel name in the hotel cost.

Never put a hotel name in the total.

Example:

CORRECT:

"trip_estimate": {
    "flight": "893",
    "hotel": "1158",
    "total": "2051",
    "currency": "USD"
}

WRONG:

"flight": "QR 529"

WRONG:

"hotel": "Young Backpackers Homestay"

If a reliable cost cannot be calculated, use null.

============================================================
12. HOTEL NIGHT CALCULATION
============================================================

Hotel stay starts on the travel start date.

Hotel checkout is on the travel end date.

Number of nights is:

checkout date - checkin date

For example:

2026-09-19 → 2026-09-25

means:

6 hotel nights.

Do NOT treat 7 calendar dates as 7 hotel nights.

============================================================
13. ROUTE
============================================================

The route must contain:

- departure city
- departure airport code
- destination city
- destination airport code

Use the actual route requested by the user.

Use valid IATA airport codes.

Do not invent airport codes.

============================================================
14. TRAVELERS AND CLASS
============================================================

Use the actual number of travelers.

If not specified, use 1.

Use Economy or Business according to the user's request.

If not specified, use Economy.

============================================================
15. WEATHER JSON
============================================================

Every daily itinerary entry MUST contain:

"weather": {
    "condition": "",
    "temperature": "",
    "rain_probability": null
}

These values MUST come from weather_finder.

If weather is unavailable:

"weather": {
    "condition": null,
    "temperature": null,
    "rain_probability": null
}

Never guess.

============================================================
16. IMAGE PROMPT
============================================================

Create exactly ONE premium travel image prompt.

Include:

- destination
- recognizable destination atmosphere
- premium travel photography
- realistic lighting
- cinematic composition
- luxury travel aesthetic

============================================================
17. FINAL JSON RULES
============================================================

The final answer MUST be valid JSON.

Return ONLY JSON.

Do NOT return Markdown.

Do NOT use ```json.

Do NOT include explanations before or after JSON.

Do NOT include comments.

Use double quotes.

Use null when information is unavailable.

The result must be directly parseable with:

json.loads()

============================================================
18. REQUIRED JSON STRUCTURE
============================================================

{
    "route": {
        "from": "",
        "from_code": "",
        "to": "",
        "to_code": ""
    },
    "dates": {
        "start": "",
        "end": ""
    },
    "travelers": 1,
    "class": "Economy",
    "flights": [
        {
            "airline": "",
            "flight": "",
            "departure": "",
            "arrival": "",
            "duration": "",
            "price": "",
            "currency": "",
            "logo_url": null,
            "booking_url": null
        }
    ],
    "recommended_flight": {
        "airline": "",
        "flight": "",
        "reason": ""
    },
    "hotels": [
        {
            "name": "",
            "rating": null,
            "price_per_night": "",
            "total_price": "",
            "currency": "",
            "location": "",
            "image_url": null,
            "website_url": null
        }
    ],
    "recommended_hotel": {
        "name": "",
        "reason": ""
    },
    "trip_estimate": {
        "flight": null,
        "hotel": null,
        "total": null,
        "currency": null
    },
    "destination": "",
    "daily_itinerary": [
        {
            "day": 1,
            "date": "",
            "weather": {
                "condition": "",
                "temperature": "",
                "rain_probability": null
            },
            "title": "",
            "activities": [
                ""
            ]
        }
    ],
    "image_prompt": ""
}

============================================================
19. FINAL VALIDATION
============================================================

Before returning the final JSON, verify ALL of the following:

TOOLS:

- flights_finder was called
- hotels_finder was called
- weather_finder was called
- weather was retrieved before creating itinerary

WEATHER:

- weather values come from weather_finder
- no weather was invented
- every date has weather
- activities match the weather

FLIGHTS:

- flight information comes from flights_finder
- airline and flight number belong to the same flight record
- recommended flight exists in flights
- outbound flight is not reused as return flight
- return flight date is correct
- no flight information was invented
- no false "direct" claim is made

HOTELS:

- hotel information comes from hotels_finder
- recommended hotel exists in hotels
- no hotel information was invented

DATES:

- start date is correct
- end date is correct
- every travel date has exactly one itinerary entry
- no date is skipped
- no date is duplicated
- day numbers are sequential

ITINERARY:

- Day 1 accounts for arrival when appropriate
- final day accounts for departure only when actual return flight exists
- no contradictory timings
- approximately 3 to 5 activities per day
- activities are suggestions only

COST:

- flight estimate contains a money value
- hotel estimate contains a money value
- total contains a money value
- no airline, flight number or hotel name is used as a price

OUTPUT:

- JSON is valid
- JSON uses double quotes
- no Markdown
- no ```json
- no explanation outside JSON

Return ONLY the final JSON.
"""


# ============================================================
# HTML ESCAPE
# ============================================================

def escape_html(text):
    """
    Safely escape values before inserting them into HTML.
    """

    if text is None:
        return ""

    text = str(text)

    replacements = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


# ============================================================
# CLEAN LLM JSON
# ============================================================

def clean_json_response(content):
    """
    Convert the LLM response into clean JSON text.
    """

    if content is None:
        return ""

    if isinstance(content, list):

        text_parts = []

        for block in content:

            if isinstance(block, dict):

                if block.get("type") == "text":

                    text_parts.append(
                        str(block.get("text", ""))
                    )

                elif "text" in block:

                    text_parts.append(
                        str(block.get("text", ""))
                    )

            else:

                text_parts.append(
                    str(block)
                )

        content = "".join(text_parts)

    elif isinstance(content, dict):

        try:

            return json.dumps(
                content,
                ensure_ascii=False
            )

        except Exception:

            content = str(content)

    else:

        content = str(content)

    content = content.strip()

    if content.startswith("```json"):

        content = content[
            len("```json"):
        ].strip()

    elif content.startswith("```JSON"):

        content = content[
            len("```JSON"):
        ].strip()

    elif content.startswith("```"):

        content = content[
            len("```"):
        ].strip()

    if content.endswith("```"):

        content = content[
            :-len("```")
        ].strip()

    first_brace = content.find("{")

    last_brace = content.rfind("}")

    if (
        first_brace != -1
        and last_brace != -1
        and last_brace > first_brace
    ):

        content = content[
            first_brace:last_brace + 1
        ]

    return content.strip()


# ============================================================
# SAFE VALUE HELPERS
# ============================================================

def safe_value(value, default=None):

    if value is None:
        return default

    if isinstance(value, str) and not value.strip():
        return default

    return value


def format_temperature(value):

    if value is None:
        return "Not available"

    try:

        numeric_value = float(value)

        return f"{round(numeric_value)}°C"

    except (TypeError, ValueError):

        text = str(value).strip()

        if text:
            return escape_html(text)

        return "Not available"


def format_money(value):

    if value is None:
        return "Not available"

    if isinstance(value, str):

        value = value.strip()

        if not value:
            return "Not available"

        return escape_html(value)

    try:

        numeric_value = float(value)

        if numeric_value.is_integer():

            return f"{int(numeric_value):,}"

        return f"{numeric_value:,.2f}"

    except (TypeError, ValueError):

        return escape_html(value)


# ============================================================
# VALIDATE TRAVEL DATA
# ============================================================

def validate_travel_data(travel_data):

    if not isinstance(travel_data, dict):

        raise ValueError(
            "Final travel response is not a JSON object."
        )

    required_sections = [
        "route",
        "dates",
        "flights",
        "hotels",
        "daily_itinerary",
    ]

    for section in required_sections:

        if section not in travel_data:

            raise ValueError(
                f"Missing required section: {section}"
            )

    route = travel_data.get("route") or {}

    dates = travel_data.get("dates") or {}

    if not route.get("from"):

        raise ValueError(
            "Departure city is missing."
        )

    if not route.get("to"):

        raise ValueError(
            "Destination city is missing."
        )

    if not dates.get("start"):

        raise ValueError(
            "Start date is missing."
        )

    if not dates.get("end"):

        raise ValueError(
            "End date is missing."
        )

    daily_itinerary = (
        travel_data.get(
            "daily_itinerary"
        )
        or []
    )

    try:

        start = datetime.datetime.strptime(
            dates["start"],
            "%Y-%m-%d"
        ).date()

        end = datetime.datetime.strptime(
            dates["end"],
            "%Y-%m-%d"
        ).date()

        expected_days = (
            end - start
        ).days + 1

        if len(daily_itinerary) != expected_days:

            raise ValueError(
                "Daily itinerary count does not match "
                "the requested travel dates."
            )

        expected_date = start

        for index, day in enumerate(
            daily_itinerary,
            start=1
        ):

            actual_date = day.get(
                "date"
            )

            if actual_date != expected_date.isoformat():

                raise ValueError(
                    f"Invalid itinerary date at day {index}. "
                    f"Expected {expected_date.isoformat()}, "
                    f"received {actual_date}."
                )

            if day.get("day") != index:

                raise ValueError(
                    f"Invalid day number at itinerary entry {index}."
                )

            expected_date += datetime.timedelta(
                days=1
            )

    except ValueError:

        raise

    except Exception as e:

        raise ValueError(
            f"Date validation failed: {str(e)}"
        )


# ============================================================
# AGENT
# ============================================================

class Agent:

    def __init__(self):

        # ----------------------------------------------------
        # LLM
        # ----------------------------------------------------

        self._tools_llm = (
            ChatOpenAI(
                model="openrouter/free",
                api_key=os.getenv(
                    "OPENROUTER_API_KEY"
                ),
                base_url="https://openrouter.ai/api/v1",
                temperature=0,
            )
            .bind_tools(
                TOOLS,
                parallel_tool_calls=True
            )
        )

        # ----------------------------------------------------
        # TOOL REGISTRY
        # ----------------------------------------------------

        self.tools = {
            tool.name: tool
            for tool in TOOLS
        }

        # ----------------------------------------------------
        # GRAPH
        # ----------------------------------------------------

        graph = StateGraph(
            AgentState
        )

        graph.add_node(
            "call_tools_llm",
            self.call_tools_llm
        )

        graph.add_node(
            "invoke_tools",
            self.invoke_tools
        )

        graph.add_node(
            "email_sender",
            self.email_sender
        )

        graph.set_entry_point(
            "call_tools_llm"
        )

        graph.add_conditional_edges(
            "call_tools_llm",
            self.exists_action,
            {
                "more_tools": "invoke_tools",
                "email_sender": "email_sender",
            },
        )

        graph.add_edge(
            "invoke_tools",
            "call_tools_llm"
        )

        graph.add_edge(
            "email_sender",
            END
        )

        # ----------------------------------------------------
        # CHECKPOINT
        # ----------------------------------------------------

        memory = MemorySaver()

        self.graph = graph.compile(
            checkpointer=memory,
            interrupt_before=[
                "email_sender"
            ],
        )


    # ========================================================
    # CHECK WHETHER TOOL CALL EXISTS
    # ========================================================

    def exists_action(
        self,
        state: AgentState
    ):

        result = state["messages"][-1]

        tool_calls = getattr(
            result,
            "tool_calls",
            []
        )

        if not tool_calls:

            return "email_sender"

        return "more_tools"


    # ========================================================
    # CALL LLM WITH TIMING
    # ========================================================

    def call_tools_llm(
        self,
        state: AgentState
    ):

        start_time = time.perf_counter()

        print("\n========================================")
        print("LLM CALL STARTED")
        print("========================================")

        messages = [
            SystemMessage(
                content=TOOLS_SYSTEM_PROMPT
            )
        ] + state["messages"]

        try:

            response = self._tools_llm.invoke(
                messages
            )

            elapsed = (
                time.perf_counter()
                - start_time
            )

            print(
                f"LLM CALL COMPLETED IN: "
                f"{elapsed:.2f} seconds"
            )

            tool_calls = getattr(
                response,
                "tool_calls",
                []
            )

            print(
                "NUMBER OF TOOL CALLS:",
                len(tool_calls)
            )

            for tool_call in tool_calls:

                print(
                    "REQUESTED TOOL:",
                    tool_call.get("name")
                )

            print("========================================")

            return {
                "messages": [
                    response
                ]
            }

        except Exception as e:

            elapsed = (
                time.perf_counter()
                - start_time
            )

            print(
                f"LLM CALL FAILED AFTER: "
                f"{elapsed:.2f} seconds"
            )

            print(
                "LLM ERROR:",
                str(e)
            )

            raise


    # ========================================================
    # INVOKE TOOLS IN PARALLEL WITH TIMING
    # ========================================================

    def invoke_tools(
        self,
        state: AgentState
    ):

        from concurrent.futures import ThreadPoolExecutor

        last_message = state["messages"][-1]

        tool_calls = last_message.tool_calls

        print("\n========================================")
        print("TOOL EXECUTION STARTED")
        print(
            "NUMBER OF TOOLS:",
            len(tool_calls)
        )
        print("========================================")

        # ----------------------------------------------------
        # Execute one tool
        # ----------------------------------------------------

        def execute_tool(tool_call):

            tool_name = tool_call["name"]

            tool_args = tool_call["args"]

            print(
                f"\nTOOL STARTED: {tool_name}"
            )

            print(
                f"TOOL ARGUMENTS: {tool_args}"
            )

            tool = self.tools.get(
                tool_name
            )

            if tool is None:

                print(
                    f"UNKNOWN TOOL: {tool_name}"
                )

                return ToolMessage(
                    content=(
                        f"Unknown tool: {tool_name}"
                    ),
                    tool_call_id=tool_call["id"]
                )

            tool_start_time = (
                time.perf_counter()
            )

            try:

                result = tool.invoke(
                    tool_args
                )

                tool_elapsed = (
                    time.perf_counter()
                    - tool_start_time
                )

                print(
                    f"TOOL COMPLETED: {tool_name}"
                )

                print(
                    f"TOOL TIME: "
                    f"{tool_elapsed:.2f} seconds"
                )

                return ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                )

            except Exception as e:

                tool_elapsed = (
                    time.perf_counter()
                    - tool_start_time
                )

                print(
                    f"TOOL FAILED: {tool_name}"
                )

                print(
                    f"TOOL TIME: "
                    f"{tool_elapsed:.2f} seconds"
                )

                print(
                    f"TOOL ERROR: {e}"
                )

                return ToolMessage(
                    content=(
                        f"Tool error: {str(e)}"
                    ),
                    tool_call_id=tool_call["id"]
                )

        # ----------------------------------------------------
        # No tools
        # ----------------------------------------------------

        if not tool_calls:

            print(
                "No tool calls found."
            )

            return {
                "messages": []
            }

        # ----------------------------------------------------
        # Parallel timer
        # ----------------------------------------------------

        parallel_start_time = (
            time.perf_counter()
        )

        # ----------------------------------------------------
        # RUN ALL TOOLS CONCURRENTLY
        # ----------------------------------------------------

        with ThreadPoolExecutor(
            max_workers=len(tool_calls)
        ) as executor:

            tool_messages = list(
                executor.map(
                    execute_tool,
                    tool_calls
                )
            )

        parallel_elapsed = (
            time.perf_counter()
            - parallel_start_time
        )

        print("\n========================================")
        print("ALL TOOLS COMPLETED")
        print(
            f"PARALLEL TOOL TIME: "
            f"{parallel_elapsed:.2f} seconds"
        )
        print("========================================")

        return {
            "messages": tool_messages
        }


    # ========================================================
    # SEND EMAIL
    # ========================================================

    def email_sender(
        self,
        state: AgentState
    ):

        print(
            "\n========================================"
        )

        print(
            "EMAIL SENDER STARTED"
        )

        print(
            "========================================"
        )

        # ----------------------------------------------------
        # GET FINAL LLM RESPONSE
        # ----------------------------------------------------

        content = state["messages"][-1].content

        print(
            "\nRAW FINAL LLM RESPONSE:"
        )

        print(
            content
        )

        # ----------------------------------------------------
        # CLEAN JSON
        # ----------------------------------------------------

        cleaned_content = (
            clean_json_response(
                content
            )
        )

        print(
            "\nCLEANED JSON:"
        )

        print(
            cleaned_content
        )

        # ----------------------------------------------------
        # PARSE JSON
        # ----------------------------------------------------

        try:

            travel_data = json.loads(
                cleaned_content
            )

        except json.JSONDecodeError as e:

            print(
                "\n========================================"
            )

            print(
                "JSON PARSING ERROR"
            )

            print(
                "========================================"
            )

            print(
                "ERROR:",
                e
            )

            print(
                "\nCONTENT AFTER CLEANING:"
            )

            print(
                cleaned_content
            )

            raise ValueError(
                "The final LLM response could not be parsed as valid JSON."
            )

        print(
            "\nJSON PARSED SUCCESSFULLY"
        )

        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        validate_travel_data(
            travel_data
        )

        print(
            "TRAVEL DATA VALIDATION PASSED"
        )

        # ====================================================
        # EXTRACT DATA
        # ====================================================

        route = (
            travel_data.get(
                "route",
                {}
            )
            or {}
        )

        dates = (
            travel_data.get(
                "dates",
                {}
            )
            or {}
        )

        flights = (
            travel_data.get(
                "flights",
                []
            )
            or []
        )

        hotels = (
            travel_data.get(
                "hotels",
                []
            )
            or []
        )

        recommended_flight = (
            travel_data.get(
                "recommended_flight",
                {}
            )
            or {}
        )

        recommended_hotel = (
            travel_data.get(
                "recommended_hotel",
                {}
            )
            or {}
        )

        trip_estimate = (
            travel_data.get(
                "trip_estimate",
                {}
            )
            or {}
        )

        daily_itinerary = (
            travel_data.get(
                "daily_itinerary",
                []
            )
            or []
        )

        destination = travel_data.get(
            "destination",
            route.get("to", "")
        )

        # ====================================================
        # INR CONFIGURATION
        # ====================================================

        try:

            usd_to_inr = float(
                os.getenv(
                    "USD_TO_INR",
                    "88"
                )
            )

        except (TypeError, ValueError):

            usd_to_inr = 88.0

        # ====================================================
        # MONEY CONVERSION HELPER
        # ====================================================

        def money_to_float(value):

            if value is None:
                return 0.0

            if isinstance(value, (int, float)):
                return float(value)

            text = str(value).strip()

            if not text:
                return 0.0

            text = (
                text
                .replace("$", "")
                .replace("USD", "")
                .replace("usd", "")
                .replace("₹", "")
                .replace(",", "")
                .strip()
            )

            try:

                return float(text)

            except (TypeError, ValueError):

                return 0.0

        # ====================================================
        # ORIGINAL TRIP COST
        # ====================================================

        raw_flight_cost = trip_estimate.get(
            "flight"
        )

        raw_hotel_cost = trip_estimate.get(
            "hotel"
        )

        trip_currency = trip_estimate.get(
            "currency"
        )

        flight_cost_raw = money_to_float(
            raw_flight_cost
        )

        hotel_cost_raw = money_to_float(
            raw_hotel_cost
        )

        # ----------------------------------------------------
        # Convert to INR
        # ----------------------------------------------------

        if (
            trip_currency
            and str(trip_currency).upper() == "INR"
        ):

            flight_cost_inr = flight_cost_raw

            hotel_cost_inr = hotel_cost_raw

        else:

            flight_cost_inr = (
                flight_cost_raw
                * usd_to_inr
            )

            hotel_cost_inr = (
                hotel_cost_raw
                * usd_to_inr
            )

        # ====================================================
        # DAYS
        # ====================================================

        number_of_days = len(
            daily_itinerary
        )

        if number_of_days <= 0:

            number_of_days = 1

        # ====================================================
        # TRAVELERS
        # ====================================================

        travelers_raw = travel_data.get(
            "travelers",
            1
        )

        try:

            travelers_count = int(
                travelers_raw
            )

        except (TypeError, ValueError):

            travelers_count = 1

        if travelers_count <= 0:

            travelers_count = 1

        # ====================================================
        # AUTOMATIC PLANNING COSTS
        # ====================================================

        FOOD_PER_PERSON_PER_DAY = 1200

        TRANSPORT_PER_PERSON_PER_DAY = 500

        ACTIVITIES_PER_PERSON_PER_DAY = 600

        food_cost_inr = (
            FOOD_PER_PERSON_PER_DAY
            * travelers_count
            * number_of_days
        )

        transportation_cost_inr = (
            TRANSPORT_PER_PERSON_PER_DAY
            * travelers_count
            * number_of_days
        )

        activities_cost_inr = (
            ACTIVITIES_PER_PERSON_PER_DAY
            * travelers_count
            * number_of_days
        )

        # ====================================================
        # TOTAL BUDGET
        # ====================================================

        total_cost_inr = (
            flight_cost_inr
            + hotel_cost_inr
            + food_cost_inr
            + transportation_cost_inr
            + activities_cost_inr
        )

        # ====================================================
        # BUDGET PERCENTAGES
        # ====================================================

        if total_cost_inr > 0:

            flight_percentage = round(
                (
                    flight_cost_inr
                    / total_cost_inr
                ) * 100,
                2
            )

            hotel_percentage = round(
                (
                    hotel_cost_inr
                    / total_cost_inr
                ) * 100,
                2
            )

            food_percentage = round(
                (
                    food_cost_inr
                    / total_cost_inr
                ) * 100,
                2
            )

            transportation_percentage = round(
                (
                    transportation_cost_inr
                    / total_cost_inr
                ) * 100,
                2
            )

            activities_percentage = round(
                (
                    activities_cost_inr
                    / total_cost_inr
                ) * 100,
                2
            )

        else:

            flight_percentage = 0

            hotel_percentage = 0

            food_percentage = 0

            transportation_percentage = 0

            activities_percentage = 0

        print(
            "\n========================================"
        )

        print(
            "VOYARA EMAIL INR BUDGET"
        )

        print(
            "========================================"
        )

        print(
            "Flight INR:",
            flight_cost_inr
        )

        print(
            "Hotel INR:",
            hotel_cost_inr
        )

        print(
            "Food INR:",
            food_cost_inr
        )

        print(
            "Transportation INR:",
            transportation_cost_inr
        )

        print(
            "Activities INR:",
            activities_cost_inr
        )

        print(
            "Total INR:",
            total_cost_inr
        )

        print(
            "========================================"
        )

        # ====================================================
        # ROUTE
        # ====================================================

        from_city = escape_html(
            route.get(
                "from",
                ""
            )
        )

        from_code = escape_html(
            route.get(
                "from_code",
                ""
            )
        )

        to_city = escape_html(
            route.get(
                "to",
                ""
            )
        )

        to_code = escape_html(
            route.get(
                "to_code",
                ""
            )
        )

        # ====================================================
        # DATES
        # ====================================================

        start_date = escape_html(
            dates.get(
                "start",
                ""
            )
        )

        end_date = escape_html(
            dates.get(
                "end",
                ""
            )
        )

        # ====================================================
        # TRAVELERS
        # ====================================================

        travelers_display = escape_html(
            travel_data.get(
                "travelers",
                1
            )
        )

        travel_class = escape_html(
            travel_data.get(
                "class",
                "Economy"
            )
        )

        # ====================================================
        # DAILY ITINERARY HTML
        # ====================================================

        itinerary_html = ""

        for day in daily_itinerary:

            day_number = escape_html(
                day.get(
                    "day",
                    ""
                )
            )

            day_date = escape_html(
                day.get(
                    "date",
                    ""
                )
            )

            day_title = escape_html(
                day.get(
                    "title",
                    ""
                )
            )

            weather = (
                day.get(
                    "weather",
                    {}
                )
                or {}
            )

            weather_condition = escape_html(
                weather.get(
                    "condition",
                    ""
                )
            )

            weather_temperature = format_temperature(
                weather.get(
                    "temperature"
                )
            )

            rain_probability_value = weather.get(
                "rain_probability"
            )

            if rain_probability_value is not None:

                rain_probability = escape_html(
                    f"{rain_probability_value}%"
                )

            else:

                rain_probability = (
                    "Not available"
                )

            activities = (
                day.get(
                    "activities",
                    []
                )
                or []
            )

            activity_html = ""

            for activity in activities:

                activity_html += f"""
                <li style="
                    margin-bottom:8px;
                    color:#34495e;
                    line-height:1.6;
                ">
                    {escape_html(activity)}
                </li>
                """

            itinerary_html += f"""
            <div style="
                margin-bottom:20px;
                padding:18px;
                border:1px solid #e6edf2;
                border-radius:14px;
                background:#f9fbfc;
            ">

                <div style="
                    font-size:13px;
                    color:#718096;
                    margin-bottom:5px;
                ">
                    DAY {day_number} · {day_date}
                </div>

                <div style="
                    font-size:18px;
                    font-weight:700;
                    color:#183b56;
                    margin-bottom:10px;
                ">
                    {day_title}
                </div>

                <div style="
                    margin-bottom:15px;
                    padding:12px 15px;
                    background:#eef6fb;
                    border-radius:10px;
                    color:#34495e;
                    font-size:13px;
                ">

                    <strong>🌤️ Weather</strong>

                    <br>

                    Condition:
                    {weather_condition or "Not available"}

                    &nbsp; | &nbsp;

                    Temperature:
                    {weather_temperature}

                    &nbsp; | &nbsp;

                    Rain Probability:
                    {rain_probability}

                </div>

                <ul style="
                    padding-left:20px;
                    margin:0;
                ">
                    {activity_html}
                </ul>

            </div>
            """

        # ====================================================
        # FLIGHTS HTML
        # ====================================================

        flight_html = ""

        for flight in flights:

            airline = escape_html(
                flight.get(
                    "airline",
                    ""
                )
            )

            flight_number = escape_html(
                flight.get(
                    "flight",
                    ""
                )
            )

            departure = escape_html(
                flight.get(
                    "departure",
                    ""
                )
            )

            arrival = escape_html(
                flight.get(
                    "arrival",
                    ""
                )
            )

            duration = escape_html(
                flight.get(
                    "duration",
                    ""
                )
            )

            price = format_money(
                flight.get(
                    "price"
                )
            )

            currency = escape_html(
                flight.get(
                    "currency",
                    ""
                )
            )

            booking_url = flight.get(
                "booking_url"
            )

            booking_html = ""

            if booking_url:

                safe_booking_url = escape_html(
                    booking_url
                )

                booking_html = f"""
                <a href="{safe_booking_url}"
                   style="
                       display:inline-block;
                       margin-top:10px;
                       padding:9px 16px;
                       background:#183b56;
                       color:#ffffff;
                       text-decoration:none;
                       border-radius:8px;
                       font-size:13px;
                   ">
                    View Flight
                </a>
                """

            flight_html += f"""
            <div style="
                margin-bottom:15px;
                padding:18px;
                border:1px solid #e6edf2;
                border-radius:12px;
            ">

                <div style="
                    font-size:17px;
                    font-weight:700;
                    color:#183b56;
                ">
                    {airline}
                </div>

                <div style="
                    font-size:13px;
                    color:#718096;
                    margin-top:4px;
                ">
                    Flight {flight_number}
                </div>

                <p style="
                    color:#34495e;
                    line-height:1.7;
                ">

                    <strong>Departure:</strong>
                    {departure}

                    <br>

                    <strong>Arrival:</strong>
                    {arrival}

                    <br>

                    <strong>Duration:</strong>
                    {duration}

                    <br>

                    <strong>Price:</strong>
                    {currency} {price}

                </p>

                {booking_html}

            </div>
            """

        # ====================================================
        # RECOMMENDED FLIGHT
        # ====================================================

        recommended_flight_html = ""

        if recommended_flight:

            rec_airline = escape_html(
                recommended_flight.get(
                    "airline",
                    ""
                )
            )

            rec_flight = escape_html(
                recommended_flight.get(
                    "flight",
                    ""
                )
            )

            rec_reason = escape_html(
                recommended_flight.get(
                    "reason",
                    ""
                )
            )

            recommended_flight_html = f"""
            <div style="
                margin-top:18px;
                padding:18px;
                background:#eef7f8;
                border-left:4px solid #2c7a7b;
                border-radius:10px;
            ">

                <div style="
                    font-weight:700;
                    color:#183b56;
                    margin-bottom:7px;
                ">
                    ⭐ Recommended Flight
                </div>

                <div style="
                    color:#34495e;
                    line-height:1.6;
                ">

                    <strong>{rec_airline}</strong>
                    —
                    {rec_flight}

                    <br>

                    {rec_reason}

                </div>

            </div>
            """

        # ====================================================
        # HOTELS HTML
        # ====================================================

        hotel_html = ""

        for hotel in hotels:

            hotel_name = escape_html(
                hotel.get(
                    "name",
                    ""
                )
            )

            rating = escape_html(
                hotel.get(
                    "rating",
                    ""
                )
            )

            price_per_night = format_money(
                hotel.get(
                    "price_per_night"
                )
            )

            total_price = format_money(
                hotel.get(
                    "total_price"
                )
            )

            currency = escape_html(
                hotel.get(
                    "currency",
                    ""
                )
            )

            location = escape_html(
                hotel.get(
                    "location",
                    ""
                )
            )

            website_url = hotel.get(
                "website_url"
            )

            website_html = ""

            if website_url:

                safe_website_url = escape_html(
                    website_url
                )

                website_html = f"""
                <a href="{safe_website_url}"
                   style="
                       display:inline-block;
                       margin-top:10px;
                       padding:9px 16px;
                       background:#183b56;
                       color:#ffffff;
                       text-decoration:none;
                       border-radius:8px;
                       font-size:13px;
                   ">
                    View Hotel
                </a>
                """

            hotel_html += f"""
            <div style="
                margin-bottom:15px;
                padding:18px;
                border:1px solid #e6edf2;
                border-radius:12px;
            ">

                <div style="
                    font-size:17px;
                    font-weight:700;
                    color:#183b56;
                ">
                    {hotel_name}
                </div>

                <p style="
                    color:#34495e;
                    line-height:1.7;
                ">

                    <strong>Rating:</strong>
                    {rating or "Not available"}

                    <br>

                    <strong>Location:</strong>
                    {location or "Not available"}

                    <br>

                    <strong>Price per night:</strong>
                    {currency}
                    {price_per_night}

                    <br>

                    <strong>Total price:</strong>
                    {currency}
                    {total_price}

                </p>

                {website_html}

            </div>
            """

        # ====================================================
        # RECOMMENDED HOTEL
        # ====================================================

        recommended_hotel_html = ""

        if recommended_hotel:

            rec_hotel_name = escape_html(
                recommended_hotel.get(
                    "name",
                    ""
                )
            )

            rec_hotel_reason = escape_html(
                recommended_hotel.get(
                    "reason",
                    ""
                )
            )

            recommended_hotel_html = f"""
            <div style="
                margin-top:18px;
                padding:18px;
                background:#eef7f8;
                border-left:4px solid #2c7a7b;
                border-radius:10px;
            ">

                <div style="
                    font-weight:700;
                    color:#183b56;
                    margin-bottom:7px;
                ">
                    ⭐ Recommended Hotel
                </div>

                <div style="
                    color:#34495e;
                    line-height:1.6;
                ">

                    <strong>{rec_hotel_name}</strong>

                    <br>

                    {rec_hotel_reason}

                </div>

            </div>
            """

        # ====================================================
        # INR DISPLAY VALUES
        # ====================================================

        flight_inr_display = (
            f"₹{flight_cost_inr:,.0f}"
        )

        hotel_inr_display = (
            f"₹{hotel_cost_inr:,.0f}"
        )

        food_inr_display = (
            f"₹{food_cost_inr:,.0f}"
        )

        transportation_inr_display = (
            f"₹{transportation_cost_inr:,.0f}"
        )

        activities_inr_display = (
            f"₹{activities_cost_inr:,.0f}"
        )

        total_inr_display = (
            f"₹{total_cost_inr:,.0f}"
        )

        # ====================================================
        # BUDGET BREAKDOWN
        # ====================================================

        budget_html = f"""
        <div style="
            margin-top:35px;
            font-size:22px;
            font-weight:700;
            color:#183b56;
            margin-bottom:15px;
        ">
            💰 Estimated Trip Budget
        </div>

        <div style="
            padding:22px;
            background:#f7fafc;
            border-radius:14px;
            border:1px solid #e6edf2;
        ">

            <div style="
                text-align:center;
                margin-bottom:22px;
                padding:18px;
                background:#eef7f8;
                border-radius:12px;
            ">

                <div style="
                    font-size:13px;
                    color:#718096;
                    margin-bottom:5px;
                ">
                    Estimated Total
                </div>

                <div style="
                    font-size:30px;
                    font-weight:800;
                    color:#183b56;
                ">
                    {total_inr_display}
                </div>

                <div style="
                    margin-top:6px;
                    font-size:12px;
                    color:#718096;
                ">
                    Approximate planning estimate for
                    {travelers_display} traveler(s)
                    for {number_of_days} day(s)
                </div>

            </div>

            <table width="100%"
                   cellpadding="8"
                   cellspacing="0"
                   style="
                       border-collapse:collapse;
                       color:#34495e;
                       font-size:14px;
                   ">

                <tr>

                    <td style="
                        border-bottom:1px solid #e6edf2;
                        padding:10px 5px;
                    ">
                        ✈️ Flights
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            font-weight:700;
                        ">
                        {flight_inr_display}
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            color:#718096;
                        ">
                        {flight_percentage}%
                    </td>

                </tr>

                <tr>

                    <td style="
                        border-bottom:1px solid #e6edf2;
                        padding:10px 5px;
                    ">
                        🏨 Hotels
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            font-weight:700;
                        ">
                        {hotel_inr_display}
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            color:#718096;
                        ">
                        {hotel_percentage}%
                    </td>

                </tr>

                <tr>

                    <td style="
                        border-bottom:1px solid #e6edf2;
                        padding:10px 5px;
                    ">
                        🍛 Food
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            font-weight:700;
                        ">
                        {food_inr_display}
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            color:#718096;
                        ">
                        {food_percentage}%
                    </td>

                </tr>

                <tr>

                    <td style="
                        border-bottom:1px solid #e6edf2;
                        padding:10px 5px;
                    ">
                        🚕 Transportation
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            font-weight:700;
                        ">
                        {transportation_inr_display}
                    </td>

                    <td align="right"
                        style="
                            border-bottom:1px solid #e6edf2;
                            padding:10px 5px;
                            color:#718096;
                        ">
                        {transportation_percentage}%
                    </td>

                </tr>

                <tr>

                    <td style="
                        padding:10px 5px;
                    ">
                        🎟️ Activities
                    </td>

                    <td align="right"
                        style="
                            padding:10px 5px;
                            font-weight:700;
                        ">
                        {activities_inr_display}
                    </td>

                    <td align="right"
                        style="
                            padding:10px 5px;
                            color:#718096;
                        ">
                        {activities_percentage}%
                    </td>

                </tr>

            </table>

            <div style="
                margin-top:18px;
                padding-top:15px;
                border-top:1px solid #dce5eb;
                font-size:12px;
                line-height:1.7;
                color:#718096;
            ">

                <strong>Planning assumptions:</strong>

                <br>

                Food:
                ₹1,200 per traveler per day

                <br>

                Transportation:
                ₹500 per traveler per day

                <br>

                Activities:
                ₹600 per traveler per day

                <br>

                Flight and hotel amounts are converted to INR
                using an approximate USD/INR rate of
                ₹{usd_to_inr:.2f}.

                <br>

                This is an estimated planning budget and may
                differ from actual booking prices.

            </div>

        </div>
        """

        # ====================================================
        # FINAL EMAIL HTML
        # ====================================================

        html_content = f"""
        <!DOCTYPE html>

        <html>

        <head>

            <meta charset="UTF-8">

            <meta name="viewport"
                  content="width=device-width,
                           initial-scale=1.0">

            <title>Voyara Travel Itinerary</title>

        </head>

        <body style="
            margin:0;
            padding:0;
            background:#f4f7f9;
            font-family:Arial, Helvetica, sans-serif;
        ">

            <div style="
                max-width:700px;
                margin:30px auto;
                background:#ffffff;
                border-radius:18px;
                overflow:hidden;
                box-shadow:0 4px 20px rgba(0,0,0,0.08);
            ">

                <!-- HEADER -->

                <div style="
                    padding:30px;
                    background:#183b56;
                    color:#ffffff;
                ">

                    <div style="
                        font-size:28px;
                        font-weight:800;
                        letter-spacing:1px;
                    ">
                        Voyara
                    </div>

                    <div style="
                        margin-top:8px;
                        font-size:14px;
                        opacity:0.85;
                    ">
                        Your personalized journey
                    </div>

                </div>

                <!-- TRIP SUMMARY -->

                <div style="
                    padding:30px;
                    text-align:center;
                ">

                    <div style="
                        font-size:26px;
                        font-weight:700;
                        color:#183b56;
                    ">
                        {from_city}
                        →
                        {to_city}
                    </div>

                    <div style="
                        margin-top:10px;
                        color:#718096;
                        font-size:14px;
                    ">
                        {from_code}
                        →
                        {to_code}
                    </div>

                    <div style="
                        margin-top:20px;
                        padding:15px;
                        background:#f7fafc;
                        border-radius:12px;
                        color:#34495e;
                        line-height:1.8;
                    ">

                        📅
                        <strong>Dates:</strong>
                        {start_date}
                        →
                        {end_date}

                        <br>

                        👤
                        <strong>Travelers:</strong>
                        {travelers_display}

                        &nbsp; | &nbsp;

                        ✈️
                        <strong>Class:</strong>
                        {travel_class}

                    </div>

                </div>

                <!-- MAIN CONTENT -->

                <div style="
                    padding:0 30px 30px 30px;
                ">

                    <!-- DAY BY DAY -->

                    <div style="
                        font-size:22px;
                        font-weight:700;
                        color:#183b56;
                        margin-bottom:8px;
                    ">
                        🗓️ Your Day-by-Day Plan
                    </div>

                    <div style="
                        font-size:13px;
                        color:#718096;
                        margin-bottom:20px;
                    ">
                        A personalized plan for your stay in
                        {escape_html(destination)}.
                    </div>

                    {itinerary_html}

                    <!-- FLIGHTS -->

                    <div style="
                        margin-top:35px;
                        font-size:22px;
                        font-weight:700;
                        color:#183b56;
                        margin-bottom:15px;
                    ">
                        ✈️ Flight Options
                    </div>

                    {flight_html}

                    {recommended_flight_html}

                    <!-- HOTELS -->

                    <div style="
                        margin-top:35px;
                        font-size:22px;
                        font-weight:700;
                        color:#183b56;
                        margin-bottom:15px;
                    ">
                        🏨 Hotel Options
                    </div>

                    {hotel_html}

                    {recommended_hotel_html}

                    <!-- BUDGET -->

                    {budget_html}

                </div>

                <!-- FOOTER -->

                <div style="
                    padding:25px 30px;
                    background:#f7fafc;
                    text-align:center;
                    color:#718096;
                    font-size:12px;
                ">

                    <div style="
                        font-weight:700;
                        color:#183b56;
                        margin-bottom:5px;
                    ">
                        Voyara
                    </div>

                    Your AI-powered travel companion.

                    <br><br>

                    Travel suggestions and budget estimates are
                    provided for planning purposes. Please verify
                    booking details and prices before purchase.

                </div>

            </div>

        </body>

        </html>
        """

        # ====================================================
        # SENDGRID CONFIGURATION
        # ====================================================

        from_email = os.getenv(
            "FROM_EMAIL"
        )

        to_email = os.getenv(
            "TO_EMAIL"
        )

        sendgrid_api_key = os.getenv(
            "SENDGRID_API_KEY"
        )

        subject = os.getenv(
            "EMAIL_SUBJECT",
            "My Voyara Travel Itinerary"
        )

        if not from_email:

            raise ValueError(
                "FROM_EMAIL is missing in .env"
            )

        if not to_email:

            raise ValueError(
                "TO_EMAIL is missing in .env"
            )

        if not sendgrid_api_key:

            raise ValueError(
                "SENDGRID_API_KEY is missing in .env"
            )

        # ====================================================
        # SEND EMAIL
        # ====================================================

        message = Mail(
            from_email=from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content,
        )

        try:

            print(
                "\n========================================"
            )

            print(
                "SENDING EMAIL THROUGH SENDGRID"
            )

            print(
                "========================================"
            )

            print(
                "FROM:",
                from_email
            )

            print(
                "TO:",
                to_email
            )

            print(
                "SUBJECT:",
                subject
            )

            sg = SendGridAPIClient(
                sendgrid_api_key
            )

            response = sg.send(
                message
            )

            print(
                "\n========================================"
            )

            print(
                "EMAIL SENT SUCCESSFULLY"
            )

            print(
                "STATUS:",
                response.status_code
            )

            print(
                "========================================"
            )

        except Exception as e:

            print(
                "\n========================================"
            )

            print(
                "EMAIL SENDING FAILED"
            )

            print(
                "ERROR:",
                str(e)
            )

            print(
                "========================================"
            )

            raise

        # ====================================================
        # RETURN STATE
        # ====================================================

        return {
            "messages": [
                ToolMessage(
                    content=(
                        "Travel itinerary email "
                        "sent successfully."
                    ),
                    tool_call_id="email_sender",
                )
            ]
        }