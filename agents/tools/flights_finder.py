import os
from typing import Optional

import serpapi
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool


class FlightsInput(BaseModel):
    departure_airport: str = Field(
        description="Departure airport IATA code, for example MAA"
    )
    arrival_airport: str = Field(
        description="Arrival airport IATA code, for example DEL"
    )
    outbound_date: str = Field(
        description="Outbound date in YYYY-MM-DD format"
    )
    return_date: Optional[str] = Field(
        default=None,
        description="Return date in YYYY-MM-DD format for round trips"
    )
    adults: int = Field(
        default=1,
        description="Number of adults"
    )
    children: int = Field(
        default=0,
        description="Number of children"
    )
    infants_in_seat: int = Field(
        default=0,
        description="Number of infants in seats"
    )
    infants_on_lap: int = Field(
        default=0,
        description="Number of infants on lap"
    )


@tool(args_schema=FlightsInput)
def flights_finder(
    departure_airport: str,
    arrival_airport: str,
    outbound_date: str,
    return_date: Optional[str] = None,
    adults: int = 1,
    children: int = 0,
    infants_in_seat: int = 0,
    infants_on_lap: int = 0,
):
    """
    Search for available Google Flights using SerpAPI.

    Supports both one-way and round-trip searches.
    """

    params = {
        "api_key": os.environ.get("SERPAPI_API_KEY"),
        "engine": "google_flights",
        "hl": "en",
        "gl": "us",
        "departure_id": departure_airport,
        "arrival_id": arrival_airport,
        "outbound_date": outbound_date,
        "currency": "USD",
        "adults": adults,
        "children": children,
        "infants_in_seat": infants_in_seat,
        "infants_on_lap": infants_on_lap,
    }

    # Add return-trip information when a return date is provided.
    if return_date:
        params["return_date"] = return_date
        params["type"] = "1"

    try:
        search = serpapi.search(params)

        data = search.data

        best_flights = data.get("best_flights", [])
        other_flights = data.get("other_flights", [])

        results = best_flights + other_flights

        # Remove duplicate flight results.
        unique = []
        seen = set()

        for flight in results:
            key = str(flight)

            if key not in seen:
                seen.add(key)
                unique.append(flight)

        print(
            f"Flights → best: {len(best_flights)}, "
            f"other: {len(other_flights)}, "
            f"unique: {len(unique)}"
        )

        return unique[:3]

    except Exception as e:
        print(f"Flight search error: {e}")

        return {
            "error": str(e)
        }