#!/usr/bin/env python3
import json
import re
from http.cookies import SimpleCookie
from typing import Any, override
from urllib.parse import urljoin

from lxml import html as lxml_html

from ..config.enums import FieldRule
from ..config.manager import manager
from ..config.models import Website
from .base import BaseCrawler, Context, CralwerException, CrawlerData

FC2CMADB_BASE_URL = "https://fc2cmadb.com"


def get_title(data):  # 获取标题
    return data.get("article", {}).get("title", "")


def get_cover(data):  # 获取封面URL
    image_url = data.get("article", {}).get("image_url", "")
    if image_url and "no-image" not in image_url:
        return image_url
    return ""


def get_release_date(data):  # 获取发行日期
    return data.get("article", {}).get("release_date", "")


def get_actors(data):  # 获取演员
    actresses = data.get("article", {}).get("actresses", [])
    return [actress.get("name", "") for actress in actresses if actress.get("name")] if actresses else []


def get_tags(data):  # 获取标签
    tags = data.get("article", {}).get("tags", [])
    return [tag.get("name", "") for tag in tags if tag.get("name")] if tags else []


def get_studio(data):  # 获取厂家
    writer = data.get("article", {}).get("writer", {})
    return writer.get("name", "")


def get_video_type(data):  # 获取视频类型
    censored = data.get("article", {}).get("censored")
    if censored == "無":
        return "無碼"
    elif censored == "有":
        return "有碼"
    else:
        return ""


def get_video_url(data):  # 获取视频URL
    # video_id = data.get("article", {}).get("video_id")
    # if video_id:
    #     return f"https://example.com/videos/{video_id}.mp4"
    return ""


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", value).replace("：", "").replace(":", "")


def clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def clean_title(value: str) -> str:
    return re.sub(r"\s*(?:コメント|评论|評論)\s*\(\d+\)\s*$", "", clean_text(value)).strip()


def absolute_url(base_url: str, value: str) -> str:
    value = clean_text(value)
    if not value or "no-image" in value:
        return ""
    return urljoin(base_url.rstrip("/") + "/", value)


def table_map_from_html(html_text: str) -> dict[str, str]:
    doc = lxml_html.fromstring(html_text)
    data: dict[str, str] = {}
    for row in doc.xpath("//tr"):
        cells = [clean_text(" ".join(cell.xpath(".//text()"))) for cell in row.xpath("./th|./td")]
        cells = [cell for cell in cells if cell]
        if len(cells) >= 2:
            data[normalize_label(cells[0])] = cells[1]
    return data


def title_from_html(doc) -> str:
    title = clean_title(" ".join(doc.xpath("//h1[1]//text()")))
    if title:
        return title

    page_title = clean_text(" ".join(doc.xpath("//title//text()")))
    title = re.sub(r"^\s*\d+\s*", "", page_title)
    return clean_title(re.sub(r"\s*作品\s*-\s*FC2CMADB\s*$", "", title))


def dict_name(value: Any) -> str:
    if isinstance(value, dict):
        return clean_text(value.get("name", ""))
    return ""


def list_names(values: Any) -> list[dict[str, str]]:
    if not isinstance(values, list):
        return []
    names = []
    for value in values:
        if name := dict_name(value):
            names.append({"name": name})
    return names


def extract_fc2cmadb_inertia_page(html_text: str) -> dict[str, Any] | None:
    doc = lxml_html.fromstring(html_text)
    for script_text in doc.xpath('//script[@data-page="app" and @type="application/json"]/text()'):
        try:
            page_data = json.loads(script_text)
        except (TypeError, json.JSONDecodeError):
            continue
        if isinstance(page_data, dict):
            return page_data
    return None


def parse_fc2cmadb_inertia_page(page_data: dict[str, Any], *, base_url: str) -> dict[str, Any] | None:
    props = page_data.get("props", {}) if isinstance(page_data, dict) else {}
    article = props.get("article", {}) if isinstance(props, dict) else {}
    if not isinstance(article, dict):
        return None

    title = clean_title(article.get("title", ""))
    if not title or title == "FC2CMADB":
        return None

    writer = article.get("writer", {})
    return {
        "article": {
            "title": title,
            "image_url": absolute_url(base_url, article.get("image_url", "")),
            "release_date": clean_text(article.get("release_date", "")),
            "actresses": list_names(article.get("actresses")),
            "tags": list_names(article.get("tags")),
            "writer": {"name": dict_name(writer)},
            "censored": clean_text(article.get("censored", "")),
            "duration": clean_text(article.get("duration", "")),
            "video_id": clean_text(article.get("video_id", "")),
        }
    }


