# pixabit/api.py

# MARK: - MODULE DOCSTRING
"""Provides HabiticaAPI client for interacting with the Habitica API v3.

Handles authentication, rate limiting, standard HTTP methods, and provides
convenience methods for common API endpoints (user, tasks, tags, challenges, etc.).
"""


# MARK: - IMPORTS
import time
from typing import Any, Dict, List, Optional, Union

import requests

# Keep requests import for exception types
from pixabit import config

# For credentials
from pixabit.utils.display import console

# MARK: - CONSTANTS
DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29
# Stay under 30/min limit
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
# ~2.07 seconds
HabiticaApiResponse = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]


# Type hint for common API response data structures

# Can be a dict (e.g., /user), a list of dicts (e.g., /tasks/user),

# or potentially None if the API returns no content (204) or on error.


# MARK: - HabiticaAPI Class
class HabiticaAPI:
    """Client class for Habitica API v3 interactions. Handles auth, rate limits, requests.

    Attributes:
        user_id (str): Habitica User ID.
        api_token (str): Habitica API Token.
        base_url (str): Base URL for the API.
        headers (Dict[str, str]): Standard request headers including auth.
        request_interval (float): Min seconds between requests for rate limiting.
        last_request_time (float): Timestamp of the last request (monotonic).
    """

    BASE_URL = DEFAULT_BASE_URL

    # & - def __init__(...)
    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """Initializes the HabiticaAPI client.

        Loads credentials from config if not provided. Sets up headers and rate limiting.

        Args:
            user_id: Habitica User ID. Defaults to config.HABITICA_USER_ID.
            api_token: Habitica API Token. Defaults to config.HABITICA_API_TOKEN.
            base_url: API base URL.

        Raises:
            ValueError: If User ID or API Token is missing after checking args/config.
        """
        # Use credentials from config (which should have validated them)
        self.user_id = user_id or config.HABITICA_USER_ID
        self.api_token = api_token or config.HABITICA_API_TOKEN
        self.base_url = base_url

        # This check might be redundant if config.py exits on missing creds, but good safety.
        if not self.user_id or not self.api_token:
            raise ValueError(
                "Habitica User ID and API Token are required. "
                "Check .env file or provide directly."
            )

        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-cli-your_identifier",
            # Optional: Identify your client
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

    # MARK: - Internal Methods

    # --------------------------------------------------------------------------

    # & - def _wait_for_rate_limit(self) -> None:
    def _wait_for_rate_limit(self) -> None:
        """Sleeps if necessary to comply with the rate limit based on monotonic time."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last

            # console.log(f"Rate limit: waiting {wait_time:.2f}s", style="subtle")
            # Optional debug
            time.sleep(wait_time)

        # Update time *after* potential sleep
        self.last_request_time = time.monotonic()

    # & - def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiResponse:
    def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiResponse:
        """Internal method for making API requests with rate limiting and error handling.

        Args:
            method: HTTP method ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            **kwargs: Additional arguments for `requests.request` (e.g., json, params).

        Returns:
            The JSON response data (dict or list) from the API's 'data' field if present
            and successful, the raw JSON if no standard wrapper is used but successful,
            or None for 204 No Content or errors.

        Raises:
            requests.exceptions.RequestException: For network or API errors after logging.
        """
        self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[requests.Response] = None

        # console.log(f"Request: {method} {url} | Kwargs: {kwargs}", style="subtle")
        # Debug

        try:
            kwargs.setdefault("timeout", 120)
            # Generous timeout
            response = requests.request(method, url, headers=self.headers, **kwargs)

            # console.log(f"Response Status: {response.status_code}", style="subtle")
            # Debug

            response.raise_for_status()
            # Raise HTTPError for 4xx/5xx

            # Handle successful 204 No Content
            if response.status_code == 204 or not response.content:

                # console.log(f"Response: No content (Status {response.status_code})", style="subtle")
                # Debug
                return None
            # Explicitly return None for No Content

            # Attempt to parse JSON for other 2xx responses
            response_data = response.json()

            # --- Handle Habitica's standard wrapper ---
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:

                    # Return the 'data' payload if success is true

                    # Use .get to handle cases where 'data' might be missing even on success
                    return response_data.get("data")
                else:

                    # API reported failure
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    err_msg = (
                        f"Habitica API Error ({response.status_code}): {error_type} - {message}"
                    )
                    console.print(err_msg, style="error")

                    # Raise a general RequestException after logging
                    raise requests.exceptions.RequestException(err_msg)
            else:

                # --- Handle successful responses WITHOUT the standard wrapper ---

                # E.g., /content endpoint or potentially others

                # console.log(f"Response for {method} {endpoint} OK, but no standard wrapper. Returning raw JSON.", style="info")

                # Basic validation: ensure it's a dict or list as expected from most endpoints
                if isinstance(response_data, (dict, list)):
                    return response_data
                else:

                    # This case is unlikely for a successful JSON response but possible
                    console.print(
                        f"Warning: Unexpected non-dict/list JSON from {method} {endpoint}: {type(response_data)}",
                        style="warning",
                    )

                    # Decide how to handle: return the data anyway, or raise an error?

                    # Raising ValueError seems appropriate as it violates expected structure.
                    raise ValueError("Unexpected JSON structure received from API.")

        # --- Exception Handling ---
        except requests.exceptions.HTTPError as http_err:

            # Log detailed HTTP error information
            error_details = f"HTTP Error: {http_err}"
            if http_err.response is not None:
                response = http_err.response
                # Use the response from the exception
                error_details += f" | Status Code: {response.status_code}"
                try:

                    # Try to get more specific error details from Habitica's JSON response body
                    err_data = response.json()
                    error_type = err_data.get("error", "N/A")
                    message = err_data.get("message", "N/A")
                    error_details += f" | API Error: '{error_type}' | Message: '{message}'"
                except requests.exceptions.JSONDecodeError:

                    # If response body is not JSON
                    error_details += (
                        f" | Response Body (non-JSON): {response.text[:200]}"
                        # Limit length
                    )
            console.print(f"Request Failed: {error_details}", style="error")

            # Re-raise as a RequestException for consistent handling upstream
            raise requests.exceptions.RequestException(error_details) from http_err

        except requests.exceptions.Timeout as timeout_err:
            msg = f"Request timed out ({kwargs.get('timeout')}s) for {method} {endpoint}"
            console.print(f"{msg}: {timeout_err}", style="error")
            raise requests.exceptions.RequestException(msg) from timeout_err

        except requests.exceptions.JSONDecodeError as json_err:

            # Successful status code (2xx) but invalid JSON body
            msg = f"Could not decode JSON response from {method} {endpoint}"
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200] if response is not None else "N/A"
            console.print(f"{msg}", style="error")
            console.print(f"Response Status: {status}, Body starts with: {body}", style="subtle")

            # Raise ValueError as the JSON structure is invalid
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err

        except requests.exceptions.RequestException as req_err:

            # Catch other requests errors (connection, DNS, etc.)
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise
        # Re-raise the original exception

        except Exception as e:
            # Catch any other unexpected errors
            console.print(
                f"Unexpected error during API request: {type(e).__name__} - {e}", style="error"
            )
            console.print_exception(show_locals=False)
            # Show traceback for unexpected errors
            raise

    # Re-raise

    # MARK: - Core HTTP Request Methods

    # --------------------------------------------------------------------------

    # & - def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
        """Sends GET request. Returns JSON data or None."""
        return self._request("GET", endpoint, params=params)

    # & - def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
        """Sends POST request with JSON data. Returns JSON data or None."""
        return self._request("POST", endpoint, json=data)

    # & - def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
        """Sends PUT request with JSON data. Returns JSON data or None."""
        return self._request("PUT", endpoint, json=data)

    # & - def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> HabiticaApiResponse:
    def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Sends DELETE request. Returns JSON data (often empty dict) or None."""
        # DELETE requests might have query params sometimes (though less common)
        return self._request("DELETE", endpoint, params=params)

    # MARK: - Convenience Methods (User)

    # --------------------------------------------------------------------------

    # & - def get_user_data(self) -> Optional[Dict[str, Any]]:
    def get_user_data(self) -> Optional[Dict[str, Any]]:
        """GET /user - Retrieves the full user object."""
        result = self.get("/user")

        # Ensure the returned data (from 'data' field) is actually a dict
        return result if isinstance(result, dict) else None

    # & - def update_user(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def update_user(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """PUT /user - Updates general user settings."""
        result = self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # & - def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
    def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
        """Sets user's custom day start hour (0-23). Uses PUT /user."""
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return self.update_user({"preferences.dayStart": hour})

    # & - def toggle_user_sleep(self) -> Optional[Dict[str, Any]]:
    def toggle_user_sleep(self) -> Optional[Dict[str, Any]]:
        """POST /user/sleep - Toggles user's sleep status."""
        # API returns { "data": <boolean> } on V3, but let's handle dict return just in case
        result = self.post("/user/sleep")

        # The _request method extracts the 'data' field.

        # If 'data' is a boolean, wrap it for consistency, otherwise return dict if present.
        if isinstance(result, bool):
            return {"sleep": result}
        elif isinstance(result, dict):
            return result
        # Return dict if API returns more info
        return None

    # Return None on error or unexpected type

    # MARK: - Convenience Methods (Tasks)

    # --------------------------------------------------------------------------

    # & - def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
    def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """GET /tasks/user - Gets user tasks, optionally filtered by type."""
        params = {"type": task_type} if task_type else None
        result = self.get("/tasks/user", params=params)

        # Ensure the result is a list, return empty list otherwise
        return result if isinstance(result, list) else []

    # & - def create_task(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def create_task(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST /tasks/user - Creates a new task."""
        if "text" not in data or "type" not in data:
            raise ValueError("Task creation data must include 'text' and 'type'.")
        result = self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    # & - def update_task(self, task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def update_task(self, task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """PUT /tasks/{taskId} - Updates an existing task."""
        result = self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    # & - def delete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
    def delete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """DELETE /tasks/{taskId} - Deletes a specific task."""
        result = self.delete(f"/tasks/{task_id}")

        # API might return empty dict or None on success
        return result if isinstance(result, dict) else None

    # & - def score_task(self, task_id: str, direction: str = "up") -> Optional[Dict[str, Any]]:
    def score_task(self, task_id: str, direction: str = "up") -> Optional[Dict[str, Any]]:
        """POST /tasks/{taskId}/score/{direction} - Scores a task ('clicks' it)."""
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    # & - def set_attribute(self, task_id: str, attribute: str) -> Optional[Dict[str, Any]]:
    def set_attribute(self, task_id: str, attribute: str) -> Optional[Dict[str, Any]]:
        """Sets the primary attribute for a task. Uses `update_task`."""
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Attribute must be one of 'str', 'int', 'con', 'per'")
        return self.update_task(task_id, {"attribute": attribute})

    # & - def move_task_to_position(self, task_id: str, position: int) -> Optional[List[Dict[str, Any]]]:
    def move_task_to_position(self, task_id: str, position: int) -> Optional[List[Dict[str, Any]]]:
        """Moves a task to a specific position (0=top, -1=bottom).
        POST /tasks/{taskId}/move/to/{position}
        """
        if position not in [0, -1]:

            # Corrected validation based on V3 API docs
            raise ValueError("Position must be 0 (to move to top) or -1 (to move to bottom).")

        # API returns the new sorted list of task IDs (not full task objects)
        result = self.post(f"/tasks/{task_id}/move/to/{position}")

        # The API response structure for move/to is often just the sorted list of IDs, not wrapped.
        return result if isinstance(result, list) else None

    # MARK: - Convenience Methods (Tags)

    # --------------------------------------------------------------------------

    # & - def get_tags(self) -> List[Dict[str, Any]]:
    def get_tags(self) -> List[Dict[str, Any]]:
        """GET /tags - Gets all user tags."""
        result = self.get("/tags")
        return result if isinstance(result, list) else []

    # & - def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
    def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """POST /tags - Creates a new tag."""
        result = self.post("/tags", data={"name": name})
        return result if isinstance(result, dict) else None

    # & - def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
    def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
        """PUT /tags/{tagId} - Updates an existing tag's name."""
        result = self.put(f"/tags/{tag_id}", data={"name": name})
        return result if isinstance(result, dict) else None

    # & - def delete_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
    def delete_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """DELETE /tags/{tagId} - Deletes an existing tag globally."""
        result = self.delete(f"/tags/{tag_id}")

        # Often returns None or empty dict on success
        return result if isinstance(result, dict) else None

    # & - def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
    def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """POST /tasks/{taskId}/tags/{tagId} - Associates a tag with a task."""
        # This endpoint might return the updated task or just success status
        result = self.post(f"/tasks/{task_id}/tags/{tag_id}")

        # V3 API likely just returns {success: true} without data, _request handles this.

        # If it returns the task, it would be a dict.
        return result if isinstance(result, dict) else None

    # Return dict if present, else None

    # & - def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
    def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """DELETE /tasks/{taskId}/tags/{tagId} - Removes tag association from task."""
        result = self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    # MARK: - Convenience Methods (Checklist)

    # --------------------------------------------------------------------------

    # & - def add_checklist_item(self, task_id: str, text: str) -> Optional[Dict[str, Any]]:
    def add_checklist_item(self, task_id: str, text: str) -> Optional[Dict[str, Any]]:
        """POST /tasks/{taskId}/checklist - Adds checklist item."""
        result = self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    # Returns updated task

    # & - def update_checklist_item(self, task_id: str, item_id: str, text: str) -> Optional[Dict[str, Any]]:
    def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        """PUT /tasks/{taskId}/checklist/{itemId} - Updates checklist item text."""
        result = self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    # Returns updated task

    # & - def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """DELETE /tasks/{taskId}/checklist/{itemId} - Deletes checklist item."""
        result = self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    # Returns updated task

    # & - def score_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
    def score_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """POST /tasks/{taskId}/checklist/{itemId}/score - Toggles checklist item completion."""
        result = self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    # Returns updated task

    # MARK: - Convenience Methods (Challenges)

    # --------------------------------------------------------------------------

    # & - def get_challenges(self, member_only: bool = True) -> List[Dict[str, Any]]:
    def get_challenges(self, member_only: bool = True) -> List[Dict[str, Any]]:
        """GET /challenges/user - Retrieves challenges (owned or joined), handles pagination."""
        all_challenges = []
        page = 0
        member_param = "true" if member_only else "false"
        console.log(
            f"Fetching challenges (member_only={member_only}, paginating)...", style="info"
        )
        while True:
            try:

                # Use params argument for GET request
                challenge_page_data = self.get(
                    "/challenges/user", params={"member": member_param, "page": page}
                )
                if isinstance(challenge_page_data, list):
                    if not challenge_page_data:
                        # Empty list means no more pages
                        break
                    all_challenges.extend(challenge_page_data)

                    # console.log(f"  Fetched page {page} ({len(challenge_page_data)} challenges)", style="subtle")
                    page += 1
                else:

                    # Should not happen with this endpoint if API is consistent
                    console.print(
                        f"Warning: Expected list from /challenges/user page {page}, got {type(challenge_page_data)}. Stopping pagination.",
                        style="warning",
                    )
                    break
            except (requests.exceptions.RequestException, ValueError) as e:
                console.print(
                    f"Error fetching challenges page {page}: {e}. Stopping pagination.",
                    style="error",
                )
                break
        # Stop pagination on error
        console.log(
            f"Finished fetching challenges. Total found: {len(all_challenges)}", style="info"
        )
        return all_challenges

    # & - def create_challenge(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    def create_challenge(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """POST /challenges - Creates a new challenge."""
        result = self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    # & - def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
    def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
        """GET /tasks/challenge/{challengeId} - Retrieves tasks for a challenge."""
        result = self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    # & - def unlink_task_from_challenge(self, task_id: str, keep: str = "keep") -> Optional[Dict[str, Any]]:
    def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[Dict[str, Any]]:
        """POST /tasks/{taskId}/unlink - Unlinks a single task from its challenge.
        Note: V3 API uses /tasks/{taskId}/unlink?keep={keep_option}
        """
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")

        # Endpoint path is just /unlink, keep option is a query parameter
        result = self.post(f"/tasks/unlink-one/{task_id}?keep={keep}")

        # API often returns None or {} on success for unlink actions
        return result if isinstance(result, dict) else None

    # & - def unlink_all_challenge_tasks(self, challenge_id: str, keep: str = "keep-all") -> Optional[Dict[str, Any]]:
    def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[Dict[str, Any]]:
        """POST /tasks/unlink-all/{challengeId} - Unlinks ALL tasks from a challenge.
        Note: V3 API uses /tasks/unlink-all/{challengeId}?keep={keep_option}
        """
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        # Pass 'keep' as a query parameter
        result = self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    # & - def leave_challenge(self, challenge_id: str, keep: str = "keep-all") -> Optional[Dict[str, Any]]:
    def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[Dict[str, Any]]:
        """POST /challenges/{challengeId}/leave - Leaves a challenge, handling tasks.
        Note: V3 API uses /challenges/{challengeId}/leave?keep={keep_option}
        """
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        # Pass 'keep' as a query parameter
        result = self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        return result if isinstance(result, dict) else None

    # MARK: - Convenience Methods (Group & Party)

    # --------------------------------------------------------------------------

    # & - def get_party_data(self) -> Optional[Dict[str, Any]]:
    def get_party_data(self) -> Optional[Dict[str, Any]]:
        """GET /groups/party - Gets data about the user's current party."""
        result = self.get("/groups/party")

        # API returns null or error if not in party, _request handles errors,

        # so None means not in party or actual error occurred.
        return result if isinstance(result, dict) else None

    # & - def get_quest_status(self) -> bool:
    def get_quest_status(self) -> bool:
        """Checks if the user's party is currently on an active quest."""
        try:
            party_data = self.get_party_data()

            # Safely access nested keys
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except requests.exceptions.RequestException as e:

            # Log error but return False, as quest status is unknown/unavailable
            console.print(f"Could not get party data for quest status: {e}", style="warning")
            return False
        except ValueError as e:
            # Catch potential errors from API response format
            console.print(f"Invalid data received for party data: {e}", style="warning")
            return False

    # MARK: - Convenience Methods (Inbox)

    # --------------------------------------------------------------------------

    # & - def get_inbox_messages(self, page: int = 0) -> List[Dict[str, Any]]:
    def get_inbox_messages(self, page: int = 0) -> List[Dict[str, Any]]:
        """GET /inbox/messages - Gets inbox messages (paginated)."""
        result = self.get("/inbox/messages", params={"page": page})

        # API returns list directly in 'data' field
        return result if isinstance(result, list) else []

    # MARK: - Convenience Methods (Content)

    # --------------------------------------------------------------------------

    # & - def get_content(self) -> Optional[Dict[str, Any]]:
    def get_content(self) -> Optional[Dict[str, Any]]:
        """GET /content - Retrieves the game content object."""
        # This endpoint does NOT use the standard {success, data} wrapper
        result = self._request("GET", "/content")
        # Use internal _request
        return result if isinstance(result, dict) else None
