import requests


class WeatherService:

    @staticmethod
    def get_weather(lat, lon):
        api_key = "YOUR_API_KEY"

        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?lat={lat}&lon={lon}&appid={api_key}&units=metric"
        )

        res = requests.get(url).json()

        return {
            "temp": res["main"]["temp"],
            "feels_like": res["main"]["feels_like"],
            "weather": res["weather"][0]["main"],
        }

    @staticmethod
    def get_weather_profile(weather):

        temp = weather["temp"]

        if temp >= 32:
            return {
                "preferred_weight": "light",
                "preferred_breathability": "high",
            }

        elif temp >= 22:
            return {
                "preferred_weight": "medium",
                "preferred_breathability": "medium",
            }

        return {
            "preferred_weight": "heavy",
            "preferred_breathability": "low",
        }