def parse_fc2cmadb_inertia_html(html_text: str, *, base_url: str = FC2CMADB_BASE_URL) -> dict[str, Any] | None:
    page_data = extract_fc2cmadb_inertia_page(html_text)
    if page_data is None:
        return None
    return parse_fc2cmadb_inertia_page(page_data, base_url=base_url)


def parse_fc2cmadb_html(html_text: str, *, base_url: str, number: str) -> dict[str, Any] | None:
    if not html_text or "FC2CMADB" not in html_text:
        return None

    inertia_info = parse_fc2cmadb_inertia_html(html_text, base_url=base_url)
    if inertia_info is not None:
        return inertia_info

    doc = lxml_html.fromstring(html_text)
    table_data = table_map_from_html(html_text)
    title = title_from_html(doc)

    image_url = ""
    for src in doc.xpath("//img/@src"):
        src = absolute_url(base_url, src)
        if src and "/storage/images/actress/" not in src:
            image_url = src
            break

    actresses = [
        {"name": name.strip()} for name in re.split(r"[,、/，]\s*|\s+", table_data.get("女優", "")) if name.strip()
    ]
    tags = [{"name": tag} for tag in table_data.get("タグ", "").split() if tag]
    mosaic = table_data.get("モザイク", "")

    if not title or title == "FC2CMADB":
        return None

    return {
        "article": {
            "title": title,
            "image_url": image_url,
            "release_date": table_data.get("販売日", ""),
            "actresses": actresses,
            "tags": tags,
            "writer": {"name": table_data.get("販売者") or table_data.get("卖家") or table_data.get("販売者名") or ""},
            "censored": "無" if mosaic in {"無", "无码", "無碼"} else "有" if mosaic else "",
            "duration": table_data.get("収録時間", ""),
            "video_id": number,
        }
    }


def get_video_time(data):  # 获取视频时长
    duration = str(data.get("article", {}).get("duration", "")).strip()
    if not duration:
        return ""

    temp_list = duration.split(":")
    if len(temp_list) == 3:
        hours, minutes, seconds = temp_list
        try:
            total_minutes = int(hours) * 60 + int(minutes)
            if total_minutes == 0 and int(seconds) > 0:
                return "1"
            return str(total_minutes)
        except ValueError:
            return duration
    if len(temp_list) <= 2 and temp_list[0].isdigit():
        return str(int(temp_list[0]))
    return duration


def cookie_str_to_dict(cookie_str: str) -> dict:  # cookie 转为字典
    cookie = SimpleCookie()
    try:
        cookie.load(cookie_str)
    except Exception:
        return {}
    return {key: morsel.value for key, morsel in cookie.items()}


def normalize_fc2_number(number: str) -> str:
    return number.upper().replace("FC2PPV", "").replace("FC2-PPV-", "").replace("FC2-", "").replace("-", "").strip()


def get_xhr_headers(article_url: str) -> dict[str, str]:
    return {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Referer": article_url,
        "X-Requested-With": "XMLHttpRequest",
    }


def describe_xhr_json_error(response, error: Exception) -> str:
    content_type = str(response.headers.get("content-type", "")).strip() or "未知"
    text = str(getattr(response, "text", "") or "")
    text_preview = " ".join(text.strip().split())[:120]
    if not text.strip():
        reason = "接口返回空内容"
    elif "ログイン" in text or "login" in text.lower():
        reason = "接口返回登录页，fc2ppvdb Cookie 可能无效或已过期"
    elif "text/html" in content_type.lower() or text.lstrip().startswith("<!DOCTYPE html"):
        reason = "接口返回 HTML 页面而不是 JSON"
    else:
        reason = "接口返回内容不是有效 JSON"

    detail = f"{reason}，status={response.status_code}，content-type={content_type}"
    if text_preview:
        detail = f"{detail}，响应摘要={text_preview}"
    return f"{detail}；JSON解析失败: {error}"


