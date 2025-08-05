import os
import json
import time
import yaml
import requests
import re
import threading
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import uuid

POSTER_CACHE = {}
CACHE_DIR = '/config/cache'
POSTER_CACHE_PATH = os.path.join(CACHE_DIR, 'poster_cache.json')
POSTER_CACHE_TTL_DAYS = 30

CONFIG_PATH = '/config/config.yaml'
CONFIG = {}
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        CONFIG = yaml.safe_load(f)
except FileNotFoundError:
    print(f"错误：配置文件 {CONFIG_PATH} 未找到。请确保已通过 -v 参数映射。")
    exit(1)
except Exception as e:
    print(f"错误：读取或解析配置文件失败: {e}")
    exit(1)

LANG_MAP = {}
LANG_MAP_PATH = os.path.join(CACHE_DIR, 'languages.json')

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

TELEGRAM_TOKEN = CONFIG.get('telegram', {}).get('token')
TELEGRAM_CHAT_ID = CONFIG.get('telegram', {}).get('chat_id')
TMDB_API_TOKEN = CONFIG.get('tmdb', {}).get('api_token')
HTTP_PROXY = CONFIG.get('proxy', {}).get('http_proxy')
settings = CONFIG.get('settings', {})
TIMEZONE = ZoneInfo(settings.get('timezone', 'UTC'))
PLAYBACK_DEBOUNCE_SECONDS = settings.get('debounce_seconds', 10)
MEDIA_BASE_PATH = settings.get('media_base_path')
POSTER_CACHE_TTL_DAYS = settings.get('poster_cache_ttl_days', 30)
EMBY_SERVER_URL = CONFIG.get('emby', {}).get('server_url')
EMBY_API_KEY = CONFIG.get('emby', {}).get('api_key')
EMBY_USER_ID = CONFIG.get('emby', {}).get('user_id')
EMBY_REMOTE_URL = CONFIG.get('emby', {}).get('remote_url')
APP_SCHEME = CONFIG.get('emby', {}).get('app_scheme')

NEW_LIBRARY_CHAT_ID = CONFIG.get('telegram', {}).get('new_library_chat_id')
NEW_LIBRARY_CHANNEL_ID = CONFIG.get('telegram', {}).get('new_library_channel_id')

ALLOWED_GROUP_ID = CONFIG.get('settings', {}).get('allowed_group_id')

ADMIN_CACHE = {}
GROUP_MEMBER_CACHE = {}
SEARCH_RESULTS_CACHE = {}

EVENT_TYPES_TO_MANAGE = {
    'playback.start': '▶️ 开始/继续播放',
    'playback.pause': '⏸️ 暂停播放',
    'playback.stop': '⏹️ 停止播放',
    'library.new': '✅ 新增媒体',
    'library.deleted': '❌ 删除媒体',
}
NOTIFICATION_SETTINGS = {}

def load_notification_settings():
    global NOTIFICATION_SETTINGS
    config_events = CONFIG.get('settings', {}).get('notification_events', {})

    for event, _ in EVENT_TYPES_TO_MANAGE.items():
        if event in config_events:
            NOTIFICATION_SETTINGS[event] = config_events[event]
        else:
            NOTIFICATION_SETTINGS[event] = True

def save_notification_settings():
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            full_config = yaml.safe_load(f)

        if 'settings' not in full_config:
            full_config['settings'] = {}
        if 'notification_events' not in full_config['settings']:
            full_config['settings']['notification_events'] = {}

        full_config['settings']['notification_events'] = NOTIFICATION_SETTINGS

        with open(CONFIG_PATH, 'w', encoding='utf-8') as f:
            yaml.dump(full_config, f, allow_unicode=True, sort_keys=False)

    except Exception as e:
        print(f"❌ 保存通知设置失败: {e}")

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


load_notification_settings()
load_poster_cache()
recent_playback_notifications = {}
load_language_map()

user_context = {}
user_search_state = {}

if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
    print("错误：环境变量未正确设置")
    exit(1)

def make_request_with_retry(method, url, max_retries=3, retry_delay=1, **kwargs):
    api_name = "Unknown API"
    if "api.telegram.org" in url:
        api_name = "Telegram"
    elif "api.themoviedb.org" in url:
        api_name = "TMDB"
    elif "ip-api.com" in url:
        api_name = "IP Geolocation"
    elif EMBY_SERVER_URL and EMBY_SERVER_URL in url:
        api_name = "Emby"

    attempts = 0
    while attempts < max_retries:
        try:
            response = requests.request(method, url, **kwargs)
            if 200 <= response.status_code < 300:
                return response
            else:
                try:
                    error_text = response.content.decode('utf-8')
                except UnicodeDecodeError:
                    error_text = response.text
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

def get_ip_geolocation(ip):
    if not ip or ip.startswith('192.168.') or ip.startswith('10.') or ip.startswith('172.'):
        return "局域网"
    
    url = f"http://ip-api.com/json/{ip}?fields=status,message,country,regionName,city,isp&lang=zh-CN"
    response = make_request_with_retry('GET', url, timeout=5)

    if response and response.json().get('status') == 'success':
        data = response.json()
        isp_map = {
            'Chinanet': '中国电信', 'China Telecom': '中国电信',
            'China Unicom': '中国联通', 'CHINA169': '中国联通',
            'CNC Group': '中国联通', 'China Netcom': '中国联通',
            'China Mobile': '中国移动', 'China Broadcasting': '中国广电', 
            'Tencent': '腾讯云', 'Alibaba': '阿里云'
        }
        isp_en = data.get('isp', '')
        isp = isp_en
        for keyword, name in isp_map.items():
            if keyword.lower() in isp_en.lower():
                isp = name
                break
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

        tmdb_id = None
        if exact_match:
            tmdb_id = exact_match.get('id')
        else:
            results.sort(key=lambda x: (x.get('popularity', 0)), reverse=True)
            tmdb_id = results[0].get('id')
        return tmdb_id
    
    print(f"❌ TMDB 搜索失败")
    return None

def extract_year_from_path(path):
    if not path:
        return None
    match = re.search(r'\((\d{4})\)', path)
    if match:
        year = match.group(1)
        return year
    return None

def get_program_type_from_path(path):
    if not MEDIA_BASE_PATH or not path or not path.startswith(MEDIA_BASE_PATH):
        return None

    relative_path = path[len(MEDIA_BASE_PATH):]

    parts = relative_path.split('/')
    if parts and parts[0]:
        program_type = parts[0]
        return program_type
    return None

