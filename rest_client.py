"""
REST Client Module

Provides a reusable HTTP client with connection pooling, retry logic,
and consistent response handling for API interactions.
"""

from typing import Dict, Any, Optional, Union
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RestClient:
    """
    HTTP client with connection pooling and automatic retries.

    Features:
        - Connection pooling for efficient reuse
        - Automatic retries with exponential backoff
        - Consistent response handling
        - Support for GET, POST, PUT, DELETE methods

    Attributes:
        base_url: Base URL for all requests
        headers: Default headers for all requests
        session: Requests session with pooling configured
    """

    # Class-level session pool for connection reuse
    _session_pool: Dict[str, requests.Session] = {}

    def __init__(self, base_url: str, headers: Optional[Dict[str, str]] = None):
        """
        Initialize RestClient.

        Args:
            base_url: Base URL for API requests
            headers: Optional default headers for all requests
        """
        self.base_url = base_url.rstrip("/")
        self.headers = headers or {}
        self.session = self._get_or_create_session(base_url)

    # =========================================================================
    # SESSION MANAGEMENT
    # =========================================================================

    @classmethod
    def _get_or_create_session(cls, base_url: str) -> requests.Session:
        """
        Get or create a pooled session for connection reuse.

        Args:
            base_url: Base URL to create session for

        Returns:
            Configured requests.Session instance
        """
        if base_url not in cls._session_pool:
            session = requests.Session()

            # Configure retry strategy
            retry_strategy = Retry(
                total=3,
                backoff_factor=0.5,
                status_forcelist=[429, 500, 502, 503, 504],
            )

            # Configure connection pooling
            adapter = HTTPAdapter(
                pool_connections=20,
                pool_maxsize=50,
                max_retries=retry_strategy
            )

            session.mount("http://", adapter)
            session.mount("https://", adapter)
            cls._session_pool[base_url] = session

        return cls._session_pool[base_url]

    # =========================================================================
    # HTTP METHODS
    # =========================================================================

    def get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Union[Dict, str]:
        """
        Send GET request.

        Args:
            endpoint: API endpoint path
            params: Optional query parameters

        Returns:
            Response data as dict or string
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(url, headers=self.headers, params=params)
        return self._handle_response(response)

    def post(
        self,
        endpoint: str,
        data: Optional[str] = None,
        json: Optional[Dict] = None
    ) -> Union[Dict, str]:
        """
        Send POST request.

        Args:
            endpoint: API endpoint path
            data: Optional request body as string
            json: Optional request body as dict (auto-serialized)

        Returns:
            Response data as dict or string
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, headers=self.headers, data=data, json=json)
        return self._handle_response(response)

    def put(
        self,
        endpoint: str,
        data: Optional[str] = None,
        json: Optional[Dict] = None
    ) -> Union[Dict, str]:
        """
        Send PUT request.

        Args:
            endpoint: API endpoint path
            data: Optional request body as string
            json: Optional request body as dict (auto-serialized)

        Returns:
            Response data as dict or string
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.put(url, headers=self.headers, data=data, json=json)
        return self._handle_response(response)

    def delete(self, endpoint: str) -> Union[Dict, str]:
        """
        Send DELETE request.

        Args:
            endpoint: API endpoint path

        Returns:
            Response data as dict or string
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.delete(url, headers=self.headers)
        return self._handle_response(response)

    # =========================================================================
    # RESPONSE HANDLING
    # =========================================================================

    @staticmethod
    def _handle_response(response: requests.Response) -> Union[Dict, str]:
        """
        Handle HTTP response with error checking.

        Args:
            response: requests.Response object

        Returns:
            Parsed JSON dict or raw text

        Raises:
            requests.HTTPError: If response indicates an error
        """
        try:
            response.raise_for_status()

            # Return JSON if possible, otherwise raw text
            content_type = response.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return response.json()
            return response.text

        except requests.HTTPError as e:
            print(f"HTTP error: {e}, Response: {response.text}")
            raise
        except ValueError:
            return response.text
