from nagatha_assistant.core.plugin import Plugin
import os
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

class WeatherPlugin(Plugin):  # Subclassing the Plugin base class
    '''
    A plugin to fetch weather data from OpenWeatherMap API.
    '''

    name = 'weather'
    version = '0.1.0'

    def __init__(self):
        logger.info('Initializing WeatherPlugin...')
        # Load API key from environment
        self.api_key = os.environ.get('OPENWEATHERMAP_API_KEY')
        if not self.api_key:
            logger.error('Missing OPENWEATHERMAP_API_KEY')
            raise ValueError('Missing OPENWEATHERMAP_API_KEY')
        logger.info('API Key Loaded Successfully.')

    async def setup(self, config: dict) -> None:
        '''
        Perform initialization and configuration.
        '''
        return None

    async def teardown(self) -> None:
        '''
        Clean up resources on shutdown.
        '''
        return None

    def function_specs(self) -> list:
        '''
        Return function specifications used to expose plugin functionality.
        '''
        return [
            {
                'name': 'get_weather_data',
                'description': 'Fetch current weather data for given coordinates.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'lat': {'type': 'number'},
                        'lon': {'type': 'number'},
                        'exclude': {'type': 'array', 'items': {'type': 'string'}},
                        'units': {'type': 'string', 'default': 'metric'},
                        'lang': {'type': 'string', 'default': 'en'}
                    },
                    'required': ['lat', 'lon']
                }
            },
            {
                'name': 'get_historical_weather',
                'description': 'Fetch historical weather data for given coordinates and timestamp.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'lat': {'type': 'number'},
                        'lon': {'type': 'number'},
                        'dt': {'type': 'integer'},
                        'units': {'type': 'string', 'default': 'metric'},
                        'lang': {'type': 'string', 'default': 'en'}
                    },
                    'required': ['lat', 'lon', 'dt']
                }
            },
            {
                'name': 'get_daily_summary',
                'description': 'Fetch daily weather summary for given coordinates and date.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'lat': {'type': 'number'},
                        'lon': {'type': 'number'},
                        'date': {'type': 'string', 'description': 'Date in YYYY-MM-DD format'},
                        'tz': {'type': ['string', 'null']},
                        'units': {'type': 'string', 'default': 'metric'},
                        'lang': {'type': 'string', 'default': 'en'}
                    },
                    'required': ['lat', 'lon', 'date']
                }
            },
            {
                'name': 'get_weather_overview',
                'description': 'Fetch weather overview for given coordinates and optional date.',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'lat': {'type': 'number'},
                        'lon': {'type': 'number'},
                        'date': {'type': ['string', 'null']},
                        'units': {'type': 'string', 'default': 'metric'}
                    },
                    'required': ['lat', 'lon']
                }
            }
        ]

    async def call(self, name: str, arguments: dict) -> str:
        '''
        Execute the function matching the specified name with given parameters.

        Args:
            name (str): The name of the function to call.
            arguments (dict): The arguments required by the function.

        Returns:
            str: Results of the called function in JSON format.
        '''
        logger.debug(f'Calling method: {name} with arguments: {arguments}')
        if name == 'get_weather_data':
            return self.get_weather_data(**arguments)
        elif name == 'get_historical_weather':
            return self.get_historical_weather(**arguments)
        elif name == 'get_daily_summary':
            return self.get_daily_summary(**arguments)
        elif name == 'get_weather_overview':
            return self.get_weather_overview(**arguments)
        else:
            logger.error(f'Unknown method requested: {name}')
            raise ValueError(f'Unknown method: {name}')

    # Exposed weather-fetching functions
    def get_weather_data(self, lat: float, lon: float, exclude: list[str] | None = None, units: str = "metric", lang: str = "en") -> dict:
        """
        Fetch weather data for given coordinates using OpenWeather One Call API.

        Args:
            lat (float): Latitude.
            lon (float): Longitude.
            exclude (list[str] | None): Parts to exclude from response.
            units (str): Units of measurement ('standard', 'metric', 'imperial').
            lang (str): Language code.

        Returns:
            dict: Parsed JSON response.

        Raises:
            ValueError: If exclude is not a list of strings.
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = "https://api.openweathermap.org/data/3.0/onecall"
        params: dict = {
            "lat": lat,
            "lon": lon,
            "units": units,
            "lang": lang,
            "appid": self.api_key,
        }
        if exclude is not None:
            if not isinstance(exclude, list) or not all(isinstance(item, str) for item in exclude):
                raise ValueError("exclude must be a list of strings")
            params["exclude"] = ",".join(exclude)

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_historical_weather(self, lat: float, lon: float, dt: int, units: str = "metric", lang: str = "en") -> dict:
        """
        Fetch historical weather data for given coordinates and timestamp.

        Args:
            lat (float): Latitude.
            lon (float): Longitude.
            dt (int): Unix timestamp (UTC).
            units (str): Units of measurement.
            lang (str): Language code.

        Returns:
            dict: Parsed JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = "https://api.openweathermap.org/data/3.0/onecall/timemachine"
        params = {
            "lat": lat,
            "lon": lon,
            "dt": dt,
            "units": units,
            "lang": lang,
            "appid": self.api_key,
        }
        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_daily_summary(self, lat: float, lon: float, date: str, tz: str | None = None, units: str = "metric", lang: str = "en") -> dict:
        """
        Fetch daily weather summary for given coordinates and date.

        Args:
            lat (float): Latitude.
            lon (float): Longitude.
            date (str): Date in YYYY-MM-DD format.
            tz (str | None): Timezone identifier.
            units (str): Units of measurement.
            lang (str): Language code.

        Returns:
            dict: Parsed JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = "https://api.openweathermap.org/data/3.0/onecall/day_summary"
        params = {
            "lat": lat,
            "lon": lon,
            "date": date,
            "units": units,
            "lang": lang,
            "appid": self.api_key,
        }
        if tz is not None:
            params["tz"] = tz

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()

    def get_weather_overview(self, lat: float, lon: float, date: str | None = None, units: str = "metric") -> dict:
        """
        Fetch weather overview for given coordinates and optional date.

        Args:
            lat (float): Latitude.
            lon (float): Longitude.
            date (str | None): Date in YYYY-MM-DD format.
            units (str): Units of measurement.

        Returns:
            dict: Parsed JSON response.

        Raises:
            requests.exceptions.HTTPError: If the HTTP request returned an unsuccessful status code.
        """
        url = "https://api.openweathermap.org/data/3.0/onecall/overview"
        params = {
            "lat": lat,
            "lon": lon,
            "units": units,
            "appid": self.api_key,
        }
        if date is not None:
            params["date"] = date

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        return response.json()