def get_response_final_url(response) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get("x-mdcx-final-url") or getattr(response, "url", "") or "")


def response_text(response) -> str:
    return str(getattr(response, "text", "") or "")


def has_inertia_deferred_prop(page_data: dict[str, Any] | None, prop_name: str) -> bool:
    if not isinstance(page_data, dict):
        return False

    deferred_props = page_data.get("deferredProps")
    if not isinstance(deferred_props, dict):
        props = page_data.get("props", {})
        deferred_props = props.get("deferredProps") if isinstance(props, dict) else None
    if isinstance(deferred_props, dict):
        groups = deferred_props.values()
    elif isinstance(deferred_props, list):
        groups = deferred_props
    else:
        return False

    for group in groups:
        if isinstance(group, str) and group == prop_name:
            return True
        if isinstance(group, list) and prop_name in group:
            return True
    return False


def get_inertia_partial_headers(article_url: str, page_data: dict[str, Any], prop_name: str) -> dict[str, str]:
    headers = {
        "Accept": "text/html, application/xhtml+xml",
        "Referer": article_url,
        "X-Inertia": "true",
        "X-Inertia-Partial-Data": prop_name,
        "X-Requested-With": "XMLHttpRequest",
    }

    component = clean_text(page_data.get("component", ""))
    if component:
        headers["X-Inertia-Partial-Component"] = component
    version = clean_text(page_data.get("version", ""))
    if version:
        headers["X-Inertia-Version"] = version
    return headers


def merge_fc2cmadb_deferred_props(html_info: dict[str, Any], props: dict[str, Any]) -> None:
    article = html_info.get("article")
    if not isinstance(article, dict) or not isinstance(props, dict):
        return

    actresses = props.get("actresses")
    if not actresses and isinstance(props.get("article"), dict):
        actresses = props["article"].get("actresses")
    parsed_actresses = list_names(actresses)
    if parsed_actresses:
        article["actresses"] = parsed_actresses


async def fetch_fc2cmadb_deferred_props(
    async_client,
    *,
    article_url: str,
    page_data: dict[str, Any],
    prop_name: str,
    cookies: dict[str, str],
    use_proxy: bool,
) -> tuple[dict[str, Any], str]:
    response, error = await async_client.request(
        "GET",
        article_url,
        headers=get_inertia_partial_headers(article_url, page_data, prop_name),
        cookies=cookies,
        use_proxy=use_proxy,
    )
    if response is None:
        return {}, error
    if response.status_code != 200:
        return {}, f"deferred props 请求失败: HTTP {response.status_code}"
    try:
        data = response.json()
    except Exception as exc:
        return {}, describe_xhr_json_error(response, exc)
    if not isinstance(data, dict):
        return {}, f"deferred props 返回 JSON 结构异常: {type(data).__name__}"
    props = data.get("props", {})
    if not isinstance(props, dict):
        return {}, f"deferred props 返回 props 结构异常: {type(props).__name__}"
    return props, ""


async def fetch_article_info(
    async_client,
    *,
    base_url: str,
    number: str,
    cookies: dict[str, str],
    use_proxy: bool,
) -> tuple[dict[str, Any] | None, str]:
    article_url = f"{base_url}/articles/{number}"
    xhr_url = f"{base_url}/articles/article-info?videoid={number}"
    response, error = await async_client.request(
        "GET",
        xhr_url,
        headers=get_xhr_headers(article_url),
        cookies=cookies,
        use_proxy=use_proxy,
    )
    if response is None:
        return None, error
    try:
        data = response.json()
    except Exception as e:
        return None, describe_xhr_json_error(response, e)
    if not isinstance(data, dict):
        return None, f"接口返回 JSON 结构异常: {type(data).__name__}"
    return data, ""