def get_media_details(item, user_id):
    details = {'poster_url': None, 'tmdb_link': None, 'year': None, 'tmdb_id': None}
    if not TMDB_API_TOKEN:
        print("❌ TMDB API Token 未设置，跳过详情获取")
        return details

    item_type = item.get('Type')
    tmdb_id = None
    api_type = None

    if item_type == 'Movie':
        details['year'] = item.get('ProductionYear')
    elif item_type in ['Episode', 'Series']:
        year_from_path = extract_year_from_path(item.get('Path'))
        if year_from_path:
            details['year'] = year_from_path
        else:
            details['year'] = item.get('ProductionYear')

    if item_type == 'Movie':
        api_type = 'movie'
        provider_ids = item.get('ProviderIds', {})
        tmdb_id = provider_ids.get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/movie/{tmdb_id}"
            details['tmdb_id'] = tmdb_id

    elif item_type == 'Series':
        api_type = 'tv'
        provider_ids = item.get('ProviderIds', {})
        tmdb_id = provider_ids.get('Tmdb')
        if tmdb_id:
            details['tmdb_link'] = f"https://www.themoviedb.org/tv/{tmdb_id}"
            details['tmdb_id'] = tmdb_id

    elif item_type == 'Episode':
        api_type = 'tv'
        series_tmdb_id = None
        series_provider_ids = item.get('SeriesProviderIds') or item.get('Series', {}).get('ProviderIds')
        if series_provider_ids and 'Tmdb' in series_provider_ids:
            series_tmdb_id = series_provider_ids.get('Tmdb')
        
        if not series_tmdb_id:
            series_id = item.get('SeriesId')
            if all([EMBY_SERVER_URL, EMBY_API_KEY, series_id]):
                request_user_id = user_id or EMBY_USER_ID
                if not request_user_id:
                    print("⚠️ 警告：无法确定用于查询的 UserID，将尝试使用系统级路径。")
                    url = f"{EMBY_SERVER_URL}/Items/{series_id}"
                else:
                    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{series_id}"

                params = {'api_key': EMBY_API_KEY}
                response = make_request_with_retry('GET', url, params=params, timeout=10)
                if response:
                    provider_ids = response.json().get('ProviderIds', {})
                    series_tmdb_id = provider_ids.get('Tmdb')

        if not series_tmdb_id:
            series_name = item.get('SeriesName') or item.get('Series', {}).get('Name')
            year_for_search = details.get('year')
            series_tmdb_id = search_tmdb_by_title(series_name, year_for_search, media_type='tv')
        
        if series_tmdb_id:
            tmdb_id = series_tmdb_id
            details['tmdb_id'] = series_tmdb_id
            season_num = item.get('ParentIndexNumber')
            episode_num = item.get('IndexNumber')
            if season_num is not None and episode_num is not None:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{series_tmdb_id}/season/{season_num}/episode/{episode_num}"
            else:
                details['tmdb_link'] = f"https://www.themoviedb.org/tv/{series_tmdb_id}"

    if not tmdb_id:
        return details

    if tmdb_id in POSTER_CACHE:
        cached_item = POSTER_CACHE[tmdb_id]
        cached_time = datetime.fromisoformat(cached_item['timestamp'])
        if datetime.now() - cached_time < timedelta(days=POSTER_CACHE_TTL_DAYS):
            details['poster_url'] = cached_item['url']
            return details

    url = f"https://api.themoviedb.org/3/{api_type}/{tmdb_id}?api_key={TMDB_API_TOKEN}&language=zh-CN"
    response = make_request_with_retry('GET', url, timeout=10, proxies={'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None)

    if response:
        poster_path = response.json().get('poster_path')
        if poster_path:
            details['poster_url'] = f"https://image.tmdb.org/t/p/w500{poster_path}"
            
            POSTER_CACHE[tmdb_id] = {
                'url': details['poster_url'],
                'timestamp': datetime.now().isoformat()
            }
            save_poster_cache()

    return details

def format_ticks_to_hms(ticks):
    if not isinstance(ticks, (int, float)) or ticks <= 0:
        return "00:00:00"
    seconds = ticks / 10_000_000
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"

def send_simple_telegram_message(text, chat_id, delay_seconds=60):
    target_chat_id = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not target_chat_id: return

    send_deletable_telegram_notification(text, chat_id=target_chat_id, delay_seconds=delay_seconds)

def send_deletable_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, delay_seconds=60, disable_preview=False):
    async def send_and_delete():
        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        target_chat_id = chat_id if chat_id else TELEGRAM_CHAT_ID
        if not target_chat_id:
            return

        api_url_base = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/"

        payload = {
            'chat_id': target_chat_id,
            'parse_mode': 'MarkdownV2'
        }

        if disable_preview:
            payload['disable_web_page_preview'] = True

        if inline_buttons:
            if inline_buttons and isinstance(inline_buttons[0], list):
                keyboard_layout = inline_buttons
            else:
                keyboard_layout = [[button] for button in inline_buttons]
            payload['reply_markup'] = json.dumps({'inline_keyboard': keyboard_layout})

        if photo_url:
            api_url = api_url_base + 'sendPhoto'
            payload['photo'] = photo_url
            payload['caption'] = text
        else:
            api_url = api_url_base + 'sendMessage'
            payload['text'] = text

        try:
            max_retries = 3
            retry_delay = 1
            attempts = 0
            response = None

            while attempts < max_retries:
                try:
                    response = requests.post(api_url, data=payload, timeout=20, proxies=proxies)
                    if response.status_code == 200:
                        break
                    else:
                        print(f"❌ Telegram API 请求失败 (发送消息) (第 {attempts + 1} 次)，状态码: {response.status_code} - {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"❌ Telegram API 请求时发生网络错误 (发送消息) (第 {attempts + 1} 次): {e}")

                attempts += 1
                if attempts < max_retries:
                    await asyncio.sleep(retry_delay)
            
            if response is None or response.status_code != 200:
                print(f"❌ 发送可删除消息失败，已达到最大重试次数 ({max_retries} 次)。")
                return

            sent_message = response.json().get('result', {})
            message_id = sent_message.get('message_id')
            if not message_id:
                return
            
            if delay_seconds <= 0:
                return

            await asyncio.sleep(delay_seconds)
            
            delete_url = api_url_base + 'deleteMessage'
            delete_payload = {'chat_id': target_chat_id, 'message_id': message_id}
            delete_max_retries = 3
            delete_retries = 0

            while delete_retries < delete_max_retries:
                try:
                    del_response = requests.post(delete_url, data=delete_payload, timeout=10, proxies=proxies)
                    
                    if del_response.status_code == 200:
                        return
                    elif 'message to delete not found' in del_response.text:
                        return
                    else:
                        delete_retries += 1
                        if delete_retries < delete_max_retries:
                            await asyncio.sleep(30)
                except Exception as e:
                    print(f"❌ 删除消息失败: {e}")
                    delete_retries += 1
                    if delete_retries < delete_max_retries:
                        await asyncio.sleep(30)

            if delete_retries == delete_max_retries:
                print(f"❌ 达到最大重试次数，放弃删除消息 ID: {message_id}")

        except Exception as e:
            print(f"执行 send_and_delete 时发生严重错误: {e}")

    threading.Thread(target=lambda: asyncio.run(send_and_delete())).start()

def send_telegram_notification(text, photo_url=None, chat_id=None, inline_buttons=None, disable_preview=False):
    target_chat_id = chat_id if chat_id else TELEGRAM_CHAT_ID
    if not target_chat_id:
        print("错误：未指定 chat_id 且配置文件中也未设置。")
        return

    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/" + ('sendPhoto' if photo_url else 'sendMessage')

    payload = {'chat_id': target_chat_id, 'parse_mode': 'MarkdownV2'}

    if photo_url:
        payload['photo'] = photo_url
        payload['caption'] = text
    else:
        payload['text'] = text

    if disable_preview:
        payload['disable_web_page_preview'] = True

    if inline_buttons and isinstance(inline_buttons, list):
        if inline_buttons and isinstance(inline_buttons[0], list):
            keyboard_layout = inline_buttons
        else:
            keyboard_layout = [[button] for button in inline_buttons]
        keyboard = {'inline_keyboard': keyboard_layout}
        payload['reply_markup'] = json.dumps(keyboard)

    make_request_with_retry('POST', api_url, data=payload, timeout=20, proxies=proxies)

def answer_callback_query(callback_query_id, text=None, show_alert=False):
    params = {'callback_query_id': callback_query_id}
    if text:
        params['text'] = text
    params['show_alert'] = show_alert

    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/answerCallbackQuery"
    make_request_with_retry('POST', url, params=params, timeout=5, proxies=proxies)

def edit_telegram_message(chat_id, message_id, text, inline_buttons=None):
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/editMessageText"

    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text,
        'parse_mode': 'MarkdownV2'
    }

    if inline_buttons:
        keyboard = {'inline_keyboard': inline_buttons}
        payload['reply_markup'] = json.dumps(keyboard)
    
    make_request_with_retry('POST', url, json=payload, timeout=10, proxies=proxies)

def delete_telegram_message(chat_id, message_id):
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
    payload = {'chat_id': chat_id, 'message_id': message_id}
    make_request_with_retry('POST', url, data=payload, timeout=10, proxies=proxies)

def get_active_sessions():
    if not EMBY_SERVER_URL or not EMBY_API_KEY:
        print("错误：Emby 服务器地址或 API 密钥未在配置中设置。")
        return []
    
    url = f"{EMBY_SERVER_URL}/Sessions"
    params = {'api_key': EMBY_API_KEY, 'activeWithinSeconds': 360}
    response = make_request_with_retry('GET', url, params=params, timeout=15)
    
    if response:
        sessions = response.json()
        return [s for s in sessions if s.get('NowPlayingItem')]
    else:
        print(f"查询 Emby 会话失败，已达最大重试次数。")
        return []

def get_active_sessions_info(user_id):
    sessions = get_active_sessions()
    if not sessions:
        return "✅ 当前无人观看 Emby。"

    sessions_data = []
    for session in sessions:
        item = session.get('NowPlayingItem', {})
        session_user_id = session.get('UserId')
        session_id = session.get('Id')

        media_details = get_media_details(item, session_user_id)
        tmdb_link = media_details.get('tmdb_link')
        year = media_details.get('year')

        raw_user_name = session.get('UserName', '未知用户')
        raw_player = session.get('Client', '未知播放器')
        raw_device = session.get('DeviceName', '未知设备')

        ip_address = session.get('RemoteEndPoint', '').split(':')[0]
        location = get_ip_geolocation(ip_address)
        raw_location_str = f"{ip_address} {location}" if location != "局域网" else "局域网"

        raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name') or '未知标题'
        year_str = f" ({year})" if year else ""

        raw_episode_info = ""
        if item.get('Type') == 'Episode':
            s_num = item.get('ParentIndexNumber')
            e_num = item.get('IndexNumber')
            e_name_raw = item.get('Name')
            if s_num is not None and e_num is not None:
                raw_episode_info = f" S{s_num:02d}E{e_num:02d} {e_name_raw or ''}"
            else:
                raw_episode_info = f" {e_name_raw or ''}"
        
        pos_ticks = session.get('PlayState', {}).get('PositionTicks', 0)
        run_ticks = item.get('RunTimeTicks')
        raw_progress_text = "N/A"
        if run_ticks and run_ticks > 0:
            percent = (pos_ticks / run_ticks) * 100
            pos_hms = format_ticks_to_hms(pos_ticks)
            run_hms = format_ticks_to_hms(run_ticks)
            raw_progress_text = f"{percent:.1f}% ({pos_hms} / {run_hms})"

        raw_program_type = get_program_type_from_path(item.get('Path'))
        timestamp = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')

        program_full_title_raw = f"{raw_title}{year_str}{raw_episode_info}"
        
        if tmdb_link:
            program_line = f"[{escape_markdown(program_full_title_raw)}]({tmdb_link})"
        else:
            program_line = f"{escape_markdown(program_full_title_raw)}"

        session_lines = [
            f"👤 *用户*: {escape_markdown(raw_user_name)}",
            f"*{escape_markdown('─' * 20)}*",
            f"播放器：{escape_markdown(raw_player)}",
            f"设备：{escape_markdown(raw_device)}",
            f"位置：{escape_markdown(raw_location_str)}",
            f"节目：{program_line}",
            f"进度：{escape_markdown(raw_progress_text)}",
        ]
        if raw_program_type:
            session_lines.append(f"节目类型：{escape_markdown(raw_program_type)}")

        session_lines.append(f"时间：{escape_markdown(timestamp)}")
        session_message = "\n".join(session_lines)

        buttons = []
        view_button_row = []
        if EMBY_REMOTE_URL:
            item_id = item.get('Id')
            server_id = item.get('ServerId')
            if item_id and server_id:
                item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
                view_button_row.append({'text': '▶️ 在服务器中查看', 'url': item_url})
        
        if view_button_row:
            buttons.append(view_button_row)
        
        action_button_row = []
        if session_id:
            action_button_row.append({'text': '❌ 终止会话', 'callback_data': f'session_terminate_{session_id}_{user_id}'})
            action_button_row.append({'text': '💬 发送消息', 'callback_data': f'session_message_{session_id}_{user_id}'})
        
        if action_button_row:
            buttons.append(action_button_row)
            
        sessions_data.append({'message': session_message, 'buttons': buttons if buttons else None})

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
        print(f"⚠️ 警告: Item ID {item_id} 无法确定 UserID，将尝试使用系统级路径。")
        url = f"{EMBY_SERVER_URL}/Items/{item_id}"
    else:
        url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"

    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)

    if not response:
        print(f"错误查询 Item ID {item_id}")
        return "未知分辨率"

    item_data = response.json()
    media_sources = item_data.get('MediaSources', [])
    if not media_sources:
        return "未知分辨率"

    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video':
            width = stream.get('Width', 0)
            height = stream.get('Height', 0)
            if width and height:
                return f"{width}x{height}"
    return "未知分辨率"

