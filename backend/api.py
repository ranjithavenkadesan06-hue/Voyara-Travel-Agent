import uuid
import json
import os
import re

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel
from sqlalchemy.orm import Session

from langchain_core.messages import HumanMessage

from agents.agent import Agent

from backend.database import engine, Base, get_db
from backend.models import User

from backend.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user_id
)

from backend.schemas import (
    UserCreate,
    UserResponse,
    Token,
    LoginRequest
)

from backend.budget_planner import calculate_budget


# =========================================================
# DATABASE
# =========================================================

Base.metadata.create_all(bind=engine)


# =========================================================
# FASTAPI APP
# =========================================================

app = FastAPI(title="Voyara API")


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# AI TRAVEL AGENT
# =========================================================

agent = Agent()


# =========================================================
# CONFIGURATION
# =========================================================

# You can change this later without changing the code.
#
# Example:
# USD_TO_INR=88
#
# If the environment variable does not exist,
# Voyara will use 88.0.
#
# This is used only for display/planning conversion.
# It is NOT a live exchange-rate service.

USD_TO_INR = float(
    os.getenv("USD_TO_INR", "88")
)


# =========================================================
# REQUEST MODELS
# =========================================================

class TravelQuery(BaseModel):
    query: str


class EmailRequest(BaseModel):
    receiver_email: str
    subject: str
    thread_id: str


class BudgetRequest(BaseModel):
    travel_info: dict
    budget: float


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def home():
    return {
        "message": "AI Travel Agent API is running"
    }


# =========================================================
# AUTHENTICATION
# =========================================================

