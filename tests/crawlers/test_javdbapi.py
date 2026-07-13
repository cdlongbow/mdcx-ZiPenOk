from urllib.parse import parse_qs, urlsplit

import pytest

import mdcx.crawlers.dmm_new as dmm_module
from mdcx.config.enums import DownloadableFile
from mdcx.config.manager import manager
from mdcx.config.models import Website
from mdcx.crawlers.javdbapi import JavdbApiCrawler, JavdbApiMovie, JavdbAppMovie
from mdcx.models.types import CrawlerInput


def test_to_crawler_data_maps_api_response():
    crawler = JavdbApiCrawler(client=None)
    data = crawler._to_crawler_data(
        JavdbApiMovie.model_validate(
            {
                "universal_id": "SSIS-001",
                "title": "Title",
                "description": "Line 1<br>Line 2",
                "fullcover_url": "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssis00001/ssis00001pl.jpg",
                "frontcover_url": "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssis00001/ssis00001ps.jpg",
                "sample_movie_url": "https://cc3001.dmm.co.jp/pv/TOKEN/ssis00001_mhb_w.mp4",
                "release_date": "2021-02-18",
                "duration": 147,
                "source_url": "https://video.dmm.co.jp/av/content/?id=ssis00001",
                "maker": "エスワン ナンバーワンスタイル",
                "label": "S1 NO.1 STYLE",
                "series": None,
                "actresses": ["葵つかさ", "葵つかさ", "乙白さやか"],
                "directors": ["苺原"],
                "genres": ["ドラマ", "ギリモザ"],
                "samples": ["https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssis00001/ssis00001jp-1.jpg"],
            }
        ),
        fallback_number="SSIS-001",
    )

    assert data.number == "SSIS-001"
    assert data.title == "Title"
    assert data.outline == "Line 1\nLine 2"
    assert data.runtime == "147"
    assert data.actors == ["葵つかさ", "乙白さやか"]
    assert data.all_actors == ["葵つかさ", "乙白さやか"]
    assert data.directors == ["苺原"]
    assert data.tags == ["ドラマ", "ギリモザ"]
    assert data.studio == "エスワン ナンバーワンスタイル"
    assert data.publisher == "S1 NO.1 STYLE"
    assert data.mosaic == "有码"
    assert data.external_id == "https://video.dmm.co.jp/av/content/?id=ssis00001"


def test_normalize_app_image_url_uses_javdb_static_host():
    assert (
        JavdbApiCrawler._normalize_app_image_url("https://tp.spfcas.com/rhe951l4q/covers/84/847XK.jpg")
        == "https://c0.jdbstatic.com/covers/84/847XK.jpg"
    )
    assert (
        JavdbApiCrawler._normalize_app_image_url("//tp.spfcas.com/rhe951l4q/samples/84/847XK_l_0.jpg")
        == "https://c0.jdbstatic.com/samples/84/847XK_l_0.jpg"
    )


def test_to_crawler_data_from_app_maps_detail_response():
    crawler = JavdbApiCrawler(client=None)
    data = crawler._to_crawler_data_from_app(
        JavdbAppMovie.model_validate(
            {
                "id": "vDgeeb",
                "type": 3,
                "number": "FC2-4159457",
                "title": "FC2 Title",
                "origin_title": "FC2 Original Title",
                "summary": "Summary",
                "cover_url": "https://tp.spfcas.com/rhe951l4q/covers/vd/vDgeeb.jpg",
                "preview_video_url": "https://example.test/preview.m3u8",
                "release_date": "2023-12-25",
                "duration": 73,
                "score": "4.46",
                "maker_name": "素人3Q",
                "actors": [
                    {"name": "石川祐奈", "gender": 0},
                    {"name": "男優", "gender": 1},
                ],
                "tags": [{"name": "FC2"}],
                "preview_images": [{"large_url": "https://tp.spfcas.com/rhe951l4q/samples/vd/vDgeeb_l_0.jpg"}],
            }
        ),
        fallback_number="FC2-PPV-4159457",
    )

    assert data.number == "FC2-4159457"
    assert data.title == "FC2 Title"
    assert data.originaltitle == "FC2 Original Title"
    assert data.actors == ["石川祐奈"]
    assert data.all_actors == ["石川祐奈", "男優"]
    assert data.studio == "素人3Q"
    assert data.tags == ["FC2"]
    assert data.thumb == "https://c0.jdbstatic.com/covers/vd/vDgeeb.jpg"
    assert data.poster == "https://c0.jdbstatic.com/covers/vd/vDgeeb.jpg"
    assert data.extrafanart == ["https://c0.jdbstatic.com/samples/vd/vDgeeb_l_0.jpg"]
    assert data.mosaic == "无码"
    assert data.external_id == "https://javdb.com/v/vDgeeb"


