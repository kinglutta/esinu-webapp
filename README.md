# ESINU

ESINU is a small Flask app that downloads an M3U playlist, groups channels by
country, and plays public HLS streams in the browser with `hls.js`.

## Run locally

```powershell
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5000>.

## Installable web app (PWA)

`static/manifest.webmanifest`, `static/sw.js` and generated app icons make ESINU
installable from Chrome/Safari when served over HTTPS (or localhost). On a
phone, Add to Home Screen opens ESINU in a standalone window.

## Endpoints

| Endpoint | Description |
| --- | --- |
| `GET /` | Player UI |
| `GET /api/channels` | Parsed channels as JSON |
| `GET /api/channels?refresh=1` | Force playlist re-download |
| `GET /api/health` | Local health/status check |
| `GET /stream/<id>` | Local HLS proxy for curated Ghanaian channels |
| `GET /sw.js` | Service worker served with root scope |

## Ghanaian channels

The app adds a curated free-to-air Ghana pack on top of the iptv-org playlist:
Adom TV, GTV Ghana, GTV Sports, GhOne TV, AfroBeats TV, UTV Ghana, Atinka TV,
Joy Prime, Metro TV Ghana and TV3 Ghana.

Some of those CDNs require a `Referer` header that browsers cannot set, so the
app proxies playlists and video segments locally. Use the **🇬🇭 Ghana** chip in
the sidebar to show only Ghanaian channels.

## Channels by country

Each channel includes a `country` field derived from the playlist's `tvg-id`
country code (for example, `GTV.gh@SD` becomes `Ghana`). Channels are sorted by
country and displayed under country headings. Use the **country** dropdown in
the sidebar to filter to a single country, or combine it with the group,
favorites and search filters.

> Only use playlists and streams you are legally allowed to access.

## Configuration

Environment variables:

- `PLAYLIST_URL` — playlist source URL
- `PLAYLIST_TIMEOUT` — download timeout in seconds (default `30`)
- `HOST`, `PORT`, `FLASK_DEBUG` — server settings
- `LOG_LEVEL` — logging level (default `INFO`)

## Keyboard shortcuts

- `/` — focus search
- `J` / `K` — next / previous channel
- `F` — toggle favorite
- `S` — shuffle
- `R` — refresh channel list
- `M` — mute
- `Enter` — fullscreen

> Only use playlists and streams you are legally allowed to access.
