---
name: quark-search
description: Search, validate, and save cloud drive resources via PanSou aggregation API and local Quark desktop APP integration. This skill should be used when the user wants to find and download resources from cloud drives (网盘资源搜索下载), especially when they mention keywords like "搜资源", "找片", "下载", "网盘", "夸克", "quark", "panso", "盘搜". Requires Quark desktop APP running and logged in with membership.
---

# Quark Search — 网盘资源搜索与下载

Automate the full workflow: search resources → validate links → save to Quark cloud drive → download locally, by combining the PanSou aggregation API with the local Quark desktop APP.

## Prerequisites Check

Before any operation, verify the environment:

```bash
# Check Quark APP status and login
curl -s "http://localhost:9128/desktop_info" | python3 -m json.tool
```

Expected: `isLogin: true`. If the APP is not running or not logged in, instruct the user to launch Quark and log in first.

## Workflow

### Step 1: Search Resources (PanSou API)

**CRITICAL:** The search parameter is `kw` (NOT `q`). The `channels` and `plugins` parameters are required for results to be returned correctly.

```bash
# First, fetch available channels and plugins from health endpoint
curl -s "https://s.panhunt.com/api/health"
# Returns: {"channels": ["channel1", ...], "plugins": ["plugin1", ...], ...}

# Search with keyword — channels and plugins are comma-separated lists
curl -s "https://s.panhunt.com/api/search?kw=KEYWORD&res=merge&src=all&channels=CHANNELS_CSV&plugins=PLUGINS_CSV&page=1&limit=30"
```

**Parameters:**

| Param | Description | Example |
|-------|-------------|---------|
| `kw` | Search keyword (**required**) | `kw=三体` |
| `res` | Result format (**required**) | `res=merge` |
| `src` | Source scope (**required**) | `src=all` |
| `channels` | Comma-separated Telegram channel list (**required**) | Fetch from `/api/health` |
| `plugins` | Comma-separated website plugin list (**required**) | Fetch from `/api/health` |
| `page` | Page number | `page=1` |
| `limit` | Results per page | `limit=30` |

**Response structure:**
```json
{
  "code": 0,
  "data": {
    "total": 1234,
    "merged_by_type": {
      "quark": [{"url": "https://pan.quark.cn/s/xxx", "note": "资源名", "password": "", "source": "plugin:libvio", "datetime": "..."}],
      "baidu": [...],
      "aliyun": [...],
      "115": [...],
      "pikpak": [...],
      "uc": [...],
      "magnet": [...],
      "others": [...]
    }
  }
}
```

When `total` is 0, the `data` object contains only `{"total": 0}` with no `merged_by_type` key.

**JSON parsing note:** PanSou API responses may contain invalid escape sequences. Always parse with `json.loads(raw, strict=False)` in Python.

**Priority:** Always prioritize `quark` type results since the user has Quark membership. Fall back to `aliyun`, `uc`, `baidu` etc. if no quark results.

### Step 2: Validate Links

Before presenting results to the user, validate each candidate link. Extract `pwd_id` from the share URL (`https://pan.quark.cn/s/{pwd_id}`), then:

```bash
# Get share token and check validity
curl -s -X POST "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc" \
  -H "content-type: application/json" \
  -d '{"pwd_id":"PWD_ID_HERE","passcode":""}'
```

**Interpret response:**

| `code` | Meaning | Action |
|--------|---------|--------|
| `0` | Valid share | Proceed. Extract `stoken` from response for detail query |
| `41006` | Share does not exist (分享不存在) | Skip, mark as invalid |
| `41004` | Share expired (分享已过期) | Skip, mark as expired |
| Other non-zero | Other error | Skip |

### Step 3: Get File Details

For valid links, fetch the file list to show the user what's inside:

```bash
curl -s "https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail?pr=ucpro&fr=pc&pwd_id=PWD_ID&stoken=STOKEN_URL_ENCODED&pdir_fid=0&force=0&_page=1&_size=50&_sort=file_type:asc,updated_at:desc" \
  -H "user-agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
```

**Important:** The `stoken` value must be URL-encoded (it contains `+`, `/`, `=` characters). Use `urllib.parse.urlencode()` in Python or `--data-urlencode` with curl.

Extract from response:
- `data.list[].file_name` — file/folder name
- `data.list[].size` — file size in bytes (0 for folders)
- `data.list[].dir` — `true` if folder, `false` if file (more reliable than `file_type`)
- `data.list[].fid` — file/folder ID (use as `pdir_fid` to browse into subfolders)
- `data.list[].include_items` — number of items in folder

To browse into a subfolder, call the same endpoint with `pdir_fid` set to the folder's `fid`.

### Step 4: Present Results to User

Format results clearly:

```
搜索 "三体" 找到 X 个有效夸克网盘资源：

1. [有效] 三体全集 4K — 3个文件，来源: plugin:libvio
   https://pan.quark.cn/s/abc123
2. [有效] 三体 第一季 1080P — 1个文件夹(42项)，来源: channel:yunpanx
   https://pan.quark.cn/s/def456
3. [已失效] 三体合集 — 分享已过期
```

Ask the user which one to save.

### Step 5: Trigger Quark APP Save

When the user selects a resource, trigger the Quark APP to open the share link:

```bash
# Method 1: via desktop_share_visiting (preferred, opens share view window)
curl -s "http://localhost:9128/desktop_share_visiting?pwd_id=PWD_ID_HERE"

# Method 2: via desktop_caller with deeplink (alternative)
curl -s "http://localhost:9128/desktop_caller?deeplink=qkclouddrive%3A%2F%2Fsave%3Furl%3Dhttps%253A%252F%252Fpan.quark.cn%252Fs%252FPWD_ID_HERE"

# Method 3: fallback — open share page in browser
open "https://pan.quark.cn/s/PWD_ID_HERE"
```

After triggering via Method 1 or 2, inform the user:

> 已在夸克 APP 中打开分享链接窗口。**注意：弹出的窗口可能很小，请留意任务栏/Dock 上的夸克图标。** 在 APP 中点击「保存到网盘」按钮完成保存。保存后文件会出现在你的网盘中，可以直接在 APP 中下载到本地。

If the user reports no window appeared, fall back to Method 3 (opens browser share page where the user can click save).

### Step 6: Batch Processing

When the user wants to search and save multiple resources, loop through steps 1-5 for each keyword. Validate all links first, then trigger APP saves sequentially with a brief delay between each.

## Error Handling

| Error | Detection | Resolution |
|-------|-----------|------------|
| Quark APP not running | `localhost:9128` connection refused | Tell user to launch Quark APP |
| Not logged in | `desktop_info` returns `isLogin: false` | Tell user to log in |
| No search results | PanSou returns `total: 0` | Suggest different keywords |
| All links invalid | All validation checks fail | Try alternative drive types or different keywords |
| Share has password | Token API returns password required error | Ask user for the extraction code (提取码) |

## Health Check Endpoint

To check PanSou API status and fetch the required `channels`/`plugins` lists for search:

```bash
curl -s "https://s.panhunt.com/api/health"
```

Returns: `channels` (array of Telegram channel names), `plugins` (array of website plugin names), `channels_count`, `plugin_count`, `status`. Join the arrays with commas to use as search parameters.

## Important Notes

- All share validation APIs are public (no authentication needed)
- The local Quark APP API at `localhost:9128` requires no authentication
- The actual save-to-drive operation happens in the Quark APP UI (user clicks one button)
- Download-to-local is handled by Quark APP's built-in download manager
- Do not attempt to call Quark's authenticated remote APIs directly
