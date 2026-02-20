# quark-search

[中文文档](README.zh.md)

A [Claude Code](https://docs.anthropic.com/en/docs/claude-code) skill for searching, validating, and saving cloud drive resources. Combines the [PanSou](https://s.panhunt.com/) aggregation API (90+ Telegram channels, 60+ website plugins) with the local Quark desktop APP to go from keyword → validated results → one-click save.

| Step | What Happens | API Used |
|------|-------------|----------|
| **Search** | Query PanSou for cloud drive links across 6 drive types | `s.panhunt.com/api/search` |
| **Validate** | Check each share link is still alive (not deleted/expired) | `drive-pc.quark.cn` public API |
| **Details** | Fetch file names, sizes, folder contents | `drive-pc.quark.cn` public API |
| **Save** | Open the share in Quark APP for one-click save to drive | `localhost:9128` local API |

## Installation

### Via skills.sh (recommended)

```bash
npx skills add psylch/quark-search-skill -g -y
```

### Via Claude Code Plugin Marketplace

```shell
/plugin marketplace add psylch/quark-search-skill
/plugin install quark-search@psylch-quark-search-skill
```

Restart Claude Code after installation.

## Prerequisites

- **Quark desktop APP** installed and running ([quark.cn](https://www.quark.cn/))
- **Logged in** with a Quark account (membership recommended for full download speed)
- **Claude Code** or any agent that supports [skills.sh](https://skills.sh/)

## Usage

In Claude Code, use any of these trigger phrases:

```
搜资源 三体
找片 星际穿越
帮我下载 xxx
搜一下网盘资源
quark search interstellar
```

## How It Works

1. **Pre-flight** — checks Quark APP is running and logged in via `localhost:9128/desktop_info`
2. **Search** — queries PanSou API, prioritizes Quark drive results
3. **Validate** — tests each share link via public token API (no auth needed)
4. **Present** — shows valid results with file details, marks invalid/expired links
5. **Save** — triggers Quark APP to open the selected share link window

> **Note:** The actual "save to drive" and "download to local" steps happen in the Quark APP UI — the user clicks one button. This is by design to avoid reverse-engineering authenticated APIs.

## Supported Drive Types

PanSou returns results from multiple cloud drives. The skill prioritizes Quark results but also reports others:

| Type | Drive |
|------|-------|
| `quark` | Quark (夸克网盘) — **preferred** |
| `aliyun` | Aliyun Drive (阿里云盘) |
| `baidu` | Baidu Netdisk (百度网盘) |
| `115` | 115 Drive |
| `pikpak` | PikPak |
| `uc` | UC Drive |

## Error Handling

| Error | Detection | Resolution |
|-------|-----------|------------|
| APP not running | `localhost:9128` connection refused | Launch Quark APP |
| Not logged in | `desktop_info` returns `isLogin: false` | Log in to Quark |
| No results | PanSou returns `total: 0` | Try different keywords |
| All links invalid | All validation checks fail | Try alternative keywords or drive types |
| Share has password | Token API returns password required | Ask user for extraction code (提取码) |

## File Structure

```
quark-search-skill/
├── .claude-plugin/
│   ├── marketplace.json          # Plugin registry
│   └── plugin.json               # Plugin manifest
├── skills/
│   └── quark-search/
│       └── SKILL.md              # Main skill definition
├── README.md
├── README.zh.md
└── LICENSE
```

## License

MIT
