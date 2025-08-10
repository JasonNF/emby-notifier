## /settings 使用说明 ⚙️

### 功能概览
- 进入 **交互式设置菜单**，点按“✅/❌”即可开/关对应功能项；修改立即生效并写入 `/config/config.yaml`。
- 覆盖：通知是否发送到群/频道/私聊、通知卡片展示内容（海报/剧情/规格/按钮/时间戳等）、自动删除策略等。

---

### 使用前提
- 仅 **超级管理员**（`ADMIN_USER_ID`）可用。  
- 容器/程序需对 `/config` 目录有写权限，否则无法保存配置。

---

### 命令格式
- 直接发送：`/settings`

---

### 操作步骤（超详细）
1. **进入主菜单**：发送 `/settings` 后会收到“⚙️ 主菜单”。  
2. **浏览分组**（常见分组说明）：  
   - **推送内容设置**  
     - **新增节目通知内容设置**：控制“新增节目”卡片是否显示海报、节目详情、剧情、节目类型、视频/音频规格、时间戳、**在服务器中查看**按钮等。  
     - **观看状态反馈内容设置**：控制 `/status` 卡片是否显示播放器/设备/位置/剧情/按钮等。  
     - **播放行为推送内容设置**：控制开始/暂停/停止播放推送的内容项。  
     - **删除节目通知内容设置**：控制“删除节目”卡片是否显示海报、详情、剧情、节目类型、删除时间等。  
     - **搜索结果展示内容设置**：控制 `/search` 结果列表与详情的显示项（电影/剧集分别配置）。  
   - **通知管理**：是否向群组/频道/私聊推送 `新增节目`、`播放开始/暂停/停止`、`删除节目`。  
   - **自动删除消息设置**：按“新增节目/删除节目/播放状态”分别控制在 群组/频道/私聊 的自动删除行为。  
3. **进入子菜单**：点击某个分组（如“新增节目通知内容设置”）进入；  
4. **切换开关**：看到某项如“展示海报”前有 `✅/❌` 标记，点击即切换并保存到 `config.yaml`；  
5. **导航**：  
   - `◀️ 返回上一级` 回到上层菜单；  
   - `☑️ 完成` 关闭设置菜单（机器人会提示“设置菜单已关闭”）。

---

### 关键设置项（示例路径）
- 新增节目卡片：`settings.content_settings.new_library_notification.*`  
  - `show_poster`、`show_media_detail`、`media_detail_has_tmdb_link`、`show_overview`、`show_media_type`、`show_video_spec`、`show_audio_spec`、`show_timestamp`、`show_view_on_server_button`
- 观看状态卡片：`settings.content_settings.status_feedback.*`（同上扩展：`show_player`、`show_device`、`show_location`、“停止/群发/停止所有”按钮开关等）  
- 播放行为推送：`settings.content_settings.playback_action.*`  
- 删除节目卡片：`settings.content_settings.library_deleted_notification.*`  
- 搜索结果展示：  
  - 列表是否显示分类：`settings.content_settings.search_display.show_media_type_in_list`  
  - 电影详情：`settings.content_settings.search_display.movie.*`  
  - 剧集详情：`settings.content_settings.search_display.series.*`（含“各季规格”“更新进度”子项）
- 通知是否发送：`settings.notification_management.*`  
- 自动删除：`settings.auto_delete_settings.*`

---

### 常见问题 & 排错
- **开关点击没变化**：检查 `/config` 是否可写、容器权限是否正确。  
- **按钮不显示**：确认对应“展示按钮”的开关已开启，且相关外部配置（如 `emby.remote_url`）已填写。  
- **改完未生效**：通常立即生效；若无效，查看日志是否有读取/保存配置错误。
