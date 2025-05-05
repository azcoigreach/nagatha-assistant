import os
import pytest
from unittest.mock import patch, MagicMock
from nagatha_assistant.plugins.weather_plugin import WeatherPlugin

def test_missing_api_key(monkeypatch):
    # Plugin initialization should fail without API key
    monkeypatch.delenv('OPENWEATHERMAP_API_KEY', raising=False)
    with pytest.raises(ValueError) as excinfo:
        WeatherPlugin()
    assert str(excinfo.value) == 'Missing OPENWEATHERMAP_API_KEY'

@pytest.fixture
def weather_plugin(monkeypatch):
    # Ensure API key is set for plugin instantiation
    monkeypatch.setenv('OPENWEATHERMAP_API_KEY', 'test_key')
    return WeatherPlugin()

@patch('requests.get')
def test_get_weather_data(mock_get, weather_plugin):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        'current': {
            'temp': 10,
            'weather': [{'description': 'clear sky'}]
        }
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    data = weather_plugin.get_weather_data(lat=51.5074, lon=-0.1278)
    assert data['current']['temp'] == 10
    assert data['current']['weather'][0]['description'] == 'clear sky'
    mock_get.assert_called_once()

@patch('requests.get')
def test_get_historical_weather(mock_get, weather_plugin):
    mock_response = MagicMock()
    mock_response.json.return_value = {'temp': 8, 'weather': [{'description': 'light rain'}]}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    data = weather_plugin.get_historical_weather(lat=51.5074, lon=-0.1278, dt=1234567890)
    assert data['temp'] == 8
    assert data['weather'][0]['description'] == 'light rain'
    mock_get.assert_called_once()

@patch('requests.get')
def test_get_daily_summary(mock_get, weather_plugin):
    mock_response = MagicMock()
    mock_response.json.return_value = {'summary': 'Sunny day', 'temp': {'day': 14}}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    data = weather_plugin.get_daily_summary(lat=51.5074, lon=-0.1278, date='2023-10-05')
    assert data['summary'] == 'Sunny day'
    assert data['temp']['day'] == 14
    mock_get.assert_called_once()

@patch('requests.get')
def test_get_weather_overview(mock_get, weather_plugin):
    mock_response = MagicMock()
    mock_response.json.return_value = {'overview': 'Clear skies', 'temp': {'current': 11}}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    data = weather_plugin.get_weather_overview(lat=51.5074, lon=-0.1278)
    assert data['overview'] == 'Clear skies'
    assert data['temp']['current'] == 11
    mock_get.assert_called_once()
 
@patch('requests.get')
def test_get_weather_data_http_error(mock_get, weather_plugin):
    # Simulate HTTP error from API
    from requests.exceptions import HTTPError
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = HTTPError('Bad request')
    mock_get.return_value = mock_response
    with pytest.raises(HTTPError):
        weather_plugin.get_weather_data(lat=0.0, lon=0.0)

def test_invalid_exclude_type(weather_plugin):
    # Exclude parameter must be a list of strings
    with pytest.raises(ValueError):
        weather_plugin.get_weather_data(lat=1.0, lon=2.0, exclude='notalist')

