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
| `GET /api/movies` | Movie listings from 7reels (`section`, `q`, `genre`, `page`) |
| `GET /api/movies/genres` | Movie genres from 7reels |
| `GET /api/movies/<id>` | Movie details and credits from 7reels |
| `GET /stream/<id>` | Local HLS proxy for curated Ghanaian channels |
| `GET /sw.js` | Service worker served with root scope |

## Movies

The **Movies** tab browses the TMDB-backed catalog exposed by
[7reels](https://7reels.cc/). It includes trending, popular, top-rated,
now-playing and discover rows, search, genre chips, pagination and a details
dialog with synopsis, rating, director and cast.

ESINU proxies the metadata so the browser does not need direct API access. It
does **not** host or embed movie streams; the **Watch on 7reels** button opens
the title on 7reels, where playback is provided by that service. The Movies tab
is also linkable at `/#movies`.

## Ghanaian channels

The app adds a curated free-to-air Ghana pack on top of the iptv-org playlist:
Adom TV, GTV Ghana, GTV Sports, GhOne TV, AfroBeats TV, UTV Ghana, Atinka TV,
Joy Prime, Metro TV Ghana, TV3 Ghana, Citi TV Ghana, TV Africa, G-eye TV and
Faculty TV. A few upstream streams may be offline at times; auto-skip moves to
the next channel when that happens.

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

## Playback

If a channel's stream is unavailable, ESINU automatically tries the next
channel in the current list. A load timeout also skips streams that never
start. It stops after five consecutive failures and shows an error with a Retry
button, so a broken playlist cannot cause an endless skip loop. Selecting a
channel or navigating manually resets the counter.

## Configuration

Environment variables:

- `PLAYLIST_URL` — playlist source URL
- `PLAYLIST_TIMEOUT` — download timeout in seconds (default `30`)
- `REELS_BASE_URL` — 7reels base URL (default `https://7reels.cc`)
- `MOVIE_TIMEOUT` — 7reels API timeout in seconds (default `15`)
- `MOVIE_LANGUAGE` — catalog language (default `en-US`)
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
