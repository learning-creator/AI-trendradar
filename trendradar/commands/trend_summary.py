# coding=utf-8
"""
Periodic trend summary command.

The command summarizes already-stored hotlist and RSS items. It does not fetch
article bodies and does not bypass publisher paywalls.
"""

from __future__ import annotations

import html
import json
import smtplib
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests


VALID_PERIODS = {"weekly", "monthly", "quarterly", "semiannual", "yearly"}


@dataclass
class SummaryItem:
    title: str
    source_id: str
    source_name: str
    item_type: str
    url: str = ""
    summary: str = ""
    first_date: str = ""
    last_date: str = ""
    count: int = 0
    best_rank: int = 9999
    days: set[str] = field(default_factory=set)

    def merge(self, other: "SummaryItem") -> None:
        self.count += other.count
        self.days.update(other.days)
        if other.best_rank and other.best_rank < self.best_rank:
            self.best_rank = other.best_rank
        if not self.url and other.url:
            self.url = other.url
        if not self.summary and other.summary:
            self.summary = other.summary
        if not self.first_date or other.first_date < self.first_date:
            self.first_date = other.first_date
        if not self.last_date or other.last_date > self.last_date:
            self.last_date = other.last_date


def _date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def calculate_previous_period(period: str, today: Optional[date] = None) -> Tuple[date, date]:
    if period not in VALID_PERIODS:
        raise ValueError(f"Unsupported trend summary period: {period}")

    today = today or date.today()

    if period == "weekly":
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)

    if period == "monthly":
        first_this_month = today.replace(day=1)
        end = first_this_month - timedelta(days=1)
        return end.replace(day=1), end

    if period == "quarterly":
        current_quarter = (today.month - 1) // 3
        first_this_quarter_month = current_quarter * 3 + 1
        first_this_quarter = today.replace(month=first_this_quarter_month, day=1)
        end = first_this_quarter - timedelta(days=1)
        start_month = ((end.month - 1) // 3) * 3 + 1
        return end.replace(month=start_month, day=1), end

    if period == "semiannual":
        first_this_half_month = 1 if today.month <= 6 else 7
        first_this_half = today.replace(month=first_this_half_month, day=1)
        end = first_this_half - timedelta(days=1)
        start_month = 1 if end.month <= 6 else 7
        return end.replace(month=start_month, day=1), end

    start = date(today.year - 1, 1, 1)
    end = date(today.year - 1, 12, 31)
    return start, end


def _period_label(period: str) -> str:
    return {
        "weekly": "Weekly",
        "monthly": "Monthly",
        "quarterly": "Quarterly",
        "semiannual": "Semiannual",
        "yearly": "Yearly",
    }[period]


def _item_key(item: SummaryItem) -> str:
    if item.url:
        return f"{item.item_type}:url:{item.url}"
    return f"{item.item_type}:title:{item.source_id}:{item.title}"


def _add_item(target: Dict[str, SummaryItem], item: SummaryItem) -> None:
    key = _item_key(item)
    if key in target:
        target[key].merge(item)
    else:
        target[key] = item


def collect_stored_items(
    storage_manager: Any,
    start: date,
    end: date,
    include_hotlist: bool = True,
    include_rss: bool = True,
) -> Tuple[List[SummaryItem], List[SummaryItem], List[str]]:
    hotlist: Dict[str, SummaryItem] = {}
    rss: Dict[str, SummaryItem] = {}
    loaded_dates: List[str] = []

    for day in _date_range(start, end):
        date_str = day.isoformat()
        day_loaded = False

        if include_hotlist:
            news_data = storage_manager.get_today_all_data(date_str)
            if news_data and news_data.items:
                day_loaded = True
                for source_id, items in news_data.items.items():
                    source_name = news_data.id_to_name.get(source_id, source_id)
                    for item in items:
                        count = int(getattr(item, "count", 1) or 1)
                        rank = int(getattr(item, "rank", 9999) or 9999)
                        _add_item(
                            hotlist,
                            SummaryItem(
                                title=item.title,
                                source_id=source_id,
                                source_name=source_name,
                                item_type="hotlist",
                                url=item.url or item.mobile_url or "",
                                first_date=date_str,
                                last_date=date_str,
                                count=count,
                                best_rank=rank,
                                days={date_str},
                            ),
                        )

        if include_rss:
            rss_data = storage_manager.get_rss_data(date_str)
            if rss_data and rss_data.items:
                day_loaded = True
                for feed_id, items in rss_data.items.items():
                    feed_name = rss_data.id_to_name.get(feed_id, feed_id)
                    for item in items:
                        _add_item(
                            rss,
                            SummaryItem(
                                title=item.title,
                                source_id=feed_id,
                                source_name=feed_name,
                                item_type="rss",
                                url=item.url or "",
                                summary=item.summary or "",
                                first_date=date_str,
                                last_date=date_str,
                                count=int(getattr(item, "count", 1) or 1),
                                days={date_str},
                            ),
                        )

        if day_loaded:
            loaded_dates.append(date_str)

    return _sort_items(hotlist.values()), _sort_items(rss.values()), loaded_dates


def _sort_items(items: Iterable[SummaryItem]) -> List[SummaryItem]:
    return sorted(
        items,
        key=lambda item: (-len(item.days), -item.count, item.best_rank, item.first_date, item.title),
    )


def _format_items(items: List[SummaryItem], max_items: int) -> str:
    lines = []
    for index, item in enumerate(items[:max_items], 1):
        parts = [
            f"{index}. [{item.source_name}] {item.title}",
            f"days={len(item.days)}",
            f"count={item.count}",
        ]
        if item.best_rank != 9999:
            parts.append(f"best_rank={item.best_rank}")
        if item.url:
            parts.append(f"url={item.url}")
        if item.summary:
            cleaned = " ".join(item.summary.split())
            if len(cleaned) > 240:
                cleaned = cleaned[:240] + "..."
            parts.append(f"summary={cleaned}")
        lines.append(" | ".join(parts))
    return "\n".join(lines) if lines else "No items."


def _load_prompt(config: Dict[str, Any]) -> str:
    prompt_file = config.get("TREND_SUMMARY", {}).get("PROMPT_FILE", "trend_summary_prompt.txt")
    prompt_path = Path("config") / prompt_file
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return (
        "You are a senior news analyst. Summarize the supplied stored news items "
        "into clear trends, evidence, risks, and watch items. Output in {language}."
    )


def build_prompt(
    config: Dict[str, Any],
    period: str,
    start: date,
    end: date,
    hotlist: List[SummaryItem],
    rss: List[SummaryItem],
    loaded_dates: List[str],
) -> str:
    summary_config = config.get("TREND_SUMMARY", {})
    max_items = int(summary_config.get("MAX_ITEMS", 300) or 300)
    hotlist_limit = max_items // 2 if hotlist and rss else max_items
    rss_limit = max_items - hotlist_limit if hotlist and rss else max_items

    template = _load_prompt(config)
    return (
        template.replace("{language}", summary_config.get("LANGUAGE", "Chinese"))
        .replace("{period}", _period_label(period))
        .replace("{start_date}", start.isoformat())
        .replace("{end_date}", end.isoformat())
        .replace("{loaded_date_count}", str(len(loaded_dates)))
        .replace("{hotlist_count}", str(len(hotlist)))
        .replace("{rss_count}", str(len(rss)))
        .replace("{hotlist_content}", _format_items(hotlist, hotlist_limit))
        .replace("{rss_content}", _format_items(rss, rss_limit))
    )


def generate_summary(config: Dict[str, Any], prompt: str) -> str:
    from trendradar.ai.client import AIClient

    client = AIClient(config.get("AI", {}))
    valid, error = client.validate_config()
    if not valid:
        raise RuntimeError(error)

    system_prompt = (
        "You write concise, source-grounded trend summaries from stored news metadata. "
        "Do not claim access to article full text unless it appears in the supplied data."
    )
    return client.chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    )


