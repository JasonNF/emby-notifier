# Emby Telegram Notification Bot

📺 一个为 Emby 媒体服务器打造的全功能 Telegram Bot，支持媒体事件推送、搜索交互、播放状态控制、精细化权限与展示设置，并具备自动消息删除功能。适用于家庭服务器、媒体分享群组等多种场景，支持 Docker 快速部署。

---

## ✨ 项目亮点

- 🔔 **精准事件推送**：支持播放开始、暂停、停止、新增、删除媒体事件，推送内容可按需展示信息  
- 🎬 **内容可视化控制**：通过配置可灵活显示节目封面、标题、TMDB链接、音视频规格、播放进度等信息  
- 🔍 **交互式搜索功能**：支持搜索关键词分页展示，剧集可展示各季码率、音轨、更新进度与状态  
- ✅ **播放状态监控与远程控制**：通过 `/status` 命令可实时查看播放状态，并可终止会话或群发消息  
- 🧩 **权限控制**：可设置机器人仅在指定群组响应，部分命令仅管理员可执行  
- ♻️ **自动消息撤回**：播放通知、搜索响应等均可设置在 60 秒后自动删除，保持聊天清爽  
- 🌐 **多语言与IP识别**：音轨语言自动翻译为中文，IP 地理归属地信息清晰展示  

---

## 📦 功能概览

| 类别         | 功能说明 |
|--------------|----------|
| 播放事件通知 | 支持播放开始、暂停、停止等事件自动推送，可展示播放进度、用户信息、设备、IP归属地等 |
| 媒体库更新   | 新增/删除节目自动通知，可选展示封面、音视频规格、剧情简介、入库时间等 |
| 播放状态控制 | `/status` 查看所有在线用户，支持发送消息、群发消息、远程终止单人/所有会话 |
| 节目搜索     | `/search` 支持关键词搜索节目，展示剧集更新进度、音视频规格、TMDB链接等 |
| 内容配置     | 通过 `content_settings` 精细控制每类通知的展示内容 |
| 通知管理     | 通过 `notification_management` 控制哪些事件启用通知，推送到哪类聊天 |
| 自动撤回     | 可配置哪些类型通知在发送后定时撤回，避免消息冗余 |
| 权限与安全   | 支持限制机器人只在特定群组响应命令，部分命令仅管理员可用 |

---

## ⚙️ 配置文件说明（config.yaml）

配置结构分为四大类：

1. `emby`: Emby 服务器信息  
2. `telegram`: Bot Token、目标聊天 ID、管理员 ID  
3. `settings`: 展示内容、事件开关、消息撤回规则等  
4. `tmdb/proxy`: 第三方服务配置

<details>
<summary>点击展开完整配置示例（config.yaml）</summary>

```yaml
# 此处粘贴你提供的完整 config.yaml 示例
（建议你将该段替换为缩略版，并单独将完整内容放入 docs/config.example.yaml）
```

</details>

---

## 🚀 快速部署（Docker）

```bash
docker run -d \
  -v /your/config/path:/config \
  -p 8080:8080 \
  --restart=always \
  xpisce/emby-notifier:latest
```

- 配置文件路径：`/config/config.yaml`  
- 缓存目录：`/config/cache/`  
- 默认监听端口：8080  

---

## 🔧 命令说明（Telegram）

| 命令       | 描述                                    | 权限要求     |
|------------|-----------------------------------------|--------------|
| `/search`  | 搜索节目关键词，展示剧集更新状态与规格 | 所有人       |
| `/status`  | 查看当前播放会话，支持远程控制          | 管理员       |
| `/settings`| 打开通知展示与开关设置交互菜单          | 管理员       |

---

## 📎 示例通知格式

### 播放通知示例：

```
▶️ 开始播放剧集 [凡人修仙传 (2025) 第1集](https://www.themoviedb.org/...)
用户：张三  
设备：Android TV  
位置：广州 广东省 电信  
进度：27.1% (00:10:00 / 00:36:55)  
时间：2025-08-07 18:23:12
```

---

## 🖼️ 截图演示

<p align="center">
  <img src="./images/new_library_notify.png" width="320" alt="新增节目通知">
</p>

<p align="center">
  <img src="./images/status.png" width="320" alt="播放状态反馈">
</p>

<p align="center">
  <img src="./images/search_tv_series.png" width="320" alt="搜索剧集">
</p>

<p align="center">
  <img src="./images/search_movie.png" width="320" alt="搜索电影">
</p>

<p align="center">
  <img src="./images/notify_settings.png" width="320" alt="通知设置面板">
</p>

---

## 🛠 注意事项

- `emby.user_id` 为必填项，否则节目信息将无法正确解析  
- 请授予机器人在群组中的消息管理、删除权限  
- 若启用了 `allowed_group_id`，则机器人仅对该群组内消息作出响应  

---

## 📜 License

MIT License  
本项目仅供学习交流使用，禁止商业用途。

---

## 🔗 项目地址

- 📦 GitHub: [https://github.com/xpisce/emby-notifier](https://github.com/xpisce/emby-notifier)
- 🐳 Docker Hub: [https://hub.docker.com/r/xpisce/emby-notifier](https://hub.docker.com/r/xpisce/emby-notifier)

---

欢迎 Star ⭐ / Fork 🍴，如有问题欢迎提 Issue 或 PR 🙌
