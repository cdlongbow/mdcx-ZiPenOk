## 220260722

## 新增
- 新增独立的封面补图工具：可通过 `scripts/cover_backfill.py` 命令行或 `scripts/cover_backfill_gui.bat` 图形界面，按番号或文件名下载并补齐封面、缩略图。
- 补图工具复用当前 MDCx 配置、站点优先级、命名、裁切和水印规则，并支持批量输入与覆盖已有图片。

## 修复
- `official` 新增 `JIMMY` 前缀路由，`JIMMY-003` 等番号会从 FALENO 官网获取资料。
- 自动最佳海报不再将横向海报作为最终 Poster；存在缩略图时会按原规则从缩略图右侧裁切，修复 `ABF-371` 一类封面未裁剪的问题。
- 所有刮削来源均失败时，日志会列出各站点的具体失败原因，便于定位超时或搜索未匹配。
- 改进 Madouqu 页面请求指纹和页面解析，提升手动指定 Madouqu 时的刮削稳定性。

## 验证
- 已通过 `tests/core/test_web_amazon.py`、`tests/crawlers/test_official.py`、`tests/test_file_crawler_runtime.py`。