def get_series_season_media_info(series_id):
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        return ["错误：此功能需要配置 Emby User ID"]

    seasons_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
    seasons_params = {'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Season'}
    seasons_response = make_request_with_retry('GET', seasons_url, params=seasons_params, timeout=10)

    if not seasons_response:
        return ["查询季度列表失败"]

    seasons = seasons_response.json().get('Items', [])
    if not seasons:
        return ["未找到任何季度"]

    season_info_lines = []
    for season in sorted(seasons, key=lambda s: s.get('IndexNumber', 0)):
        season_num = season.get('IndexNumber')
        season_id = season.get('Id')
        if season_num is None or season_id is None:
            continue

        episodes_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
        episodes_params = {
            'api_key': EMBY_API_KEY, 'ParentId': season_id, 'IncludeItemTypes': 'Episode',
            'Limit': 1, 'Fields': 'Id', 'SortBy': 'IndexNumber', 'SortOrder': 'Ascending'
        }
        episodes_response = make_request_with_retry('GET', episodes_url, params=episodes_params, timeout=10)

        season_line = f"S{season_num:02d}：\n        规格未知"
        if episodes_response:
            first_episode_list = episodes_response.json().get('Items', [])
            if first_episode_list:
                first_episode_id = first_episode_list[0].get('Id')
                stream_details = get_media_stream_details(first_episode_id, request_user_id)
                
                if stream_details:
                    formatted_parts = format_stream_details_message(stream_details, is_season_info=True)
                    if formatted_parts:
                        escaped_parts = [escape_markdown(part) for part in formatted_parts]
                        season_line = f"S{season_num:02d}：\n" + "\n".join(escaped_parts)

        season_info_lines.append(season_line)

    return season_info_lines if season_info_lines else ["未找到剧集规格信息"]

