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

New engine proposals can add a release repository and bilingual descriptions
to [sources.json](sources.json). A plugin includes a manifest, a native engine
executable, and optionally a JavaScript panel. See the
[NDM Next SDK and package contract](https://github.com/AreChen/NDM-Next/tree/f8524704ba20b601ce8da9683b500bcf673b1512/desktop/crates/ndm-plugin-sdk).
