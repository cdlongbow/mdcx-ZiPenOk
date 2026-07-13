## 2202607131

## 新增
- `javdbapi` 改为优先使用 JavDB App API：先通过 `/v2/search` 搜索 movie id，再通过 `/v4/movies/{movieId}` 获取详情。
- `javdbapi` 支持 FC2 番号归一化搜索，例如 `FC2-PPV-4159457` 会尝试 `FC2-4159457` 和纯数字候选。

## 修复
- 修复 `javdbapi` 返回的 `tp.spfcas.com/rhe951l4q` 图片下载后无法识别的问题；现在会统一转换到可直接下载的 `c0.jdbstatic.com` 静态图片地址。
- 修复 `javdbapi` 网络检测仍访问旧接口的问题，改为使用 App API 搜索接口和 `jdSignature` 请求头。

## 验证
- 已验证 `FC2-PPV-868635` 的封面和剧照地址可转换为正常 JPEG 图片。
- 已通过 `tests/crawlers/test_javdbapi.py`、`tests/test_network_check.py`、`tests/test_base_web.py`。