@app.post(
    "/auth/register",
    response_model=UserResponse
)
def register(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = (
        db.query(User)
        .filter(User.email == user.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = User(
        name=user.name,
        email=user.email,
        hashed_password=hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.post(
    "/auth/login",
    response_model=Token
)
def login(
    credentials: LoginRequest,
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.email == credentials.email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    if not verify_password(
        credentials.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id)
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }


@app.get(
    "/auth/me",
    response_model=UserResponse
)
def get_me(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    return user


# =========================================================
# HELPER — EXTRACT TEXT FROM AI RESPONSE
# =========================================================

def extract_ai_text(content):

    # -----------------------------------------
    # Case 1: normal string
    # -----------------------------------------

    if isinstance(content, str):
        return content.strip()

    # -----------------------------------------
    # Case 2: list of content blocks
    # -----------------------------------------

    if isinstance(content, list):

        parts = []

        for item in content:

            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):

                if item.get("type") == "text":
                    parts.append(
                        str(item.get("text", ""))
                    )

                elif "text" in item:
                    parts.append(
                        str(item["text"])
                    )

        return "".join(parts).strip()

    # -----------------------------------------
    # Case 3: anything else
    # -----------------------------------------

    return str(content).strip()


# =========================================================
# HELPER — CLEAN JSON RESPONSE
# =========================================================

def clean_json_response(text):

    text = text.strip()

    # Remove markdown code fences

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(
        r"^```\s*",
        "",
        text
    )

    text = re.sub(
        r"\s*```$",
        "",
        text
    )

    text = text.strip()

    # -----------------------------------------
    # Sometimes AI adds text before JSON.
    # Find the first JSON object.
    # -----------------------------------------

    first_brace = text.find("{")

    last_brace = text.rfind("}")

    if first_brace != -1 and last_brace != -1:

        text = text[
            first_brace:last_brace + 1
        ]

    return text.strip()


# =========================================================
# MONEY HELPERS
# =========================================================

def to_number(value):
    """
    Convert values such as:

        250
        "250"
        "$250"
        "USD 250"
        "250.50"

    into float.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):

        cleaned = value.strip()

        if not cleaned:
            return None

        allowed = "0123456789.-"

        numeric = "".join(
            character
            for character in cleaned
            if character in allowed
        )

        if not numeric:
            return None

        try:
            return float(numeric)

        except ValueError:
            return None

    return None


def convert_usd_to_inr(value):
    """
    Convert USD amount to INR using the configured
    USD_TO_INR value.
    """

    number = to_number(value)

    if number is None:
        return 0.0

    return round(
        number * USD_TO_INR,
        2
    )


# =========================================================
# EXTRACT TRIP COST
# =========================================================

def get_trip_cost(
    travel_info,
    field
):
    """
    Extract flight/hotel cost from trip_estimate.
    """

    trip_estimate = (
        travel_info.get(
            "trip_estimate",
            {}
        )
        or {}
    )

    return to_number(
        trip_estimate.get(field)
    )


# =========================================================
# CALCULATE AUTOMATIC TRIP ESTIMATE
# =========================================================

def calculate_automatic_trip_estimate(
    travel_info
):
    """
    Creates an automatic estimated trip budget.

    Important:
    - Flight and hotel prices come from the AI/search data.
    - Food, transportation and activities are planning estimates.
    - The result is converted to INR.
    - No additional LLM call is required.
    """

    flight_usd = get_trip_cost(
        travel_info,
        "flight"
    ) or 0.0

    hotel_usd = get_trip_cost(
        travel_info,
        "hotel"
    ) or 0.0

    # -----------------------------------------------------
    # Convert actual/search-derived costs
    # -----------------------------------------------------

    flight_inr = convert_usd_to_inr(
        flight_usd
    )

    hotel_inr = convert_usd_to_inr(
        hotel_usd
    )

    # -----------------------------------------------------
    # Determine number of days
    # -----------------------------------------------------

    dates = (
        travel_info.get(
            "dates",
            {}
        )
        or {}
    )

    daily_itinerary = (
        travel_info.get(
            "daily_itinerary",
            []
        )
        or []
    )

    number_of_days = len(
        daily_itinerary
    )

    # Fallback if itinerary isn't available
    if number_of_days <= 0:
        number_of_days = 1

    travelers = to_number(
        travel_info.get(
            "travelers",
            1
        )
    ) or 1

    travelers = max(
        int(travelers),
        1
    )

    # -----------------------------------------------------
    # Planning estimates
    # -----------------------------------------------------
    #
    # These are NOT actual bookings.
    #
    # Food:
    # ₹1,200 per traveler/day
    #
    # Local transport:
    # ₹500 per traveler/day
    #
    # Activities:
    # ₹600 per traveler/day
    #
    # These can be changed later.
    # -----------------------------------------------------

    food_inr = (
        1200
        * travelers
        * number_of_days
    )

    transportation_inr = (
        500
        * travelers
        * number_of_days
    )

    activities_inr = (
        600
        * travelers
        * number_of_days
    )

    # -----------------------------------------------------
    # Total
    # -----------------------------------------------------

    total_inr = (
        flight_inr
        + hotel_inr
        + food_inr
        + transportation_inr
        + activities_inr
    )

    # -----------------------------------------------------
    # Percentages
    # -----------------------------------------------------

    if total_inr > 0:

        percentages = {

            "flights": round(
                (flight_inr / total_inr) * 100,
                2
            ),

            "hotels": round(
                (hotel_inr / total_inr) * 100,
                2
            ),

            "food": round(
                (food_inr / total_inr) * 100,
                2
            ),

            "transportation": round(
                (transportation_inr / total_inr) * 100,
                2
            ),

            "activities": round(
                (activities_inr / total_inr) * 100,
                2
            )
        }

    else:

        percentages = {
            "flights": 0,
            "hotels": 0,
            "food": 0,
            "transportation": 0,
            "activities": 0
        }

    # -----------------------------------------------------
    # Return automatic estimate
    # -----------------------------------------------------

    return {

        "currency": "INR",

        "exchange_rate": USD_TO_INR,

        "estimated_cost": round(
            total_inr,
            2
        ),

        "breakdown": {

            "flights": round(
                flight_inr,
                2
            ),

            "hotels": round(
                hotel_inr,
                2
            ),

            "food": round(
                food_inr,
                2
            ),

            "transportation": round(
                transportation_inr,
                2
            ),

            "activities": round(
                activities_inr,
                2
            )
        },

        "percentages": percentages,

        "planning_notes": [
            "Flight and hotel amounts are based on the current search results.",
            "Food, transportation and activity amounts are planning estimates.",
            "Exchange rate is configurable and is not a live exchange-rate feed."
        ]
    }


# =========================================================
# TRAVEL SEARCH
# =========================================================

@app.post("/travel")
def travel(data: TravelQuery):

    thread_id = str(uuid.uuid4())

    messages = [
        HumanMessage(
            content=data.query
        )
    ]

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:

        print("\n")
        print("=" * 70)
        print("VOYARA TRAVEL SEARCH")
        print("=" * 70)
        print("QUERY:")
        print(data.query)
        print("THREAD ID:")
        print(thread_id)
        print("=" * 70)

        # -----------------------------------------
        # Run AI agent
        # -----------------------------------------

        result = agent.graph.invoke(
            {
                "messages": messages
            },
            config=config
        )

        # -----------------------------------------
        # Validate result
        # -----------------------------------------

        if not result:

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI did not return a response."
                )
            )

        if "messages" not in result:

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI returned an unexpected response."
                )
            )

        if not result["messages"]:

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI returned no messages."
                )
            )

        # -----------------------------------------
        # Get final message
        # -----------------------------------------

        final_message = result["messages"][-1]

        raw_content = final_message.content

        print("\n")
        print("=" * 70)
        print("AI CONTENT TYPE")
        print("=" * 70)
        print(type(raw_content))

        print("\n")
        print("=" * 70)
        print("RAW AI CONTENT")
        print("=" * 70)
        print(repr(raw_content))
        print("=" * 70)

        # -----------------------------------------
        # Extract text
        # -----------------------------------------

        cleaned = extract_ai_text(
            raw_content
        )

        print("\n")
        print("=" * 70)
        print("EXTRACTED AI TEXT")
        print("=" * 70)
        print(repr(cleaned))
        print("=" * 70)

        # -----------------------------------------
        # Empty response
        # -----------------------------------------

        if not cleaned:

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI returned an empty response. "
                    "Please try again."
                )
            )

        # -----------------------------------------
        # Clean JSON
        # -----------------------------------------

        cleaned_json = clean_json_response(
            cleaned
        )

        print("\n")
        print("=" * 70)
        print("CLEANED JSON")
        print("=" * 70)
        print(cleaned_json)
        print("=" * 70)

        # -----------------------------------------
        # Parse JSON
        # -----------------------------------------

        try:

            travel_info = json.loads(
                cleaned_json
            )

        except json.JSONDecodeError as e:

            print("\n")
            print("=" * 70)
            print("JSON PARSING FAILED")
            print("=" * 70)
            print("ERROR:", str(e))
            print("CONTENT:", repr(cleaned_json))
            print("=" * 70)

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI generated travel information "
                    "but the response format was invalid. "
                    "Please try again."
                )
            )

        # -----------------------------------------
        # Make sure JSON is an object
        # -----------------------------------------

        if not isinstance(
            travel_info,
            dict
        ):

            raise HTTPException(
                status_code=502,
                detail=(
                    "Voyara AI returned an invalid travel format."
                )
            )

        # =================================================
        # AUTOMATIC INR TRIP BUDGET
        # =================================================

        print("\n")
        print("=" * 70)
        print("CALCULATING VOYARA INR TRIP ESTIMATE")
        print("=" * 70)

        automatic_budget = (
            calculate_automatic_trip_estimate(
                travel_info
            )
        )

        # -------------------------------------------------
        # Add automatic budget to travel_info
        # -------------------------------------------------

        travel_info["budget"] = automatic_budget

        # -------------------------------------------------
        # Also replace the trip estimate with INR values
        # -------------------------------------------------
        #
        # This makes the existing trip estimate section
        # display INR instead of USD.
        #
        # We preserve all other existing fields.
        # -------------------------------------------------

        existing_trip_estimate = (
            travel_info.get(
                "trip_estimate",
                {}
            )
            or {}
        )

        travel_info["trip_estimate"] = {
            **existing_trip_estimate,

            "flight": automatic_budget[
                "breakdown"
            ]["flights"],

            "hotel": automatic_budget[
                "breakdown"
            ]["hotels"],

            "food": automatic_budget[
                "breakdown"
            ]["food"],

            "transportation": automatic_budget[
                "breakdown"
            ]["transportation"],

            "activities": automatic_budget[
                "breakdown"
            ]["activities"],

            "total": automatic_budget[
                "estimated_cost"
            ],

            "currency": "INR"
        }

        print(
            "Flight INR:",
            automatic_budget[
                "breakdown"
            ]["flights"]
        )

        print(
            "Hotel INR:",
            automatic_budget[
                "breakdown"
            ]["hotels"]
        )

        print(
            "Food INR:",
            automatic_budget[
                "breakdown"
            ]["food"]
        )

        print(
            "Transportation INR:",
            automatic_budget[
                "breakdown"
            ]["transportation"]
        )

        print(
            "Activities INR:",
            automatic_budget[
                "breakdown"
            ]["activities"]
        )

        print(
            "Estimated Total INR:",
            automatic_budget[
                "estimated_cost"
            ]
        )

        print("=" * 70)

        # -----------------------------------------
        # Success logging
        # -----------------------------------------

        print("\n")
        print("=" * 70)
        print("VOYARA TRAVEL SEARCH SUCCESS")
        print("=" * 70)

        print(
            "Destination:",
            travel_info.get(
                "destination",
                "Unknown"
            )
        )

        print(
            "Flights:",
            len(
                travel_info.get(
                    "flights",
                    []
                )
            )
        )

        print(
            "Hotels:",
            len(
                travel_info.get(
                    "hotels",
                    []
                )
            )
        )

        print(
            "Recommended flight:",
            travel_info.get(
                "recommended_flight"
            )
        )

        print(
            "Recommended hotel:",
            travel_info.get(
                "recommended_hotel"
            )
        )

        print(
            "Automatic budget:",
            travel_info.get(
                "budget"
            )
        )

        print("=" * 70)
        print("\n")

        # -----------------------------------------
        # Final response
        # -----------------------------------------

        return {
            "thread_id": thread_id,
            "travel_info": travel_info
        }

    except HTTPException:
        raise

    except Exception as e:

        print("\n")
        print("=" * 70)
        print("VOYARA TRAVEL ERROR")
        print("=" * 70)
        print(
            "ERROR:",
            repr(e)
        )
        print("=" * 70)
        print("\n")

        raise HTTPException(
            status_code=500,
            detail=(
                f"Travel search failed: {str(e)}"
            )
        )


# =========================================================
# AI BUDGET PLANNER
# =========================================================

@app.post("/budget")
def budget_planner(data: BudgetRequest):

    try:

        print("\n")
        print("=" * 70)
        print("VOYARA AI BUDGET PLANNER")
        print("=" * 70)

        print(
            "USER BUDGET:",
            data.budget
        )

        result = calculate_budget(
            travel_info=data.travel_info,
            budget=data.budget
        )

        print(
            "ESTIMATED COST:",
            result["estimated_cost"]
        )

        print(
            "REMAINING:",
            result["remaining"]
        )

        print(
            "STATUS:",
            result["status"]
        )

        print("=" * 70)

        return {
            "success": True,
            "budget": result
        }

    except ValueError as e:

        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:

        print(
            "BUDGET PLANNER ERROR:",
            repr(e)
        )

        raise HTTPException(
            status_code=500,
            detail=(
                f"Budget calculation failed: {str(e)}"
            )
        )


# =========================================================
# SEND EMAIL
# =========================================================

@app.post("/send-email")
def send_email(data: EmailRequest):

    try:

        # -----------------------------------------
        # Receiver
        # -----------------------------------------

        os.environ["TO_EMAIL"] = (
            data.receiver_email
        )

        # -----------------------------------------
        # Subject
        # -----------------------------------------

        os.environ["EMAIL_SUBJECT"] = (
            data.subject
        )

        # -----------------------------------------
        # Thread configuration
        # -----------------------------------------

        config = {
            "configurable": {
                "thread_id": data.thread_id
            }
        }

        # -----------------------------------------
        # Get graph state
        # -----------------------------------------

        state = agent.graph.get_state(
            config
        )

        print("\n")
        print("=" * 60)
        print("VOYARA EMAIL")
        print("=" * 60)

        print(
            "THREAD ID:",
            data.thread_id
        )

        print(
            "NEXT:",
            state.next
        )

        print(
            "FROM EMAIL:",
            os.environ.get(
                "FROM_EMAIL"
            )
        )

        print(
            "TO EMAIL:",
            data.receiver_email
        )

        print(
            "SUBJECT:",
            data.subject
        )

        print("=" * 60)

        # -----------------------------------------
        # Continue interrupted graph
        # -----------------------------------------

        agent.graph.invoke(
            None,
            config=config
        )

        print(
            "Email workflow completed."
        )

        return {
            "success": True,
            "message": (
                "Email sent successfully!"
            )
        }

    except Exception as e:

        print("\n")
        print("=" * 60)
        print("EMAIL ERROR")
        print("=" * 60)
        print(
            repr(e)
        )
        print("=" * 60)

        return {
            "success": False,
            "message": (
                f"Error sending email: {str(e)}"
            )
        }