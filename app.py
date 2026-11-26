"""ESINU: a Flask app for browsing and playing public HLS streams."""

from __future__ import annotations

import logging
import os
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from flask import Flask, Response, jsonify, render_template, request, url_for

from country_names import COUNTRY_NAMES

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PLAYLIST_PATH = DATA_DIR / "playlist.m3u"

DEFAULT_PLAYLIST_URL = "https://iptv-org.github.io/iptv/index.m3u"
PLAYLIST_URL = os.getenv("PLAYLIST_URL", DEFAULT_PLAYLIST_URL)
DOWNLOAD_TIMEOUT = float(os.getenv("PLAYLIST_TIMEOUT", "30"))
USER_AGENT = os.getenv(
    "PLAYLIST_USER_AGENT", "Mozilla/5.0 (compatible; ESINU/1.0)"
)

# Curated free-to-air Ghanaian streams that are embedded publicly by
# LiveGhanaTV. They require a Referer header, so the app proxies them locally.
# Use only streams you are legally permitted to watch.
GHANA_SOURCE_REFERER = "https://liveghanatv.com/"
GHANA_STREAMS = {
    "adom": {
        "name": "Adom TV",
        "group": "Ghana · Entertainment",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/adomtv/ghanatvweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "gtv": {
        "name": "GTV Ghana",
        "logo": "https://i.imgur.com/5cFLWKO.png",
        "group": "Ghana · General",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/gtvghana/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "gtv-sports": {
        "name": "GTV Sports",
        "group": "Ghana · Sports",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/gtvsport/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "ghone": {
        "name": "GhOne TV",
        "group": "Ghana · Entertainment",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/ghonetv/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "afrobeats": {
        "name": "AfroBeats TV",
        "group": "Ghana · Music",
        "url": "https://stream.ecable.tv/afrobeats/index.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "utv": {
        "name": "UTV Ghana",
        "group": "Ghana · Entertainment",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/utvgha/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "atinka": {
        "name": "Atinka TV",
        "group": "Ghana · News",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/atinkkatv/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "joy-prime": {
        "name": "Joy Prime",
        "group": "Ghana · Entertainment",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/joyprim/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "metro": {
        "name": "Metro TV Ghana",
        "group": "Ghana · News",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/metrotvg/ghanaweb.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
    "tv3": {
        "name": "TV3 Ghana",
        "logo": "https://i.imgur.com/8t967Hq.png",
        "group": "Ghana · Entertainment",
        "url": "https://g2qd3exjy7an-hls-live.5centscdn.com/webtv3/ghanatv.stream/playlist.m3u8",
        "referer": GHANA_SOURCE_REFERER,
    },
}

_URI_RE = re.compile(r'URI="([^"]+)"')
_ATTRIBUTE_RE = re.compile(r'([\w.-]+)\s*=\s*(?:"([^"]*)"|([^\s,]+))')
_TVG_COUNTRY_RE = re.compile(r"\.([a-z]{2})(?:@|$)", re.I)

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO").upper())
log = logging.getLogger("esinu")

app = Flask(__name__)
app.config.update(PLAYLIST_URL=PLAYLIST_URL, PLAYLIST_PATH=PLAYLIST_PATH)


def download_playlist(url: str | None = None, force: bool = False) -> Path:
    """Download the M3U playlist unless a local copy already exists.

    Only use sources you are legally allowed to access. The default source is a
    community-maintained list of public, free-to-air streams.
    """
    source = url or str(app.config["PLAYLIST_URL"])
    target = Path(app.config["PLAYLIST_PATH"])
    target.parent.mkdir(parents=True, exist_ok=True)

    if target.exists() and not force:
        return target

    log.info("Downloading playlist from %s", source)
    response = requests.get(
        source,
        timeout=DOWNLOAD_TIMEOUT,
        headers={"User-Agent": USER_AGENT, "Accept": "application/x-mpegURL, */*"},
    )
    response.raise_for_status()
    response.encoding = "utf-8"

    content = response.text.lstrip("\ufeff").strip()
    if not content.startswith("#EXTM3U"):
        raise ValueError("Downloaded content does not look like an M3U playlist")

    temporary = target.with_name(target.name + ".tmp")
    try:
        temporary.write_text(content + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        if temporary.exists():
            temporary.unlink()

    log.info("Saved %d bytes to %s", len(content), target)
    return target


def _parse_attributes(text: str) -> dict[str, str]:
    """Extract key/value attributes from the attribute portion of #EXTINF.

    M3U attributes use double quotes for values containing spaces, so a small
    regex is safer than shell tokenisation here.
    """
    attributes: dict[str, str] = {}
    for match in _ATTRIBUTE_RE.finditer(text):
        key = match.group(1).lower()
        value = match.group(2) if match.group(2) is not None else match.group(3)
        attributes[key] = value.strip()
    return attributes


def _split_extinf(info: str) -> tuple[str, str]:
    """Split an #EXTINF value into attributes and the human-readable name."""
    quote = None
    for index, char in enumerate(info):
        if char == '"':
            if quote == char:
                quote = None
            elif quote is None:
                quote = char
        elif char == "," and quote is None:
            return info[:index], info[index + 1 :].strip()
    return info, ""


def _is_playable_url(value: str) -> bool:
    """Keep HTTP(S) HLS candidates and reject formats hls.js cannot play."""
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    path = parsed.path.lower()
    if not path or path == "/":
        return False

    non_hls = (
        ".mpd", ".ts", ".flv", ".m4s", ".mp4", ".mov", ".mkv", ".avi", ".webm",
    )
    return not path.endswith(non_hls)


def _country_from_tvg_id(tvg_id: str | None) -> str | None:
    """Map an iptv-org tvg-id country suffix to a readable country name."""
    if not tvg_id:
        return None
    match = _TVG_COUNTRY_RE.search(tvg_id)
    if not match:
        return None
    code = match.group(1).upper()
    return COUNTRY_NAMES.get(code, code)


def _country_name(value: str | None) -> str | None:
    """Resolve a country code, tvg-id suffix or literal country name."""
    if not value:
        return None
    cleaned = value.strip()
    if cleaned.upper() in COUNTRY_NAMES:
        return COUNTRY_NAMES[cleaned.upper()]
    return _country_from_tvg_id(cleaned) or cleaned or None


def parse_playlist(path: str | Path | None = None) -> list[dict[str, str | None]]:
    """Parse an M3U file into channel dictionaries.

    Returns dictionaries with ``name``, ``logo``, ``group``, ``country`` and
    ``url`` keys. Missing optional values are ``None``. Duplicate URLs are
    ignored.
    """
    source = Path(path) if path is not None else Path(app.config["PLAYLIST_PATH"])
    channels: list[dict[str, str | None]] = []
    seen_urls: set[str] = set()
    pending: dict[str, str | None] | None = None
    ext_group: str | None = None
    tvg_id: str | None = None

    with source.open("r", encoding="utf-8-sig", errors="replace") as playlist_file:
        for raw_line in playlist_file:
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("#EXTINF:"):
                info = line[len("#EXTINF:") :]
                attributes_part, name = _split_extinf(info)
                attributes = _parse_attributes(attributes_part)
                tvg_id = attributes.get("tvg-id")
                pending = {
                    "name": name
                    or attributes.get("tvg-name")
                    or attributes.get("name")
                    or "",
                    "logo": attributes.get("tvg-logo") or attributes.get("logo"),
                    "group": (
                        attributes.get("group-title")
                        or attributes.get("group")
                        or ext_group
                    ),
                    "country": _country_from_tvg_id(tvg_id)
                    or _country_name(
                        attributes.get("country") or attributes.get("tvg-country")
                    ),
                    "url": "",
                }
                continue

            if line.startswith("#EXTGRP:"):
                ext_group = line[len("#EXTGRP:") :].strip() or None
                if pending is not None and not pending["group"]:
                    pending["group"] = ext_group
                continue

            if line.startswith("#"):
                continue

            if pending is not None and _is_playable_url(line):
                if line not in seen_urls:
                    channel = dict(pending)
                    channel["url"] = line
                    if not channel["group"] and ext_group:
                        channel["group"] = ext_group
                    channels.append(channel)
                    seen_urls.add(line)
                pending = None
                ext_group = None

    return channels


def _curated_channels() -> list[dict[str, str | None]]:
    """Expose the curated Ghana pack through the local proxy endpoints."""
    return [
        {
            "name": item["name"],
            "logo": item.get("logo"),
            "group": item["group"],
            "country": "Ghana",
            "url": f"/stream/{channel_id}",
        }
        for channel_id, item in GHANA_STREAMS.items()
    ]


def _unique_channels(
    channels: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Drop channels with duplicate URLs or names, preserving input order."""
    seen: set[str] = set()
    unique: list[dict[str, str | None]] = []
    for channel in channels:
        key = channel["url"] or channel["name"] or ""
        if key and key not in seen:
            seen.add(key)
            unique.append(channel)
    return unique


def get_channels(force: bool = False) -> list[dict[str, str | None]]:
    """Ensure the playlist exists locally and return all available channels."""
    playlist_path = download_playlist(force=force)
    curated_upstreams = {item["url"] for item in GHANA_STREAMS.values()}
    channels = [
        channel
        for channel in parse_playlist(playlist_path)
        if channel["url"] not in curated_upstreams
    ]
    channels.extend(_curated_channels())

    unique = _unique_channels(channels)
    if not unique:
        raise ValueError("Playlist contains no playable HTTP(S) streams")

    unique.sort(
        key=lambda channel: (
            (channel["country"] or "Uncategorized").casefold(),
            (channel["group"] or "").casefold(),
            (channel["name"] or "").casefold(),
        )
    )
    return unique


def _api_error(message: str, status_code: int):
    """Return a consistent JSON error payload for API failures."""
    log.warning("API error %s: %s", status_code, message)
    return jsonify({"error": message}), status_code


def _is_allowed_upstream(target: str, stream: dict) -> bool:
    """Prevent the proxy from being used as an open URL fetcher."""
    parsed_target = urlparse(target)
    parsed_source = urlparse(stream["url"])
    if parsed_target.scheme not in {"http", "https"}:
        return False
    if parsed_target.netloc.lower() != parsed_source.netloc.lower():
        return False

    raw_path = unquote(parsed_target.path)
    if "\\" in raw_path or ".." in raw_path.split("/") or "." in raw_path.split("/"):
        return False

    normalized = posixpath.normpath(raw_path)
    source_dir = posixpath.dirname(parsed_source.path)
    if source_dir in {"", "/", "."}:
        return normalized.startswith("/")

    source_dir = posixpath.normpath(source_dir).rstrip("/")
    return normalized == source_dir or normalized.startswith(source_dir + "/")


def _rewrite_playlist(text: str, base_url: str, channel_id: str) -> str:
    """Rewrite HLS playlist URLs so the browser fetches them via our proxy."""

    def proxied(target: str) -> str:
        return url_for("stream_proxy", channel_id=channel_id, u=target)

    def replace_uri(match: re.Match) -> str:
        resolved = urljoin(base_url, match.group(1))
        if urlparse(resolved).scheme not in {"http", "https"}:
            return match.group(0)
        return f'URI="{proxied(resolved)}"'

    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            resolved = urljoin(base_url, stripped)
            if urlparse(resolved).scheme in {"http", "https"}:
                lines.append(proxied(resolved))
            else:
                lines.append(stripped)
        else:
            lines.append(_URI_RE.sub(replace_uri, line))
    return "\n".join(lines) + "\n"


@app.get("/")
def index():
    """Render the player frontend."""
    return render_template("index.html")


@app.get("/sw.js")
def service_worker():
    """Serve the service worker from the origin root with full scope."""
    response = app.send_static_file("sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.get("/api/channels")
def api_channels():
    """Return channels as JSON; pass ``?refresh=1`` to force a re-download."""
    force = request.args.get("refresh", "").lower() in {"1", "true", "yes", "on"}
    try:
        return jsonify(get_channels(force=force))
    except requests.RequestException as exc:
        return _api_error(f"Could not download playlist: {exc}", 502)
    except (OSError, ValueError) as exc:
        return _api_error(str(exc), 500)


@app.get("/api/health")
def api_health():
    """Lightweight health endpoint for local checks."""
    playlist_path = Path(app.config["PLAYLIST_PATH"])
    present = playlist_path.exists()
    count = 0
    if present:
        try:
            curated_upstreams = {item["url"] for item in GHANA_STREAMS.values()}
            base = [
                channel
                for channel in parse_playlist(playlist_path)
                if channel["url"] not in curated_upstreams
            ]
            count = len(_unique_channels(base + _curated_channels()))
        except (OSError, ValueError):
            count = 0

    return jsonify(
        {
            "status": "ok",
            "playlist_present": present,
            "channel_count": count,
        }
    )


@app.get("/stream/<channel_id>")
def stream_proxy(channel_id: str):
    """Proxy a curated HLS stream with the referer its CDN requires."""
    stream = GHANA_STREAMS.get(channel_id)
    if stream is None:
        return _api_error("Unknown stream", 404)

    target = request.args.get("u") or stream["url"]
    if not _is_allowed_upstream(target, stream):
        return _api_error("Blocked upstream URL", 400)

    referer = stream["referer"]
    parsed_referer = urlparse(referer)
    origin = f"{parsed_referer.scheme}://{parsed_referer.netloc}"

    try:
        upstream = requests.get(
            target,
            stream=True,
            allow_redirects=False,
            timeout=(5, 30),
            headers={
                "User-Agent": USER_AGENT,
                "Referer": referer,
                "Origin": origin,
            },
        )
        if 300 <= upstream.status_code < 400:
            upstream.close()
            return _api_error("Upstream redirects are not proxied", 502)
        upstream.raise_for_status()
    except requests.RequestException as exc:
        return _api_error(f"Upstream stream unavailable: {exc}", 502)

    content_type = upstream.headers.get("Content-Type", "")
    is_playlist = (
        ".m3u8" in urlparse(target).path.lower() or "mpegurl" in content_type.lower()
    )

    if is_playlist:
        playlist = _rewrite_playlist(upstream.text, target, channel_id)
        upstream.close()
        response = Response(
            playlist, status=200, content_type="application/vnd.apple.mpegurl"
        )
    else:

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        response = Response(
            generate(), status=200, content_type=content_type or "video/mp2t"
        )

    response.headers["Cache-Control"] = "no-store"
    return response


if __name__ == "__main__":
    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes", "on"}
    if host not in {"127.0.0.1", "localhost", "::1"}:
        debug = False
    app.run(host=host, port=port, debug=debug)
