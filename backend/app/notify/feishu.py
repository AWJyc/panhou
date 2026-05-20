"""飞书自定义机器人 webhook 推送。

只暴露 send_card(webhook_url, secret, title, content_lines, color)。
失败抛 RuntimeError，调用方决定是否吞掉。
"""

import base64
import hashlib
import hmac
import json
import logging
import time
import urllib.request
from typing import Literal

log = logging.getLogger(__name__)

Color = Literal["green", "red", "blue", "grey", "orange"]


def _sign(secret: str, timestamp: int) -> str:
    sign_str = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(sign_str, b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def send_card(
    webhook_url: str,
    title: str,
    content_lines: list[str],
    *,
    color: Color = "blue",
    secret: str | None = None,
    timeout: float = 5.0,
) -> None:
    body: dict = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": color,
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": "\n".join(content_lines),
                    },
                }
            ],
        },
    }
    if secret:
        ts = int(time.time())
        body["timestamp"] = str(ts)
        body["sign"] = _sign(secret, ts)

    data = json.dumps(body).encode("utf-8")
    last_err: Exception | None = None
    payload: dict = {}
    for attempt in range(3):
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8") or "{}")
                last_err = None
                break
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    if last_err is not None:
        raise RuntimeError(f"飞书 webhook 调用失败（重试 3 次）: {last_err}") from last_err

    code = payload.get("code") or payload.get("StatusCode")
    if code not in (0, None):
        raise RuntimeError(f"飞书 webhook 返回错误: {payload}")
