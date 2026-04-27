from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        cleaned = value.strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), cleaned)


def _read_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _read_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw.strip())


class Settings(BaseModel):
    app_env: str = "local"
    backend_port: int = 8000
    review_provider: Literal["mock", "tencent_yuanqi", "tencent_yuanqi_sse", "tencent_yuanqi_async"] = "tencent_yuanqi_async"
    max_upload_size_mb: float = 3.5
    mock_fast_complete: bool = False

    storage_root: Path = Field(default_factory=lambda: ROOT_DIR / "storage")
    uploads_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "uploads")
    results_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "results")
    raw_results_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "raw_results")
    temp_dir: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "temp")
    task_db_path: Path = Field(default_factory=lambda: ROOT_DIR / "storage" / "tasks.sqlite3")
    mock_result_path: Path = Field(default_factory=lambda: ROOT_DIR / "examples" / "mock_result.json")
    public_file_base_url: str = "http://127.0.0.1:8000"
    use_fixed_test_file_url: bool = False
    fixed_test_file_url: str = ""

    yuanqi_api_url: str = "https://yuanqi.tencent.com/openapi/v1/agent/chat/completions"
    yuanqi_api_key: str = ""
    yuanqi_app_key: str = ""
    yuanqi_app_id: str = ""
    yuanqi_app_biz_id: str = ""
    yuanqi_stream_default: bool = False
    yuanqi_request_timeout_seconds: float = 1000
    yuanqi_variables_field_name: str = "custom_variables"
    yuanqi_bot_app_key: str = ""
    yuanqi_sse_api_url: str = "https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse"
    yuanqi_sse_workflow_status: str = "enable"
    yuanqi_sse_stream: str = "enable"
    yuanqi_sse_visitor_biz_id: str = "law_test_user"
    yuanqi_sse_contract_text_max_length: int = 3000
    yuanqi_sse_official_minimal_mode: bool = True

    yuanqi_async_endpoint: str = "https://lke.tencentcloudapi.com"
    yuanqi_async_service: str = "lke"
    yuanqi_async_version: str = "2023-11-30"
    yuanqi_async_region: str = "ap-guangzhou"
    yuanqi_async_run_env: int = 1
    yuanqi_async_include_workflow_graph: bool = True
    yuanqi_async_poll_node_details: bool = True
    yuanqi_default_visitor_biz_id: str = "law_self_user"
    yuanqi_tc_secret_id: str = ""
    yuanqi_tc_secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    _load_env_file(DEFAULT_ENV_PATH)
    backend_port = int(os.getenv("BACKEND_PORT", "8000"))
    fixed_test_file_url = os.getenv("FIXED_TEST_FILE_URL", "") or os.getenv("PUBLIC_FILE_URL_OVERRIDE", "")
    use_fixed_test_file_url = _read_bool("USE_FIXED_TEST_FILE_URL", bool(fixed_test_file_url))

    yuanqi_app_key = os.getenv("YUANQI_APP_KEY", "") or os.getenv("YUANQI_API_KEY", "")
    yuanqi_app_id = os.getenv("YUANQI_APP_ID", "") or os.getenv("YUANQI_APP_BIZ_ID", "")
    yuanqi_app_biz_id = os.getenv("YUANQI_APP_BIZ_ID", "") or yuanqi_app_id
    yuanqi_bot_app_key = os.getenv("YUANQI_BOT_APP_KEY", "")
    yuanqi_tc_secret_id = os.getenv("YUANQI_TC_SECRET_ID", "") or os.getenv("TC_SECRET_ID", "")
    yuanqi_tc_secret_key = os.getenv("YUANQI_TC_SECRET_KEY", "") or os.getenv("TC_SECRET_KEY", "")

    return Settings(
        app_env=os.getenv("APP_ENV", "local"),
        backend_port=backend_port,
        review_provider=os.getenv("REVIEW_PROVIDER", "tencent_yuanqi_async"),
        max_upload_size_mb=float(os.getenv("MAX_UPLOAD_SIZE_MB", "3.5")),
        mock_fast_complete=_read_bool("MOCK_FAST_COMPLETE", False),
        public_file_base_url=os.getenv("PUBLIC_FILE_BASE_URL", f"http://127.0.0.1:{backend_port}"),
        use_fixed_test_file_url=use_fixed_test_file_url,
        fixed_test_file_url=fixed_test_file_url,
        yuanqi_api_url=os.getenv(
            "YUANQI_API_URL",
            "https://yuanqi.tencent.com/openapi/v1/agent/chat/completions",
        ),
        yuanqi_api_key=os.getenv("YUANQI_API_KEY", ""),
        yuanqi_app_key=yuanqi_app_key,
        yuanqi_app_id=yuanqi_app_id,
        yuanqi_app_biz_id=yuanqi_app_biz_id,
        yuanqi_stream_default=_read_bool("YUANQI_STREAM_DEFAULT", False),
        yuanqi_request_timeout_seconds=_read_float("YUANQI_REQUEST_TIMEOUT_SECONDS", 1000.0),
        yuanqi_variables_field_name=os.getenv("YUANQI_VARIABLES_FIELD_NAME", "custom_variables"),
        yuanqi_bot_app_key=yuanqi_bot_app_key,
        yuanqi_sse_api_url=os.getenv("YUANQI_SSE_API_URL", "https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse"),
        yuanqi_sse_workflow_status=os.getenv("YUANQI_SSE_WORKFLOW_STATUS", "enable"),
        yuanqi_sse_stream=os.getenv("YUANQI_SSE_STREAM", "enable"),
        yuanqi_sse_visitor_biz_id=os.getenv("YUANQI_SSE_VISITOR_BIZ_ID", "law_test_user"),
        yuanqi_sse_contract_text_max_length=int(os.getenv("YUANQI_SSE_CONTRACT_TEXT_MAX_LENGTH", "3000")),
        yuanqi_sse_official_minimal_mode=_read_bool("YUANQI_SSE_OFFICIAL_MINIMAL_MODE", True),
        yuanqi_async_endpoint=os.getenv("YUANQI_ASYNC_ENDPOINT", "https://lke.tencentcloudapi.com"),
        yuanqi_async_service=os.getenv("YUANQI_ASYNC_SERVICE", "lke"),
        yuanqi_async_version=os.getenv("YUANQI_ASYNC_VERSION", "2023-11-30"),
        yuanqi_async_region=os.getenv("YUANQI_ASYNC_REGION", "ap-guangzhou"),
        yuanqi_async_run_env=int(os.getenv("YUANQI_ASYNC_RUN_ENV", "1")),
        yuanqi_async_include_workflow_graph=_read_bool("YUANQI_ASYNC_INCLUDE_WORKFLOW_GRAPH", True),
        yuanqi_async_poll_node_details=_read_bool("YUANQI_ASYNC_POLL_NODE_DETAILS", True),
        yuanqi_default_visitor_biz_id=os.getenv("YUANQI_DEFAULT_VISITOR_BIZ_ID", "law_self_user"),
        yuanqi_tc_secret_id=yuanqi_tc_secret_id,
        yuanqi_tc_secret_key=yuanqi_tc_secret_key,
    )

