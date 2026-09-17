from typing import Any, Dict, Optional


# ============================================================
# HELPERS
# ============================================================

def to_number(value: Any) -> Optional[float]:
    """
    Convert a value into a numeric amount.

    Handles values such as:
        250
        "250"
        "$250"
        "USD 250"
        "250.50"
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

        # Keep digits, decimal point and minus sign.
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


def round_money(value: float) -> float:
    return round(float(value), 2)


# ============================================================
# EXTRACT EXISTING TRIP COSTS
# ============================================================

def extract_flight_cost(travel_info: Dict[str, Any]) -> float:
    """
    Prefer the existing trip_estimate flight value.

    This preserves the flight-cost logic already produced by
    Voyara instead of calculating a different value.
    """

    trip_estimate = (
        travel_info.get("trip_estimate", {})
        or {}
    )

    flight_cost = to_number(
        trip_estimate.get("flight")
    )

    if flight_cost is not None:
        return round_money(flight_cost)

    return 0.0


def extract_hotel_cost(travel_info: Dict[str, Any]) -> float:
    """
    Prefer the existing trip_estimate hotel value.
    """

    trip_estimate = (
        travel_info.get("trip_estimate", {})
        or {}
    )

    hotel_cost = to_number(
        trip_estimate.get("hotel")
    )

    if hotel_cost is not None:
        return round_money(hotel_cost)

    return 0.0


def extract_currency(travel_info: Dict[str, Any]) -> str:
    trip_estimate = (
        travel_info.get("trip_estimate", {})
        or {}
    )

    currency = trip_estimate.get("currency")

    if currency:
        return str(currency)

    flights = travel_info.get("flights", []) or []

    for flight in flights:
        currency = flight.get("currency")

        if currency:
            return str(currency)

    hotels = travel_info.get("hotels", []) or []

    for hotel in hotels:
        currency = hotel.get("currency")

        if currency:
            return str(currency)

    return "USD"


# ============================================================
# BUDGET PLANNER
# ============================================================

def calculate_budget(
    travel_info: Dict[str, Any],
    budget: float,
) -> Dict[str, Any]:
    """
    Calculate a complete travel budget.

    Existing real flight and hotel costs are preserved.

    The remaining budget is divided between:
        - food
        - transportation
        - activities

    This calculation is deterministic and does not require
    another LLM call.
    """

    if not isinstance(travel_info, dict):
        raise ValueError(
            "travel_info must be a JSON object."
        )

    if budget <= 0:
        raise ValueError(
            "Budget must be greater than zero."
        )

    # --------------------------------------------------------
    # Existing real/search-derived costs
    # --------------------------------------------------------

    flight_cost = extract_flight_cost(
        travel_info
    )

    hotel_cost = extract_hotel_cost(
        travel_info
    )

    currency = extract_currency(
        travel_info
    )

    fixed_cost = (
        flight_cost +
        hotel_cost
    )

    # --------------------------------------------------------
    # Determine remaining budget
    # --------------------------------------------------------

    remaining_budget = budget - fixed_cost

    # --------------------------------------------------------
    # If flights + hotel already exceed the budget
    # --------------------------------------------------------

    if remaining_budget <= 0:

        total_estimated = fixed_cost

        return {
            "currency": currency,

            "budget": round_money(budget),

            "estimated_cost": round_money(
                total_estimated
            ),

            "remaining": round_money(
                budget - total_estimated
            ),

            "status": "over_budget",

            "breakdown": {
                "flights": round_money(
                    flight_cost
                ),
                "hotels": round_money(
                    hotel_cost
                ),
                "food": 0.0,
                "transportation": 0.0,
                "activities": 0.0,
            },

            "percentages": {
                "flights": round_money(
                    (flight_cost / budget) * 100
                ) if budget else 0.0,

                "hotels": round_money(
                    (hotel_cost / budget) * 100
                ) if budget else 0.0,

                "food": 0.0,
                "transportation": 0.0,
                "activities": 0.0,
            },

            "message": (
                "Your selected flight and hotel costs "
                "already use or exceed the available budget."
            ),
        }

    # --------------------------------------------------------
    # Remaining budget allocation
    # --------------------------------------------------------
    #
    # Food            → 45%
    # Transportation → 25%
    # Activities      → 30%
    #
    # These are planning estimates, not real bookings.
    # --------------------------------------------------------

    food_cost = remaining_budget * 0.45

    transportation_cost = (
        remaining_budget * 0.25
    )

    activities_cost = (
        remaining_budget * 0.30
    )

    total_estimated = (
        flight_cost
        + hotel_cost
        + food_cost
        + transportation_cost
        + activities_cost
    )

    remaining = budget - total_estimated

    # Correct tiny floating-point differences.
    if abs(remaining) < 0.01:
        remaining = 0.0

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if total_estimated <= budget:
        status = "within_budget"
    else:
        status = "over_budget"

    # --------------------------------------------------------
    # Percentages
    # --------------------------------------------------------

    percentages = {
        "flights": round_money(
            (flight_cost / budget) * 100
        ),

        "hotels": round_money(
            (hotel_cost / budget) * 100
        ),

        "food": round_money(
            (food_cost / budget) * 100
        ),

        "transportation": round_money(
            (transportation_cost / budget) * 100
        ),

        "activities": round_money(
            (activities_cost / budget) * 100
        ),
    }

    # --------------------------------------------------------
    # Final response
    # --------------------------------------------------------

    return {
        "currency": currency,

        "budget": round_money(
            budget
        ),

        "estimated_cost": round_money(
            total_estimated
        ),

        "remaining": round_money(
            remaining
        ),

        "status": status,

        "breakdown": {
            "flights": round_money(
                flight_cost
            ),

            "hotels": round_money(
                hotel_cost
            ),

            "food": round_money(
                food_cost
            ),

            "transportation": round_money(
                transportation_cost
            ),

            "activities": round_money(
                activities_cost
            ),
        },

        "percentages": percentages,

        "message": (
            "Budget calculated using the current flight "
            "and hotel estimates. Food, transportation, "
            "and activity amounts are planning estimates."
        ),
    }