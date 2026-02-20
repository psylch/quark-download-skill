# quark-download-skill

[English](README.md)

一个 [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 技能，用于搜索、验证和保存网盘资源。结合 [PanSou 盘搜](https://s.panhunt.com/) 聚合 API（90+ Telegram 频道、60+ 网站插件）与本地夸克桌面端，实现从关键词搜索 → 链接验证 → 一键保存的完整流程。

| 步骤 | 做了什么 | 使用的 API |
|------|---------|-----------|
| **搜索** | 通过 PanSou 搜索 6 种网盘的资源链接 | `s.panhunt.com/api/search`（参数：`kw`） |
| **验证** | 检查每个分享链接是否有效（未删除/过期） | `drive-pc.quark.cn` 公开 API |
| **详情** | 获取文件名、大小、文件夹内容 | `drive-pc.quark.cn` 公开 API |
| **保存** | 在夸克 APP 中打开分享链接，一键保存 | `localhost:9128` 本地 API |

## 安装

### 一键安装全部媒体技能（推荐）

本技能是 [media-master](https://github.com/psylch/media-master) 的一部分，可一次安装音乐、网盘资源、书籍三个下载技能：

```bash
npx skills add psylch/media-master -g -y
```

### 仅安装本技能

```bash
npx skills add psylch/quark-download-skill -g -y
```

### 通过 Claude Code Plugin Marketplace

```shell
/plugin marketplace add psylch/quark-download-skill
/plugin install quark-download@psylch-quark-download-skill
```

安装后需重启 Claude Code。

## 前置条件

- **夸克桌面端** 已安装并运行（[quark.cn](https://www.quark.cn/)）
- **已登录** 夸克账号（建议开通会员以获取完整下载速度）
- **Claude Code** 或任何支持 [skills.sh](https://skills.sh/) 的 agent

## 使用方法

在 Claude Code 中使用以下触发短语：

```
搜资源 三体
找片 星际穿越
帮我下载 xxx
搜一下网盘资源
quark search interstellar
```

## 工作原理

1. **环境检查** — 通过 `localhost:9128/desktop_info` 确认夸克 APP 在运行且已登录
2. **搜索** — 查询 PanSou API，优先展示夸克网盘结果
3. **验证** — 通过公开的 token API 检测每个分享链接是否有效（无需登录）
4. **展示** — 显示有效结果及文件详情，标记失效/过期链接
5. **保存** — 触发夸克 APP 打开选中的分享链接窗口（注意：弹窗可能较小）

> **说明：** 实际的「保存到网盘」和「下载到本地」在夸克 APP 界面操作——用户只需点一个按钮。这是有意为之，避免逆向调用需要登录验证的远程 API。

## 支持的网盘类型

PanSou 返回多种网盘的结果，Skill 优先展示夸克结果，同时也报告其他网盘：

| 类型 | 网盘 |
|------|------|
| `quark` | 夸克网盘 — **优先** |
| `aliyun` | 阿里云盘 |
| `baidu` | 百度网盘 |
| `115` | 115 网盘 |
| `pikpak` | PikPak |
| `uc` | UC 网盘 |

## 错误处理

| 错误 | 检测方式 | 解决方法 |
|------|---------|---------|
| APP 未运行 | `localhost:9128` 连接被拒 | 启动夸克 APP |
| 未登录 | `desktop_info` 返回 `isLogin: false` | 登录夸克账号 |
| 无搜索结果 | PanSou 返回 `total: 0` | 换个关键词试试 |
| 全部链接失效 | 所有验证检查失败 | 换关键词或尝试其他网盘类型 |
| 分享有密码 | Token API 返回需要密码 | 询问用户提取码 |

## 文件结构

```
quark-search-skill/
├── .claude-plugin/
│   ├── marketplace.json          # 插件注册表
│   └── plugin.json               # 插件清单
├── skills/
│   └── quark-search/
│       ├── SKILL.md              # 主 Skill 定义
│       └── scripts/
│           └── quark_search.py   # CLI 脚本（搜索、验证、详情、保存）
├── README.md
├── README.zh.md
└── LICENSE
```

## 许可证

MIT