def _get_latest_episode_info(series_id):
    request_user_id = EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, series_id, request_user_id]):
        if not request_user_id:
              print("⚠️ 警告: _get_latest_episode_info 需要配置全局 Emby User ID。")
        return {}

    api_endpoint = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"

    latest_episode_params = {
        'api_key': EMBY_API_KEY, 'ParentId': series_id, 'IncludeItemTypes': 'Episode',
        'Recursive': 'true', 'SortBy': 'ParentIndexNumber,IndexNumber', 'SortOrder': 'Descending', 'Limit': 1,
        'Fields': 'ProviderIds,Path,ServerId,DateCreated,ParentIndexNumber,IndexNumber,SeriesName,SeriesProviderIds,Overview'
    }

    response = make_request_with_retry('GET', api_endpoint, params=latest_episode_params, timeout=15)
    if response and response.json().get('Items'):
        return response.json()['Items'][0]
    
    return {}

def get_tmdb_season_details(series_tmdb_id, season_number):
    if not all([TMDB_API_TOKEN, series_tmdb_id, season_number is not None]):
        return None

    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
    url = f"https://api.themoviedb.org/3/tv/{series_tmdb_id}/season/{season_number}"
    params = {'api_key': TMDB_API_TOKEN, 'language': 'zh-CN'}
    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)

    if response:
        data = response.json()
        episodes = data.get('episodes', [])
        if not episodes:
            return None
        
        total_episodes = len(episodes)
        last_episode = episodes[-1]
        is_finale_marked = last_episode.get('episode_type') == 'finale'
        
        return {'total_episodes': total_episodes, 'is_finale_marked': is_finale_marked}
    else:
        print(f"❌ TMDB 季度详情请求失败")
        return None

def search_emby_and_format(query, chat_id, user_id, is_group_chat, mention):
    year_for_filter = None
    search_term = query.strip()
    match = re.search(r'(\d{4})$', search_term)
    if match:
        year_for_filter = match.group(1)
        search_term = search_term[:match.start()].strip()
    else:
        search_term = query.strip()

    if not search_term:
        send_deletable_telegram_notification("关键词无效！输入的关键词中必须包含节目名称的关键词。", chat_id=chat_id, delay_seconds=60)
        return

    try:
        request_user_id = EMBY_USER_ID
        if not request_user_id:
            send_deletable_telegram_notification("错误：机器人管理员尚未在配置文件中设置 Emby `user_id`，搜索功能无法使用。", chat_id=chat_id)
            return

        url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items"
        params = {
            'api_key': EMBY_API_KEY,
            'SearchTerm': search_term,
            'IncludeItemTypes': 'Movie,Series',
            'Recursive': 'true',
            'Fields': 'ProviderIds,Path,ProductionYear,Name'
        }
        if year_for_filter:
            params['Years'] = year_for_filter

        response = make_request_with_retry('GET', url, params=params, timeout=20)
        if not response:
            send_deletable_telegram_notification(f"搜索失败，无法连接到 Emby API。", chat_id=chat_id, delay_seconds=60)
            return

        results = response.json().get('Items', [])
        if not results:
            send_deletable_telegram_notification(f"在 Emby 中找不到与“{escape_markdown(query)}”相关的任何内容。", chat_id=chat_id, delay_seconds=60)
            return

        search_id = str(uuid.uuid4())
        SEARCH_RESULTS_CACHE[search_id] = results
        
        send_search_results_page(chat_id, search_id, user_id, page=1)

    except Exception as e:
        import traceback
        traceback.print_exc()
        send_simple_telegram_message(f"搜索过程中发生严重错误: {escape_markdown(str(e))}", chat_id=chat_id)

def send_search_results_page(chat_id, search_id, user_id, page=1, message_id=None):
    if search_id not in SEARCH_RESULTS_CACHE:
        if message_id:
            edit_telegram_message(chat_id, message_id, "抱歉，此搜索结果已过期，请重新发起搜索。")
        else:
            send_deletable_telegram_notification("抱歉，此搜索结果已过期，请重新发起搜索。", chat_id=chat_id)
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
        
        raw_program_type = get_program_type_from_path(item.get('Path'))
        
        button_text = f"{i + 1 + start_index}. {title_with_year}"
        if raw_program_type:
            button_text += f" | {raw_program_type}"

        buttons.append([{'text': button_text, 'callback_data': f'search_detail_{search_id}_{start_index + i}_{user_id}'}])

    page_buttons = []
    if page > 1:
        page_buttons.append({'text': '◀️ 上一页', 'callback_data': f'search_page_{search_id}_{page-1}_{user_id}'})
    if end_index < len(results):
        page_buttons.append({'text': '下一页 ▶️', 'callback_data': f'search_page_{search_id}_{page+1}_{user_id}'})
    
    if page_buttons:
        buttons.append(page_buttons)

    if message_id:
        edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else:
        send_deletable_telegram_notification(message_text, chat_id=chat_id, inline_buttons=buttons, delay_seconds=90)

def get_media_stream_details(item_id, user_id=None):
    request_user_id = user_id or EMBY_USER_ID
    if not all([EMBY_SERVER_URL, EMBY_API_KEY, request_user_id]):
        return None

    url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'MediaSources'}
    response = make_request_with_retry('GET', url, params=params, timeout=10)

    if not response:
        return None

    item_data = response.json()
    media_sources = item_data.get('MediaSources', [])
    if not media_sources:
        return None

    video_info = {}
    audio_info_list = []

    for stream in media_sources[0].get('MediaStreams', []):
        if stream.get('Type') == 'Video' and not video_info:
            try:
                video_title = stream.get('Title')
                if not video_title or video_title.isspace():
                    video_title = stream.get('Codec', '未知').upper()
                
                bitrate_bps = stream.get('BitRate', 0) 
                bitrate_mbps = bitrate_bps / 1_000_000
                
                video_info = {
                    'title': video_title,
                    'resolution': f"{stream.get('Width', 0)}x{stream.get('Height', 0)}",
                    'bitrate': f"{bitrate_mbps:.1f}" if bitrate_mbps > 0 else "未知",
                    'video_range': stream.get('VideoRange', '')
                }
            except Exception as e:
                video_info = {}

        elif stream.get('Type') == 'Audio':
            try:
                audio_info = {
                    'language': stream.get('Language', '未知'),
                    'codec': stream.get('Codec', '未知'),
                    'layout': stream.get('ChannelLayout', '')
                }
                audio_info_list.append(audio_info)
            except Exception as e:
                pass

    if not video_info and not audio_info_list:
        return None
        
    return {'video_info': video_info, 'audio_info': audio_info_list}

def format_stream_details_message(stream_details, is_season_info=False):
    if not stream_details:
        return []

    message_parts = []
    indent = "    " if is_season_info else "        "

    video_info = stream_details.get('video_info')
    if video_info:
        video_line_parts = []
        
        codec = video_info.get('title')
        if codec:
            video_line_parts.append(codec)

        resolution = video_info.get('resolution')
        if resolution and resolution != '0x0':
            video_line_parts.append(resolution)

        bitrate = video_info.get('bitrate', '未知')
        if bitrate != '未知':
            video_line_parts.append(f"{bitrate}Mbps")

        video_range = video_info.get('video_range')
        if video_range:
            video_line_parts.append(video_range)

        if video_line_parts:
            video_line = ' '.join(video_line_parts)
            if is_season_info:
                message_parts.append(f"{indent}视频：{video_line}")
            else:
                message_parts.append(f"视频：{video_line}")

    audio_info_list = stream_details.get('audio_info')
    if audio_info_list:
        audio_lines = []
        for a_info in audio_info_list:
            audio_line_parts = []
            lang_code = a_info.get('language', 'und').lower()
            lang_info = LANG_MAP.get(lang_code, {})
            lang_display = lang_info.get('zh', lang_code.capitalize())
            if lang_display != '未知': audio_line_parts.append(lang_display)
            codec_audio = a_info.get('codec', '').upper()
            if codec_audio and codec_audio != '未知': audio_line_parts.append(codec_audio)
            layout = a_info.get('layout', '')
            if layout and layout != '未知': audio_line_parts.append(layout)
            if audio_line_parts:
                audio_lines.append(' '.join(filter(None, audio_line_parts)))
        
        if audio_lines:
            if is_season_info:
                message_parts.append(f"{indent}音频：{', '.join(audio_lines)}")
            else:
                if len(audio_lines) == 1:
                    message_parts.append(f"音频：{audio_lines[0]}")
                else:
                    full_audio_block = "\n".join([f"{indent}{line}" for line in audio_lines])
                    message_parts.append(f"音频：\n{full_audio_block}")
            
    return message_parts