def _markdown_title(period: str, start: date, end: date) -> str:
    return f"TrendRadar {_period_label(period)} Trend Summary ({start.isoformat()} to {end.isoformat()})"


def save_summary_outputs(
    config: Dict[str, Any],
    period: str,
    start: date,
    end: date,
    content: str,
) -> Dict[str, str]:
    output_dir = Path(config.get("STORAGE", {}).get("LOCAL", {}).get("DATA_DIR", "output"))
    summary_dir = output_dir / "summaries" / period
    summary_dir.mkdir(parents=True, exist_ok=True)

    base_name = f"{start.isoformat()}_{end.isoformat()}"
    title = _markdown_title(period, start, end)
    paths: Dict[str, str] = {}
    summary_config = config.get("TREND_SUMMARY", {})

    if summary_config.get("SAVE_MARKDOWN", True):
        markdown_path = summary_dir / f"{base_name}.md"
        markdown_path.write_text(f"# {title}\n\n{content}\n", encoding="utf-8")
        paths["markdown"] = str(markdown_path)

    if summary_config.get("SAVE_HTML", True):
        html_path = summary_dir / f"{base_name}.html"
        html_path.write_text(
            "<!doctype html><html><head><meta charset=\"utf-8\">"
            f"<title>{html.escape(title)}</title>"
            "<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;"
            "max-width:900px;margin:32px auto;line-height:1.65;padding:0 20px;}"
            "pre{white-space:pre-wrap;font-family:inherit;}</style></head><body>"
            f"<h1>{html.escape(title)}</h1><pre>{html.escape(content)}</pre></body></html>",
            encoding="utf-8",
        )
        paths["html"] = str(html_path)

    return paths


