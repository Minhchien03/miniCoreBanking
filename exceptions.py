from typing import Any, Dict, Optional

class BusinessException(Exception):
    """
    Custom exception for business logic errors.
    This allows for centralized exception handling in FastAPI.
    """
    def __init__(self, status_code: int, detail: str, headers: Optional[Dict[str, Any]] = None):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers

    def __repr__(self) -> str:
        return f"BusinessException(status_code={self.status_code}, detail='{self.detail}')"