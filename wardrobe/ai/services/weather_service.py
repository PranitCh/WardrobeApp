import requests


class WeatherService:

    @staticmethod
    def get_weather(lat, lon):
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,apparent_temperature,weather_code"
        )

        res = requests.get(url, timeout=5)
        res.raise_for_status()
        data = res.json()["current"]

        return {
            "temp": data["temperature_2m"],
            "feels_like": data["apparent_temperature"],
            "weather": WeatherService.weather_label(
                data.get("weather_code")
            ),
        }

    @staticmethod
    def get_weather_profile(weather):

        temp = weather["temp"]
        condition = weather.get("weather", "")

        if temp >= 32:
            return {
                "preferred_weight": "light",
                "preferred_breathability": "high",
                "allow_heavy": False,
                "allow_light": True,
                "prefer_light_colors": True,
                "prefer_dark_colors": False,
                "rain_mode": condition == "Rain",
            }

        elif temp >= 22:
            return {
                "preferred_weight": "medium",
                "preferred_breathability": "medium",
                "allow_heavy": True,
                "allow_light": True,
                "prefer_light_colors": False,
                "prefer_dark_colors": False,
                "rain_mode": condition == "Rain",
            }

        return {
            "preferred_weight": "heavy",
            "preferred_breathability": "low",
            "allow_heavy": True,
            "allow_light": False,
            "prefer_light_colors": False,
            "prefer_dark_colors": True,
            "rain_mode": condition == "Rain",
        }

    @staticmethod
    def weather_label(code):
        if code in {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}:
            return "Rain"
        if code in {71, 73, 75, 77, 85, 86}:
            return "Snow"
        if code in {45, 48}:
            return "Fog"
        if code in {1, 2, 3}:
            return "Clouds"
        return "Clear"
