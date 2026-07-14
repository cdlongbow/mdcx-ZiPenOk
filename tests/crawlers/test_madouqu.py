from pathlib import Path

import pytest
from lxml import etree

from mdcx.crawlers.madouqu import (
    MadouquCrawler,
    _extract_number_candidates,
    get_detail_info,
    get_real_url,
    normalize_cover_url,
)
from mdcx.models.types import CrawlerInput


def test_normalize_cover_url_rewrites_legacy_wp_proxy_host():
    url = "https://i0.wp.com/md.hm1225.cyou/wp-content/uploads/2022/02/demo.jpg?resize=700%2C394&ssl=1"

    assert (
        normalize_cover_url(url)
        == "https://i0.wp.com/madouqu.com/wp-content/uploads/2022/02/demo.jpg?resize=700%2C394&ssl=1"
    )


def test_extract_number_candidates_strips_date_suffix_from_filename():
    file_path = r"C:\temp\(香蕉视频)(xjx-0754)(20260707)xjx0754 嫂子的诱惑不伦性交内射-米菲兔(mp4).strm"

    assert _extract_number_candidates("XJX-075420260707", "", file_path)[:2] == ["XJX-0754", "XJX0754"]


@pytest.mark.asyncio
async def test_generate_search_url_prioritizes_short_number_from_filename():
    crawler = MadouquCrawler(client=None)
    input_data = CrawlerInput.empty()
    input_data.number = "XJX-075420260707"
    input_data.file_path = Path(
        r"C:\temp\(香蕉视频)(xjx-0754)(20260707)xjx0754 嫂子的诱惑不伦性交内射-米菲兔(mp4).strm"
    )
    ctx = crawler.new_context(input_data)

    search_urls = await crawler._generate_search_url(ctx)

    assert ctx.number_candidates[:2] == ["XJX-0754", "XJX0754"]
    assert search_urls[:2] == ["https://madouqu.com/?s=XJX-0754", "https://madouqu.com/?s=XJX0754"]


def test_get_real_url_prefers_search_result_data_src_cover():
    html = etree.fromstring(
        """
        <html>
          <body>
            <div class="entry-media">
              <div>
                <a href="https://madouqu.com/video/md0217/">
                  <img
                    class="thumb"
                    alt="MD0217 換母盪元宵"
                    src="data:image/gif;base64,xxx"
                    data-src="https://i0.wp.com/madouqu.com/wp-content/uploads/2022/02/demo.jpg?fit=700%2C394&ssl=1"
                  />
                </a>
              </div>
            </div>
          </body>
        </html>
        """,
        etree.HTMLParser(),
    )

    assert get_real_url(html, ["MD0217"]) == (
        True,
        "MD0217",
        "MD0217 換母盪元宵",
        "https://madouqu.com/video/md0217/",
        "https://i0.wp.com/madouqu.com/wp-content/uploads/2022/02/demo.jpg?fit=700%2C394&ssl=1",
    )


def test_get_detail_info_normalizes_detail_cover_url():
    html = etree.fromstring(
        """
        <html>
          <body>
            <div class="cao_entry_header">
              <header>
                <h1>MD0217 換母盪元宵</h1>
              </header>
            </div>
            <span class="meta-category">麻豆传媒</span>
            <div class="entry-content u-text-format u-clearfix">
              <p>番号：MD0217</p>
              <p>片名：換母盪元宵</p>
              <p><img src="https://i0.wp.com/md.hm1225.cyou/wp-content/uploads/2022/02/demo.jpg?resize=700%2C394&ssl=1" /></p>
            </div>
            <time datetime="2022-02-16T10:00:00+08:00"></time>
          </body>
        </html>
        """,
        etree.HTMLParser(),
    )

    number, title, actor, cover_url, studio, release, year = get_detail_info(html, "MD0217", "MD0217")

    assert number == "MD0217"
    assert title == "換母盪元宵"
    assert actor == ""
    assert cover_url == "https://i0.wp.com/madouqu.com/wp-content/uploads/2022/02/demo.jpg?resize=700%2C394&ssl=1"
    assert studio == "麻豆传媒"
    assert release == "2022-02-16"
    assert year == "2022"


def test_get_detail_info_parses_prefixed_madouqu_labels():
    html = etree.fromstring(
        """
        <html>
          <body>
            <div class="cao_entry_header">
              <header>
                <h1>XJX-0754 嫂子的诱惑不伦性交內射</h1>
              </header>
            </div>
            <span class="meta-category">香蕉视频</span>
            <div class="entry-content u-text-format u-clearfix">
              <p>香蕉番號：XJX-0754</p>
              <p>香蕉片名：嫂子的诱惑不伦性交內射</p>
              <p>麻豆女郎</p>
              <p>：米菲兔</p>
              <p><img src="https://i0.wp.com/madouqu.com/wp-content/uploads/2026/07/demo.jpg?resize=800%2C420&ssl=1" /></p>
            </div>
            <time datetime="2026-07-07T16:00:34+08:00"></time>
          </body>
        </html>
        """,
        etree.HTMLParser(),
    )

    number, title, actor, cover_url, studio, release, year = get_detail_info(html, "XJX-075420260707", "XJX-0754")

    assert number == "XJX-0754"
    assert title == "嫂子的诱惑不伦性交內射"
    assert actor == "米菲兔"
    assert cover_url == "https://i0.wp.com/madouqu.com/wp-content/uploads/2026/07/demo.jpg?resize=800%2C420&ssl=1"
    assert studio == "香蕉视频"
    assert release == "2026-07-07"
    assert year == "2026"
