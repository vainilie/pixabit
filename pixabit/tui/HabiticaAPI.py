"""Habitica API client with async support and proper error handling."""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, TypeVar, Union, cast

import httpx
from pydantic import BaseModel, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Type aliases for better readability
HabiticaApiResponsePayload = Optional[
    Union[dict[str, Any], List[dict[str, Any]]]
]

# API rate limiting constants
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3/"
REQUESTS_PER_MINUTE: int = 29
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE


class HabiticaConfig(BaseSettings):
    """Pydantic settings model for Habitica API configuration."""

    habitica_user_id: str = Field(..., description="Habitica User ID")
    habitica_api_token: SecretStr = Field(..., description="Habitica API Token")
    habitica_base_url: str = Field(
        DEFAULT_BASE_URL, description="Habitica API Base URL"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


class HabiticaAPIError(Exception):
    """Custom exception for Habitica API errors with detailed information."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_type: str | None = None,
        response_data: Any | None = None,
    ):
        """Initialize the API error with detailed context."""
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self) -> str:
        """Format the error with all available details."""
        details = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")
        if self.error_type:
            details.append(f"Type='{self.error_type}'")

        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (
            f" ({', '.join(details)})" if details else ""
        )


class HabiticaAPI:
    """Asynchronous client for interacting with the Habitica API."""

    def __init__(
        self,
        config: HabiticaConfig | None = None,
        user_id: str | None = None,
        api_token: str | None = None,
        base_url: str | None = None,
        client_id: str = "habitica-python-client-v1.0.0",
    ):
        """Initialize the API client with authentication and configuration.

        Args:
            config: Pydantic config object (preferred way to configure)
            user_id: Override user ID from config
            api_token: Override API token from config
            base_url: Override base URL from config
            client_id: Client identifier for API requests
        """
        # Load config from .env if not provided
        if config is None:
            config = HabiticaConfig()

        # Set credentials with priority to explicit parameters
        self.user_id = user_id or config.habitica_user_id
        self.api_token = (
            api_token or config.habitica_api_token.get_secret_value()
        )
        self.base_url = base_url or config.habitica_base_url

        # Validate credentials
        if not self.user_id or not self.api_token:
            raise ValueError("Habitica User ID and API Token are required")

        # Set up request headers
        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": client_id,
        }

        # Rate limiting tracking
        self.last_request_time = 0.0
        self.request_interval = MIN_REQUEST_INTERVAL

    async def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting by waiting if necessary."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            await asyncio.sleep(wait_time)

        self.last_request_time = time.monotonic()

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponsePayload:
        """Make an API request with proper error handling and rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            **kwargs: Additional parameters for the request

        Returns:
            Parsed API response data

        Raises:
            HabiticaAPIError: For API-related errors
            ValueError: For data parsing issues
        """
        # Respect rate limits
        await self._wait_for_rate_limit()

        # Prepare request URL
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

        try:
            # Make the request
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.request(
                    method, url, headers=self.headers, **kwargs
                )

            # Check for HTTP errors
            response.raise_for_status()

            # Handle empty responses
            if response.status_code == 204 or not response.content:
                return None

            # Parse JSON response
            response_data = response.json()

            # Handle standard Habitica response format
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")
                else:
                    # API returned an error
                    error_type = response_data.get("error", "Unknown Error")
                    message = response_data.get(
                        "message", "No message provided"
                    )
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )

            # Handle non-standard but valid JSON responses
            elif isinstance(response_data, (dict, list)):
                return response_data

            # Handle unexpected response format
            else:
                raise ValueError(
                    f"Unexpected response structure: {type(response_data).__name__}"
                )

        except httpx.TimeoutException as err:
            raise HabiticaAPIError(
                f"Request timed out for {method} {endpoint}", status_code=408
            ) from err

        except httpx.HTTPStatusError as err:
            response = err.response
            status_code = response.status_code

            try:
                # Try to extract error details from JSON response
                err_data = response.json()
                error_type = err_data.get("error", f"HTTP{status_code}")
                message = err_data.get("message", f"HTTP {status_code} Error")

                raise HabiticaAPIError(
                    f"{error_type} - {message}",
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from err

            except json.JSONDecodeError:
                # Handle non-JSON error responses
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON response",
                    status_code=status_code,
                ) from err

        except httpx.RequestError as err:
            raise HabiticaAPIError(
                f"Network error for {method} {endpoint}"
            ) from err

        except json.JSONDecodeError as err:
            raise ValueError(
                f"Invalid JSON received from {method} {endpoint}"
            ) from err

        except Exception as err:
            raise HabiticaAPIError(f"Unexpected error: {err}") from err

    async def get(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiResponsePayload:
        """Make a GET request to the Habitica API.

        Args:
            endpoint: API endpoint path
            data: Optional JSON body data
            params: Optional query parameters

        Returns:
            API response payload
        """
        endpoint = endpoint.lstrip("/")
        return await self._request("GET", endpoint, json=data, params=params)

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiResponsePayload:
        """Make a POST request to the Habitica API.

        Args:
            endpoint: API endpoint path
            data: Optional JSON body data
            params: Optional query parameters

        Returns:
            API response payload
        """
        endpoint = endpoint.lstrip("/")
        return await self._request("POST", endpoint, json=data, params=params)

    async def put(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiResponsePayload:
        """Make a PUT request to the Habitica API.

        Args:
            endpoint: API endpoint path
            data: Optional JSON body data
            params: Optional query parameters

        Returns:
            API response payload
        """
        endpoint = endpoint.lstrip("/")
        return await self._request("PUT", endpoint, json=data, params=params)

    async def delete(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> HabiticaApiResponsePayload:
        """Make a DELETE request to the Habitica API.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            API response payload
        """
        endpoint = endpoint.lstrip("/")
        return await self._request("DELETE", endpoint, params=params)

    # Helper para conversión de tipos seguros

    def _ensure_type(self, value: Any, expected_type: type[T]) -> T | None:
        T = TypeVar("T")  # Tipo genérico para ayudar con las conversiones
        """Ensure the value is of the expected type or None."""
        return cast(T, value) if isinstance(value, expected_type) else None

    async def get_content(self) -> Optional[Dict[str, Any]]:
        result = await self._request("GET", "/content")
        return result if isinstance(result, dict) else None
