"""Build and validate the OnesDM marketplace catalog."""
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
DISPLAY_FIELDS = {"name", "description", "keywords"}


def latest_release(repository):
    api = f"https://api.github.com/repos/{repository}/releases/latest"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "onesdm-plugin-market",
    }
    token = os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    with urllib.request.urlopen(urllib.request.Request(api, headers=headers), timeout=45) as response:
        return json.load(response)


def release_url(source, version, platform):
    repository = source["repository"]
    if source.get("universal", False):
        filename = f"{repository.split('/')[-1]}-{version}.zip"
    else:
        filename = f"ndm-{source['id']}-{version}-{platform}.zip"
    url = f"https://github.com/{repository}/releases/download/v{version}/{filename}"
    return filename, url


def listing_for_version(source, version):
    listing = {key: value for key, value in source.items() if key not in {"release_metadata", "universal"}}
    listing.update(source.get("release_metadata", {}).get(version, {}))
    listing["version"] = version
    return listing


def published(source):
    release = latest_release(source["repository"])
    tag = release["tag_name"]
    if not tag.startswith("v") or not VERSION.fullmatch(tag[1:]) or release["draft"] or release["prerelease"]:
        raise ValueError(f"no stable versioned release for {source['id']}")
    plugin = listing_for_version(source, tag[1:]) | {"artifacts": {}}
    assets = {asset["name"]: asset for asset in release["assets"]}
    verified = {}
    for platform in PLATFORMS:
        filename, url = release_url(source, plugin["version"], platform)
        if filename not in verified:
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
            verified[filename] = {"url": url, "sha256": digest[7:]}
        plugin["artifacts"][platform] = verified[filename]
    return plugin


def valid_text(text, limit):
    return isinstance(text, str) and bool(text.strip()) and len(text.encode("utf-8")) <= limit


def valid_localized(text, limit):
    chinese = text.get("zh", "")
    return valid_text(text["en"], limit) and (
        chinese == "" or valid_text(chinese, limit)
    )


def validate_listing(listing):
    for key, limit in (("name", 128), ("description", 1024)):
        if not valid_localized(listing[key], limit):
            raise ValueError(f"invalid localized {key} for {listing['id']}")
    keywords = listing.get("keywords", [])
    if not isinstance(keywords, list) or len(keywords) > 16 or any(
        not valid_text(keyword, 96) for keyword in keywords
    ):
        raise ValueError(f"invalid search keywords for {listing['id']}")


def validate_sources(sources):
    categories = sources["categories"]
    if not 1 <= len(categories) <= 16 or any(
        not ID.fullmatch(key) or not valid_localized(label, 96)
        for key, label in categories.items()
    ):
        raise ValueError("invalid marketplace category definitions")
    if not 1 <= len(sources["plugins"]) <= 128:
        raise ValueError("invalid source count")
    ids = set()
    for source in sources["plugins"]:
        if not ID.fullmatch(source["id"]) or not REPO.fullmatch(source["repository"]) or source["id"] in ids:
            raise ValueError("invalid plugin identity")
        if source["category"] not in categories:
            raise ValueError(f"unrecognized category for {source['id']}")
        if not isinstance(source.get("universal", False), bool):
            raise ValueError(f"invalid universal package setting for {source['id']}")
        validate_listing(source)
        metadata = source.get("release_metadata", {})
        if not isinstance(metadata, dict) or len(metadata) > 32:
            raise ValueError(f"invalid release metadata for {source['id']}")
        for version, fields in metadata.items():
            if not VERSION.fullmatch(version) or not isinstance(fields, dict) or fields.keys() - DISPLAY_FIELDS:
                raise ValueError(f"invalid display override for {source['id']} / {version}")
            validate_listing(listing_for_version(source, version))
        ids.add(source["id"])
    return ids


def validate(catalog, sources, ids, require_packages):
    if catalog["schema"] != 1 or catalog["categories"] != sources["categories"]:
        raise ValueError("invalid catalog schema or categories")
    if {item["id"] for item in catalog["plugins"]} != ids or len(catalog["plugins"]) != len(ids):
        raise ValueError("catalog does not match source list")
    for plugin in catalog["plugins"]:
        source = next(item for item in sources["plugins"] if item["id"] == plugin["id"])
        if plugin["repository"] != source["repository"] or not VERSION.fullmatch(plugin["version"]):
            raise ValueError("invalid release identity")
        listing = listing_for_version(source, plugin["version"])
        for key in (*DISPLAY_FIELDS, "category"):
            if plugin.get(key) != listing.get(key):
                raise ValueError(f"invalid catalog {key} for {plugin['id']}")
        artifacts = plugin["artifacts"]
        if require_packages and set(artifacts) != set(PLATFORMS):
            raise ValueError(f"missing release packages for {plugin['id']}")
        for platform, artifact in artifacts.items():
            _, url = release_url(source, plugin["version"], platform)
            if platform not in PLATFORMS or artifact["url"] != url or not DIGEST.fullmatch(artifact["sha256"]):
                raise ValueError("invalid platform package or digest")
        if source.get("universal", False) and len({artifact["sha256"] for artifact in artifacts.values()}) > 1:
            raise ValueError(f"universal package digests differ for {plugin['id']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "refresh"))
    parser.add_argument("--require-packages", action="store_true")
    args = parser.parse_args()
    sources = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    ids = validate_sources(sources)
    path = ROOT / "catalog.json"
    if args.action == "refresh":
        catalog = {
            "schema": 1,
            "categories": sources["categories"],
            "plugins": [published(source) for source in sources["plugins"]],
        }
        validate(catalog, sources, ids, True)
        path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        validate(json.loads(path.read_text(encoding="utf-8")), sources, ids, args.require_packages)
    print("Catalog verified")


if __name__ == "__main__":
    main()
