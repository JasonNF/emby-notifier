# Emby Telegram Notification Bot

📺 一个为 Emby 媒体服务器打造的高度可定制 Telegram Bot，支持事件通知、互动搜索、播放监控和自动消息撤回等功能。使用 Python 编写，适合通过 Docker 快速部署。

---

## ✨ 项目亮点

- 🔔 **实时事件推送**：播放、暂停、停止、新增、删除媒体等事件自动发送至 Telegram 群组或频道  
- 🎬 **详细节目信息**：自动解析 TMDB、展示封面图、分辨率、语言、播放进度、IP归属地等  
- 🔍 **互动式节目搜索**：支持分页展示、剧集各季码率/音轨、更新状态查询等  
- ✅ **权限控制**：支持限制群组使用、仅管理员可执行部分命令  
- ♻️ **自动消息撤回**：除新增节目外的所有消息及命令响应将在 60 秒后自动删除  
- 📤 **主动控制播放状态**：管理员可远程终止会话、群发消息、查看所有在线播放情况  
- 🌐 **多语言支持**：音轨语言自动翻译为中文，IP 归属地信息准确标注

---

## 📦 功能总览

| 类型         | 功能描述 |
|--------------|----------|
| 播放通知     | 播放开始/暂停/停止事件自动推送至 Telegram |
| 媒体库变动   | 新增/删除媒体自动通知，支持封面图、分辨率、总集数等展示 |
| 播放状态查看 | `/status` 命令查看当前所有会话，支持远程终止、群发消息 |
| 节目搜索     | `/search [关键词 年份]` 支持分页展示、获取剧集各季规格、更新状态等 |
| 消息控制     | 除新增节目外所有命令/互动消息自动在 60 秒后删除 |
| 权限限制     | 限定群组使用、管理员专属命令，防止滥用 |
| 多语言支持   | 音轨语言代码自动转中文，IP地址归属地识别 |

---

## 🚀 快速部署（Docker）

建议通过 Docker 部署：

```bash
docker run -d \
  -v /your/local/config:/config \
  -p 8080:8080 \
  --restart=always \
  xpisce/emby-notifier:latest
```

- `/config/config.yaml`：挂载配置目录
- `8080`：Webhook 监听端口

---

## ⚙️ 配置文件说明（config.yaml）

```yaml
telegram:
  token: "123456:ABCDEF"  # Telegram Bot Token
  chat_id: "-100xxxxxxxx" # 默认通知目标（私聊机器人/群组/频道 ID）
  new_library_channel_id: "-100xxxxxxxx" # 媒体新增推送目标（如为频道）

tmdb:
  api_token: "your_tmdb_token"

proxy:
  http_proxy: "http://127.0.0.1:7890" # 代理服务器地址（HTTP协议）

emby:
  server_url: "http://192.168.1.100:8096"  # Emby服务器的内网访问地址
  remote_url: "https://emby.yourdomain.com"  # Emby服务器的外网访问地址
  api_key: "emby_api_key"  
  user_id: "xxxxxxxx"  # 管理员用户的USER ID

settings:
  timezone: "Asia/Shanghai"
  debounce_seconds: 10
  media_base_path: "/media"  # 媒体文件所在的目录，比如“/media/国产剧/凡人修仙传 (2025)”就填写为/media
  poster_cache_ttl_days: 30
  allowed_group_id: "-100xxxxxxxx"  # 可选：用于限制机器人仅能被该群内成员使用
  notification_events:             # 可开关各类事件通知
    playback.start: true
    playback.pause: true
    playback.stop: true
    library.new: true
    library.deleted: true
```

---

## 🔧 可用命令列表（Telegram）

| 命令               | 描述                                      | 权限要求       |
|--------------------|-------------------------------------------|----------------|
| `/search`          | 关键词节目搜索，支持剧集、电影           | 所有人         |
| `/status`          | 当前在线播放状态，支持远程终止、发送/群发消息     | 管理员         |
| `/notify_settings` | 各类事件通知开关设置                     | 管理员         |

---

## 📎 使用示例

### 搜索节目：

```
/search 流浪地球
```

或仅输入关键词后等待机器人提示，再回复节目名：

> 请提供您想搜索的节目名称（可选年份）。例如：流浪地球 或 凡人修仙传 2025

---

### 播放通知示例：

```
▶️ 开始播放电影 [流浪地球2 (2023)](https://www.themoviedb.org/movie/...)
用户：张三  
设备：NVIDIA Shield  
位置：广州 广东省 中国移动  
进度：12.5% (00:15:30 / 02:00:00)  
分辨率：1920x1080  
时间：2025-08-05 13:05:33
```

---

## 📂 缓存与存储

- `/config/cache/poster_cache.json`：TMDB 封面缓存
- `/config/cache/languages.json`：音轨语言映射表（可选）

---

## 🛠 注意事项

- **Emby `user_id` 必须填写**，否则部分 API 将报错（404 Not Found）  
- 请将机器人添加为群组成员，并确保其具备 **删除消息** 和 **管理消息** 权限  
- 若配置了 `allowed_group_id`，则机器人仅响应该群成员的命令

---


## 📜 License

MIT License  
本项目仅用于个人学习、交流，请勿用于商业用途。

---

欢迎 Star ⭐ / Fork 🍴，有问题欢迎提 Issue 或 PR 🙌
