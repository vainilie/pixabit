# pixabit/habitica/api.py

# SECTION: MODULE DOCSTRING
"""Habitica API client with async support and proper error handling."""

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Literal, TypeAlias, TypeVar, cast

import httpx
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from pixabit.api.exception import HabiticaAPIError

# Assuming logger helper is in helpers now
from pixabit.helpers._logger import log

# SECTION: TYPE ALIASES
HabiticaApiSuccessData: TypeAlias = dict[str, Any] | list[dict[str, Any]] | None
HabiticaApiResponsePayload: TypeAlias = dict[str, Any] | list[Any] | None

# SECTION: CONSTANTS
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3/"
REQUESTS_PER_MINUTE: int = 29  # Habitica rate limit (30/min, use 29 for safety)
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE

# SECTION: CONFIGURATION MODEL


# KLASS: HabiticaConfig
class HabiticaConfig(BaseSettings):
    """Pydantic settings model for Habitica API configuration."""

    habitica_user_id: str = Field(..., description="Habitica User ID")
    habitica_api_token: SecretStr = Field(..., description="Habitica API Token")
    habitica_base_url: str = Field(DEFAULT_BASE_URL, description="Habitica API Base URL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


# SECTION: API CLIENT CLASS


# KLASS: HabiticaAPI
class HabiticaAPI:
    """Asynchronous client for interacting with the Habitica API."""

    # FUNC: __init__
    def __init__(
        self,
        config: HabiticaConfig | None = None,
        user_id: str | None = None,
        api_token: str | None = None,
        base_url: str | None = None,
    ):
        """Initialize the API client with authentication and configuration.

        Args:
            config: Pydantic config object (preferred way to configure).
            user_id: Override user ID from config.
            api_token: Override API token from config.
            base_url: Override base URL from config.
        """
        log.debug("Initializing HabiticaAPI client...")
        # Load config from .env if not provided
        if config is None:
            try:
                config = HabiticaConfig()
                log.debug("Loaded HabiticaConfig from environment.")
            except Exception as e:
                log.error(f"Failed to load HabiticaConfig from environment: {e}")
                raise ValueError("Habitica configuration not provided and failed to load from .env") from e

        # Set credentials with priority to explicit parameters
        self.user_id = user_id or config.habitica_user_id
        self.api_token = api_token or config.habitica_api_token.get_secret_value()
        self.base_url = base_url or config.habitica_base_url

        # Validate credentials
        if not self.user_id or not self.api_token:
            log.error("Habitica User ID and API Token are required.")
            raise ValueError("Habitica User ID and API Token are required")

        # Set up request headers
        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
        }
        log.debug(f"API Headers set for user: {self.user_id[:6]}...")

        # Rate limiting tracking
        self._last_request_time: float = 0.0
        self._request_interval: float = MIN_REQUEST_INTERVAL
        self._async_client: httpx.AsyncClient | None = None
        log.info("HabiticaAPI client initialized successfully.")

    # FUNC: get_async_client (Lazy initialization of httpx client)
    def get_async_client(self) -> httpx.AsyncClient:
        """Returns the httpx.AsyncClient instance, creating it if necessary."""
        if self._async_client is None or self._async_client.is_closed:
            log.debug("Creating new httpx.AsyncClient instance.")
            self._async_client = httpx.AsyncClient(headers=self.headers, base_url=self.base_url, timeout=120.0)  # Set base_url and headers here
        return self._async_client

    # FUNC: close (To close the client when done)
    async def close(self) -> None:
        """Closes the underlying httpx client."""
        if self._async_client and not self._async_client.is_closed:
            log.debug("Closing httpx.AsyncClient.")
            await self._async_client.aclose()
            self._async_client = None

    # FUNC: _wait_for_rate_limit
    async def _wait_for_rate_limit(self) -> None:
        """Enforce rate limiting by waiting if necessary."""
        current_time = time.monotonic()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self._request_interval:
            wait_time = self._request_interval - time_since_last
            log.debug(f"Rate limit: waiting for {wait_time:.2f} seconds.")
            await asyncio.sleep(wait_time)

        self._last_request_time = time.monotonic()

    # FUNC: _request
    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiSuccessData:
        """Make an API request with proper error handling and rate limiting.

        Args:
            method: HTTP method (GET, POST, etc.).
            endpoint: API endpoint path (relative to base_url).
            **kwargs: Additional parameters for the httpx request (e.g., json, params).

        Returns:
            The 'data' part of a successful Habitica API response, or the full
            response body if the standard structure isn't found but the request
            was successful (status 2xx). Returns None for 204 No Content.

        Raises:
            HabiticaAPIError: For API-related errors (non-2xx status codes) or
                              Habitica explicit errors (success: false).
            ValueError: For data parsing issues (invalid JSON).
        """
        await self._wait_for_rate_limit()

        # Construct URL (httpx client handles base_url)
        relative_url = endpoint.lstrip("/")
        client = self.get_async_client()
        log.debug(f"Request: {method} {relative_url}, args: {kwargs}")

        try:
            response = await client.request(method, relative_url, **kwargs)
            log.debug(f"Response: {response.status_code} {response.reason_phrase}")
            # Check for HTTP errors first
            response.raise_for_status()

            # Handle empty responses (common for DELETE or success without data)
            if response.status_code == 204 or not response.content:
                log.debug("Received 204 No Content or empty body.")
                return None

            # Parse JSON response
            try:
                response_data = response.json()
            except json.JSONDecodeError as json_err:
                log.error(f"Invalid JSON received from {method} {relative_url}")
                raise ValueError(f"Invalid JSON received from {method} {relative_url}") from json_err

            # Handle standard Habitica V3 response format
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    # Return the 'data' field if present, otherwise the whole dict?
                    # Habitica usually has 'data', but let's be safe.
                    return cast(HabiticaApiSuccessData, response_data.get("data"))
                else:
                    # API returned success: false
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided")
                    log.warning(f"Habitica API Error: {error_type} - {message}")
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )
            # Handle non-standard but valid JSON responses (e.g., /content)
            elif isinstance(response_data, (dict, list)):
                log.debug("Received non-standard JSON response (dict or list).")
                return cast(HabiticaApiSuccessData, response_data)

            # Handle unexpected response format
            else:
                log.error(f"Unexpected JSON response structure: {type(response_data).__name__}")
                raise ValueError(f"Unexpected response structure: {type(response_data).__name__}")

        except httpx.TimeoutException as err:
            log.error(f"Request timed out for {method} {relative_url}")
            raise HabiticaAPIError(
                f"Request timed out for {method} {relative_url}",
                status_code=408,
            ) from err

        except httpx.HTTPStatusError as err:
            response = err.response
            status_code = response.status_code
            error_type = f"HTTP{status_code}"
            message = f"HTTP {status_code} Error for {method} {relative_url}"
            response_data = None
            try:
                # Try to extract error details from JSON response
                err_data = response.json()
                if isinstance(err_data, dict):
                    response_data = err_data
                    error_type = err_data.get("error", error_type)
                    message = err_data.get("message", message)
                    log.warning(f"HTTP Error {status_code} with JSON body: {error_type} - {message}")
                else:
                    log.warning(f"HTTP Error {status_code} with non-dict JSON body: {err_data}")

            except json.JSONDecodeError:
                # Handle non-JSON error responses
                log.warning(f"HTTP Error {status_code} with non-JSON response body: {response.text}")
                message = f"HTTP {status_code} Error (non-JSON response)"

            raise HabiticaAPIError(
                message,
                status_code=status_code,
                error_type=error_type,
                response_data=response_data,
            ) from err

        except httpx.RequestError as err:
            # Network-related errors
            log.error(f"Network error for {method} {relative_url}: {err}")
            raise HabiticaAPIError(f"Network error for {method} {relative_url}: {err}") from err

        except Exception as err:
            # Catch any other unexpected errors
            log.exception(f"Unexpected error during request {method} {relative_url}: {err}")
            raise HabiticaAPIError(f"Unexpected error: {err}") from err

    # --- HTTP Method Helpers ---

    # FUNC: get
    async def get(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiSuccessData:
        """Make a GET request to the Habitica API.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            API response payload or None.
        """
        return await self._request("GET", endpoint, params=params)

    # FUNC: post
    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiSuccessData:
        """Make a POST request to the Habitica API.

        Args:
            endpoint: API endpoint path.
            data: Optional JSON body data.
            params: Optional query parameters.

        Returns:
            API response payload or None.
        """
        return await self._request("POST", endpoint, json=data, params=params)

    # FUNC: put
    async def put(
        self,
        endpoint: str,
        data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HabiticaApiSuccessData:
        """Make a PUT request to the Habitica API.

        Args:
            endpoint: API endpoint path.
            data: Optional JSON body data.
            params: Optional query parameters.

        Returns:
            API response payload or None.
        """
        return await self._request("PUT", endpoint, json=data, params=params)

    # FUNC: delete
    async def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> HabiticaApiSuccessData:
        """Make a DELETE request to the Habitica API.

        Args:
            endpoint: API endpoint path.
            params: Optional query parameters.

        Returns:
            API response payload or None (often None for successful DELETE).
        """
        return await self._request("DELETE", endpoint, params=params)

    # --- Specific Endpoint Methods (Examples moved to Mixins/Client) ---
    # Example:
    # async def get_user_data(self) -> dict[str, Any] | None:
    #     """Get current user data."""
    #     result = await self.get("user")
    #     return cast(dict[str, Any], result) if isinstance(result, dict) else None

    async def get_content(self) -> dict[str, Any] | None:
        """Get the main game content object."""
        result = await self.get("/content")
        # Basic validation
        return cast(dict[str, Any], result) if isinstance(result, dict) else None
