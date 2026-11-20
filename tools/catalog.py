"""Build and validate the NDM Next marketplace catalog."""
import argparse
import json
import os
from pathlib import Path
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
PLATFORMS = ("linux-x86_64", "macos-aarch64", "macos-x86_64", "windows-x86_64")
ID = re.compile(r"[a-z0-9][a-z0-9-]{0,39}")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?")
REPO = re.compile(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+")
DIGEST = re.compile(r"[0-9a-f]{64}")


def latest_release(repository):
    api = f"https://api.github.com/repos/{repository}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "NDM-Next-Plugin-Market",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=45) as response:
        return json.load(response)


def release_url(plugin, platform):
    version = plugin["version"]
    filename = f"ndm-{plugin['id']}-{version}-{platform}.zip"
    url = f"https://github.com/{plugin['repository']}/releases/download/v{version}/{filename}"
    return filename, url


def published(source):
    release = latest_release(source["repository"])
    tag = release["tag_name"]
    if not tag.startswith("v") or not VERSION.fullmatch(tag[1:]) or release["draft"] or release["prerelease"]:
        raise ValueError(f"no stable versioned release for {source['id']}")
    plugin = source | {"version": tag[1:], "artifacts": {}}
    assets = {asset["name"]: asset for asset in release["assets"]}
    for platform in PLATFORMS:
        filename, url = release_url(plugin, platform)
        asset = assets.get(filename)
        if not asset or asset["browser_download_url"] != url or f"{filename}.sha256" not in assets:
            raise ValueError(f"incomplete release asset for {source['id']} / {platform}")
        digest = asset.get("digest") or ""
        if not digest.startswith("sha256:") or not DIGEST.fullmatch(digest[7:]):
            raise ValueError(f"missing GitHub asset digest for {filename}")
        with urllib.request.urlopen(url + ".sha256", timeout=30) as response:
            check = response.read(1024).decode("ascii").strip().split()
        if check != [digest[7:], filename]:
            raise ValueError(f"release checksum sidecar disagrees for {filename}")
        plugin["artifacts"][platform] = {"url": url, "sha256": digest[7:]}
    return plugin


def validate(catalog, sources, require_packages):
    if catalog["schema"] != 1 or not 1 <= len(sources) <= 128:
        raise ValueError("invalid catalog schema or plugin count")
    ids = set()
    for source in sources:
        if not ID.fullmatch(source["id"]) or not REPO.fullmatch(source["repository"]) or source["id"] in ids:
            raise ValueError("invalid plugin identity")
        ids.add(source["id"])
    if {item["id"] for item in catalog["plugins"]} != ids or len(catalog["plugins"]) != len(ids):
        raise ValueError("catalog does not match source list")
    for plugin in catalog["plugins"]:
        source = next(item for item in sources if item["id"] == plugin["id"])
        if plugin["repository"] != source["repository"] or not VERSION.fullmatch(plugin["version"]):
            raise ValueError("invalid release identity")
        for key in ("name", "description"):
            if plugin[key] != source[key] or not plugin[key]["en"]:
                raise ValueError("invalid catalog descriptions")
        artifacts = plugin["artifacts"]
        if require_packages and set(artifacts) != set(PLATFORMS):
            raise ValueError(f"missing release packages for {plugin['id']}")
        for platform, artifact in artifacts.items():
            _, url = release_url(plugin, platform)
            if platform not in PLATFORMS or artifact["url"] != url or not DIGEST.fullmatch(artifact["sha256"]):
                raise ValueError("invalid platform package or digest")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "refresh"))
    parser.add_argument("--require-packages", action="store_true")
    args = parser.parse_args()
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    path = ROOT / "catalog.json"
    if args.action == "refresh":
        for source in sources:
            if not ID.fullmatch(source["id"]) or not REPO.fullmatch(source["repository"]):
                raise ValueError("invalid plugin identity")
        catalog = {"schema": 1, "plugins": [published(source) for source in sources]}
        validate(catalog, sources, True)
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        validate(json.loads(path.read_text(encoding="utf-8")), sources, args.require_packages)
    print("Catalog verified")


if __name__ == "__main__":
    main()
