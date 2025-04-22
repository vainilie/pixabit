# pixabit/api/client.py # Suggested file path

# SECTION: IMPORTS
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin  # Slightly more robust for joining URLs

# Use httpx for async HTTP requests
import httpx

# SECTION: CONSTANTS
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3"
# Habitica rate limit: 30 requests per minute
# Use slightly lower limit for safety margin
REQUESTS_PER_MINUTE_LIMIT: int = 29
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE_LIMIT
# Define client identifier
CLIENT_IDENTIFIER: str = (
    "pixabit-tui-v0.1.0"  # Consider updating version dynamically
)

# SECTION: TYPE ALIASES
# Type alias for the expected structure within the 'data' field of successful responses
HabiticaDataPayload = Union[Dict[str, Any], List[Dict[str, Any]]]
# Type alias for the *full* response payload which might be None or the data payload
HabiticaApiResponse = Optional[HabiticaDataPayload]

# SECTION: LOGGING SETUP
# Configure logger for this module
logger = logging.getLogger(__name__)
# Example basic config (application should configure root logger)
# logging.basicConfig(level="INFO", format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# SECTION: CUSTOM EXCEPTION


class HabiticaAPIError(Exception):
    """Custom exception for errors encountered during Habitica API interactions."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        response_data: Optional[Any] = None,
    ):
        """Initializes the API error.

        Args:
            message: The primary error message.
            status_code: The HTTP status code received, if applicable.
            error_type: The specific Habitica error type string (e.g., 'BadRequest'), if available.
            response_data: The raw response data associated with the error, if available.
        """
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self) -> str:
        """Provides a formatted string representation of the error."""
        details = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")
        if self.error_type:
            details.append(f"Type='{self.error_type}'")
        base_msg = super().__str__()
        details_str = f" ({', '.join(details)})" if details else ""
        return f"HabiticaAPIError: {base_msg}{details_str}"


# SECTION: API CLIENT CLASS


class HabiticaAPI:
    """An asynchronous client for interacting with the Habitica API v3.

    Handles authentication, rate limiting, request sending, basic response parsing,
    and error handling.
    """

    def __init__(
        self,
        user_id: str,
        api_token: str,
        base_url: str = DEFAULT_BASE_URL,
        client_id_suffix: str = "API_Client",  # Optional suffix for x-client header
    ):
        """Initializes the Habitica API client.

        Args:
            user_id: The user's Habitica User ID (UUID).
            api_token: The user's Habitica API Token (UUID).
            base_url: The base URL for the Habitica API (defaults to v3).
            client_id_suffix: A suffix to append to the client identifier header.

        Raises:
            ValueError: If user_id or api_token is missing or invalid.
        """
        if not user_id or not isinstance(user_id, str):
            raise ValueError(
                "Habitica User ID is required and must be a string."
            )
        if not api_token or not isinstance(api_token, str):
            raise ValueError(
                "Habitica API Token is required and must be a string."
            )

        self.user_id: str = user_id
        self.api_token: str = api_token
        # Ensure base_url ends with a slash for urljoin
        self.base_url: str = (
            base_url if base_url.endswith("/") else base_url + "/"
        )

        client_header = f"{CLIENT_IDENTIFIER}-{client_id_suffix}"
        self.headers: Dict[str, str] = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": client_header,
        }

        # Rate limiting state
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

        # HTTP Client - Instantiate once and reuse
        # Consider adding options for proxies, custom transports, etc. if needed
        self._client: httpx.AsyncClient = httpx.AsyncClient(
            headers=self.headers,
            timeout=120.0,  # Default timeout, adjust as needed
            base_url=self.base_url,  # Use base_url for the client
        )
        logger.info(
            f"HabiticaAPI client initialized for user {self.user_id[:8]}..."
        )  # Log partial ID

    async def close(self) -> None:
        """Closes the underlying HTTP client session. Should be called when done."""
        await self._client.aclose()
        logger.info("HabiticaAPI client closed.")

    async def _wait_for_rate_limit(self) -> None:
        """Pauses execution if the time since the last request is less than the minimum interval."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            logger.debug(f"Rate limit: waiting for {wait_time:.3f} seconds.")
            await asyncio.sleep(wait_time)
        self.last_request_time = (
            time.monotonic()
        )  # Update time *after* potential wait

    def _parse_response(self, response: httpx.Response) -> HabiticaApiResponse:
        """Parses the httpx response, handling Habitica's common structure and errors.

        Args:
            response: The httpx Response object.

        Returns:
            The parsed data payload (dict or list) or None.

        Raises:
            HabiticaAPIError: If the API returns an error (`success: false` or based on status).
            ValueError: If the response body is not valid JSON when expected.
        """
        # Check for successful status codes that might have no content
        if response.status_code == 204 or not response.content:
            logger.debug(
                f"Request successful with status {response.status_code}, no content."
            )
            return None

        # Attempt to parse JSON
        try:
            response_data = response.json()
        except json.JSONDecodeError as json_err:
            body_preview = response.text[:200].replace("\n", "\\n")
            msg = f"Could not decode JSON response (Status: {response.status_code}). Body: '{body_preview}'"
            logger.error(f"{msg} | Error: {json_err}")
            # Raise ValueError instead of HabiticaAPIError as it's a parsing issue, not an API logic error
            raise ValueError(msg) from json_err

        # Check Habitica's success envelope if present
        if isinstance(response_data, dict) and "success" in response_data:
            if response_data["success"]:
                # Return the content of the 'data' field if success is true
                data_payload = response_data.get("data")
                logger.debug(
                    f"API call successful, returning 'data' payload (type: {type(data_payload).__name__})."
                )
                return data_payload  # Can be dict, list, or potentially other types
            else:
                # Habitica indicated failure
                error_type = response_data.get("error", "UnknownHabiticaError")
                message = response_data.get(
                    "message", "No error message provided by API."
                )
                full_message = f"{error_type} - {message}"
                logger.warning(
                    f"API Error reported (success: false): {full_message}"
                )
                raise HabiticaAPIError(
                    full_message,
                    status_code=response.status_code,
                    error_type=error_type,
                    response_data=response_data,
                )
        # If no 'success' envelope, assume the whole response is the data (common for GET lists/objects)
        elif isinstance(response_data, (dict, list)):
            logger.debug(
                f"API call successful, returning full response body (type: {type(response_data).__name__})."
            )
            return response_data
        else:
            # Unexpected structure
            msg = f"Unexpected JSON structure received: {type(response_data).__name__}"
            logger.error(msg)
            raise ValueError(msg)  # Or potentially HabiticaAPIError

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponse:
        """Internal method to perform an asynchronous API request with rate limiting and error handling.

        Args:
            method: HTTP method (e.g., "GET", "POST").
            endpoint: API endpoint path (relative to base_url).
            **kwargs: Additional arguments passed to `httpx.AsyncClient.request`.

        Returns:
            Parsed data payload (dict or list) or None for success with no content.

        Raises:
            HabiticaAPIError: For API-specific errors or HTTP status errors.
            ValueError: For JSON decoding issues or unexpected response structures.
            httpx.TimeoutException: If the request times out.
            httpx.RequestError: For other network or request-related issues.
        """
        await self._wait_for_rate_limit()
        # Use client's base_url implicitly, just pass the relative endpoint
        relative_url = endpoint.lstrip("/")
        log_url = f"{self.base_url}{relative_url}"  # For logging only
        logger.debug(f"Making API request: {method} {log_url}")
        response: Optional[httpx.Response] = None
        try:
            response = await self._client.request(
                method, relative_url, **kwargs
            )
            response.raise_for_status()  # Raise exception for 4xx/5xx statuses
            # Parse successful response using helper
            return self._parse_response(response)

        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out for {method} {log_url}"
            logger.error(f"Timeout Error: {msg}", exc_info=True)
            raise HabiticaAPIError(msg, status_code=408) from timeout_err

        except httpx.HTTPStatusError as http_err:
            response = http_err.response
            status_code = response.status_code
            error_details = f"HTTP Error {status_code} for {method} {log_url}"
            try:
                # Try parsing error response using the standard parser logic
                self._parse_response(
                    response
                )  # This will raise HabiticaAPIError if parsing works
                # If _parse_response *doesn't* raise (e.g., non-standard error format), raise generic
                raise HabiticaAPIError(
                    f"HTTP Error {status_code}",
                    status_code=status_code,
                    response_data=response.text,
                )
            except (HabiticaAPIError, ValueError) as api_parse_err:
                # Catch errors raised by _parse_response (either Habitica format or JSON/Value error)
                logger.warning(
                    f"Request Failed: {error_details} | Parsed Error: {api_parse_err}"
                )
                if isinstance(api_parse_err, HabiticaAPIError):
                    # Re-raise specific HabiticaAPIError parsed from body
                    raise api_parse_err from http_err
                else:
                    # Raise a new HabiticaAPIError if parsing the error body failed
                    body_preview = response.text[:200].replace("\n", "\\n")
                    error_details += f" | Response Body: {body_preview}"
                    raise HabiticaAPIError(
                        f"HTTP Error {status_code} with unparseable body",
                        status_code=status_code,
                        response_data=response.text,  # Store raw text
                    ) from http_err
            except Exception as unexpected_err:
                # Catch unexpected errors during error handling
                logger.exception(
                    f"Unexpected error during HTTPStatusError handling for {method} {log_url}"
                )
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} (unexpected error during parsing)",
                    status_code=status_code,
                ) from unexpected_err

        except httpx.RequestError as req_err:
            # Network errors, DNS issues, etc.
            msg = f"Network/Request Error for {method} {log_url}"
            logger.error(f"Network Error: {msg}", exc_info=True)
            raise HabiticaAPIError(msg) from req_err
        except Exception as e:
            # Catch-all for truly unexpected issues
            logger.exception(
                f"Unexpected Error during API request {method} {log_url}",
                exc_info=True,
            )
            raise HabiticaAPIError(
                f"Unexpected error during {method} request: {e}"
            ) from e

    # --- Public API Methods ---

    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Performs a GET request to the specified endpoint.

        Args:
            endpoint: API endpoint path.
            params: Optional dictionary of query parameters.

        Returns:
            Parsed API response data or None.
        """
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponse:
        """Performs a POST request to the specified endpoint.

        Args:
            endpoint: API endpoint path.
            data: Optional dictionary payload to send as JSON body.
            params: Optional dictionary of query parameters.

        Returns:
            Parsed API response data or None.
        """
        return await self._request("POST", endpoint, json=data, params=params)

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponse:
        """Performs a PUT request to the specified endpoint.

        Args:
            endpoint: API endpoint path.
            data: Optional dictionary payload to send as JSON body.
            params: Optional dictionary of query parameters.

        Returns:
            Parsed API response data or None.
        """
        return await self._request("PUT", endpoint, json=data, params=params)

    async def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Performs a DELETE request to the specified endpoint.

        Args:
            endpoint: API endpoint path.
            params: Optional dictionary of query parameters.

        Returns:
            Parsed API response data or None.
        """
        # Note: Habitica DELETE often returns empty body on success (handled by _parse_response returning None)
        return await self._request("DELETE", endpoint, params=params)

    # --- Specific Endpoint Methods ---
    # These methods provide a higher-level interface to common API calls.
    # Consider adding Pydantic validation to the results here for more type safety.

    async def get_user_data(self) -> Optional[Dict[str, Any]]:
        """Fetches the user object (/user). Returns raw dictionary."""
        result = await self.get("user")  # Endpoint relative to base URL
        # Basic type check, consider Pydantic User.model_validate(result) here
        return result if isinstance(result, dict) else None

    async def update_user(
        self, update_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates the user object (/user). Returns raw response data dict."""
        result = await self.put("user", data=update_data)
        return result if isinstance(result, dict) else None

    async def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
        """Sets the user's Custom Day Start hour."""
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        # Note: API expects 'dayStart', Pydantic might use alias if modeling input
        result = await self.post(
            "user/custom-day-start", data={"dayStart": hour}
        )
        return result if isinstance(result, dict) else None

    async def toggle_user_sleep(self) -> HabiticaApiResponse:
        """Toggles the user's sleep status (/user/sleep)."""
        # Response varies: might be { "data": <bool> } or other structure
        return await self.post("user/sleep")

    async def run_cron(self) -> Optional[Dict[str, Any]]:
        """Manually triggers the user's cron process."""
        result = await self.post("cron")
        return result if isinstance(result, dict) else None

    async def get_tasks(
        self, task_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetches user tasks, optionally filtered by type. Returns raw list of task dicts."""
        params = {"type": task_type} if task_type else None
        result = await self.get("tasks/user", params=params)
        # Consider TaskList([Task.model_validate(t) for t in result]) here
        return result if isinstance(result, list) else []

    async def create_task(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Creates a new user task."""
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        # Consider validating 'data' against a Pydantic Task model before sending
        result = await self.post("tasks/user", data=data)
        return result if isinstance(result, dict) else None

    async def update_task(
        self, task_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Updates an existing task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        # Consider validating 'data' fields
        result = await self.put(f"tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    async def delete_task(self, task_id: str) -> bool:
        """Deletes a task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        # DELETE often returns 204 No Content on success -> _parse_response returns None
        result = await self.delete(f"tasks/{task_id}")
        return (
            result is None
        )  # True if successful (no data returned), False otherwise

    async def score_task(
        self, task_id: str, direction: str = "up"
    ) -> Optional[Dict[str, Any]]:
        """Scores a task up (+) or down (-)."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'.")
        result = await self.post(f"tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    async def add_checklist_item(
        self, task_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        """Adds a checklist item to a task."""
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(
            f"tasks/{task_id}/checklist", data={"text": text}
        )
        return result if isinstance(result, dict) else None

    async def score_checklist_item(
        self, task_id: str, item_id: str
    ) -> Optional[Dict[str, Any]]:
        """Scores (completes/uncompletes) a checklist item."""
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.post(f"tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    async def get_tags(self) -> List[Dict[str, Any]]:
        """Fetches all user tags. Returns raw list of tag dicts."""
        result = await self.get("tags")
        # Consider returning List[Tag] using Pydantic models
        return result if isinstance(result, list) else []

    async def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """Creates a new tag."""
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    # --- (Add other endpoint methods as needed, following the pattern) ---
    # Example: get_content
    async def get_content(self) -> Optional[Dict[str, Any]]:
        """Fetches the game content object."""
        # Content endpoint might not have the standard /api/v3 base, check docs
        # Assuming it uses the standard base for now
        result = await self.get("content")  # GET /content relative to base_url
        return result if isinstance(result, dict) else None

    # Add methods for party, challenges, user settings, etc.


# --- Example Usage (Illustrative) ---
async def main():
    # Assume USER_ID and API_TOKEN are loaded securely (e.g., env vars, config file)
    try:
        import os

        user_id = os.environ.get("HABITICA_USER_ID")
        api_token = os.environ.get("HABITICA_API_TOKEN")
        if not user_id or not api_token:
            raise ValueError(
                "Set HABITICA_USER_ID and HABITICA_API_TOKEN environment variables"
            )

        # --- Initialize Client ---
        api = HabiticaAPI(user_id=user_id, api_token=api_token)

        try:
            # --- Make API Calls ---
            print("Fetching user data...")
            user_data = await api.get_user_data()
            if user_data:
                print(
                    f"  Welcome, {user_data.get('profile', {}).get('name', 'User')}!"
                )
                print(
                    f"  Level: {user_data.get('stats', {}).get('lvl', 'N/A')}"
                )
            else:
                print("  Could not fetch user data.")

            print("\nFetching tasks...")
            tasks = await api.get_tasks()
            print(f"  Fetched {len(tasks)} tasks.")
            if tasks:
                print(f"  First task text: {tasks[0].get('text', 'N/A')}")

            # Example: Score a task (replace with a real task ID)
            # try:
            #     print("\nScoring task 'dummy-task-id' up...")
            #     score_result = await api.score_task("dummy-task-id", "up")
            #     print(f"  Score result: {score_result}")
            # except HabiticaAPIError as e:
            #     print(f"  Failed to score task: {e}")

        finally:
            # --- Close Client ---
            await api.close()

    except ValueError as e:
        print(f"Configuration Error: {e}")
    except HabiticaAPIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logger.exception("Unexpected error in main execution", exc_info=True)


if __name__ == "__main__":
    # Basic logging setup for the example
    logging.basicConfig(
        level="INFO", format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting Habitica API example...")
    asyncio.run(main())
