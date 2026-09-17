import os
import requests
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool


class WeatherInput(BaseModel):
    city: str = Field(
        description="Destination city, for example Delhi"
    )
    start_date: str = Field(
        description="Travel start date in YYYY-MM-DD format"
    )
    end_date: str = Field(
        description="Travel end date in YYYY-MM-DD format"
    )


@tool(args_schema=WeatherInput)
def weather_finder(
    city: str,
    start_date: str,
    end_date: str,
):
    """
    Get the weather forecast for the destination during the travel dates.
    """

    api_key = os.environ.get("WEATHER_API_KEY")

    if not api_key:
        return {
            "error": "WEATHER_API_KEY is missing from the environment."
        }

    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "q": city,
        "appid": api_key,
        "units": "metric",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()

        data = response.json()

        if "list" not in data:
            return {
                "error": "Weather forecast data was not returned."
            }

        forecasts = []

        for item in data["list"]:
            datetime_text = item["dt_txt"]
            date = datetime_text.split(" ")[0]

            if start_date <= date <= end_date:
                forecasts.append({
                    "date": date,
                    "time": datetime_text.split(" ")[1],
                    "temperature": item["main"]["temp"],
                    "feels_like": item["main"]["feels_like"],
                    "humidity": item["main"]["humidity"],
                    "weather": item["weather"][0]["description"],
                    "rain_probability": round(
                        item.get("pop", 0) * 100
                    ),
                })

        if not forecasts:
            return {
                "error": (
                    "No weather forecast is available "
                    "for the requested travel dates."
                )
            }

        return {
            "city": city,
            "start_date": start_date,
            "end_date": end_date,
            "forecast": forecasts,
        }

    except Exception as e:
        print("Weather search error:", repr(e))

        return {
            "error": f"Weather search failed: {str(e)}"
        }