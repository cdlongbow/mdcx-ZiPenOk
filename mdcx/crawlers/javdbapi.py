import hashlib
import html as html_utils
import re
import time
from typing import override
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict

from mdcx.config.enums import DownloadableFile
from mdcx.config.manager import manager
from mdcx.config.models import Website
from mdcx.models.types import CrawlerResult
from mdcx.signals import signal

from .base import CralwerException, CrawlerData
from .dmm_new import DMMContext, DmmCrawler


class JavdbApiMovie(BaseModel):
    model_config = ConfigDict(extra="ignore")

    universal_id: str | None = None
    title: str | None = None
    description: str | None = None
    fullcover_url: str | None = None
    frontcover_url: str | None = None
    sample_movie_url: str | None = None
    release_date: str | None = None
    duration: int | str | None = None
    source_url: str | None = None
    maker: str | None = None
    label: str | None = None
    series: str | None = None
    actresses: list[str | None] | None = None
    directors: list[str | None] | None = None
    genres: list[str | None] | None = None
    samples: list[str | None] | None = None


class JavdbAppActor(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    gender: int | None = None


class JavdbAppTag(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None


class JavdbAppPreviewImage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    large_url: str | None = None
    thumb_url: str | None = None


class JavdbAppMovie(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    type: int | None = None
    number: str | None = None
    title: str | None = None
    origin_title: str | None = None
    summary: str | None = None
    thumb_url: str | None = None
    cover_url: str | None = None
    preview_video_url: str | None = None
    release_date: str | None = None
    duration: int | str | None = None
    score: int | float | str | None = None
    maker_name: str | None = None
    publisher_name: str | None = None
    series_name: str | None = None
    director_name: str | None = None
    actors: list[JavdbAppActor | None] | None = None
    tags: list[JavdbAppTag | None] | None = None
    preview_images: list[JavdbAppPreviewImage | None] | None = None


class JavdbApiCrawler(DmmCrawler):
    APP_SIGNATURE_SALT = "71cf27bb3c0bcdf207b64abecddc970098c7421ee7203b9cdae54478478a199e7d5a6e1a57691123c1a931c057842fb73ba3b3c83bcd69c17ccf174081e3d8aa"

    @staticmethod
    def _log(message: str) -> None:
        signal.add_log(f"🎬 [JavdbApi] {message}")

    @classmethod
    @override
    def site(cls) -> Website:
        return Website.JAVDBAPI

    @classmethod
    @override
    def base_url_(cls) -> str:
        return "https://jdforrepam.com/api"

    @classmethod
    def legacy_base_url(cls) -> str:
        return "https://api.thejavdb.net/v1"

    @classmethod
    def app_headers(cls) -> dict[str, str]:
        timestamp = int(time.time())
        secret = hashlib.md5(f"{timestamp}{cls.APP_SIGNATURE_SALT}".encode()).hexdigest()
        return {
            "Accept": "application/json",
            "jdSignature": f"{timestamp}.lpw6vgqzsp.{secret}",
        }

    @staticmethod
    def _clean_text(value: object) -> str:
        text = html_utils.unescape(str(value or "").strip())
        if not text:
            return ""
        text = re.sub(r"(?i)<br\s*/?>", "\n", text)
        text = re.sub(r"(?i)</p\s*>", "\n", text)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @classmethod
    def _clean_list(cls, values: list[str | None] | None) -> list[str]:
        return list(dict.fromkeys(item for value in (values or []) if (item := cls._clean_text(value))))

    @staticmethod
    def _runtime(value: int | str | None) -> str:
        if value is None:
            return ""
        if isinstance(value, int):
            return str(value) if value > 0 else ""
        if matched := re.search(r"\d+", str(value)):
            return matched.group()
        return ""

    @classmethod
    def _number_key(cls, value: str) -> str:
        key = cls._clean_text(value).upper()
        key = re.sub(r"[\s_\-]+", "", key)
        return key.replace("FC2PPV", "FC2")

    @classmethod
    def _search_candidates(cls, number: str) -> list[str]:
        cleaned = cls._clean_text(number)
        candidates = [cleaned]
        key = cls._number_key(cleaned)
        if key.startswith("FC2"):
            digits = re.sub(r"\D", "", key[3:])
            if digits:
                candidates.extend([f"FC2-{digits}", digits])
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))

    def _search_url(self, number: str) -> str:
        return f"{self.base_url}/v2/search?{urlencode({'q': number, 'page': 1, 'type': 'movie', 'limit': 5, 'movie_type': 'all', 'from_recent': 'false', 'movie_filter_by': 'all', 'movie_sort_by': 'relevance'})}"

    def _detail_url(self, movie_id: str) -> str:
        return f"{self.base_url}/v4/movies/{movie_id}"

    def _legacy_api_url(self, number: str) -> str:
        return f"{self.legacy_base_url()}/movies?{urlencode({'q': number})}"

    @classmethod
    def _normalize_app_image_url(cls, url: str) -> str:
        normalized = cls._with_https(str(url or "").strip())
        if not normalized:
            return ""
        return re.sub(r"^https?://[^/]+/rhe951l4q(?=/)", "https://c0.jdbstatic.com", normalized)

    @classmethod
    def _select_search_movie(cls, response: object, *, number: str) -> dict | None:
        if not isinstance(response, dict) or response.get("success") != 1:
            return None
        data = response.get("data")
        movies = data.get("movies") if isinstance(data, dict) else None
        if not isinstance(movies, list):
            return None

        target_key = cls._number_key(number)
        for movie in movies:
            if isinstance(movie, dict) and cls._number_key(str(movie.get("number") or "")) == target_key:
                return movie
        return None

    async def _fetch_app_movie(self, ctx: DMMContext, number: str) -> tuple[JavdbAppMovie | None, list[str], str]:
        search_urls = []
        errors = []
        headers = self.app_headers()
        for candidate in self._search_candidates(number):
            search_url = self._search_url(candidate)
            search_urls.append(search_url)
            response, error = await self.async_client.get_json(search_url, headers=headers)
            if response is None:
                errors.append(f"{candidate}: {error}")
                continue

            search_movie = self._select_search_movie(response, number=number)
            if not search_movie:
                errors.append(f"{candidate}: 未匹配到番号")
                continue

            movie_id = self._clean_text(search_movie.get("id", ""))
            if not movie_id:
                errors.append(f"{candidate}: 搜索结果缺少 movie id")
                continue

            detail_url = self._detail_url(movie_id)
            ctx.debug_info.detail_urls = [detail_url]
            detail_response, detail_error = await self.async_client.get_json(detail_url, headers=headers)
            if detail_response is None:
                errors.append(f"{candidate}: 详情请求失败: {detail_error}")
                continue
            try:
                movie_data = detail_response["data"]["movie"]
                return JavdbAppMovie.model_validate(movie_data), search_urls, ""
            except Exception as e:
                ctx.debug(f"App API 详情解析失败: {e} {detail_response=}")
                errors.append(f"{candidate}: 详情解析失败")

        return None, search_urls, "; ".join(errors)

    @override
    async def _run(self, ctx: DMMContext) -> CrawlerResult:
        number = ctx.input.number.strip()
        if not number:
            raise CralwerException("番号为空")

        app_movie, search_urls, app_error = await self._fetch_app_movie(ctx, number)
        ctx.debug_info.search_urls = search_urls
        if app_movie is not None:
            data = self._to_crawler_data_from_app(app_movie, fallback_number=number)
        else:
            api_url = self._legacy_api_url(number)
            ctx.debug(f"App API 未命中，回退 Legacy API: {app_error}")
            ctx.debug(f"API URL: {api_url}")
            ctx.debug_info.search_urls = [*search_urls, api_url]

            response, error = await self.async_client.get_json(api_url, headers={"Accept": "application/json"})
            if response is None:
                raise CralwerException(f"API 请求失败: App API: {app_error}; Legacy API: {error}")

            try:
                movie = JavdbApiMovie.model_validate(response)
            except Exception as e:
                ctx.debug(f"API 响应解析失败: {e} {response=}")
                raise CralwerException("API 响应解析失败") from e

            data = self._to_crawler_data(movie, fallback_number=number)
        if not data.title and not data.thumb:
            ctx.debug(f"API 返回空内容: {app_movie=}")
            raise CralwerException("API 返回空内容")

        if data.external_id:
            ctx.debug_info.detail_urls = [str(data.external_id)]

        data.source = self.site().value
        result = data.to_result()
        return await self.post_process(ctx, result)

    def _to_crawler_data_from_app(self, movie: JavdbAppMovie, *, fallback_number: str) -> CrawlerData:
        title = self._clean_text(movie.title)
        originaltitle = self._clean_text(movie.origin_title) or title
        outline = self._clean_text(movie.summary)
        number = self._clean_text(movie.number) or fallback_number
        cover_url = self._normalize_app_image_url(str(movie.cover_url or movie.thumb_url or ""))
        actor_names = [self._clean_text(actor.name) for actor in (movie.actors or []) if actor and actor.gender != 1]
        all_actor_names = [self._clean_text(actor.name) for actor in (movie.actors or []) if actor]
        preview_images = []
        for image in movie.preview_images or []:
            if image:
                url = self._normalize_app_image_url(str(image.large_url or image.thumb_url or ""))
                if url:
                    preview_images.append(url)

        return CrawlerData(
            title=title,
            originaltitle=originaltitle,
            outline=outline,
            originalplot=outline,
            number=number,
            thumb=cover_url,
            poster=cover_url,
            trailer=self._with_https(str(movie.preview_video_url or "").strip()),
            release=self._clean_text(movie.release_date),
            runtime=self._runtime(movie.duration),
            score=self._clean_text(movie.score),
            studio=self._clean_text(movie.maker_name),
            publisher=self._clean_text(movie.publisher_name),
            series=self._clean_text(movie.series_name),
            actors=self._clean_list(actor_names),
            all_actors=self._clean_list(all_actor_names),
            directors=self._clean_list([movie.director_name]),
            tags=self._clean_list([tag.name for tag in (movie.tags or []) if tag]),
            extrafanart=preview_images,
            external_id=f"https://javdb.com/v/{self._clean_text(movie.id)}" if movie.id else number,
            mosaic="无码" if self._number_key(number).startswith("FC2") else "有码",
        )

    def _to_crawler_data(self, movie: JavdbApiMovie, *, fallback_number: str) -> CrawlerData:
        title = self._clean_text(movie.title)
        outline = self._clean_text(movie.description)
        source_url = self._clean_text(movie.source_url)
        number = self._clean_text(movie.universal_id) or fallback_number
        thumb = self._with_https(str(movie.fullcover_url or "").strip())
        poster = self._with_https(str(movie.frontcover_url or "").strip())

        return CrawlerData(
            title=title,
            originaltitle=title,
            outline=outline,
            originalplot=outline,
            number=number,
            thumb=thumb,
            poster=poster,
            trailer=self._with_https(str(movie.sample_movie_url or "").strip()),
            release=self._clean_text(movie.release_date),
            runtime=self._runtime(movie.duration),
            studio=self._clean_text(movie.maker),
            publisher=self._clean_text(movie.label),
            series=self._clean_text(movie.series),
            actors=self._clean_list(movie.actresses),
            all_actors=self._clean_list(movie.actresses),
            directors=self._clean_list(movie.directors),
            tags=self._clean_list(movie.genres),
            extrafanart=[self._with_https(str(url or "").strip()) for url in (movie.samples or []) if url],
            external_id=source_url or number,
            mosaic="有码",
        )

    @override
    async def post_process(self, ctx: DMMContext, res: CrawlerResult) -> CrawlerResult:
        if res.trailer:
            res.trailer = self._pick_best_unvalidated_trailer("", [res.trailer])
        if not res.publisher:
            res.publisher = res.studio
        if res.extrafanart and DownloadableFile.EXTRAFANART not in manager.config.download_files:
            res.extrafanart = self._dedupe_urls(res.extrafanart)
        return await super().post_process(ctx, res)
