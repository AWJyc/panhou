"""阿里云 DM 通过 SMTP 发邮件 —— 注册验证码 / 密码重置码。

只用 stdlib（smtplib + email），不引入额外依赖。
未配置 SMTP_HOST 时 send_email 会抛 RuntimeError；上层应在配置缺失时优雅降级。
"""

import logging
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr

from app.config import get_settings

log = logging.getLogger(__name__)


def _ensure_configured() -> None:
    settings = get_settings()
    missing = [
        k
        for k, v in (
            ("SMTP_HOST", settings.smtp_host),
            ("SMTP_USER", settings.smtp_user),
            ("SMTP_PASSWORD", settings.smtp_password),
        )
        if not v
    ]
    if missing:
        raise RuntimeError(f"SMTP 未配置: 缺 {', '.join(missing)}")


def send_email(to: str, subject: str, html: str, *, text: str | None = None, retries: int = 3) -> None:
    """向 to 发一封 multipart 邮件。失败重试 retries 次（含首次）。

    Raises:
        RuntimeError: SMTP 未配置 or 重试用尽
    """
    _ensure_configured()
    settings = get_settings()

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.smtp_from_name, settings.smtp_user))
    msg["To"] = to
    # 用户回邮件直接到运维个人邮箱
    msg["Reply-To"] = "jin156152251@gmail.com"

    plain = text or _strip_html(html)
    msg.set_content(plain)
    msg.add_alternative(html, subtype="html")

    last_err: Exception | None = None
    context = ssl.create_default_context()
    for attempt in range(retries):
        try:
            with smtplib.SMTP_SSL(
                settings.smtp_host, settings.smtp_port, context=context, timeout=10
            ) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
            log.info("email sent to=%s subject=%s", _mask_email(to), subject)
            return
        except Exception as e:
            last_err = e
            log.warning(
                "smtp 发送失败 attempt=%s/%s err=%s", attempt + 1, retries, e
            )
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
    raise RuntimeError(f"SMTP 发送失败（重试 {retries} 次）: {last_err}")


def _strip_html(html: str) -> str:
    import re

    text = re.sub(r"<[^>]+>", "", html)
    text = re.sub(r"\s+\n", "\n", text)
    return text.strip()


def _mask_email(addr: str) -> str:
    if "@" not in addr:
        return "***"
    local, domain = addr.split("@", 1)
    if len(local) <= 2:
        masked_local = local[0] + "*"
    else:
        masked_local = local[0] + "***" + local[-1]
    return f"{masked_local}@{domain}"


# ── 业务模板 ───────────────────────────────────────────────────────────────────


def send_verify_code(to: str, code: str, *, ttl_minutes: int = 15) -> None:
    """注册激活码邮件。"""
    subject = f"【panhou】你的注册验证码：{code}"
    html = _render_code_email(
        title="欢迎注册 panhou",
        intro="你正在注册 panhou 账户，验证码如下，请在 {ttl} 分钟内填写完成激活：".format(
            ttl=ttl_minutes
        ),
        code=code,
        footer="如果不是你本人操作，请忽略此邮件，账户不会被创建。",
    )
    send_email(to, subject, html)


def send_reset_code(to: str, code: str, *, ttl_minutes: int = 15) -> None:
    """密码重置码邮件。"""
    subject = f"【panhou】密码重置验证码：{code}"
    html = _render_code_email(
        title="重置 panhou 密码",
        intro="你刚刚申请重置 panhou 账户密码，验证码如下，请在 {ttl} 分钟内输入完成重置：".format(
            ttl=ttl_minutes
        ),
        code=code,
        footer="如果不是你本人操作，请忽略此邮件，你的密码不会被改动。建议同时检查邮箱是否被盗用。",
    )
    send_email(to, subject, html)


_EMAIL_CSS = """
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
color: #111;
"""


def _render_code_email(*, title: str, intro: str, code: str, footer: str) -> str:
    return f"""\
<!doctype html>
<html lang="zh">
<body style="margin:0;padding:24px;background:#f6f7f9;">
  <table cellpadding="0" cellspacing="0" border="0" align="center"
         style="max-width:520px;width:100%;background:#fff;border-radius:12px;
                box-shadow:0 1px 3px rgba(0,0,0,0.06);{_EMAIL_CSS}">
    <tr><td style="padding:32px 32px 16px 32px;">
      <div style="font-size:14px;color:#666;letter-spacing:1px;">PANHOU · 全球股市日报</div>
      <h2 style="margin:8px 0 16px 0;font-size:22px;">{title}</h2>
      <p style="line-height:1.7;color:#333;margin:0 0 24px 0;">{intro}</p>
      <div style="text-align:center;margin:24px 0;">
        <span style="display:inline-block;font-size:36px;letter-spacing:10px;
                     font-family:'SFMono-Regular', Consolas, Monaco, monospace;
                     color:#111;background:#f0f3f7;padding:14px 22px;border-radius:8px;
                     font-weight:600;">{code}</span>
      </div>
      <p style="color:#888;line-height:1.6;margin:24px 0 0 0;font-size:13px;">
        {footer}
      </p>
    </td></tr>
    <tr><td style="padding:0 32px 32px 32px;">
      <hr style="border:0;border-top:1px solid #eee;margin:0 0 16px 0;">
      <p style="color:#aaa;font-size:12px;margin:0;">
        本邮件由系统自动发送，请勿直接回复。<br>
        panhou.xyz — 每日盘后聚合 A 股 / 美股 / 日股 / 韩股
      </p>
    </td></tr>
  </table>
</body>
</html>"""