@pytest.mark.asyncio
async def test_run_calls_app_api_and_reuses_dmm_image_processing(monkeypatch: pytest.MonkeyPatch):
    class FakeClient:
        async def get_json(self, url: str, **kwargs):
            assert kwargs["headers"]["Accept"] == "application/json"
            assert "jdSignature" in kwargs["headers"]
            if url.startswith("https://jdforrepam.com/api/v2/search?"):
                q = parse_qs(urlsplit(url).query).get("q", [""])[0]
                if q == "FC2-PPV-4159457":
                    return {"success": 1, "data": {"movies": []}}, ""
                assert q == "FC2-4159457"
                return (
                    {
                        "success": 1,
                        "data": {
                            "movies": [
                                {
                                    "id": "vDgeeb",
                                    "number": "FC2-4159457",
                                    "title": "FC2 Search Title",
                                }
                            ]
                        },
                    },
                    "",
                )
            assert url == "https://jdforrepam.com/api/v4/movies/vDgeeb"
            return (
                {
                    "success": 1,
                    "data": {
                        "movie": {
                            "id": "vDgeeb",
                            "number": "FC2-4159457",
                            "title": "FC2 Title",
                            "origin_title": "FC2 Original Title",
                            "summary": "Outline",
                            "cover_url": "https://example.test/cover.jpg",
                            "release_date": "2023-12-25",
                            "duration": 73,
                            "maker_name": "Maker",
                            "actors": [{"name": "石川祐奈", "gender": 0}],
                            "preview_images": [{"large_url": "https://example.test/sample.jpg"}],
                        }
                    },
                },
                "",
            )

    async def fake_check_url(url: str, length: bool = False, real_url: bool = False):
        return url

    monkeypatch.setattr(dmm_module, "check_url", fake_check_url)
    monkeypatch.setattr(
        manager.config,
        "download_files",
        [DownloadableFile.POSTER, DownloadableFile.THUMB, DownloadableFile.EXTRAFANART],
    )

    crawler = JavdbApiCrawler(client=FakeClient())
    input_data = CrawlerInput.empty()
    input_data.number = "FC2-PPV-4159457"

    response = await crawler.run(input_data)

    assert response.data is not None
    assert response.data.source == Website.JAVDBAPI.value
    assert response.data.number == "FC2-4159457"
    assert response.data.title == "FC2 Title"
    assert response.data.actors == ["石川祐奈"]
    assert response.data.release == "2023-12-25"
    assert response.data.year == "2023"
    assert response.data.thumb == "https://example.test/cover.jpg"
    assert response.data.poster == "https://example.test/cover.jpg"
    assert response.data.extrafanart == ["https://example.test/sample.jpg"]


@pytest.mark.asyncio
async def test_run_falls_back_to_legacy_api(monkeypatch: pytest.MonkeyPatch):
    class FakeClient:
        async def get_json(self, url: str, **kwargs):
            if url.startswith("https://jdforrepam.com/api/v2/search?"):
                return {"success": 1, "data": {"movies": []}}, ""
            assert url == "https://api.thejavdb.net/v1/movies?q=SSIS-001"
            assert kwargs == {"headers": {"Accept": "application/json"}}
            return (
                {
                    "universal_id": "SSIS-001",
                    "title": "Title",
                    "description": "Outline",
                    "fullcover_url": "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssis00001/ssis00001pl.jpg",
                    "frontcover_url": "https://awsimgsrc.dmm.co.jp/pics_dig/digital/video/ssis00001/ssis00001ps.jpg",
                    "release_date": "2021-02-18",
                    "duration": 147,
                    "source_url": "https://video.dmm.co.jp/av/content/?id=ssis00001",
                    "maker": "Maker",
                    "label": "Label",
                    "actresses": ["Actor"],
                },
                "",
            )

    async def fake_check_url(url: str, length: bool = False, real_url: bool = False):
        return url

    monkeypatch.setattr(dmm_module, "check_url", fake_check_url)
    monkeypatch.setattr(manager.config, "download_files", [DownloadableFile.POSTER, DownloadableFile.THUMB])

    crawler = JavdbApiCrawler(client=FakeClient())
    input_data = CrawlerInput.empty()
    input_data.number = "SSIS-001"

    response = await crawler.run(input_data)

    assert response.data is not None
    assert response.data.number == "SSIS-001"
    assert response.data.title == "Title"
    assert response.data.actors == ["Actor"]