def _post_json(url: str, payload: Dict[str, Any]) -> bool:
    try:
        response = requests.post(url, json=payload, timeout=30)
        return 200 <= response.status_code < 300
    except Exception as exc:
        print(f"[趋势总结] 推送失败: {exc}")
        return False


def push_summary(config: Dict[str, Any], title: str, content: str) -> Dict[str, bool]:
    from trendradar.core.config import limit_accounts, parse_multi_account_config

    if not config.get("TREND_SUMMARY", {}).get("PUSH", True):
        return {}
    if not config.get("ENABLE_NOTIFICATION", True):
        return {}

    results: Dict[str, bool] = {}
    max_accounts = config.get("MAX_ACCOUNTS_PER_CHANNEL", 3)
    clipped = content if len(content) <= 3500 else content[:3500] + "\n\n...(truncated)"

    for url in limit_accounts(parse_multi_account_config(config.get("FEISHU_WEBHOOK_URL", "")), max_accounts):
        payload = {"msg_type": "text", "content": {"text": f"{title}\n\n{clipped}"}}
        if "www.feishu.cn" not in url:
            payload = {
                "msg_type": "interactive",
                "card": {"schema": "2.0", "body": {"elements": [{"tag": "markdown", "content": f"**{title}**\n\n{clipped}"}]}},
            }
        results["feishu"] = _post_json(url, payload)

    for url in limit_accounts(parse_multi_account_config(config.get("DINGTALK_WEBHOOK_URL", "")), max_accounts):
        results["dingtalk"] = _post_json(
            url,
            {"msgtype": "markdown", "markdown": {"title": title, "text": f"## {title}\n\n{clipped}"}},
        )

    for url in limit_accounts(parse_multi_account_config(config.get("WEWORK_WEBHOOK_URL", "")), max_accounts):
        msg_type = config.get("WEWORK_MSG_TYPE", "markdown")
        payload = {"msgtype": msg_type, msg_type: {"content": f"{title}\n\n{clipped}"}}
        results["wework"] = _post_json(url, payload)

    bot_tokens = limit_accounts(parse_multi_account_config(config.get("TELEGRAM_BOT_TOKEN", "")), max_accounts)
    chat_ids = limit_accounts(parse_multi_account_config(config.get("TELEGRAM_CHAT_ID", "")), max_accounts)
    for token, chat_id in zip(bot_tokens, chat_ids):
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        results["telegram"] = _post_json(url, {"chat_id": chat_id, "text": f"{title}\n\n{clipped}"})

    ntfy_topics = limit_accounts(parse_multi_account_config(config.get("NTFY_TOPIC", "")), max_accounts)
    if config.get("NTFY_SERVER_URL") and ntfy_topics:
        for topic in ntfy_topics:
            url = f"{config['NTFY_SERVER_URL'].rstrip('/')}/{topic}"
            try:
                headers = {"Title": title}
                if config.get("NTFY_TOKEN"):
                    headers["Authorization"] = f"Bearer {config['NTFY_TOKEN']}"
                response = requests.post(url, data=clipped.encode("utf-8"), headers=headers, timeout=30)
                results["ntfy"] = 200 <= response.status_code < 300
            except Exception as exc:
                print(f"[趋势总结] ntfy 推送失败: {exc}")
                results["ntfy"] = False

    for url in limit_accounts(parse_multi_account_config(config.get("BARK_URL", "")), max_accounts):
        results["bark"] = _post_json(url, {"title": title, "body": clipped})

    for url in limit_accounts(parse_multi_account_config(config.get("SLACK_WEBHOOK_URL", "")), max_accounts):
        results["slack"] = _post_json(url, {"text": f"*{title}*\n\n{clipped}"})

    for url in limit_accounts(parse_multi_account_config(config.get("GENERIC_WEBHOOK_URL", "")), max_accounts):
        template = config.get("GENERIC_WEBHOOK_TEMPLATE", "")
        if template:
            payload = json.loads(template.replace("{title}", title).replace("{content}", clipped))
        else:
            payload = {"title": title, "content": clipped}
        results["generic_webhook"] = _post_json(url, payload)

    if config.get("EMAIL_FROM") and config.get("EMAIL_PASSWORD") and config.get("EMAIL_TO"):
        results["email"] = _send_email(config, title, content)

    return results