def send_search_detail(chat_id, search_id, item_index, user_id):
    if search_id not in SEARCH_RESULTS_CACHE or item_index >= len(SEARCH_RESULTS_CACHE[search_id]):
        send_deletable_telegram_notification("抱歉，此搜索结果已过期或无效，请重新发起搜索。", chat_id=chat_id)
        return

    item = SEARCH_RESULTS_CACHE[search_id][item_index]
    item_id = item.get('Id')
    
    request_user_id = EMBY_USER_ID
    if not request_user_id:
        send_deletable_telegram_notification("错误：机器人管理员尚未在配置文件中设置 Emby `user_id`，无法获取详情。", chat_id=chat_id)
        return

    full_item_url = f"{EMBY_SERVER_URL}/Users/{request_user_id}/Items/{item_id}"
    params = {'api_key': EMBY_API_KEY, 'Fields': 'ProviderIds,Path,Overview,ProductionYear,ServerId,DateCreated'}
    response = make_request_with_retry('GET', full_item_url, params=params, timeout=10)

    if not response:
        send_deletable_telegram_notification("获取详细信息失败。", chat_id=chat_id)
        return
    
    item = response.json()
    item_type = item.get('Type')
    raw_title = item.get('Name', '未知标题')
    raw_overview = item.get('Overview', '暂无剧情简介')
    final_year = extract_year_from_path(item.get('Path')) or item.get('ProductionYear') or ''
    
    media_details = get_media_details(item, request_user_id)
    poster_url = media_details.get('poster_url')
    tmdb_link = media_details.get('tmdb_link', '')

    message_parts = []
    
    title_with_year = f"{raw_title} ({final_year})" if final_year else raw_title
    if tmdb_link:
        message_parts.append(f"名称：[{escape_markdown(title_with_year)}]({tmdb_link})")
    else:
        message_parts.append(f"名称：*{escape_markdown(title_with_year)}*")
    
    item_type_cn = "电影" if item_type == 'Movie' else "剧集"
    message_parts.append(f"类型：{escape_markdown(item_type_cn)}")

    raw_program_type_from_path = get_program_type_from_path(item.get('Path'))
    if raw_program_type_from_path:
        message_parts.append(f"分类：{escape_markdown(raw_program_type_from_path)}")
    
    if raw_overview:
        overview_text = raw_overview[:150] + "..." if len(raw_overview) > 150 else raw_overview
        message_parts.append(f"剧情：{escape_markdown(overview_text)}")

    if item_type == 'Movie':
        stream_details = get_media_stream_details(item_id, request_user_id)
        formatted_parts = format_stream_details_message(stream_details)
        if formatted_parts:
            message_parts.extend([escape_markdown(part) for part in formatted_parts])
            
        update_time_line = ""
        date_created_str = item.get('DateCreated')
        if date_created_str:
            try:
                date_str_no_z = date_created_str.rstrip('Z')
                if '.' in date_str_no_z:
                    main_part, fractional_part = date_str_no_z.split('.', 1)
                    fractional_part = fractional_part[:6]
                    date_to_parse = f"{main_part}.{fractional_part}"
                else:
                    date_to_parse = date_str_no_z
                dt_naive = datetime.fromisoformat(date_to_parse)
                dt_utc = dt_naive.replace(tzinfo=ZoneInfo("UTC"))
                dt_local = dt_utc.astimezone(TIMEZONE)
                update_time_line = f"入库时间：{escape_markdown(dt_local.strftime('%Y-%m-%d %H:%M:%S'))}"
            except Exception as e:
                update_time_line = "入库时间：未知"
        if update_time_line:
            message_parts.append(update_time_line)

    elif item_type == 'Series':
        season_info_list = get_series_season_media_info(item_id)
        if season_info_list:
            formatted_info = [f"    {info}" for info in season_info_list]
            message_parts.append(f"各季规格：\n" + "\n".join(formatted_info))
        
        latest_episode = _get_latest_episode_info(item_id)
        if latest_episode:
            message_parts.append("")
            
            s_num = latest_episode.get('ParentIndexNumber')
            e_num = latest_episode.get('IndexNumber')
            update_info_raw = "信息不完整"
            if s_num is not None and e_num is not None:
                update_info_raw = f"第 {s_num} 季 第 {e_num} 集"
            
            episode_media_details = get_media_details(latest_episode, EMBY_USER_ID)
            episode_tmdb_link = episode_media_details.get('tmdb_link')
            if episode_tmdb_link:
                message_parts.append(f"\n已更新至：[{escape_markdown(update_info_raw)}]({episode_tmdb_link})")
            else:
                message_parts.append(f"\n已更新至：{escape_markdown(update_info_raw)}")
            
            date_created_str = latest_episode.get('DateCreated')
            if date_created_str:
                try:
                    date_to_parse = date_created_str.rstrip('Z')
                    if '.' in date_to_parse:
                        main_part, fractional_part = date_to_parse.split('.', 1)
                        fractional_part = fractional_part[:6]
                        date_to_parse = f"{main_part}.{fractional_part}"
                    dt_naive = datetime.fromisoformat(date_to_parse)
                    dt_utc = dt_naive.replace(tzinfo=ZoneInfo("UTC"))
                    dt_local = dt_utc.astimezone(TIMEZONE)
                    message_parts.append(f"入库时间：{escape_markdown(dt_local.strftime('%Y-%m-%d %H:%M:%S'))}")
                except Exception as e:
                    message_parts.append("入库时间：未知")
            
            update_progress_line = ""
            series_tmdb_id = media_details.get('tmdb_id')
            local_s_num = latest_episode.get('ParentIndexNumber')
            local_e_num = latest_episode.get('IndexNumber')

            if series_tmdb_id and local_s_num is not None and local_e_num is not None:
                tmdb_season_info = get_tmdb_season_details(series_tmdb_id, local_s_num)
                if tmdb_season_info:
                    update_progress_str = ""
                    tmdb_total_episodes = tmdb_season_info['total_episodes']
                    is_finale_marked = tmdb_season_info['is_finale_marked']

                    if local_e_num == tmdb_total_episodes:
                        if is_finale_marked:
                            update_progress_str = "已完结"
                        else:
                            update_progress_str = "已完结 (可能不准确)"
                    elif local_e_num < tmdb_total_episodes:
                        remaining_episodes = tmdb_total_episodes - local_e_num
                        if is_finale_marked:
                            update_progress_str = f"剩余{remaining_episodes}集待更新"
                        else:
                            update_progress_str = f"剩余{remaining_episodes}集待更新 (可能不准确)"
                    else:
                        update_progress_str = "已完结 (可能不准确)"
                    
                    if update_progress_str:
                        update_progress_line = f"更新进度：{escape_markdown(update_progress_str)}"
                else:
                    update_progress_line = f"更新进度：{escape_markdown('查询失败 (TMDB)')}"
            
            if update_progress_line:
                message_parts.append(update_progress_line)

    message = "\n".join(filter(None, message_parts))
    
    buttons = []
    
    send_deletable_telegram_notification(
        message,
        photo_url=poster_url,
        chat_id=chat_id,
        inline_buttons=buttons,
        delay_seconds=90
    )


