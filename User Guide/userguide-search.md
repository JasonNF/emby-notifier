## /search 使用说明 🔎

### 功能概览
- 在 Emby 内搜索 **电影/剧集**；支持“名称 + 可选年份（4位）”。  
- 结果支持分页；点击条目可查看**详情卡片**（可包含海报、剧情、规格、入库时间、更新进度、在服务器中查看按钮等）。  
- 若 Emby 直搜无结果，自动尝试 **TMDB 别名后备搜索** 再匹配 Emby，提高命中率。

---

### 使用前提
- 无特别权限要求；任意授权用户可用（但详情里“在服务器中查看”需管理员配置 `emby.remote_url`）。  

---

### 命令格式
- 方式一（推荐）：`/search 片名 [年份]`  
  - 例：`/search 让子弹飞 2010`、`/search 凡人修仙传 2025`
- 方式二（交互）：
  1. 发送 `/search`（不带参数）；  
  2. 机器人会提示“请提供搜索关键词”，**在群组必须直接回复该条提示消息** 输入“片名 [年份]”。

---

### 操作步骤（超详细）
1. **发起搜索**：按“命令格式”选择方式一或方式二。  
2. **查看结果列表**：  
   - 每页最多 10 项；显示为“序号. 标题 (年份) | 分类（可选）”。  
   - 是否展示“分类”取决于开关：`settings.content_settings.search_display.show_media_type_in_list`。  
3. **翻页**：点击 `◀️ 上一页` / `下一页 ▶️`。  
4. **查看详情**：点击任一条目，机器人发送详情卡片：  
   - **电影**：可显示（按开关决定）海报、剧情、视频/音频规格、入库时间、在服务器中查看按钮。  
   - **剧集**：可显示海报、剧情、“各季规格”（抽样首集获取流信息）、“已更新至 第 S/E”（可选带 TMDB 链接）、入库时间、“更新进度”（对比 TMDB 季信息）、在服务器中查看按钮。  
5. **消息清理**：  
   - 列表/详情通常会设置自动删除时间以减少刷屏；  
   - 带图卡片可能保留更久，取决于你的自动删除设置。

---

### 相关设置开关（路径）
- 列表是否显示分类：`settings.content_settings.search_display.show_media_type_in_list`  
- 电影详情：`settings.content_settings.search_display.movie.*`  
  - `show_poster`、`title_has_tmdb_link`、`show_type`、`show_category`、`show_overview`、`show_video_spec`、`show_audio_spec`、`show_added_time`、`show_view_on_server_button`
- 剧集详情：`settings.content_settings.search_display.series.*`  
  - 基本项同电影；  
  - “各季规格”：`season_specs.show_video_spec`、`season_specs.show_audio_spec`  
  - “更新进度”：`update_progress.show_latest_episode`、`latest_episode_has_tmdb_link`、`show_overview`、`show_added_time`、`show_progress_status`

---

### 搜索技巧
- **加年份更精准**：例如 `海王 2018` 能减少同名误匹配。  
- **别名/本地标题不同**：机器人会用 TMDB 结果再回搜 Emby，提高命中率。  
- **只搜到剧集/电影之一**：尝试去掉年份或换另一个常见译名。

---

### 常见问题 & 排错
- **群组里没有响应**：请务必**回复机器人那条提示消息**提交关键词。  
- **没有任何结果**：确认目标是否已入库 Emby，或换关键词/加年份重试。  
- **“在服务器中查看”没出现**：需配置 `emby.remote_url` 并开启展示按钮。
