import os
from typing import Optional

import serpapi
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool


class HotelsInput(BaseModel):
    q: str = Field(
        description="City or destination where the hotel should be searched"
    )

    check_in_date: str = Field(
        description="Hotel check-in date in YYYY-MM-DD format"
    )

    check_out_date: str = Field(
        description="Hotel check-out date in YYYY-MM-DD format"
    )

    sort_by: int = Field(
        default=8,
        description="Hotel sorting option. 8 means highest rating."
    )

    adults: int = Field(
        default=1,
        description="Number of adults"
    )

    children: int = Field(
        default=0,
        description="Number of children"
    )

    rooms: int = Field(
        default=1,
        description="Number of rooms"
    )

    hotel_class: Optional[str] = Field(
        default=None,
        description="Optional hotel class such as 3,4,5"
    )


@tool(args_schema=HotelsInput)
def hotels_finder(
    q: str,
    check_in_date: str,
    check_out_date: str,
    sort_by: int = 8,
    adults: int = 1,
    children: int = 0,
    rooms: int = 1,
    hotel_class: Optional[str] = None,
):
    """
    Find hotel options using Google Hotels through SerpAPI.
    Returns up to 5 hotels.
    """

    params = {
        "api_key": os.environ.get("SERPAPI_API_KEY"),
        "engine": "google_hotels",
        "hl": "en",
        "gl": "us",
        "q": q,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "currency": "USD",
        "adults": adults,
        "children": children,
        "rooms": rooms,
        "sort_by": sort_by,
    }

    if hotel_class:
        params["hotel_class"] = hotel_class

    try:
        search = serpapi.search(params)

        data = search.data

        properties = data.get("properties", [])

        print(f"Hotels → found: {len(properties)}")

        return properties[:5]

    except Exception as e:
        print(f"Hotel search error: {e}")

        return {
            "error": str(e)
        }