def send_notification_settings_menu(chat_id, user_id, message_id=None):
    text_parts = ["*🔔 通知事件开关设置*\n请选择要切换状态的通知类型：\n"]
    buttons = []

    for event, label in EVENT_TYPES_TO_MANAGE.items():
        status_icon = "✅ 启用" if NOTIFICATION_SETTINGS.get(event, False) else "❌ 禁用"
        text_parts.append(f"{label}: *{status_icon}*")
        buttons.append([
            {'text': f"切换 {label}", 'callback_data': f'toggle_notify_{event}_{user_id}'}
        ])
    
    buttons.append([{'text': '完成', 'callback_data': f'close_menu_{user_id}'}])
    
    message_text = "\n".join(text_parts)

    if message_id:
        edit_telegram_message(chat_id, message_id, message_text, inline_buttons=buttons)
    else:
        send_deletable_telegram_notification(text=message_text, chat_id=chat_id, inline_buttons=buttons, delay_seconds=60)

def is_user_in_allowed_group(user_id):
    if not ALLOWED_GROUP_ID:
        return True

    if str(user_id) == str(TELEGRAM_CHAT_ID):
        return True

    now = time.time()
    
    if user_id in GROUP_MEMBER_CACHE:
        cached_data = GROUP_MEMBER_CACHE[user_id]
        is_currently_member = cached_data['is_member']
        cache_age = now - cached_data['timestamp']

        if is_currently_member and cache_age < 3600:
            return True
        elif not is_currently_member and cache_age < 1: 
            return False

    is_member = False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getChatMember"
    params = {'chat_id': ALLOWED_GROUP_ID, 'user_id': user_id}
    proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None

    response = make_request_with_retry('GET', url, params=params, timeout=10, proxies=proxies)
    if response:
        member_info = response.json().get('result', {})
        status = member_info.get('status')
        if status in ['creator', 'administrator', 'member', 'restricted']:
            is_member = True
    else:
        print(f"API确认用户 {user_id} 不在群组中，或请求失败。")

    GROUP_MEMBER_CACHE[user_id] = {'is_member': is_member, 'timestamp': now}
    return is_member

def is_user_admin_in_group(chat_id, user_id):
    if str(chat_id) == str(TELEGRAM_CHAT_ID):
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
        print(f"❌ 获取群组 {chat_id} 管理员列表失败。")
        if chat_id in ADMIN_CACHE:
            return user_id in ADMIN_CACHE[chat_id]['admins']
        return False

def handle_callback_query(callback_query):
    query_id = callback_query['id']
    data = callback_query.get('data')
    message = callback_query.get('message', {})
    clicker_id = callback_query['from']['id']
    chat_id = message['chat']['id']
    message_id = message['message_id']

    if data.startswith('search_page_'):
        parts = data.split('_')
        search_id, page, initiator_id = parts[2], int(parts[3]), parts[4]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="搜索由其他用户发起，您无法操作！", show_alert=True)
            return
        answer_callback_query(query_id)
        send_search_results_page(chat_id, search_id, int(initiator_id), page, message_id)
        return

    if data.startswith('search_detail_'):
        parts = data.split('_')
        search_id, item_index, initiator_id = parts[2], int(parts[3]), parts[4]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="搜索由其他用户发起，您无法操作！", show_alert=True)
            return
        answer_callback_query(query_id, text="正在获取详细信息...")
        send_search_detail(chat_id, search_id, item_index, int(initiator_id))
        return

    if data.startswith('toggle_notify_'):
        parts = data.split('_')
        initiator_id = parts[-1]
        event_to_toggle = '_'.join(parts[2:-1])

        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        if event_to_toggle in NOTIFICATION_SETTINGS:
            NOTIFICATION_SETTINGS[event_to_toggle] = not NOTIFICATION_SETTINGS[event_to_toggle]
            save_notification_settings()
            answer_callback_query(query_id, text=f"设置已更新: {EVENT_TYPES_TO_MANAGE[event_to_toggle]}")
            send_notification_settings_menu(chat_id, int(initiator_id), message_id)
        else:
            answer_callback_query(query_id, text="错误：未知的设置项", show_alert=True)
        return

    if data.startswith('close_menu_'):
        initiator_id = data.split('_')[2]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        delete_telegram_message(chat_id, message_id)
        send_simple_telegram_message("✅ 设置菜单已关闭。", chat_id)
        return

    if data.startswith('session_broadcast_message_'):
        initiator_id = data.split('_')[3]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        user_context[chat_id] = {'state': 'awaiting_broadcast_message'}
        prompt_text = "✍️ 请输入您想*群发*给所有用户的消息内容："
        if chat_id < 0:
            prompt_text = "✍️ *请回复本消息*，输入您想*群发*给所有用户的消息内容："
        send_deletable_telegram_notification(escape_markdown(prompt_text), chat_id=chat_id, delay_seconds=60)
        return
        
    if data.startswith('session_terminate_all_ask_'):
        initiator_id = data.split('_')[4]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        confirmation_buttons = [[
            {'text': '⚠️ 是的，全部终止', 'callback_data': f'session_terminate_all_confirm_{initiator_id}'},
            {'text': '取消', 'callback_data': f'action_cancel_{initiator_id}'}
        ]]
        edit_telegram_message(chat_id, message_id, "❓ 您确定要终止*所有*正在播放的会话吗？此操作无法撤销。", confirmation_buttons)
        return

    if data.startswith('session_terminate_all_confirm_'):
        initiator_id = data.split('_')[4]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        answer_callback_query(query_id, text="正在终止所有会话...", show_alert=False)
        active_sessions = get_active_sessions()
        count = 0
        if not active_sessions:
            edit_telegram_message(chat_id, message_id, "✅ 当前已无活跃会话，无需操作。")
        else:
            for session in active_sessions:
                session_id = session.get('Id')
                if session_id and terminate_emby_session(session_id, None):
                    count += 1
            edit_telegram_message(chat_id, message_id, f"✅ 操作完成，共终止了 {count} 个会话。")
        delete_user_message_later(chat_id, message_id, delay_seconds=60)
        return

    if data.startswith('action_cancel_'):
        initiator_id = data.split('_')[2]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        answer_callback_query(query_id)
        original_text = message.get('text', '操作已取消')
        edit_telegram_message(chat_id, message_id, f"~~{original_text}~~\n\n✅ 操作已取消。")
        delete_user_message_later(chat_id, message_id, delay_seconds=60)
        return

    if data.startswith('session_terminate_'):
        parts = data.split('_')
        session_id, initiator_id = parts[2], parts[3]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        if terminate_emby_session(session_id, chat_id):
            answer_callback_query(query_id, text="✅ 会话已成功终止。", show_alert=True)
        else:
            answer_callback_query(query_id, text="❌ 终止失败，请检查日志。", show_alert=True)
            
    if data.startswith('session_message_'):
        parts = data.split('_')
        session_id, initiator_id = parts[2], parts[3]
        if str(clicker_id) != initiator_id:
            answer_callback_query(query_id, text="交互由其他用户发起，您无法操作！", show_alert=True)
            return
        if not is_user_admin_in_group(chat_id, clicker_id):
            answer_callback_query(query_id, text="抱歉，此命令仅对群组管理员开放。", show_alert=True)
            return
        answer_callback_query(query_id)
        user_context[chat_id] = {'state': 'awaiting_message_for_session', 'session_id': session_id}
        prompt_text = "✍️ 请输入您想发送给该用户的消息内容："
        if chat_id < 0:
            prompt_text = "✍️ *请回复本消息*，输入您想发送给该用户的消息内容："
        send_deletable_telegram_notification(escape_markdown(prompt_text), chat_id=chat_id, delay_seconds=60)

