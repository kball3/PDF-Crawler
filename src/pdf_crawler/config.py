from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class AuthField:
    selector: str
    value: str


@dataclass
class AuthConfig:
    login_url: str
    username: str
    password: str
    username_selector: str
    password_selector: str
    submit_selector: str
    extra_fields: List[AuthField] = field(default_factory=list)
    wait_for_selector: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AuthConfig":
        extra_fields = [AuthField(**field) for field in data.get("extra_fields", [])]
        return cls(
            login_url=data["login_url"],
            username=data["username"],
            password=data["password"],
            username_selector=data.get("username_selector", "input[name='username']"),
            password_selector=data.get("password_selector", "input[type='password']"),
            submit_selector=data.get("submit_selector", "button[type='submit']"),
            extra_fields=extra_fields,
            wait_for_selector=data.get("wait_for_selector"),
        )


@dataclass
class CrawlConfig:
    url: str
    output_dir: Path
    auth: Optional[AuthConfig] = None
    max_depth: int = 1
    concurrency: int = 3
    timeout: int = 30
    respect_robots_txt: bool = True
    retries: int = 2

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CrawlConfig":
        auth = data.get("auth")
        return cls(
            url=data["url"],
            output_dir=Path(data.get("output_dir", "downloads")),
            auth=AuthConfig.from_dict(auth) if auth else None,
            max_depth=data.get("max_depth", 1),
            concurrency=data.get("concurrency", 3),
            timeout=data.get("timeout", 30),
            respect_robots_txt=data.get("respect_robots_txt", True),
            retries=data.get("retries", 2),
        )

    @classmethod
    def load(cls, path: Path) -> "CrawlConfig":
        data = json.loads(path.read_text())
        return cls.from_dict(data)