async def fetch_article_info_with_warmup(
    async_client,
    *,
    base_url: str,
    number: str,
    cookies: dict[str, str],
    use_proxy: bool,
) -> tuple[dict[str, Any] | None, str]:
    article_url = f"{base_url}/articles/{number}"
    response_article, error = await async_client.request(
        "GET",
        article_url,
        cookies=cookies,
        use_proxy=use_proxy,
    )
    if response_article is None:
        return None, f"详情页请求失败: {error}"
    if response_article.status_code != 200:
        return None, f"详情页请求失败: HTTP {response_article.status_code}"
    final_url = get_response_final_url(response_article)
    if "/login" in final_url:
        return None, f"详情页跳转到登录页，fc2ppvdb Cookie 未生效: {final_url}"

    article_html = response_text(response_article)
    html_info = parse_fc2cmadb_html(article_html, base_url=base_url, number=number)
    if html_info is not None:
        page_data = extract_fc2cmadb_inertia_page(article_html)
        if not get_actors(html_info) and has_inertia_deferred_prop(page_data, "actresses"):
            deferred_props, _ = await fetch_fc2cmadb_deferred_props(
                async_client,
                article_url=article_url,
                page_data=page_data or {},
                prop_name="actresses",
                cookies=cookies,
                use_proxy=use_proxy,
            )
            merge_fc2cmadb_deferred_props(html_info, deferred_props)
        return html_info, ""

    return await fetch_article_info(
        async_client,
        base_url=base_url,
        number=number,
        cookies=cookies,
        use_proxy=use_proxy,
    )


class Fc2ppvdbCrawler(BaseCrawler):
    @classmethod
    @override
    def site(cls) -> Website:
        return Website.FC2PPVDB

    @classmethod
    @override
    def base_url_(cls) -> str:
        return FC2CMADB_BASE_URL

    @override
    async def _run(self, ctx: Context):
        number = normalize_fc2_number(ctx.input.number)
        article_url = f"{self.base_url}/articles/{number}"
        xhr_url = f"{self.base_url}/articles/article-info?videoid={number}"
        ctx.debug(f"番号地址: {article_url}")
        ctx.debug_info.detail_urls = [article_url]

        cookies = cookie_str_to_dict(manager.config.fc2ppvdb)
        use_proxy = manager.config.use_proxy
        ctx.debug(f"XHR 地址: {xhr_url}")
        html_info, error = await fetch_article_info_with_warmup(
            self.async_client,
            base_url=self.base_url,
            number=number,
            cookies=cookies,
            use_proxy=use_proxy,
        )
        if html_info is None:
            raise CralwerException(f"XHR 请求失败: {error}")

        title = get_title(html_info)
        if not title:
            raise CralwerException("数据获取失败: 未获取到title！")
        cover_url = get_cover(html_info)
        if "http" not in cover_url:
            ctx.debug("数据获取失败: 未获取到cover！")
        release_date = get_release_date(html_info)
        site_actors = get_actors(html_info)
        actors = site_actors
        tags = [tag for tag in get_tags(html_info) if tag != "無修正"]
        studio = get_studio(html_info)  # 使用卖家作为厂商
        if FieldRule.FC2_SELLER in manager.config.fields_rule and not actors and studio:
            actors = [studio]
        video_type = get_video_type(html_info)

        data = CrawlerData(
            number="FC2-" + str(number),
            title=title,
            originaltitle=title,
            outline="",
            actors=actors,
            all_actors=site_actors or actors,
            originalplot="",
            tags=tags,
            release=release_date,
            year=release_date[:4] if release_date else "",
            runtime=get_video_time(html_info),
            score="",
            series="FC2系列",
            directors=[],
            studio=studio,
            publisher=studio,
            thumb=cover_url,
            poster=cover_url,
            extrafanart=[],
            trailer=get_video_url(html_info),
            image_download=False,
            mosaic="无码" if video_type == "無碼" else "有码",
            external_id=article_url,
            wanted="",
        )
        result = data.to_result()
        result.source = self.site().value
        ctx.debug("数据获取成功！")
        return result

    @override
    async def _generate_search_url(self, ctx: Context) -> list[str] | str | None:
        return None

    @override
    async def _parse_search_page(self, ctx: Context, html, search_url: str) -> list[str] | str | None:
        return None

    @override
    async def _parse_detail_page(self, ctx: Context, html, detail_url: str) -> CrawlerData | None:
        return None