def _send_email(config: Dict[str, Any], title: str, content: str) -> bool:
    try:
        smtp_server = config.get("EMAIL_SMTP_SERVER")
        smtp_port = int(config.get("EMAIL_SMTP_PORT") or 587)
        if not smtp_server:
            domain = config["EMAIL_FROM"].split("@")[-1]
            smtp_server = f"smtp.{domain}"
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = title
        msg["From"] = config["EMAIL_FROM"]
        msg["To"] = config["EMAIL_TO"]
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(config["EMAIL_FROM"], config["EMAIL_PASSWORD"])
            server.sendmail(
                config["EMAIL_FROM"],
                [addr.strip() for addr in config["EMAIL_TO"].split(",") if addr.strip()],
                msg.as_string(),
            )
        return True
    except Exception as exc:
        print(f"[趋势总结] email 推送失败: {exc}")
        return False


def run_trend_summary(config: Dict[str, Any], period: str) -> bool:
    period = period.lower()
    if period not in VALID_PERIODS:
        raise ValueError(f"Unsupported trend summary period: {period}")

    summary_config = config.get("TREND_SUMMARY", {})
    if not summary_config.get("ENABLED", True):
        print("[趋势总结] trend_summary.enabled=false，跳过")
        return False

    period_key = period.upper()
    if not summary_config.get("PERIODS", {}).get(period_key, True):
        print(f"[趋势总结] {period} 未启用，跳过")
        return False

    from trendradar.context import AppContext

    ctx = AppContext(config)
    storage = ctx.get_storage_manager()

    start, end = calculate_previous_period(period, ctx.get_time().date())
    print(f"[趋势总结] 汇总范围: {start.isoformat()} -> {end.isoformat()}")

    hotlist, rss, loaded_dates = collect_stored_items(
        storage,
        start,
        end,
        include_hotlist=summary_config.get("INCLUDE_HOTLIST", True),
        include_rss=summary_config.get("INCLUDE_RSS", True),
    )

    if not hotlist and not rss:
        print("[趋势总结] 没有找到可用于总结的历史新闻，未调用 AI")
        ctx.cleanup()
        return False

    prompt = build_prompt(config, period, start, end, hotlist, rss, loaded_dates)
    content = generate_summary(config, prompt)
    paths = save_summary_outputs(config, period, start, end, content)
    title = _markdown_title(period, start, end)
    push_results = push_summary(config, title, content)

    print(f"[趋势总结] 热榜素材: {len(hotlist)}，RSS素材: {len(rss)}，覆盖日期: {len(loaded_dates)}")
    for kind, path in paths.items():
        print(f"[趋势总结] 已保存 {kind}: {path}")
    if push_results:
        print(f"[趋势总结] 推送结果: {push_results}")

    ctx.cleanup()
    return True