def handle_telegram_command(message):
    msg_text = message.get('text', '').strip()
    chat_id = message['chat']['id']
    user_id = message['from']['id']

    if not is_user_in_allowed_group(user_id):
        print(f"🚫 已拒绝来自非授权用户 {user_id} 的访问 (静默处理)。")
        return

    is_group_chat = chat_id < 0
    is_reply = 'reply_to_message' in message

    user_info = message.get('from', {})
    user_name = user_info.get('username')
    mention = f"@{user_name} " if user_name and is_group_chat else ""

    if msg_text.startswith('/'):
        user_search_state.pop(chat_id, None)
        user_context.pop(chat_id, None)

    is_awaiting_input = chat_id in user_search_state or chat_id in user_context

    if is_awaiting_input:
        if not is_group_chat:
            if chat_id in user_search_state:
                del user_search_state[chat_id]
                search_emby_and_format(msg_text, chat_id, user_id, is_group_chat, mention)
            elif chat_id in user_context:
                context = user_context.pop(chat_id)
                state = context.get('state')

                if not is_user_admin_in_group(chat_id, user_id):
                    send_simple_telegram_message("抱歉，此功能仅对群组管理员开放。", chat_id)
                    return

                if state == 'awaiting_message_for_session':
                    session_id = context.get('session_id')
                    send_message_to_emby_session(session_id, msg_text, chat_id)
                elif state == 'awaiting_broadcast_message':
                    active_sessions = get_active_sessions()
                    if not active_sessions:
                        send_simple_telegram_message("当前无人观看，无需群发。", chat_id)
                    else:
                        count = 0
                        for session in active_sessions:
                            session_id = session.get('Id')
                            if session_id:
                                send_message_to_emby_session(session_id, msg_text, None)
                                count += 1
                        send_simple_telegram_message(f"✅ 已向 {count} 个会话发送群发消息。", chat_id)
            return

        elif is_reply:
            if chat_id in user_search_state:
                del user_search_state[chat_id]
                search_emby_and_format(msg_text, chat_id, user_id, is_group_chat, mention)
            elif chat_id in user_context:
                context = user_context.pop(chat_id)
                state = context.get('state')

                if not is_user_admin_in_group(chat_id, user_id):
                    send_simple_telegram_message("抱歉，此功能仅对群组管理员开放。", chat_id)
                    return

                if state == 'awaiting_message_for_session':
                    session_id = context.get('session_id')
                    send_message_to_emby_session(session_id, msg_text, chat_id)
                elif state == 'awaiting_broadcast_message':
                    active_sessions = get_active_sessions()
                    if not active_sessions:
                        send_simple_telegram_message("当前无人观看，无需群发。", chat_id)
                    else:
                        count = 0
                        for session in active_sessions:
                            session_id = session.get('Id')
                            if session_id:
                                send_message_to_emby_session(session_id, msg_text, None)
                                count += 1
                        send_simple_telegram_message(f"✅ 已向 {count} 个会话发送群发消息。", chat_id)
            return

        else:
            return

    if '@' in msg_text:
        msg_text = msg_text.split('@')[0]

    if not msg_text.startswith('/'):
        return

    admin_commands = ['/status', '/notify_settings']
    is_admin_command = any(msg_text.startswith(cmd) for cmd in admin_commands)
    if is_admin_command and not is_user_admin_in_group(chat_id, user_id):
        send_simple_telegram_message("抱歉，此命令仅对群组管理员开放。", chat_id)
        return

    if msg_text.startswith('/search'):
        search_term = msg_text[len('/search'):].strip()
        if search_term:
            search_emby_and_format(search_term, chat_id, user_id, is_group_chat, mention)
        else:
            user_search_state[chat_id] = 'awaiting_search_term'
            prompt_message = "请提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            if is_group_chat:
                prompt_message = f"{mention}请回复本消息，提供您想搜索的节目名称（可选年份）。\n例如：流浪地球 或 凡人修仙传 2025"
            send_deletable_telegram_notification(escape_markdown(prompt_message), chat_id=chat_id, delay_seconds=60)
        return

    elif msg_text == '/status':
        status_info_or_str = get_active_sessions_info(user_id)
        if isinstance(status_info_or_str, str):
            send_deletable_telegram_notification(f"{mention}{status_info_or_str}", chat_id=chat_id, delay_seconds=60)
        elif isinstance(status_info_or_str, list) and status_info_or_str:
            session_count = len(status_info_or_str)
            title_message = f"{mention}*🎬 Emby 当前播放会话数: {session_count}*"
            global_action_buttons = [[
                {'text': '💬 群发消息', 'callback_data': f'session_broadcast_message_{user_id}'},
                {'text': '❌ 终止所有', 'callback_data': f'session_terminate_all_ask_{user_id}'}
            ]]
            send_deletable_telegram_notification(text=title_message, chat_id=chat_id, inline_buttons=global_action_buttons, disable_preview=True, delay_seconds=60)
            time.sleep(0.5)
            for session_data in status_info_or_str:
                send_deletable_telegram_notification(text=session_data['message'], chat_id=chat_id, inline_buttons=session_data.get('buttons'), disable_preview=True, delay_seconds=60)
                time.sleep(0.5)
        return

    elif msg_text == '/notify_settings':
        send_notification_settings_menu(chat_id, user_id)
        return

