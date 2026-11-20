# NDM Next plugin market

NDM Next reads [catalog.json](catalog.json) to browse, install, update and
uninstall plugin packages. The first catalog sources are the YouTube and
BitTorrent engines.

- [YouTube engine](https://github.com/AreChen/NDM-Next-Plugin-yt-dlp)
- [BitTorrent engine](https://github.com/AreChen/NDM-Next-Plugin-BitTorrent)

Each engine publishes its own versioned ZIPs and SHA-256 sidecars. After both
releases are available, run `python3 tools/catalog.py refresh` and review the
resulting catalog. The script checks the platform ZIP URLs and compares the
release sidecars with the digests reported by GitHub. Use
`python3 tools/catalog.py check --require-packages` for a catalog ready to
serve to users.

## Listing and translations

Add the engine release repository and stable plugin ID to the `plugins` list
in [sources.json](sources.json). Give the entry a `name` and `description`
with a required English `en` string and an optional Simplified Chinese
`zh` string. NDM uses English when the Chinese string is missing or empty.

Set `category` to a key from the `categories` object in the same file.
Each category has bilingual labels with the same fallback. New categories
can be defined here. An optional `keywords` array can include protocol
abbreviations and search terms in either language. Search also covers the
plugin ID, both translations and both category labels.

A plugin archive includes a manifest, a native engine executable, and
optionally a JavaScript panel. Use localized label objects in the manifest
and panel. [NDM Next SDK and package contract](https://github.com/AreChen/NDM-Next/tree/codex/plugin-sdk-mcp/desktop/crates/ndm-plugin-sdk)

## 上架与多语言

在 [sources.json](sources.json) 的 `plugins` 中填写固定的插件 ID 和发布仓库。
`name` 和 `description` 支持 `en` 与 `zh`，省略或留空中文时显示英文。
`category` 引用同一文件中 `categories` 的分类 ID，分类标签也支持中英文。
可通过 `keywords` 添加中英文搜索词和协议简称。搜索还会匹配插件 ID、
两种语言的名称和描述，以及分类标签。

包内清单和可选 JavaScript 面板同样支持多语言标签。
[下载引擎 SDK 与包格式](https://github.com/AreChen/NDM-Next/tree/codex/plugin-sdk-mcp/desktop/crates/ndm-plugin-sdk)
