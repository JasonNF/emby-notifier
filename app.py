# -*- coding: utf-8 -*-
import os
import json
import time
import yaml
import requests
import re
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid
from functools import reduce
import operator


POSTER_CACHE = {}
CACHE_DIR = '/config/cache'
POSTER_CACHE_PATH = os.path.join(CACHE_DIR, 'poster_cache.json')
CONFIG_PATH = '/config/config.yaml'
CONFIG = {}
DEFAULT_SETTINGS = {}
TOGGLE_INDEX_TO_KEY = {}
TOGGLE_KEY_TO_INFO = {}
LANG_MAP = {}
LANG_MAP_PATH = os.path.join(CACHE_DIR, 'languages.json')
ADMIN_CACHE = {}
GROUP_MEMBER_CACHE = {}
SEARCH_RESULTS_CACHE = {}
recent_playback_notifications = {}
user_context = {}
user_search_state = {}


SETTINGS_MENU_STRUCTURE = {
    'root': {'label': '⚙️ 主菜单', 'children': ['content_settings', 'notification_management', 'auto_delete_settings']},
    'content_settings': {'label': '推送内容设置', 'parent': 'root', 'children': ['status_feedback', 'playback_action', 'library_deleted_content', 'new_library_content_settings', 'search_display']},
    'new_library_content_settings': {'label': '新增节目通知内容设置', 'parent': 'content_settings', 'children': [
        'new_library_show_poster', 'new_library_show_media_detail', 'new_library_media_detail_has_tmdb_link', 'new_library_show_overview', 'new_library_show_media_type',
        'new_library_show_video_spec', 'new_library_show_audio_spec', 'new_library_show_timestamp', 'new_library_show_view_on_server_button'
    ]},
    'new_library_show_poster': {'label': '展示海报', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_poster', 'default': True},
    'new_library_show_media_detail': {'label': '展示节目详情', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_media_detail', 'default': True},
    'new_library_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.media_detail_has_tmdb_link', 'default': True},
    'new_library_show_overview': {'label': '展示剧情', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_overview', 'default': True},
    'new_library_show_media_type': {'label': '展示节目类型', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_media_type', 'default': True},
    'new_library_show_video_spec': {'label': '展示视频规格', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_video_spec', 'default': False},
    'new_library_show_audio_spec': {'label': '展示音频规格', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_audio_spec', 'default': False},
    'new_library_show_timestamp': {'label': '展示更新时间', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_timestamp', 'default': True},
    'new_library_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'new_library_content_settings', 'config_path': 'settings.content_settings.new_library_notification.show_view_on_server_button', 'default': True},
    'status_feedback': {'label': '观看状态反馈内容设置', 'parent': 'content_settings', 'children': [
        'status_show_poster', 'status_show_player', 'status_show_device', 'status_show_location', 'status_show_media_detail', 'status_media_detail_has_tmdb_link', 'status_show_media_type', 'status_show_overview', 'status_show_timestamp',
        'status_show_view_on_server_button', 'status_show_terminate_session_button', 'status_show_send_message_button', 'status_show_broadcast_button', 'status_show_terminate_all_button'
    ]},
    'status_show_poster': {'label': '展示海报', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_poster', 'default': True},
    'status_show_player': {'label': '展示播放器', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_player', 'default': True},
    'status_show_device': {'label': '展示设备', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_device', 'default': True},
    'status_show_location': {'label': '展示位置信息', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_location', 'default': True},
    'status_show_media_detail': {'label': '展示节目详情', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_media_detail', 'default': True},
    'status_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.media_detail_has_tmdb_link', 'default': True},
    'status_show_media_type': {'label': '展示节目类型', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_media_type', 'default': True},
    'status_show_overview': {'label': '展示剧情', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_overview', 'default': False},
    'status_show_timestamp': {'label': '展示时间', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_timestamp', 'default': True},
    'status_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_view_on_server_button', 'default': True},
    'status_show_terminate_session_button': {'label': '展示“终止会话”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_terminate_session_button', 'default': True},
    'status_show_send_message_button': {'label': '展示“发送消息”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_send_message_button', 'default': True},
    'status_show_broadcast_button': {'label': '展示“群发消息”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_broadcast_button', 'default': True},
    'status_show_terminate_all_button': {'label': '展示“终止所有”按钮', 'parent': 'status_feedback', 'config_path': 'settings.content_settings.status_feedback.show_terminate_all_button', 'default': True},
    'playback_action': {'label': '播放行为推送内容设置', 'parent': 'content_settings', 'children': [
        'playback_show_poster', 'playback_show_media_detail', 'playback_media_detail_has_tmdb_link', 'playback_show_user', 'playback_show_player', 'playback_show_device', 'playback_show_location', 'playback_show_progress',
        'playback_show_video_spec', 'playback_show_audio_spec', 'playback_show_media_type', 'playback_show_overview', 'playback_show_timestamp', 'playback_show_view_on_server_button'
    ]},
    'playback_show_poster': {'label': '展示海报', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_poster', 'default': True},
    'playback_show_media_detail': {'label': '展示节目详情', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_media_detail', 'default': True},
    'playback_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.media_detail_has_tmdb_link', 'default': True},
    'playback_show_user': {'label': '展示用户名', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_user', 'default': True},
    'playback_show_player': {'label': '展示播放器', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_player', 'default': True},
    'playback_show_device': {'label': '展示设备', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_device', 'default': True},
    'playback_show_location': {'label': '展示位置信息', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_location', 'default': True},
    'playback_show_progress': {'label': '展示播放进度', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_progress', 'default': True},
    'playback_show_video_spec': {'label': '展示视频规格', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_video_spec', 'default': False},
    'playback_show_audio_spec': {'label': '展示音频规格', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_audio_spec', 'default': False},
    'playback_show_media_type': {'label': '展示节目类型', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_media_type', 'default': True},
    'playback_show_overview': {'label': '展示剧情', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_overview', 'default': True},
    'playback_show_timestamp': {'label': '展示时间', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_timestamp', 'default': True},
    'playback_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'playback_action', 'config_path': 'settings.content_settings.playback_action.show_view_on_server_button', 'default': True},
    'library_deleted_content': {'label': '删除节目通知内容设置', 'parent': 'content_settings', 'children': [
        'deleted_show_poster', 'deleted_show_media_detail', 'deleted_media_detail_has_tmdb_link', 'deleted_show_overview', 'deleted_show_media_type', 'deleted_show_timestamp'
    ]},
    'deleted_show_poster': {'label': '展示海报', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_poster', 'default': True},
    'deleted_show_media_detail': {'label': '展示节目详情', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_media_detail', 'default': True},
    'deleted_media_detail_has_tmdb_link': {'label': '节目详情添加TMDB链接', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.media_detail_has_tmdb_link', 'default': True},
    'deleted_show_overview': {'label': '展示剧情', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_overview', 'default': True},
    'deleted_show_media_type': {'label': '展示节目类型', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_media_type', 'default': True},
    'deleted_show_timestamp': {'label': '展示删除时间', 'parent': 'library_deleted_content', 'config_path': 'settings.content_settings.library_deleted_notification.show_timestamp', 'default': True},
    'search_display': {'label': '搜索结果展示内容设置', 'parent': 'content_settings', 'children': ['search_show_media_type_in_list', 'search_movie', 'search_series']},
    'search_show_media_type_in_list': {'label': '搜索结果列表展示节目分类', 'parent': 'search_display', 'config_path': 'settings.content_settings.search_display.show_media_type_in_list', 'default': True},
    'search_movie': {'label': '电影展示设置', 'parent': 'search_display', 'children': [
        'movie_show_poster', 'movie_title_has_tmdb_link', 'movie_show_type', 'movie_show_category', 'movie_show_overview', 'movie_show_video_spec', 'movie_show_audio_spec', 'movie_show_added_time', 'movie_show_view_on_server_button'
    ]},
    'search_series': {'label': '剧集展示设置', 'parent': 'search_display', 'children': [
        'series_show_poster', 'series_title_has_tmdb_link', 'series_show_type', 'series_show_category', 'series_show_overview', 'series_season_specs', 'series_update_progress', 'series_show_view_on_server_button'
    ]},
    'movie_show_poster': {'label': '展示海报', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_poster', 'default': True},
    'movie_title_has_tmdb_link': {'label': '电影名称添加TMDB链接', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.title_has_tmdb_link', 'default': True},
    'movie_show_type': {'label': '展示类型', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_type', 'default': True},
    'movie_show_category': {'label': '展示分类', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_category', 'default': True},
    'movie_show_overview': {'label': '展示剧情', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_overview', 'default': True},
    'movie_show_video_spec': {'label': '展示视频规格', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_video_spec', 'default': True},
    'movie_show_audio_spec': {'label': '展示音频规格', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_audio_spec', 'default': True},
    'movie_show_added_time': {'label': '展示入库时间', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_added_time', 'default': True},
    'movie_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'search_movie', 'config_path': 'settings.content_settings.search_display.movie.show_view_on_server_button', 'default': True},
    'series_show_poster': {'label': '展示海报', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_poster', 'default': True},
    'series_title_has_tmdb_link': {'label': '剧目名称添加TMDB链接', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.title_has_tmdb_link', 'default': True},
    'series_show_type': {'label': '展示类型', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_type', 'default': True},
    'series_show_category': {'label': '展示分类', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_category', 'default': True},
    'series_show_overview': {'label': '展示剧情', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_overview', 'default': True},
    'series_show_view_on_server_button': {'label': '展示“在服务器中查看按钮”', 'parent': 'search_series', 'config_path': 'settings.content_settings.search_display.series.show_view_on_server_button', 'default': True},
    'series_season_specs': {'label': '各季规格', 'parent': 'search_series', 'children': ['series_season_show_video_spec', 'series_season_show_audio_spec']},
    'series_season_show_video_spec': {'label': '展示视频规格', 'parent': 'series_season_specs', 'config_path': 'settings.content_settings.search_display.series.season_specs.show_video_spec', 'default': True},
    'series_season_show_audio_spec': {'label': '展示各季音频规格', 'parent': 'series_season_specs', 'config_path': 'settings.content_settings.search_display.series.season_specs.show_audio_spec', 'default': True},
    'series_update_progress': {'label': '更新进度', 'parent': 'search_series', 'children': ['series_progress_show_latest_episode', 'series_progress_latest_episode_has_tmdb_link', 'series_progress_show_overview', 'series_progress_show_added_time', 'series_progress_show_progress_status']},
    'series_progress_show_latest_episode': {'label': '展示已更新至', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_latest_episode', 'default': True},
    'series_progress_latest_episode_has_tmdb_link': {'label': '已更新至添加TMDB链接', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.latest_episode_has_tmdb_link', 'default': True},
    'series_progress_show_overview': {'label': '展示剧情', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_overview', 'default': False},
    'series_progress_show_added_time': {'label': '展示入库时间', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_added_time', 'default': True},
    'series_progress_show_progress_status': {'label': '展示更新进度', 'parent': 'series_update_progress', 'config_path': 'settings.content_settings.search_display.series.update_progress.show_progress_status', 'default': True},
    'notification_management': {'label': '通知管理', 'parent': 'root', 'children': ['notify_library_new', 'notify_playback_start', 'notify_playback_pause', 'notify_playback_stop', 'notify_library_deleted']},
    'notify_library_new': {'label': '新增节目', 'parent': 'notification_management', 'children': ['new_to_group', 'new_to_channel', 'new_to_private']},
    'new_to_group': {'label': '到群组', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_group', 'default': True},
    'new_to_channel': {'label': '到频道', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_channel', 'default': True},
    'new_to_private': {'label': '到私聊', 'parent': 'notify_library_new', 'config_path': 'settings.notification_management.library_new.to_private', 'default': False},
    'notify_playback_start': {'label': '开始/继续播放', 'parent': 'notification_management', 'config_path': 'settings.notification_management.playback_start', 'default': True},
    'notify_playback_pause': {'label': '暂停播放', 'parent': 'notification_management', 'config_path': 'settings.notification_management.playback_pause', 'default': False},
    'notify_playback_stop': {'label': '停止播放', 'parent': 'notification_management', 'config_path': 'settings.notification_management.playback_stop', 'default': True},
    'notify_library_deleted': {'label': '删除节目', 'parent': 'notification_management', 'config_path': 'settings.notification_management.library_deleted', 'default': True},
    'auto_delete_settings': {'label': '自动删除消息设置', 'parent': 'root', 'children': ['delete_new_library', 'delete_library_deleted', 'delete_playback_status']},
    'delete_new_library': {'label': '新增节目通知消息', 'parent': 'auto_delete_settings', 'children': ['delete_new_library_group', 'delete_new_library_channel', 'delete_new_library_private']},
    'delete_new_library_group': {'label': '到群组', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_group', 'default': False},
    'delete_new_library_channel': {'label': '到频道', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_channel', 'default': False},
    'delete_new_library_private': {'label': '到私聊', 'parent': 'delete_new_library', 'config_path': 'settings.auto_delete_settings.new_library.to_private', 'default': True},
    'delete_library_deleted': {'label': '删除节目通知消息', 'parent': 'auto_delete_settings', 'config_path': 'settings.auto_delete_settings.library_deleted', 'default': True},
    'delete_playback_status': {'label': '播放状态通知消息', 'parent': 'auto_delete_settings', 'children': ['delete_playback_start', 'delete_playback_pause', 'delete_playback_stop']},
    'delete_playback_start': {'label': '开始/继续播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_start', 'default': True},
    'delete_playback_pause': {'label': '暂停播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_pause', 'default': True},
    'delete_playback_stop': {'label': '停止播放通知消息', 'parent': 'delete_playback_status', 'config_path': 'settings.auto_delete_settings.playback_stop', 'default': True},
}

def build_toggle_maps():
    index = 0
    for key, node in SETTINGS_MENU_STRUCTURE.items():
        if 'config_path' in node:
            TOGGLE_INDEX_TO_KEY[index] = key
            TOGGLE_KEY_TO_INFO[key] = {
                'config_path': node['config_path'],
                'parent': node['parent']
            }
            SETTINGS_MENU_STRUCTURE[key]['index'] = index
            index += 1

def _build_default_settings():
    defaults = {}
    for node in SETTINGS_MENU_STRUCTURE.values():
        if 'config_path' in node:
            path = node['config_path']
            value = node['default']
            keys = path.split('.')
            d = defaults
            for k in keys[:-1]:
                d = d.setdefault(k, {})
            d[keys[-1]] = value
    return defaults

def get_setting(path_str):
    try:
        return reduce(operator.getitem, path_str.split('.'), CONFIG)
    except (KeyError, TypeError):
        try:
            return reduce(operator.getitem, path_str.split('.'), DEFAULT_SETTINGS)
        except (KeyError, TypeError):
            print(f"警告: 在用户配置和默认配置中都找不到键: {path_str}")
            return None

def set_setting(path_str, value):
    keys = path_str.split('.')
    d = CONFIG
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def merge_configs(user_config, default_config):
    if isinstance(user_config, dict) and isinstance(default_config, dict):
        merged = default_config.copy()
        for key, value in user_config.items():
            if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
                merged[key] = merge_configs(value, merged[key])
            else:
                merged[key] = value
        return merged
    return user_config

def load_config():
    global CONFIG
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            user_config = yaml.safe_load(f) or {}
        CONFIG = merge_configs(user_config, DEFAULT_SETTINGS)
    except FileNotFoundError:
        print(f"警告：配置文件 {CONFIG_PATH} 未找到。将使用内置的默认设置。")
        CONFIG = DEFAULT_SETTINGS
    except Exception as e:
        print(f"错误：读取或解析配置文件失败: {e}")
        exit(1)

def save_config():
    try:
        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(CONFIG, f, allow_unicode=True, sort_keys=False)
    except Exception as e:
        print(f"❌ 保存配置失败: {e}")

def load_language_map():
    global LANG_MAP
    fallback_map = {
        'eng': {'en': 'English', 'zh': '英语'}, 'jpn': {'en': 'Japanese', 'zh': '日语'},
        'chi': {'en': 'Chinese', 'zh': '中文'}, 'zho': {'en': 'Chinese', 'zh': '中文'},
        'kor': {'en': 'Korean', 'zh': '韩语'}, 'und': {'en': 'Undetermined', 'zh': '未知'},
        'mis': {'en': 'Multiple languages', 'zh': '多语言'}
    }
    if not os.path.exists(LANG_MAP_PATH):
        print(f"⚠️ 警告：语言配置文件 {LANG_MAP_PATH} 未找到，将使用内置的精简版语言列表。")
        LANG_MAP = fallback_map
        return
    try:
        with open(LANG_MAP_PATH, 'r', encoding='utf-8') as f:
            LANG_MAP = json.load(f)
    except Exception as e:
        print(f"❌ 加载语言配置文件失败: {e}，将使用内置的精简版语言列表。")
        LANG_MAP = fallback_map

def load_poster_cache():
    global POSTER_CACHE
    if not os.path.exists(POSTER_CACHE_PATH):
        POSTER_CACHE = {}
        return
    try:
        with open(POSTER_CACHE_PATH, 'r', encoding='utf-8') as f:
            POSTER_CACHE = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"❌ 加载海报缓存失败: {e}，将使用空缓存。")
        POSTER_CACHE = {}

def save_poster_cache():
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(POSTER_CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump(POSTER_CACHE, f, indent=4)
    except Exception as e:
        print(f"❌ 保存海报缓存失败: {e}")

DEFAULT_SETTINGS = _build_default_settings()
build_toggle_maps()
load_config()
load_language_map()
load_poster_cache()

TELEGRAM_TOKEN = CONFIG.get('telegram', {}).get('token')
ADMIN_USER_ID = CONFIG.get('telegram', {}).get('admin_user_id')
GROUP_ID = CONFIG.get('telegram', {}).get('group_id')
CHANNEL_ID = CONFIG.get('telegram', {}).get('channel_id')

TMDB_API_TOKEN = CONFIG.get('tmdb', {}).get('api_token')
HTTP_PROXY = CONFIG.get('proxy', {}).get('http_proxy')

TIMEZONE = ZoneInfo(get_setting('settings.timezone') or 'UTC')
PLAYBACK_DEBOUNCE_SECONDS = get_setting('settings.debounce_seconds') or 10
MEDIA_BASE_PATH = get_setting('settings.media_base_path')
POSTER_CACHE_TTL_DAYS = get_setting('settings.poster_cache_ttl_days') or 30

EMBY_SERVER_URL = CONFIG.get('emby', {}).get('server_url')
EMBY_API_KEY = CONFIG.get('emby', {}).get('api_key')
EMBY_USER_ID = CONFIG.get('emby', {}).get('user_id')
EMBY_REMOTE_URL = CONFIG.get('emby', {}).get('remote_url')
APP_SCHEME = CONFIG.get('emby', {}).get('app_scheme')
ALLOWED_GROUP_ID = GROUP_ID

if not TELEGRAM_TOKEN or not ADMIN_USER_ID:
    print("错误：TELEGRAM_TOKEN 或 ADMIN_USER_ID 未在 config.yaml 中正确设置")
    exit(1)

def make_request_with_retry(method, url, max_retries=3, retry_delay=1, **kwargs):
    api_name = "Unknown API"
    if "api.telegram.org" in url: api_name = "Telegram"
    elif "api.themoviedb.org" in url: api_name = "TMDB"
    elif "ip-api.com" in url: api_name = "IP Geolocation"
    elif EMBY_SERVER_URL and EMBY_SERVER_URL in url: api_name = "Emby"
    attempts = 0
    while attempts < max_retries:
        try:
            response = requests.request(method, url, **kwargs)
            if 200 <= response.status_code < 300:
                return response
            else:
                error_text = response.text
                if "message is not modified" in error_text:
                    print(f"INFO: Telegram 消息未被修改，无需操作。")
                    return None
                if "BUTTON_DATA_INVALID" in error_text:
                    print(f"ERROR: Telegram报告按钮数据无效。请检查回调数据长度是否超过64字节。")
                    return None
                print(f"❌ {api_name} API 请求失败 (第 {attempts + 1} 次)，URL: {url.split('?')[0]}, 状态码: {response.status_code}, 响应: {error_text}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {api_name} API 请求发生网络错误 (第 {attempts + 1} 次)，URL: {url.split('?')[0]}, 错误: {e}")
        attempts += 1
        if attempts < max_retries:
            time.sleep(retry_delay)
    print(f"❌ {api_name} API 请求失败，已达到最大重试次数 ({max_retries} 次)，URL: {url.split('?')[0]}")
    return None

def escape_markdown(text: str) -> str:
    if not text: return ""
    text = str(text)
    escape_chars = r'\_*[]()~>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', text)

def format_ticks_to_hms(ticks):
    if not isinstance(ticks, (int, float)) or ticks <= 0:
        return "00:00:00"
    seconds = ticks / 10_000_000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def get_program_type_from_path(path):
    if not MEDIA_BASE_PATH or not path or not path.startswith(MEDIA_BASE_PATH):
        return None
    relative_path = path[len(MEDIA_BASE_PATH):].lstrip('/')
    parts = relative_path.split('/')
    if parts and parts[0]:
        return parts[0]
    return None

def extract_year_from_path(path):
    if not path:
        return None
    match = re.search(r'\((\d{4})\)', path)
    if match:
        year = match.group(1)
        return year
    return None

def get_ip_geolocation(ip):
    if not ip or ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
        return "局域网"
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp&lang=zh-CN"
    response = make_request_with_retry('GET', url, timeout=5)
    if response and response.json().get('status') == 'success':
        data = response.json()
        isp_map = {
            'Chinanet': '中国电信', 'China Telecom': '中国电信', 'China Unicom': '中国联通', 'CHINA169': '中国联通',
            'CNC Group': '中国联通', 'China Netcom': '中国联通', 'China Mobile': '中国移动', 'China Broadcasting': '中国广电',
            'Tencent': '腾讯云', 'Alibaba': '阿里云'
        }
        isp_en = data.get('isp', '')
        isp = next((name for keyword, name in isp_map.items() if keyword.lower() in isp_en.lower()), isp_en)
        parts = [data.get('country', ''), data.get('regionName', ''), data.get('city', ''), isp]
        location = ' '.join([part for part in parts if part])
        return location if location.strip() else "未知位置"
    return "未知位置"

def search_tmdb_by_title(title, year=None, media_type='tv'):
    if not TMDB_API_TOKEN: return None
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    params = {'api_key': TMDB_API_TOKEN, 'query': title, 'language': 'zh-CN'}
    if year:
        params['first_air_date_year' if media_type == 'tv' else 'year'] = year
    url = f"https://api.themoviedb.org/3/search/{media_type}"
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        results = response.json().get('results', [])
        if not results:
            return None
        exact_match = next((item for item in results if (item.get('name') or item.get('title')) == title), None)
        if exact_match:
            return exact_match.get('id')
        else:
            results.sort(key=lambda x: (x.get('popularity', 0)), reverse=True)
            return results[0].get('id')
    print(f"❌ TMDB 搜索失败")
    return None

def get_media_details(item, user_id):
    details = {'poster_url': None, 'tmdb_link': None, 'year': None, 'tmdb_id': None}
    if not TMDB_API_TOKEN:
        return details
    item_type = item.get('Type')
    tmdb_id, api_type = None, None
    details['year'] = item.get('ProductionYear') or extract_year_from_path(item.get('Path'))
    if item_type == 'Movie':
        api_type = 'movie'
        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/movie/{tmdb_id}"
    elif item_type == 'Series':
        api_type = 'tv'
        tmdb_id = item.get('ProviderIds', {}).get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}"
    elif item_type == 'Episode':
        api_type = 'tv'
        series_provider_ids = item.get('SeriesProviderIds', {}) or item.get('Series', {}).get('ProviderIds', {})
        tmdb_id = series_provider_ids.get('Tmdb')
        if not tmdb_id and item.get('SeriesId'):
            series_id = item.get('SeriesId')
            request_user_id = user_id or EMBY_USER_ID
            url_part = f"/Users/{request_user_id}/Items/{series_id}" if request_user_id else f"/Items/{series_id}"
            url = f"{EMBY_SERVER_URL}{url_part}"
            response = make_request_with_retry('GET', url, params={'api_key': EMBY_API_KEY}, timeout=10)
            if response:
                tmdb_id = response.json().get('ProviderIds', {}).get('Tmdb')
        if not tmdb_id:
            tmdb_id = search_tmdb_by_title(item.get('SeriesName'), details.get('year'), media_type='tv')
        if tmdb_id:
            season_num, episode_num = item.get('ParentIndexNumber'), item.get('IndexNumber')
            if season_num is not None and episode_num is not None:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}/season/{season_num}/episode/{episode_num}"
            else:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}"
    if tmdb_id:
        details['tmdb_id'] = tmdb_id
        if tmdb_id in POSTER_CACHE:
            cached_item = POSTER_CACHE[tmdb_id]
            cached_time = datetime.fromisoformat(cached_item['timestamp'])
            if datetime.now() - cached_time < timedelta(days=POSTER_CACHE_TTL_DAYS):
                details['poster_url'] = cached_item['url']
                return details
        url = f"https://api.themoviedb.org/3/{api_type}/{tmdb_id}?api_key={TMDB_API_TOKEN}&language=zh-CN"
        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        response = make_request_with_retry('GET', url, timeout=10, proxies=proxies)
        if response:
            poster_path = response.json().get('poster_path')
            if poster_path:
                details['poster_url'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
                POSTER_CACHE[tmdb_id] = {'url': details['poster_url'], 'timestamp': datetime.now().isoformat()}
                save_poster_cache()
    return details

def send_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, disable_preview=False):
    if not chat_id:
        print("错误：未指定 chat_id。")
        return
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/" + ('sendPhoto' if photo_url else 'sendMessage')
    payload = {'chat_id': chat_id, 'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_preview}
    if photo_url:
        payload['photo'], payload['caption'] = photo_url, text
    else:
        payload['text'] = text
    if inline_buttons:
        keyboard_layout = inline_buttons if isinstance(inline_buttons[0], list) else [[button] for button in inline_buttons]
        payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard_layout})
    make_request_with_retry('POST', api_url, data=payload, timeout=20, proxies=proxies)

def send_deletable_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, delay_seconds=60, disable_preview=False):
    async def send_and_delete():
        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        if not chat_id: return
        api_url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"
        payload = {'chat_id': chat_id, 'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_preview}
        if inline_buttons:
            keyboard_layout = inline_buttons if isinstance(inline_buttons[0], list) else [[button] for button in inline_buttons]
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard_layout})
        api_url = api_url_base + 'sendPhoto' if photo_url else api_url_base + 'sendMessage'
        if photo_url:
            payload['photo'], payload['caption'] = photo_url, text
        else:
            payload['text'] = text
        response = make_request_with_retry('POST', api_url, data=payload, timeout=20, proxies=proxies)
        if not response:
            return
        sent_message = response.json().get('result', {})
        message_id = sent_message.get('message_id')
        if not message_id or delay_seconds <= 0:
            return
        await asyncio.sleep(delay_seconds)
        delete_url = api_url_base + 'deleteMessage'
        delete_payload = {'chat_id': chat_id, 'message_id': message_id}
        del_response = make_request_with_retry('POST', delete_url, data=delete_payload, timeout=10, proxies=proxies, max_retries=5, retry_delay=5)
        if not del_response and (not del_response or 'message to delete not found' not in del_response.text):
            print(f"❌ 达到最大重试次数，放弃删除消息 ID: {message_id}")
    threading.Thread(target=lambda: asyncio.run(send_and_delete())).start()
    
def send_simple_telegram_message(text, chat_id=None, delay_seconds=60):
    target_chat_id = chat_id if chat_id else ADMIN_USER_ID
    if not target_chat_id: return
    send_deletable_telegram_notification(text, chat_id=target_chat_id, delay_seconds=delay_seconds)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    params = {'callback_query_id': callback_query_id, 'show_alert': show_alert}
    if text: params['text'] = text
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    make_request_with_retry('POST', url, params=params, timeout=5, proxies=proxies)

def edit_telegram_message(chat_id, message_id, text, inline_buttons=None, disable_preview=False):
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"
    payload = {'chat_id': chat_id, 'message_id': message_id, 'text': text, 'parse_mode': 'MarkdownV2', 'disable_web_page_preview': disable_preview}
    if inline_buttons:
        payload['reply_markup'] = json.dumps({'inline_keyboard': inline_buttons})
    make_request_with_retry('POST', url, json=payload, timeout=10, proxies=proxies)

def delete_telegram_message(chat_id, message_id):
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {'chat_id': chat_id, 'message_id': message_id}
    make_request_with_retry('POST', url, data=payload, timeout=10, proxies=proxies)

def delete_user_message_later(chat_id, message_id, delay_seconds=60):
    async def delete_later():
        await asyncio.sleep(delay_seconds)
        delete_telegram_message(chat_id, message_id)
    threading.Thread(target=lambda: asyncio.run(delete_later())).start()
    
def is_super_admin(user_id):
    if not ADMIN_USER_ID:
        return False
    return str(user_id) == str(ADMIN_USER_ID)

def is_user_authorized(user_id):
    if is_super_admin(user_id):
        return True
    if not GROUP_ID:
        return False
    now = time.time()
    if user_id in GROUP_MEMBER_CACHE and (now - GROUP_MEMBER_CACHE[user_id]['timestamp'] < 3600):
        return GROUP_MEMBER_CACHE[user_id]['is_member']
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {'chat_id': GROUP_ID, 'user_id': user_id}
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        result = response.json().get('result', {})
        status = result.get('status')
        if status in ['creator', 'administrator', 'member', 'restricted']:
            GROUP_MEMBER_CACHE[user_id] = {'is_member': True, 'timestamp': now}
            return True
        else:
            GROUP_MEMBER_CACHE[user_id] = {'is_member': False, 'timestamp': now}
            return False
    else:
        print(f"⚠️ 警告：查询用户 {user_id} 的群成员身份失败。本次将临时放行。")
        return True

def is_bot_admin(chat_id, user_id):
    if is_super_admin(user_id):
        return True
    if chat_id > 0:
        return False
    now = time.time()
    if chat_id in ADMIN_CACHE and (now - ADMIN_CACHE[chat_id]['timestamp'] < 300):
        return user_id in ADMIN_CACHE[chat_id]['admins']
    admin_ids = []
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatAdministrators"
    params = {'chat_id': chat_id}
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        admins = response.json().get('result', [])
        admin_ids = [admin['user']['id'] for admin in admins]
        ADMIN_CACHE[chat_id] = {'admins': admin_ids, 'timestamp': now}
        return user_id in admin_ids
    else:
        if chat_id in ADMIN_CACHE:
            return user_id in ADMIN_CACHE[chat_id]['admins']
        return False

def get_active_sessions():
    if not EMBY_SERVER_URL or not EMBY_API_KEY:
        return []
    url = f"{EMBY_SERVER_URL}/Sessions"
    params = {'api_key': EMBY_API_KEY, 'activeWithinSeconds': 360}
    response = make_request_with_retry('GET', url, params=params, timeout=15)
    return [s for s in response.json()] if response else []

def get_active_sessions_info(user_id):
    sessions = [s for s in get_active_sessions() if s.get('NowPlayingItem')]
    if not sessions:
        return "✅ 当前无人观看 Emby。"
    sessions_data = []
    for session in sessions:
        item = session.get('NowPlayingItem', {})
        session_user_id, session_id = session.get('UserId'), session.get('Id')
        media_details = get_media_details(item, session_user_id)
        tmdb_link, year = media_details.get('tmdb_link'), media_details.get('year')
        raw_user_name = session.get('UserName', '未知用户')
        raw_player = session.get('Client', '未知播放器')
        raw_device = session.get('DeviceName', '未知设备')
        ip_address = session.get('RemoteEndPoint', '').split(':')[0]
        location = get_ip_geolocation(ip_address)
        raw_location_str = f"{ip_address} {location}" if location != "局域网" else "局域网"
        raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name', '未知标题')
        year_str = f" ({year})" if year else ""
        raw_episode_info = ""
        if item.get('Type') == 'Episode':
            s_num, e_num, e_name_raw = item.get('ParentIndexNumber'), item.get('IndexNumber'), item.get('Name')
            if s_num is not None and e_num is not None:
                raw_episode_info = f" S{s_num:02d}E{e_num:02d} {e_name_raw or ''}"
            else:
                raw_episode_info = f" {e_name_raw or ''}"
        program_full_title_raw = f"{raw_title}{year_str}{raw_episode_info}"
        session_lines = [
            f"\n",
            f"👤 *用户*: {escape_markdown(raw_user_name)}",
            f"*{escape_markdown('─' * 20)}*"
        ]
        if get_setting('settings.content_settings.status_feedback.show_player'):
            session_lines.append(f"播放器：{escape_markdown(raw_player)}")
        if get_setting('settings.content_settings.status_feedback.show_device'):
            session_lines.append(f"设备：{escape_markdown(raw_device)}")
        if get_setting('settings.content_settings.status_feedback.show_location'):
            session_lines.append(f"位置：{escape_markdown(raw_location_str)}")
        if get_setting('settings.content_settings.status_feedback.show_media_detail'):
            program_line = f"[{escape_markdown(program_full_title_raw)}]({tmdb_link})" if tmdb_link and get_setting('settings.content_settings.status_feedback.media_detail_has_tmdb_link') else escape_markdown(program_full_title_raw)
            session_lines.append(f"节目：{program_line}")
        pos_ticks, run_ticks = session.get('PlayState', {}).get('PositionTicks', 0), item.get('RunTimeTicks')
        if run_ticks and run_ticks > 0:
            percent = (pos_ticks / run_ticks) * 100
            raw_progress_text = f"{percent:.1f}% ({format_ticks_to_hms(pos_ticks)} / {format_ticks_to_hms(run_ticks)})"
            session_lines.append(f"进度：{escape_markdown(raw_progress_text)}")
        raw_program_type = get_program_type_from_path(item.get('Path'))
        if raw_program_type and get_setting('settings.content_settings.status_feedback.show_media_type'):
            session_lines.append(f"节目类型：{escape_markdown(raw_program_type)}")
        if get_setting('settings.content_settings.status_feedback.show_overview'):
            overview = item.get('Overview', '')
            if overview: session_lines.append(f"剧情: {escape_markdown(overview[:100] + '...')}")
        if get_setting('settings.content_settings.status_feedback.show_timestamp'):
            session_lines.append(f"时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")
        buttons = []
        view_button_row = []
        if EMBY_REMOTE_URL and get_setting('settings.content_settings.status_feedback.show_view_on_server_button'):
            item_id, server_id = item.get('Id'), item.get('ServerId')
            if item_id and server_id:
                item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
                view_button_row.append({'text': '▶️ 在服务器中查看', 'url': item_url})
        if view_button_row: buttons.append(view_button_row)
        action_button_row = []
        if session_id:
            if get_setting('settings.content_settings.status_feedback.show_terminate_session_button'):
                action_button_row.append({'text': '❌ 终止会话', 'callback_data': f'session_terminate_{session_id}_{user_id}'})
            if get_setting('settings.content_settings.status_feedback.show_send_message_button'):
                action_button_row.append({'text': '💬 发送消息', 'callback_data': f'session_message_{session_id}_{user_id}'})
        if action_button_row: buttons.append(action_button_row)
        sessions_data.append({
            'message': "\n".join(session_lines),
            'buttons': buttons if buttons else None,
            'poster_url': media_details.get('poster_url') if get_setting('settings.content_settings.status_feedback.show_poster') else None
        })
    return sessions_data

def terminate_emby_session(session_id, chat_id):
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, session_id]):
        if chat_id: send_simple_telegram_message("错误：缺少终止会话所需的服务器配置。", chat_id)
        return False
    url = f"{EMBY_SERVER_URL}/Sessions/{session_id}/Playing/Stop"
    params = {'api_key': EMBY_API_KEY}
    response = make_request_with_retry('POST', url, params=params, timeout=10)
    if response:
        return True
    else:
        if chat_id: send_simple_telegram_message(f"终止会话 {escape_markdown(session_id)} 失败。", chat_id)
        return False

def send_message_to_emby_session(session_id, message, chat_id):
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, session_id]):
        if chat_id: send_simple_telegram_message("错误：缺少发送消息所需的服务器配置。", chat_id)
        return
    url = f"{EMBY_SERVER_URL}/Sessions/{session_id}/Message"
    params = {'api_key': EMBY_API_KEY}
    payload = { "Text": message, "Header": "来自管理员的消息", "TimeoutMs": 15000 }
    response = make_request_with_retry('POST', url, params=params, json=payload, timeout=10)
    if response:
        if chat_id: send_simple_telegram_message("✅ 消息已成功发送。", chat_id)
    else:
        if chat_id: send_simple_telegram_message(f"向会话 {escape_markdown(session_id)} 发送消息失败。", chat_id)

def get_resolution_for_item(item_id, user_id=None):
    request_user_id = user_id or EMBY_USER_ID
    if not request_user_id:
        url = f"{EMBY_SERVER_URL}/Items/{item_id}"
    else:
        url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)
    if not response: return "未知分辨率"
    media_sources = response.json().get('MediaSources', [])
    if not media_sources: return "未知分辨率"
    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video':
            width, height = stream.get('Width', 0), stream.get('Height', 0)
            if width and height: return f"{width}x{height}"
    return "未知分辨率"

def get_series_season_media_info(series_id):
    request_user_id = EMBY_USER_ID
    if not request_user_id: return ["错误：此功能需要配置 Emby User ID"]
    seasons_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    seasons_params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Season'}
    seasons_response = make_request_with_retry('GET', seasons_url, params=seasons_params, timeout=10)
    if not seasons_response: return ["查询季度列表失败"]
    seasons = seasons_response.json().get('Items', [])
    if not seasons: return ["未找到任何季度"]
    season_info_lines = []
    for season in sorted(seasons, key=lambda s: s.get('IndexNumber', 0)):
        season_num, season_id = season.get('IndexNumber'), season.get('Id')
        if season_num is None or season_id is None: continue
        episodes_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
        episodes_params = {'api_key': EMBY_API_KEY, 'ParentId': season_id, 'IncludeItemTypes': 'Episode', 'Limit': 1, 'Fields': 'Id'}
        episodes_response = make_request_with_retry('GET', episodes_url, params=episodes_params, timeout=10)
        season_line = f"S{season_num:02d}：\n    规格未知"
        if episodes_response and episodes_response.json().get('Items'):
            first_episode_id = episodes_response.json()['Items'][0].get('Id')
            stream_details = get_media_stream_details(first_episode_id, request_user_id)
            if stream_details:
                formatted_parts = format_stream_details_message(stream_details, is_season_info=True, prefix='series')
                if formatted_parts:
                    escaped_parts = [escape_markdown(part) for part in formatted_parts]
                    season_line = f"S{season_num:02d}：\n" + "\n".join(escaped_parts)
        season_info_lines.append(season_line)
    return season_info_lines if season_info_lines else ["未找到剧集规格信息"]

def _get_latest_episode_info(series_id):
    request_user_id = EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, series_id, request_user_id]): return {}
    api_endpoint = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Episode', 'Recursive': 'true',
        'SortBy': 'ParentIndexNumber,IndexNumber', 'SortOrder': 'Descending', 'Limit': 1,
        'Fields': 'ProviderIds,Path,ServerId,DateCreated,ParentIndexNumber,IndexNumber,SeriesName,SeriesProviderIds,Overview'
    }
    response = make_request_with_retry('GET', api_endpoint, params=params, timeout=15)
    return response.json()['Items'][0] if response and response.json().get('Items') else {}

def get_tmdb_season_details(series_tmdb_id, season_number):
    if not all([TMDB_API_TOKEN, series_tmdb_id, season_number is not None]): return None
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.themoviedb.org/3/tv/{series_tmdb_id}/season/{season_number}"
    params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        data = response.json()
        episodes = data.get('episodes', [])
        if not episodes: return None
        return {'total_episodes': len(episodes), 'is_finale_marked': episodes[-1].get('episode_type') == 'finale'}
    return None

def send_search_emby_and_format(query, chat_id, user_id, is_group_chat, mention):
    search_term = query.strip()
    match = re.search(r'(\d{4})$', search_term)
    year_for_filter = match.group(1) if match else None
    if match: search_term = search_term[:match.start()].strip()
    if not search_term:
        send_deletable_telegram_notification("关键词无效！", chat_id=chat_id)
        return
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未在配置文件中设置 Emby `user_id`。", chat_id=chat_id)
        return
    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    params = {
        'api_key': EMBY_API_KEY, 'SearchTerm': search_term, 'IncludeItemTypes': 'Movie,Series',
        'Recursive': 'true', 'Fields': 'ProviderIds,Path,ProductionYear,Name'
    }
    if year_for_filter: params['Years'] = year_for_filter
    response = make_request_with_retry('GET', url, params=params, timeout=20)
    if not response:
        send_deletable_telegram_notification(f"搜索失败，无法连接到 Emby API。", chat_id=chat_id)
        return
    results = response.json().get('Items', [])
    if not results:
        send_deletable_telegram_notification(f"在 Emby 中找不到与“{escape_markdown(query)}”相关的任何内容。", chat_id=chat_id)
        return
    search_id = str(uuid.uuid4())
    SEARCH_RESULTS_CACHE[search_id] = results
    send_search_results_page(chat_id, search_id, user_id, page=1)

def send_search_results_page(chat_id, search_id, user_id, page=1, message_id=None):
    if search_id not in SEARCH_RESULTS_CACHE:
        error_msg = "抱歉，此搜索结果已过期，请重新发起搜索。"
        if message_id: edit_telegram_message(chat_id, message_id, error_msg)
        else: send_deletable_telegram_notification(error_msg, chat_id=chat_id)
        return
    results = SEARCH_RESULTS_CACHE[search_id]
    items_per_page = 10
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    page_items = results[start_index:end_index]
    message_text = "查询到以下节目，点击名称可查看详情："
    buttons = []
    for i, item in enumerate(page_items):
        raw_title = item.get('Name', '未知标题')
        final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
        title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
        button_text = f"{i + 1 + start_index}. {title_with_year}"
        if get_setting('settings.content_settings.search_display.show_media_type_in_list'):
            raw_program_type = get_program_type_from_path(item.get('Path'))
            if raw_program_type: button_text += f" | {raw_program_type}"
        buttons.append([{'text': button_text, 'callback_data': f's_detail_{search_id}_{start_index + i}_{user_id}'}])
    page_buttons = []
    if page > 1: page_buttons.append({'text': '◀️ 上一页', 'callback_data': f's_page_{search_id}_{page-1}_{user_id}'})
    if end_index < len(results): page_buttons.append({'text': '下一页 ▶️', 'callback_data': f's_page_{search_id}_{page+1}_{user_id}'})
    if page_buttons: buttons.append(page_buttons)
    if message_id: edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else: send_deletable_telegram_notification(message_text, chat_id=chat_id, inline_buttons=buttons, delay_seconds=90)

def get_media_stream_details(item_id, user_id=None):
    request_user_id = user_id or EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, request_user_id]): return None

    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)

    if not response: return None
    item_data = response.json()
    media_sources = item_data.get('MediaSources', [])
    if not media_sources: return None

    video_info, audio_info_list = {}, []
    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video' and not video_info:
            bitrate_mbps = stream.get('BitRate', 0) / 1_000_000
            video_info = {
                'title': stream.get('Title') or stream.get('Codec', '未知').upper(),
                'resolution': f"{stream.get('Width', 0)}x{stream.get('Height', 0)}",
                'bitrate': f"{bitrate_mbps:.1f}" if bitrate_mbps > 0 else "未知",
                'video_range': stream.get('VideoRange', '')
            }
        elif stream.get('Type') == 'Audio':
            audio_info_list.append({
                'language': stream.get('Language', '未知'), 'codec': stream.get('Codec', '未知'),
                'layout': stream.get('ChannelLayout', '')
            })
    return {'video_info': video_info, 'audio_info': audio_info_list} if video_info or audio_info_list else None

def format_stream_details_message(stream_details, is_season_info=False, prefix='movie'):
    if not stream_details: return []

    message_parts = []

    video_setting_path_map = {
        'movie': 'settings.content_settings.search_display.movie.show_video_spec',
        'series': 'settings.content_settings.search_display.series.season_specs.show_video_spec'
    }
    video_setting_path = video_setting_path_map[prefix] if not is_season_info else video_setting_path_map['series']

    video_info = stream_details.get('video_info')
    if video_info and get_setting(video_setting_path):
        parts = [p for p in [video_info.get('title'), video_info.get('resolution') if video_info.get('resolution') != '0x0' else None, f"{video_info.get('bitrate')}Mbps" if video_info.get('bitrate') != '未知' else None, video_info.get('video_range')] if p]
        if parts:
            video_line = ' '.join(parts)
            label = "视频："
            indent = "    " if is_season_info else ""
            message_parts.append(f"{indent}{label}{video_line}")

    audio_setting_path_map = {
        'movie': 'settings.content_settings.search_display.movie.show_audio_spec',
        'series': 'settings.content_settings.search_display.series.season_specs.show_audio_spec'
    }
    audio_setting_path = audio_setting_path_map[prefix] if not is_season_info else audio_setting_path_map['series']

    audio_info_list = stream_details.get('audio_info')
    if audio_info_list and get_setting(audio_setting_path):
        audio_lines = []
        seen_tracks = set()
        for a_info in audio_info_list:
            lang_code = a_info.get('language', 'und').lower()
            lang_display = LANG_MAP.get(lang_code, {}).get('zh', lang_code.capitalize())
            audio_parts = [p for p in [lang_display if lang_display != '未知' else None, a_info.get('codec', '').upper() if a_info.get('codec', '') != '未知' else None, a_info.get('layout', '')] if p]
            if audio_parts:
                track_str = ' '.join(audio_parts)
                if track_str not in seen_tracks:
                    audio_lines.append(track_str)
                    seen_tracks.add(track_str)
        
        if audio_lines:
            full_audio_str = "、".join(audio_lines)
            label = "音频："
            indent = "    " if is_season_info else ""
            message_parts.append(f"{indent}{label}{full_audio_str}")
            
    return message_parts

def send_search_detail(chat_id, search_id, item_index, user_id):
    if search_id not in SEARCH_RESULTS_CACHE or item_index >= len(SEARCH_RESULTS_CACHE[search_id]):
        send_deletable_telegram_notification("抱歉，此搜索结果已过期或无效。", chat_id=chat_id)
        return
    item_from_cache = SEARCH_RESULTS_CACHE[search_id][item_index]
    item_id = item_from_cache.get('Id')
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未设置 Emby `user_id`。", chat_id=chat_id)
        return
    full_item_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated'}
    response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
    if not response:
        send_deletable_telegram_notification("获取详细信息失败。", chat_id=chat_id)
        return
    item = response.json()
    item_type, raw_title, raw_overview = item.get('Type'), item.get('Name', '未知标题'), item.get('Overview', '暂无剧情简介')
    final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
    media_details = get_media_details(item, request_user_id)
    poster_url, tmdb_link = media_details.get('poster_url'), media_details.get('tmdb_link', '')
    message_parts = []
    prefix = 'movie' if item_type == 'Movie' else 'series'
    title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
    if tmdb_link and get_setting(f'settings.content_settings.search_display.{prefix}.title_has_tmdb_link'):
        message_parts.append(f"名称：[{escape_markdown(title_with_year)}]({tmdb_link})")
    else:
        message_parts.append(f"名称：*{escape_markdown(title_with_year)}*")
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_type'):
        item_type_cn = "电影" if item_type == 'Movie' else "剧集"
        message_parts.append(f"类型：{escape_markdown(item_type_cn)}")
    raw_program_type = get_program_type_from_path(item.get('Path'))
    if raw_program_type and get_setting(f'settings.content_settings.search_display.{prefix}.show_category'):
        message_parts.append(f"分类：{escape_markdown(raw_program_type)}")
    if raw_overview and get_setting(f'settings.content_settings.search_display.{prefix}.show_overview'):
        overview_text = raw_overview[:150] + "..." if len(raw_overview) > 150 else raw_overview
        message_parts.append(f"剧情：{escape_markdown(overview_text)}")
    def format_date(date_str):
        if not date_str: return "未知"
        try:
            date_str = date_str.rstrip('Z')
            if '.' in date_str:
                main_part, fractional_part = date_str.split('.', 1)
                fractional_part = fractional_part[:6]
                date_to_parse = f"{main_part}.{fractional_part}"
            else:
                date_to_parse = date_str
            dt_naive = datetime.fromisoformat(date_to_parse)
            dt_utc = dt_naive.replace(tzinfo=ZoneInfo("UTC"))
            return dt_utc.astimezone(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
        except (ValueError, TypeError):
            return "未知"
    if item_type == 'Movie':
        stream_details = get_media_stream_details(item_id, request_user_id)
        formatted_parts = format_stream_details_message(stream_details, prefix='movie')
        if formatted_parts: message_parts.extend([escape_markdown(part) for part in formatted_parts])
        if get_setting('settings.content_settings.search_display.movie.show_added_time'):
            date_created_str = item.get('DateCreated')
            message_parts.append(f"入库时间：{escape_markdown(format_date(date_created_str))}")
    elif item_type == 'Series':
        season_info_list = get_series_season_media_info(item_id)
        if season_info_list: message_parts.append(f"各季规格：\n" + "\n".join([f"    {info}" for info in season_info_list]))
        latest_episode = _get_latest_episode_info(item_id)
        if latest_episode:
            message_parts.append("\u200b")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_latest_episode'):
                s_num, e_num = latest_episode.get('ParentIndexNumber'), latest_episode.get('IndexNumber')
                update_info_raw = f"第 {s_num} 季 第 {e_num} 集" if s_num is not None and e_num is not None else "信息不完整"
                episode_media_details = get_media_details(latest_episode, EMBY_USER_ID)
                episode_tmdb_link = episode_media_details.get('tmdb_link')
                if episode_tmdb_link and get_setting('settings.content_settings.search_display.series.update_progress.latest_episode_has_tmdb_link'):
                    message_parts.append(f"已更新至：[{escape_markdown(update_info_raw)}]({episode_tmdb_link})")
                else:
                    message_parts.append(f"已更新至：{escape_markdown(update_info_raw)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_overview'):
                episode_overview = latest_episode.get('Overview')
                if episode_overview:
                    overview_text = episode_overview[:100] + "..." if len(episode_overview) > 100 else episode_overview
                    message_parts.append(f"剧情：{escape_markdown(overview_text)}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_added_time'):
                message_parts.append(f"入库时间：{escape_markdown(format_date(latest_episode.get('DateCreated')))}")
            if get_setting('settings.content_settings.search_display.series.update_progress.show_progress_status'):
                series_tmdb_id = media_details.get('tmdb_id')
                local_s_num, local_e_num = latest_episode.get('ParentIndexNumber'), latest_episode.get('IndexNumber')
                if series_tmdb_id and local_s_num is not None and local_e_num is not None:
                    tmdb_season_info = get_tmdb_season_details(series_tmdb_id, local_s_num)
                    if tmdb_season_info:
                        tmdb_total, is_finale = tmdb_season_info['total_episodes'], tmdb_season_info['is_finale_marked']
                        status = "已完结" if local_e_num >= tmdb_total and is_finale else "已完结 (可能不准确)" if local_e_num >= tmdb_total else f"剩余{tmdb_total - local_e_num}集"
                        message_parts.append(f"更新进度：{escape_markdown(status)}")
                    else:
                        message_parts.append(f"更新进度：{escape_markdown('查询失败 (TMDB)')}")
    final_poster_url = poster_url if poster_url and get_setting(f'settings.content_settings.search_display.{prefix}.show_poster') else None
    buttons = []
    if get_setting(f'settings.content_settings.search_display.{prefix}.show_view_on_server_button') and EMBY_REMOTE_URL:
        server_id = item.get('ServerId')
        if item_id and server_id:
            item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
            buttons.append([{'text': '▶️ 在服务器中查看', 'url': item_url}])
    send_deletable_telegram_notification(
        "\n".join(filter(None, message_parts)),
        photo_url=final_poster_url, chat_id=chat_id,
        inline_buttons=buttons if buttons else None,
        delay_seconds=90
    )

def send_settings_menu(chat_id, user_id, message_id=None, menu_key='root'):
    node = SETTINGS_MENU_STRUCTURE.get(menu_key, SETTINGS_MENU_STRUCTURE['root'])
    text_parts = [f"*{escape_markdown(node['label'])}*"]
    if menu_key == 'root':
        text_parts.append("管理机器人的各项功能与通知")
    buttons = []
    if 'children' in node:
        for child_key in node['children']:
            child_node = SETTINGS_MENU_STRUCTURE[child_key]
            if 'children' in child_node:
                buttons.append([{'text': f"➡️ {child_node['label']}", 'callback_data': f'n_{child_key}_{user_id}'}])
            elif 'config_path' in child_node:
                is_enabled = get_setting(child_node['config_path'])
                status_icon = "✅" if is_enabled else "❌"
                item_index = child_node.get('index')
                if item_index is not None:
                    callback_data = f"t_{item_index}_{user_id}"
                    buttons.append([{'text': f"{status_icon} {child_node['label']}", 'callback_data': callback_data}])
    nav_buttons = []
    if 'parent' in node and node['parent'] is not None:
        nav_buttons.append({'text': '◀️ 返回上一级', 'callback_data': f'n_{node["parent"]}_{user_id}'})
    nav_buttons.append({'text': '☑️ 完成', 'callback_data': f'c_menu_{user_id}'})
    buttons.append(nav_buttons)
    message_text = "\n".join(text_parts)
    if message_id:
        edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else:
        send_telegram_notification(text=message_text, chat_id=chat_id, inline_buttons=buttons)

def handle_callback_query(callback_query):
    query_id, data = callback_query['id'], callback_query.get('data')
    if not data:
        answer_callback_query(query_id)
        return
    message = callback_query.get('message', {})
    clicker_id, chat_id, message_id = callback_query['from']['id'], message['chat']['id'], message['message_id']
    try:
        command, rest_of_data = data.split('_', 1)
        main_data, initiator_id_str = rest_of_data.rsplit('_', 1)
        initiator_id = int(initiator_id_str)
    except (ValueError, IndexError) as e:
        print(f"ERROR: Could not parse callback data: {data}. Error: {e}")
        answer_callback_query(query_id, text="发生了一个内部错误。", show_alert=True)
        return

    if clicker_id != initiator_id:
        answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
        return

    is_super_admin_action = command in ['n', 't', 'c', 'session']
    if is_super_admin_action and not is_super_admin(clicker_id):
        answer_callback_query(query_id, text="抱歉，此操作仅对超级管理员开放。", show_alert=True)
        return
        
    if command == 'n':
        menu_key = main_data
        answer_callback_query(query_id)
        send_settings_menu(chat_id, initiator_id, message_id, menu_key)
        return
    if command == 't':
        item_index = int(main_data)
        node_key = TOGGLE_INDEX_TO_KEY.get(item_index)
        if not node_key:
            print(f"ERROR: Invalid toggle index received: {item_index}")
            return
        node_info = TOGGLE_KEY_TO_INFO.get(node_key)
        config_path = node_info['config_path']
        menu_key_to_refresh = node_info['parent']
        current_value = get_setting(config_path)
        set_setting(config_path, not current_value)
        save_config()
        answer_callback_query(query_id, text=f"设置已更新: {'✅' if not current_value else '❌'}")
        send_settings_menu(chat_id, initiator_id, message_id, menu_key_to_refresh)
        return
    if command == 'c' and main_data == 'menu':
        answer_callback_query(query_id)
        delete_telegram_message(chat_id, message_id)
        send_simple_telegram_message("✅ 设置菜单已关闭。", chat_id=chat_id)
        return
    if command == 's':
        action, rest_params = main_data.split('_', 1)
        search_id, final_param = rest_params.rsplit('_', 1)
        if action == 'page':
            page = int(final_param)
            answer_callback_query(query_id)
            send_search_results_page(chat_id, search_id, initiator_id, page, message_id)
        elif action == 'detail':
            item_index = int(final_param)
            answer_callback_query(query_id, text="正在获取详细信息...")
            send_search_detail(chat_id, search_id, item_index, initiator_id)
        return
    if command == 'session':
        action, session_id = main_data.split('_', 1)
        if action == 'terminate':
            answer_callback_query(query_id)
            if terminate_emby_session(session_id, chat_id):
                answer_callback_query(query_id, text="✅ 会话已成功终止。", show_alert=True)
            else:
                answer_callback_query(query_id, text="❌ 终止失败。", show_alert=True)
        elif action == 'message':
            answer_callback_query(query_id)
            user_context[chat_id] = {'state': 'awaiting_message_for_session', 'session_id': session_id}
            prompt_text = "✍️ 请输入您想发送给该用户的消息内容："
            if chat_id < 0:
                prompt_text = "✍️ *请回复本消息*，输入您想发送给该用户的消息内容："
            send_deletable_telegram_notification(escape_markdown(prompt_text), chat_id=chat_id, delay_seconds=60)
        return
        
def handle_telegram_command(message):
    msg_text, chat_id, user_id = message.get('text', '').strip(), message['chat']['id'], message['from']['id']

    if not is_user_authorized(user_id):
        print(f"🚫 已忽略来自非授权用户 {user_id} 的消息。")
        return

    is_group_chat = chat_id < 0
    is_reply = 'reply_to_message' in message
    mention = f"@{message['from'].get('username')} " if is_group_chat and message['from'].get('username') else ""
    is_awaiting_input = chat_id in user_search_state or chat_id in user_context

    if is_awaiting_input:
        is_bot_command = msg_text.startswith('/')
        if is_bot_command:
            user_search_state.pop(chat_id, None)
            user_context.pop(chat_id, None)
        else:
            if not is_group_chat or is_reply:
                if chat_id in user_search_state:
                    original_user_id = user_search_state.get(chat_id)
                    if original_user_id is None or original_user_id != user_id:
                        return
                    del user_search_state[chat_id]
                    send_search_emby_and_format(msg_text, chat_id, user_id, is_group_chat, mention)
                    return
                elif chat_id in user_context and user_context[chat_id].get('state') == 'awaiting_message_for_session':
                    session_id_to_send = user_context[chat_id]['session_id']
                    del user_context[chat_id]
                    send_message_to_emby_session(session_id_to_send, msg_text, chat_id)
                    return

    if '@' in msg_text: msg_text = msg_text.split('@')[0]
    if not msg_text.startswith('/'): return
    command = msg_text.split()[0]

    if command in ['/status', '/settings']:
        if not is_super_admin(user_id):
            send_simple_telegram_message("权限不足：此命令仅限超级管理员使用。", chat_id)
            return
        
        if command == '/status':
            status_info = get_active_sessions_info(user_id)
            if isinstance(status_info, str):
                send_deletable_telegram_notification(f"{mention}{status_info}", chat_id=chat_id)
            elif isinstance(status_info, list) and status_info:
                title_message = f"{mention}*🎬 Emby 当前播放会话数: {len(status_info)}*"
                global_buttons = []
                row = []
                if get_setting('settings.content_settings.status_feedback.show_broadcast_button'):
                    row.append({'text': '💬 群发消息', 'callback_data': f'session_broadcast_{user_id}'})
                if get_setting('settings.content_settings.status_feedback.show_terminate_all_button'):
                    row.append({'text': '❌ 终止所有', 'callback_data': f'session_terminateall_{user_id}'})
                if row: global_buttons.append(row)
                send_deletable_telegram_notification(text=title_message, chat_id=chat_id, inline_buttons=global_buttons or None, disable_preview=True)
                time.sleep(0.5)
                for session_data in status_info:
                    if session_data.get('poster_url'):
                        send_telegram_notification(text=session_data['message'], photo_url=session_data['poster_url'], chat_id=chat_id, inline_buttons=session_data.get('buttons'), disable_preview=True)
                    else:
                        send_deletable_telegram_notification(text=session_data['message'], chat_id=chat_id, inline_buttons=session_data.get('buttons'), disable_preview=True)
                    time.sleep(0.5)
        elif command == '/settings':
            send_settings_menu(chat_id, user_id)
        return

    if command == '/search':
        search_term = msg_text[len('/search'):].strip()
        if search_term:
            send_search_emby_and_format(search_term, chat_id, user_id, is_group_chat, mention)
        else:
            user_search_state[chat_id] = user_id
            prompt_message = "请提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            if is_group_chat:
                prompt_message = f"{mention}请回复本消息，提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            send_deletable_telegram_notification(escape_markdown(prompt_message), chat_id=chat_id, delay_seconds=60)

def poll_telegram_updates():
    update_id = 0
    print("🤖 Telegram 命令轮询服务已启动...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
            params = {'offset': update_id + 1, 'timeout': 30}
            proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
            response = requests.get(url, params=params, timeout=40, proxies=proxies)
            if response.status_code == 200:
                updates = response.json().get('result', [])
                for update in updates:
                    update_id = update['update_id']
                    if 'message' in update:
                        message = update['message']
                        chat_id = message['chat']['id']
                        message_id = message['message_id']
                        is_group_chat = chat_id < 0
                        
                        should_delete = False
                        if not is_group_chat:
                            should_delete = True
                        else:
                            msg_text = message.get('text', '')
                            if msg_text.startswith('/'):
                                should_delete = True
                            elif 'reply_to_message' in message:
                                bot_id = int(TELEGRAM_TOKEN.split(':')[0])
                                if message['reply_to_message']['from']['id'] == bot_id:
                                    should_delete = True
                        
                        if should_delete:
                            delete_user_message_later(chat_id, message_id, delay_seconds=60)

                        handle_telegram_command(message)

                    elif 'callback_query' in update:
                        handle_callback_query(update['callback_query'])
            else:
                print(f"❌ 轮询 Telegram 更新失败: {response.status_code} - {response.text}")
                time.sleep(10)
        except requests.exceptions.RequestException as e:
            print(f"轮询 Telegram 时网络错误: {e}")
            time.sleep(10)
        except Exception as e:
            import traceback
            print(f"处理 Telegram 更新时发生未处理错误: {e}")
            traceback.print_exc()
            time.sleep(5)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data_bytes = self.rfile.read(content_length)
            
            content_type = self.headers.get('Content-Type', '').lower()
            if 'application/json' in content_type:
                json_string = post_data_bytes.decode('utf-8')
            elif 'application/x-www-form-urlencoded' in content_type:
                parsed_form = parse_qs(post_data_bytes.decode('utf-8'))
                json_string = parsed_form.get('data', [None])[0]
            else:
                self.send_response(400); self.end_headers(); return

            if not json_string: 
                self.send_response(400); self.end_headers(); return
            
            event_data = json.loads(unquote(json_string))
            event_type = event_data.get('Event')
            item_from_webhook = event_data.get('Item', {})

            if event_type == 'library.deleted':
                item_type = item_from_webhook.get('Type')
                if item_type not in ['Movie', 'Series', 'Episode']:
                    self.send_response(204); self.end_headers()
                    return
            
            event_map = {
                'playback.start': 'settings.notification_management.playback_start', 
                'playback.unpause': 'settings.notification_management.playback_start',
                'playback.pause': 'settings.notification_management.playback_pause', 
                'playback.stop': 'settings.notification_management.playback_stop',
                'library.new': 'library.new',
                'library.deleted': 'settings.notification_management.library_deleted'
            }
            setting_key = event_map.get(event_type)

            if setting_key == 'library.new':
                if not any([get_setting('settings.notification_management.library_new.to_group'), get_setting('settings.notification_management.library_new.to_channel'), get_setting('settings.notification_management.library_new.to_private')]):
                    self.send_response(204); self.end_headers(); return
            elif setting_key and not get_setting(setting_key):
                self.send_response(204); self.end_headers(); return

            user, session = event_data.get('User', {}), event_data.get('Session', {})
            playback_info = event_data.get('PlaybackInfo', {})

            if event_type in ["playback.start", "playback.unpause", "playback.stop", "playback.pause", "library.new", "library.deleted"]:
                if event_type in ["playback.start", "playback.unpause"]:
                    now = time.time()
                    event_key = (user.get('Id'), item_from_webhook.get('Id'))
                    if now - recent_playback_notifications.get(event_key, 0) < PLAYBACK_DEBOUNCE_SECONDS:
                        self.send_response(204); self.end_headers(); return
                    recent_playback_notifications[event_key] = now
                
                item = item_from_webhook
                if event_type not in ["library.deleted"]:
                    item_id = item_from_webhook.get('Id')
                    if item_id and EMBY_USER_ID:
                        full_item_url = f"{EMBY_SERVER_URL}/Users/{EMBY_USER_ID}/Items/{item_id}"
                        params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated,SeriesProviderIds'}
                        response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)
                        if response:
                            item = response.json()
                
                media_details = get_media_details(item, user.get('Id'))
                
                raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name', '未知标题')
                raw_episode_info = ""
                
                # --- 新增逻辑: 检查是否为 Type:Series 的多集更新 ---
                if item.get('Type') == 'Series':
                    description = event_data.get('Description', '')
                    # 使用正则表达式从 Description 中提取 "S01 E01-E05" 这样的信息
                    match = re.search(r'(S\d+ E\d+[-]?E?\d*)', description)
                    if match:
                        raw_episode_info = f" {match.group(1)}"
                elif item.get('Type') == 'Episode':
                    s, e, en = item.get('ParentIndexNumber'), item.get('IndexNumber'), item.get('Name')
                    raw_episode_info = f" S{s:02d}E{e:02d} {en or ''}" if s is not None and e is not None else f" {en or ''}"
                
                title_with_year_and_episode = f"{raw_title} ({media_details.get('year')})" if media_details.get('year') else raw_title
                title_with_year_and_episode += raw_episode_info
                
                action_text_map = {"playback.start": "▶️ 开始播放", "playback.unpause": "▶️ 继续播放", "playback.stop": "⏹️ 停止播放", "playback.pause": "⏸️ 暂停播放", "library.new": "✅ 新增", "library.deleted": "❌ 删除"}
                action_text = action_text_map.get(event_type, "")
                item_type_cn = "剧集" if item.get('Type') in ['Episode', 'Series'] else "电影" if item.get('Type') == 'Movie' else ""

                message = ""
                photo_url = None
                buttons = []
                
                if event_type == "library.new":
                    parts = []
                    # 对于多集更新，item_type是Series，但我们需要显示剧集类型为“剧集”
                    current_item_type = item.get('Type')
                    if current_item_type == 'Series' or current_item_type == 'Episode':
                        item_type_cn = '剧集'
                    elif current_item_type == 'Movie':
                        item_type_cn = '电影'
                    else:
                        item_type_cn = ''

                    if get_setting('settings.content_settings.new_library_notification.show_media_detail'):
                        if get_setting('settings.content_settings.new_library_notification.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                            full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({media_details.get('tmdb_link')})"
                        else:
                            full_title_line = escape_markdown(title_with_year_and_episode)
                        parts.append(f"{action_text}{item_type_cn} {full_title_line}")
                    else:
                        parts.append(f"{action_text}{item_type_cn}")

                    if get_setting('settings.content_settings.new_library_notification.show_media_type'):
                        raw_program_type = get_program_type_from_path(item.get('Path'))
                        if raw_program_type:
                            parts.append(f"节目类型：{escape_markdown(raw_program_type)}")

                    if get_setting('settings.content_settings.new_library_notification.show_overview'):
                        overview_text = item.get('Overview', '暂无剧情简介')
                        if overview_text:
                            overview_text = overview_text[:150] + "..." if len(overview_text) > 150 else overview_text
                            parts.append(f"剧情：{escape_markdown(overview_text)}")

                    stream_details = get_media_stream_details(item.get('Id'), None)
                    if stream_details:
                        if get_setting('settings.content_settings.new_library_notification.show_video_spec'):
                            video_info = stream_details.get('video_info', {})
                            if video_info and video_info.get('resolution') != '0x0':
                                parts.append(f"视频规格：{escape_markdown(' '.join([v for k, v in video_info.items() if v]))}")

                        if get_setting('settings.content_settings.new_library_notification.show_audio_spec'):
                            audio_info_list = stream_details.get('audio_info', [])
                            if audio_info_list:
                                audio_lines = []
                                seen_tracks = set()
                                for a_info in audio_info_list:
                                    lang_code = a_info.get('language', 'und').lower()
                                    lang_display = LANG_MAP.get(lang_code, {}).get('zh', lang_code.capitalize())
                                    audio_parts = [p for p in [lang_display, a_info.get('codec', '').upper(), a_info.get('layout', '')] if p and p != '未知']
                                    track_str = ' '.join(audio_parts)
                                    if track_str and track_str not in seen_tracks:
                                        audio_lines.append(track_str)
                                        seen_tracks.add(track_str)
                                if audio_lines: parts.append(f"音频规格：{escape_markdown('、'.join(audio_lines))}")

                    if get_setting('settings.content_settings.new_library_notification.show_timestamp'):
                        parts.append(f"入库时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")

                    message = "\n".join(parts)
                    
                    if get_setting('settings.content_settings.new_library_notification.show_poster'): photo_url = media_details.get('poster_url')
                    
                    view_button = None
                    if get_setting('settings.content_settings.new_library_notification.show_view_on_server_button') and EMBY_REMOTE_URL:
                        item_id, server_id = item.get('Id'), item.get('ServerId')
                        if item_id and server_id:
                            item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
                            view_button = {'text': '▶️ 在服务器中查看', 'url': item_url}
                            buttons.append([view_button])

                    auto_delete_group = get_setting('settings.auto_delete_settings.new_library.to_group')
                    auto_delete_channel = get_setting('settings.auto_delete_settings.new_library.to_channel')
                    auto_delete_private = get_setting('settings.auto_delete_settings.new_library.to_private')
                    
                    if get_setting('settings.notification_management.library_new.to_group') and GROUP_ID:
                        if auto_delete_group: send_deletable_telegram_notification(message, photo_url, chat_id=GROUP_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                        else: send_telegram_notification(message, photo_url, chat_id=GROUP_ID, inline_buttons=buttons if buttons else None)

                    if get_setting('settings.notification_management.library_new.to_channel') and CHANNEL_ID:
                        if auto_delete_channel: send_deletable_telegram_notification(message, photo_url, chat_id=CHANNEL_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                        else: send_telegram_notification(message, photo_url, chat_id=CHANNEL_ID, inline_buttons=buttons if buttons else None)

                    if get_setting('settings.notification_management.library_new.to_private') and ADMIN_USER_ID:
                        if auto_delete_private: send_deletable_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                        else: send_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None)


                elif event_type == "library.deleted":
                    parts = []
                    if get_setting('settings.content_settings.library_deleted_notification.show_media_detail'):
                        if get_setting('settings.content_settings.library_deleted_notification.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                            full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({media_details.get('tmdb_link')})"
                        else:
                            full_title_line = escape_markdown(title_with_year_and_episode)
                        parts.append(f"❌ 删除 {item_type_cn} {full_title_line}")
                    else:
                        parts.append(f"❌ 删除 {item_type_cn}")

                    raw_program_type = get_program_type_from_path(item.get('Path'))
                    if raw_program_type and get_setting('settings.content_settings.library_deleted_notification.show_media_type'):
                        parts.append(f"节目类型：{escape_markdown(raw_program_type)}")

                    webhook_overview = item.get('Overview')
                    if webhook_overview and get_setting('settings.content_settings.library_deleted_notification.show_overview'):
                        overview = webhook_overview[:150] + '...' if len(webhook_overview) > 150 else webhook_overview
                        parts.append(f"剧情：{escape_markdown(overview)}")
                    
                    if get_setting('settings.content_settings.library_deleted_notification.show_timestamp'):
                        parts.append(f"删除时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")
                    
                    message = "\n".join(parts)
                    if get_setting('settings.content_settings.library_deleted_notification.show_poster'):
                        photo_url = media_details.get('poster_url')
                    auto_delete = get_setting('settings.auto_delete_settings.library_deleted')
                    if auto_delete:
                        send_deletable_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID)
                
                else:
                    parts = []
                    if get_setting('settings.content_settings.playback_action.show_media_detail'):
                        if get_setting('settings.content_settings.playback_action.media_detail_has_tmdb_link') and media_details.get('tmdb_link'):
                            full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({media_details.get('tmdb_link')})"
                        else:
                            full_title_line = escape_markdown(title_with_year_and_episode)
                        parts.append(f"{action_text}{item_type_cn} {full_title_line}")
                    else:
                        parts.append(f"{action_text}{item_type_cn}")
                    
                    if get_setting('settings.content_settings.playback_action.show_user'): parts.append(f"用户：{escape_markdown(user.get('Name', '未知用户'))}")
                    if get_setting('settings.content_settings.playback_action.show_player'): parts.append(f"播放器：{escape_markdown(session.get('Client', ''))}")
                    if get_setting('settings.content_settings.playback_action.show_device'): parts.append(f"设备：{escape_markdown(session.get('DeviceName', ''))}")
                    if get_setting('settings.content_settings.playback_action.show_location'):
                        ip = session.get('RemoteEndPoint', '').split(':')[0]
                        loc = get_ip_geolocation(ip)
                        parts.append(f"位置：{escape_markdown('局域网' if loc == '局域网' else f'{ip} {loc}')}")
                    if get_setting('settings.content_settings.playback_action.show_progress'):
                        pos_ticks, run_ticks = playback_info.get('PositionTicks'), item.get('RunTimeTicks')
                        if pos_ticks is not None and run_ticks and run_ticks > 0:
                            percent = (pos_ticks / run_ticks) * 100
                            progress = f"进度：已观看 {percent:.1f}%" if event_type == "playback.stop" else f"进度：{percent:.1f}% ({format_ticks_to_hms(pos_ticks)} / {format_ticks_to_hms(run_ticks)})"
                            parts.append(escape_markdown(progress))
                    
                    stream_details = get_media_stream_details(item.get('Id'), user.get('Id'))
                    if stream_details:
                        if get_setting('settings.content_settings.playback_action.show_video_spec'):
                            video_info = stream_details.get('video_info', {})
                            if video_info:
                                video_line_parts = [p for p in [video_info.get('title'), video_info.get('resolution') if video_info.get('resolution') != '0x0' else None, f"{video_info.get('bitrate')}Mbps" if video_info.get('bitrate') != '未知' else None, video_info.get('video_range')] if p]
                                if video_line_parts: parts.append(f"视频规格: {escape_markdown(' '.join(video_line_parts))}")
                        if get_setting('settings.content_settings.playback_action.show_audio_spec'):
                            audio_info_list = stream_details.get('audio_info', [])
                            if audio_info_list:
                                audio_lines = []
                                seen_tracks = set()
                                for a_info in audio_info_list:
                                    lang_code = a_info.get('language', 'und').lower()
                                    lang_display = LANG_MAP.get(lang_code, {}).get('zh', lang_code.capitalize())
                                    audio_parts = [p for p in [lang_display if lang_display != '未知' else None, a_info.get('codec', '').upper() if a_info.get('codec', '') != '未知' else None, a_info.get('layout', '')] if p]
                                    if audio_parts:
                                        track_str = ' '.join(audio_parts)
                                        if track_str not in seen_tracks:
                                            audio_lines.append(track_str)
                                            seen_tracks.add(track_str)
                                if audio_lines: parts.append(f"音频规格: {escape_markdown('、'.join(audio_lines))}")
                    
                    raw_program_type = get_program_type_from_path(item.get('Path'))
                    if raw_program_type and get_setting('settings.content_settings.playback_action.show_media_type'):
                        parts.append(f"节目类型：{escape_markdown(raw_program_type)}")

                    webhook_overview = item.get('Overview')
                    if webhook_overview and get_setting('settings.content_settings.playback_action.show_overview'):
                        overview = webhook_overview[:150] + '...' if len(webhook_overview) > 150 else webhook_overview
                        parts.append(f"剧情：{escape_markdown(overview)}")
                    
                    if get_setting('settings.content_settings.playback_action.show_timestamp'):
                        parts.append(f"时间：{escape_markdown(datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S'))}")

                    message = "\n".join(parts)
                    
                    if get_setting('settings.content_settings.playback_action.show_poster'): photo_url = media_details.get('poster_url')
                    if EMBY_REMOTE_URL and get_setting('settings.content_settings.playback_action.show_view_on_server_button'):
                        item_id, server_id = item.get('Id'), item.get('ServerId') or event_data.get('Server', {}).get('Id')
                        if item_id and server_id:
                            button = {'text': '▶️ 在服务器中查看', 'url': f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"}
                            buttons.append([button])

                    auto_delete_path_map = {'playback.start': 'settings.auto_delete_settings.playback_start', 'playback.unpause': 'settings.auto_delete_settings.playback_start','playback.pause': 'settings.auto_delete_settings.playback_pause', 'playback.stop': 'settings.auto_delete_settings.playback_stop'}
                    auto_delete_path = auto_delete_path_map.get(event_type)
                    if auto_delete_path and get_setting(auto_delete_path):
                        send_deletable_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None, delay_seconds=60)
                    else:
                        send_telegram_notification(message, photo_url, chat_id=ADMIN_USER_ID, inline_buttons=buttons if buttons else None)

            self.send_response(200); self.end_headers(); return

        except Exception as e:
            import traceback
            print(f"处理 Webhook 请求时发生错误: {e}")
            traceback.print_exc()
            self.send_response(500)
        finally:
            if not self.wfile.closed:
                self.end_headers()

class QuietWebhookHandler(WebhookHandler):
    def log_message(self, format, *args):
        pass


class QuietWebhookHandler(WebhookHandler):
    def log_message(self, format, *args):
        pass

def run_server(server_class=HTTPServer, handler_class=WebhookHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"服务器已在 http://0.0.0.0:{port} 启动...")
    httpd.serve_forever()

class QuietWebhookHandler(WebhookHandler):
    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    if not EMBY_USER_ID:
        print("="*60 + "\n⚠️ 严重警告：在 config.yaml 中未找到 'user_id' 配置。\n 这可能导致部分需要用户上下文的 Emby API 请求失败。\n 强烈建议配置一个有效的用户ID以确保所有功能正常运作。\n" + "="*60)

    telegram_poll_thread = threading.Thread(target=poll_telegram_updates, daemon=True)
    telegram_poll_thread.start()

    run_server(handler_class=QuietWebhookHandler)