def delete_user_message_later(chat_id, message_id, delay_seconds=60):
    async def delete_later():
        await asyncio.sleep(delay_seconds)

        proxies = {'http': HTTP_PROXY, 'https': HTTP_PROXY} if HTTP_PROXY else None
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteMessage"
        payload = {'chat_id': chat_id, 'message_id': message_id}

        max_retries = 3
        retries = 0
        retry_delay = 1

        while retries < max_retries:
            try:
                del_response = requests.post(url, data=payload, timeout=10, proxies=proxies)

                if del_response.status_code == 200:
                    return
                elif 'message to delete not found' in del_response.text:
                    return 
                else:
                    print(f"⚠️ 自动删除用户消息 ID {message_id} 时出错 (第 {retries + 1} 次): {del_response.text}")
            
            except Exception as e:
                print(f"❌ 删除用户消息时发生网络错误 (第 {retries + 1} 次): {e}")

            retries += 1
            if retries < max_retries:
                await asyncio.sleep(retry_delay)

        print(f"❌ 达到最大重试次数，放弃删除用户消息 ID: {message_id}")

    threading.Thread(target=lambda: asyncio.run(delete_later())).start()

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
            print(f"处理 Telegram 更新时发生未处理错误: {e}")
            time.sleep(5)

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_type = self.headers.get('Content-Type', '').lower()
            content_length = int(self.headers.get('Content-Length', 0))
            post_data_bytes = self.rfile.read(content_length)
            json_string = None
            if 'application/json' in content_type:
                json_string = post_data_bytes.decode('utf-8')
            elif 'application/x-www-form-urlencoded' in content_type:
                parsed_form = parse_qs(post_data_bytes.decode('utf-8'))
                if 'data' in parsed_form:
                    json_string = parsed_form['data'][0]
            if not json_string:
                return self.send_response(400)

            event_data = json.loads(json_string)
            event_type = event_data.get('Event')

            event_check_key = 'playback.start' if event_type == 'playback.unpause' else event_type
            
            if event_check_key in NOTIFICATION_SETTINGS and not NOTIFICATION_SETTINGS[event_check_key]:
                return self.send_response(204)

            item = event_data.get('Item', {})
            user = event_data.get('User', {})
            server = event_data.get('Server', {})
            session = event_data.get('Session', {})
            playback_info = event_data.get('PlaybackInfo', {})

            if event_type in ["playback.start", "playback.unpause", "playback.stop", "playback.pause", "library.new", "library.deleted"]:
                now = time.time()
                event_key = (user.get('Name'), item.get('Name', '未知项目'))

                if event_type in ["playback.start", "playback.unpause"]:
                    last_notification_time = recent_playback_notifications.get(event_key)
                    if last_notification_time and (now - last_notification_time) < PLAYBACK_DEBOUNCE_SECONDS:
                        return self.send_response(204)
                    recent_playback_notifications[event_key] = now

                user_id = user.get('Id')
                media_details = get_media_details(item, user_id)
                photo_url = media_details.get('poster_url')
                tmdb_link = media_details.get('tmdb_link')
                year = media_details.get('year')

                raw_title = item.get('SeriesName') if item.get('Type') == 'Episode' else item.get('Name', '未知标题')
                raw_overview = item.get('Overview', '')
                raw_program_type = get_program_type_from_path(item.get('Path'))
                
                action_text_map = {
                    "playback.start": "▶️ 开始播放", "playback.unpause": "▶️ 继续播放",
                    "playback.stop": "⏹️ 停止播放", "playback.pause": "⏸️ 暂停播放",
                    "library.new": "✅ 新增", "library.deleted": "❌ 删除"
                }
                action_text = action_text_map.get(event_type, "")
                item_type_cn = "剧集" if item.get('Type') in ['Episode', 'Series'] else "电影" if item.get('Type') == 'Movie' else ""

                raw_episode_info = ""
                if item.get('Type') == 'Episode':
                    s_num = item.get('ParentIndexNumber')
                    e_num = item.get('IndexNumber')
                    e_name = item.get('Name')
                    if s_num is not None and e_num is not None:
                        raw_episode_info = f" S{s_num:02d}E{e_num:02d} {e_name or ''}"
                    else:
                        raw_episode_info = f" {e_name or ''}"

                title_with_year_and_episode = f"{raw_title} ({year})" if year else raw_title
                title_with_year_and_episode += raw_episode_info

                if tmdb_link:
                    full_title_line = f"[{escape_markdown(title_with_year_and_episode)}]({tmdb_link})"
                else:
                    full_title_line = f"{escape_markdown(title_with_year_and_episode)}"

                parts = [f"{action_text}{item_type_cn} {full_title_line}"]

                if event_type == "library.new":
                    item_id = item.get('Id')
                    if item_id and item.get('Type') in ['Movie', 'Episode']:
                        resolution = get_resolution_for_item(item_id, user_id)
                        parts.append(f"分辨率：{escape_markdown(resolution)}")

                if event_type in ["library.new", "library.deleted"] and item.get('Type') == 'Series':
                    description_raw = event_data.get('Description', '')
                    if description_raw:
                        episode_list_str = description_raw.split('\n')[0].strip()
                        parts.append(f"集数：{escape_markdown(episode_list_str)}")

                if event_type not in ["library.new", "library.deleted"]:
                    raw_user_name = user.get('Name', '未知用户')
                    raw_player = session.get('Client', '')
                    raw_device = session.get('DeviceName', '')
                    ip_address = session.get('RemoteEndPoint', '').split(':')[0]
                    location = get_ip_geolocation(ip_address)
                    raw_location = "局域网" if location == "局域网" else f"{ip_address} {location}"
                    
                    if raw_user_name != '未知用户': parts.append(f"用户：{escape_markdown(raw_user_name)}")
                    if raw_player: parts.append(f"播放器：{escape_markdown(raw_player)}")
                    if raw_device: parts.append(f"设备：{escape_markdown(raw_device)}")
                    if raw_location: parts.append(f"位置：{escape_markdown(raw_location)}")

                    pos_ticks = playback_info.get('PositionTicks')
                    run_ticks = item.get('RunTimeTicks')
                    if pos_ticks is not None and run_ticks and run_ticks > 0:
                        percent = (pos_ticks / run_ticks) * 100
                        current_time_str = format_ticks_to_hms(pos_ticks)
                        total_time_str = format_ticks_to_hms(run_ticks)
                        raw_progress = f"进度：已观看 {percent:.1f}%" if event_type == "playback.stop" else f"进度：{percent:.1f}% ({current_time_str} / {total_time_str})"
                        parts.append(escape_markdown(raw_progress))
                
                if raw_program_type:
                    parts.append(f"节目类型：{escape_markdown(raw_program_type)}")
                
                if raw_overview:
                    overview = raw_overview[:150] + "..." if len(raw_overview) > 150 else raw_overview
                    parts.append(f"剧情：{escape_markdown(overview)}")
                
                timestamp = datetime.now(TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')
                parts.append(f"时间：{escape_markdown(timestamp)}")

                message = "\n".join(parts)

                button = None
                if EMBY_REMOTE_URL and event_type != "library.deleted":
                    item_id = item.get('Id')
                    server_id = item.get('ServerId') or server.get('Id')
                    if item_id and server_id:
                        item_url = f"{EMBY_REMOTE_URL}/web/index.html#!/item?id={item_id}&serverId={server_id}"
                        button = {'text': '▶️ 在服务器中查看', 'url': item_url}

                if event_type == "library.new":
                    send_telegram_notification(message, photo_url, chat_id=NEW_LIBRARY_CHANNEL_ID, inline_buttons=[button] if button else None)
                else:
                    send_deletable_telegram_notification(message, photo_url, inline_buttons=[button] if button else None, delay_seconds=60)
                
                return self.send_response(200)

            elif event_type in ["user.authenticated", "system.pending_restart", "system.update_available"]:
                server_name = event_data.get('Server', {}).get('Name', 'Emby Server')
                user_name = user.get('Name', '未知用户')
                message_map = {
                    "user.authenticated": f"👤 *用户登录*\n用户: {escape_markdown(user_name)}",
                    "system.pending_restart": f"⚠️ *系统提醒*\n服务器 {escape_markdown(server_name)} 需要重启。",
                    "system.update_available": f"⬆️ *系统更新*\n服务器 {escape_markdown(server_name)} 有新版本可用。"
                }
                message = message_map.get(event_type)
                if message:
                    send_deletable_telegram_notification(message, delay_seconds=60)
                return self.send_response(200)
            
            else:
                return self.send_response(204)

        except Exception as e:
            import traceback
            print(f"处理请求时发生未预期的错误: {e}")
            traceback.print_exc()
            self.send_response(500)
        finally:
            self.end_headers()

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
        print("="*60)
        print("⚠️ 严重警告：在 config.yaml 中未找到 'user_id' 配置。")
        print("    这可能导致部分 Emby API 请求失败 (404 Not Found)。")
        print("    强烈建议配置一个有效的用户ID以确保所有功能正常运作。")
        print("="*60)

    telegram_poll_thread = threading.Thread(target=poll_telegram_updates, daemon=True)
    telegram_poll_thread.start()

    run_server(handler_class=QuietWebhookHandler)
