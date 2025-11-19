from flask import Flask, render_template, request, jsonify, send_file, session
from flask_cors import CORS
import yt_dlp
import os
import tempfile
import uuid
from urllib.parse import urlparse, urljoin
import re
import requests
from bs4 import BeautifulSoup
import json
import threading
import time
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For session management
CORS(app)

# API Configuration
API_KEY = os.environ.get('API_KEY', None)  # Optional API key for authentication
API_VERSION = 'v1'

# 配置临时文件目录
TEMP_DIR = tempfile.gettempdir()
DOWNLOAD_DIR = os.path.join(TEMP_DIR, 'video_downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# 下载状态存储
download_status = {}
status_lock = threading.Lock()

# Webhook callbacks storage
webhook_callbacks = {}
webhook_lock = threading.Lock()

# Preferred download settings
PREFERRED_DEFAULT_FORMAT = 'bv*+ba/bestvideo+bestaudio/best'
MERGE_OUTPUT_FORMAT = 'mp4'

# 导入翻译数据（直接嵌入代码，不依赖外部文件）
try:
    from translations import TRANSLATIONS
    translations = TRANSLATIONS
except ImportError as e:
    print(f"Error importing translations: {e}")
    # 提供默认的英文翻译作为后备
    translations = {
        'en': {
            'app_title': 'Video Downloader',
            'subtitle': 'Enter URL, download videos easily',
            'error_url_empty': 'URL cannot be empty',
            'error_invalid_url': 'Invalid URL format',
            'search_video': 'Search Video',
            'download_video': 'Download Video',
            'processing': 'Processing...',
            'status_starting': 'Starting download...',
            'status_completed': 'Download completed!',
            'click_to_download': 'Click to download video',
            'download_prepared': 'Video download ready!',
            'download_failed': 'Download failed',
        },
        'zh-TW': {},
        'zh-CN': {}
    }

def get_language():
    """获取当前语言"""
    try:
        # 从session获取，如果没有则从请求头获取，默认繁体中文
        from flask import has_request_context
        if has_request_context():
            lang = session.get('language', request.headers.get('Accept-Language', 'zh-TW'))
        else:
            lang = 'zh-TW'  # 默认繁体中文（在请求上下文外）
    except:
        lang = 'zh-TW'  # 默认繁体中文
    
    # 简化语言代码处理
    if isinstance(lang, str) and lang.startswith('zh'):
        if 'TW' in lang or 'HK' in lang or lang == 'zh-TW':
            return 'zh-TW'
        else:
            return 'zh-CN'
    elif isinstance(lang, str) and lang.startswith('en'):
        return 'en'
    else:
        return 'zh-TW'  # 默认繁体中文

def normalize_format_id(format_id):
    """Normalize format id to avoid manifest-only downloads."""
    if not format_id or format_id.lower() in ('best', 'default'):
        return PREFERRED_DEFAULT_FORMAT
    return format_id

def t(key, lang=None):
    """翻译函数"""
    if lang is None:
        lang = get_language()
    
    if lang in translations and key in translations[lang]:
        return translations[lang][key]
    elif 'en' in translations and key in translations['en']:
        return translations['en'][key]  # 回退到英文
    else:
        return key  # 如果找不到翻译，返回key本身

def require_api_key(f):
    """API认证装饰器（如果设置了API_KEY）"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if API_KEY:
            provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if not provided_key or provided_key != API_KEY:
                return jsonify({
                    'success': False,
                    'error': 'Invalid or missing API key'
                }), 401
        return f(*args, **kwargs)
    return decorated_function

def send_webhook_callback(task_id, status_data):
    """发送webhook回调"""
    with webhook_lock:
        if task_id in webhook_callbacks:
            webhook_url = webhook_callbacks[task_id]
            try:
                requests.post(
                    webhook_url,
                    json={
                        'task_id': task_id,
                        'status': status_data.get('status'),
                        'message': status_data.get('message'),
                        'progress': status_data.get('progress'),
                        'download_url': status_data.get('download_url'),
                        'filename': status_data.get('filename'),
                        'timestamp': datetime.utcnow().isoformat()
                    },
                    timeout=5
                )
            except Exception as e:
                print(f"Webhook callback failed: {e}")

def is_valid_url(url):
    """验证URL是否有效"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def extract_video_info(url):
    """提取视频信息（包含预览信息）"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            # 获取缩略图
            thumbnail = info.get('thumbnail', '')
            if not thumbnail and info.get('thumbnails'):
                # 尝试获取最高质量的缩略图
                thumbnails = info.get('thumbnails', [])
                if thumbnails:
                    # 优先选择最大尺寸的缩略图
                    best_thumb = max(thumbnails, key=lambda x: x.get('width', 0) * x.get('height', 0), default={})
                    thumbnail = best_thumb.get('url', '') or thumbnails[-1].get('url', '')
            
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'thumbnail': thumbnail,
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'uploader_id': info.get('uploader_id', ''),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'webpage_url': info.get('webpage_url', url),
                'formats': []
            }
    except Exception as e:
        return None

def get_video_formats(url):
    """获取可用的视频格式"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'listformats': True,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = []
            
            # 获取最佳视频格式
            if 'formats' in info:
                for fmt in info['formats']:
                    if fmt.get('vcodec') != 'none':  # 有视频编码
                        formats.append({
                            'format_id': fmt.get('format_id'),
                            'ext': fmt.get('ext', 'mp4'),
                            'resolution': fmt.get('resolution', 'unknown'),
                            'filesize': fmt.get('filesize', 0),
                            'quality': fmt.get('quality', 0),
                        })
            
            return formats
    except Exception as e:
        return []

def extract_instagram_video(url):
    """專門處理 Instagram 貼文/Reels 的視頻提取"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        page_text = response.text
        video_info = {
            'title': 'Instagram Video',
            'duration': 0,
            'video_urls': [],
            'method': 'instagram_parse'
        }
        
        # 方法1: 查找 window._sharedData 或類似結構
        shared_data_patterns = [
            r'window\._sharedData\s*=\s*({.+?});',
            r'window\.__additionalDataLoaded\s*\([^,]+,\s*({.+?})\)',
        ]
        
        for pattern in shared_data_patterns:
            match = re.search(pattern, page_text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    # 遞歸查找 video_url
                    def find_video_url(obj, path=[]):
                        if isinstance(obj, dict):
                            if 'video_url' in obj:
                                return obj['video_url']
                            if 'video_versions' in obj and isinstance(obj['video_versions'], list):
                                for v in obj['video_versions']:
                                    if isinstance(v, dict) and 'url' in v:
                                        return v['url']
                            for key, value in obj.items():
                                result = find_video_url(value, path + [key])
                                if result:
                                    return result
                        elif isinstance(obj, list):
                            for item in obj:
                                result = find_video_url(item, path)
                                if result:
                                    return result
                        return None
                    
                    video_url = find_video_url(data)
                    if video_url:
                        video_info['video_urls'].append({
                            'url': video_url,
                            'type': 'video/mp4',
                            'quality': 'unknown'
                        })
                        # 提取標題
                        if 'entry_data' in data:
                            entry = data['entry_data']
                            if 'PostPage' in entry and entry['PostPage']:
                                post = entry['PostPage'][0]
                                if 'graphql' in post and 'shortcode_media' in post['graphql']:
                                    media = post['graphql']['shortcode_media']
                                    if 'edge_media_to_caption' in media and media['edge_media_to_caption']['edges']:
                                        caption = media['edge_media_to_caption']['edges'][0]['node']['text']
                                        video_info['title'] = caption[:100] if len(caption) > 100 else caption
                except:
                    pass
        
        # 方法2: 查找包含 video_url 的 JSON 數據
        json_patterns = [
            r'"video_url"\s*:\s*"([^"]+)"',
            r'"video_versions"\s*:\s*\[.*?"url"\s*:\s*"([^"]+)"',
            r'https://[^"]*instagram\.com[^"]*\.mp4[^"]*',
        ]
        
        for pattern in json_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                video_url = match.group(1) if match.lastindex else match.group(0)
                if video_url.startswith('http') and 'instagram' in video_url:
                    video_info['video_urls'].append({
                        'url': video_url,
                        'type': 'video/mp4',
                        'quality': 'unknown'
                    })
        
        # 方法3: 查找 meta 標籤中的影片 URL
        soup = BeautifulSoup(response.text, 'html.parser')
        meta_video = soup.find('meta', property='og:video')
        if meta_video and meta_video.get('content'):
            video_url = meta_video.get('content')
            if video_url.startswith('http'):
                video_info['video_urls'].append({
                    'url': video_url,
                    'type': 'video/mp4',
                    'quality': 'unknown'
                })
        
        # 提取標題
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            video_info['title'] = meta_title.get('content')
        
        # 去重
        seen_urls = set()
        unique_videos = []
        for video in video_info['video_urls']:
            if video['url'] not in seen_urls:
                seen_urls.add(video['url'])
                unique_videos.append(video)
        video_info['video_urls'] = unique_videos
        
        return video_info if video_info['video_urls'] else None
        
    except Exception as e:
        return None

def extract_video_from_html(url):
    """備用方案：從HTML頁面直接提取視頻"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        video_info = {
            'title': 'Unknown',
            'duration': 0,
            'video_urls': [],
            'method': 'html_parse'
        }
        
        # 提取標題
        title_tag = soup.find('title')
        if title_tag:
            video_info['title'] = title_tag.get_text().strip()
        
        # 查找 meta 標籤中的標題
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            video_info['title'] = meta_title.get('content')
        
        # 方法1: 查找 <video> 標籤
        video_tags = soup.find_all('video')
        for video in video_tags:
            # 查找 src 屬性
            if video.get('src'):
                video_url = urljoin(url, video.get('src'))
                video_info['video_urls'].append({
                    'url': video_url,
                    'type': video.get('type', 'video/mp4'),
                    'quality': 'unknown'
                })
            
            # 查找 <source> 標籤
            sources = video.find_all('source')
            for source in sources:
                if source.get('src'):
                    video_url = urljoin(url, source.get('src'))
                    video_info['video_urls'].append({
                        'url': video_url,
                        'type': source.get('type', 'video/mp4'),
                        'quality': source.get('data-quality', 'unknown')
                    })
        
        # 方法2: 查找 JSON-LD 結構化數據
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                # 處理列表格式的 JSON-LD
                if isinstance(data, list):
                    data = data[0] if data else {}
                
                if isinstance(data, dict):
                    if 'name' in data and video_info['title'] == 'Unknown':
                        video_info['title'] = data['name']
                    if 'contentUrl' in data:
                        video_info['video_urls'].append({
                            'url': data['contentUrl'],
                            'type': data.get('encodingFormat', 'video/mp4'),
                            'quality': 'unknown'
                        })
            except:
                pass
        
        # 方法3: 使用正則表達式查找常見的視頻URL模式
        video_patterns = [
            r'https?://[^\s"\'<>]+\.(mp4|webm|ogg|mov|avi|flv|mkv)(\?[^\s"\'<>]*)?',
            r'["\']([^"\']*\.(mp4|webm|ogg|mov|avi|flv|mkv)[^"\']*)["\']',
            r'src=["\']([^"\']*video[^"\']*)["\']',
        ]
        
        page_text = response.text
        for pattern in video_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                video_url = match.group(1) if match.lastindex else match.group(0)
                if video_url.startswith('http'):
                    video_info['video_urls'].append({
                        'url': video_url,
                        'type': 'video/mp4',
                        'quality': 'unknown'
                    })
                elif video_url.startswith('/') or video_url.startswith('./'):
                    video_url = urljoin(url, video_url)
                    video_info['video_urls'].append({
                        'url': video_url,
                        'type': 'video/mp4',
                        'quality': 'unknown'
                    })
        
        # 方法4: 查找 iframe 中的視頻（如 Vimeo, YouTube 嵌入）
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            iframe_src = iframe.get('src', '')
            if iframe_src:
                # 如果是 YouTube 或 Vimeo，嘗試提取原始 URL
                if 'youtube.com' in iframe_src or 'youtu.be' in iframe_src:
                    yt_match = re.search(r'(?:youtube\.com/embed/|youtu\.be/)([a-zA-Z0-9_-]+)', iframe_src)
                    if yt_match:
                        video_id = yt_match.group(1)
                        video_info['video_urls'].append({
                            'url': f'https://www.youtube.com/watch?v={video_id}',
                            'type': 'youtube',
                            'quality': 'unknown'
                        })
                elif 'vimeo.com' in iframe_src:
                    vimeo_match = re.search(r'vimeo\.com/(\d+)', iframe_src)
                    if vimeo_match:
                        video_id = vimeo_match.group(1)
                        video_info['video_urls'].append({
                            'url': f'https://vimeo.com/{video_id}',
                            'type': 'vimeo',
                            'quality': 'unknown'
                        })
        
        # 去重視頻URL
        seen_urls = set()
        unique_videos = []
        for video in video_info['video_urls']:
            if video['url'] not in seen_urls:
                seen_urls.add(video['url'])
                unique_videos.append(video)
        video_info['video_urls'] = unique_videos
        
        return video_info if video_info['video_urls'] else None
        
    except Exception as e:
        return None

def update_status(task_id, status, message, progress=0, lang=None, file_id=None, filename=None, download_url=None):
    """更新下載狀態"""
    if lang is None:
        lang = get_language()
    
    # 存储原始消息key和翻译后的消息
    message_key = message if message.startswith('status_') or message.startswith('error_') else None
    translated_message = t(message, lang) if message_key else message
    
    with status_lock:
        download_status[task_id] = {
            'status': status,  # 'processing', 'downloading', 'completed', 'error'
            'message': translated_message,  # 翻译后的消息（用于向后兼容）
            'message_key': message_key,  # 翻译key（用于前端重新翻译）
            'progress': progress,
            'timestamp': time.time()
        }
        if file_id:
            download_status[task_id]['file_id'] = file_id
        if filename:
            download_status[task_id]['filename'] = filename
        if download_url:
            download_status[task_id]['download_url'] = download_url
        
        # 如果状态是 completed 或 error，发送 webhook 回调
        if status in ['completed', 'error']:
            send_webhook_callback(task_id, download_status[task_id])

def download_video_direct(url, video_url, file_id, task_id=None, lang=None):
    """直接下載視頻文件"""
    if lang is None:
        lang = get_language()
    try:
        if task_id:
            update_status(task_id, 'downloading', 'status_connecting', 10, lang)
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
        # 獲取文件大小
        total_size = int(response.headers.get('content-length', 0))
        
        if task_id:
            update_status(task_id, 'downloading', 'status_preparing', 20, lang)
        
        # 確定文件擴展名
        content_type = response.headers.get('content-type', '')
        ext = 'mp4'
        if 'webm' in content_type:
            ext = 'webm'
        elif 'ogg' in content_type:
            ext = 'ogg'
        elif 'mov' in content_type:
            ext = 'mov'
        else:
            # 從URL推斷
            parsed = urlparse(video_url)
            path_ext = os.path.splitext(parsed.path)[1]
            if path_ext:
                ext = path_ext[1:]  # 移除點號
        
        file_path = os.path.join(DOWNLOAD_DIR, f'{file_id}.{ext}')
        
        downloaded_size = 0
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded_size += len(chunk)
                    
                    if task_id and total_size > 0:
                        progress = 20 + int((downloaded_size / total_size) * 70)
                        msg = f"{t('status_downloading', lang)} ({downloaded_size // 1024 // 1024}MB / {total_size // 1024 // 1024}MB)"
                        update_status(task_id, 'downloading', msg, progress, lang)
        
        if task_id:
            update_status(task_id, 'downloading', 'status_finalizing', 95, lang)
        
        return file_path if os.path.exists(file_path) else None
        
    except Exception as e:
        if task_id:
            update_status(task_id, 'error', f"{t('error_download_failed', lang)}: {str(e)}", 0, lang)
        return None

@app.route('/')
def index():
    """主页面"""
    lang = get_language()
    return render_template('index.html', lang=lang, translations_data=translations)

@app.route('/api/language', methods=['GET', 'POST'])
def set_language():
    """设置语言API"""
    if request.method == 'POST':
        data = request.get_json()
        lang = data.get('language', 'zh-TW')
        if lang in ['zh-TW', 'zh-CN', 'en']:
            session['language'] = lang
            return jsonify({'success': True, 'language': lang})
        else:
            return jsonify({'error': 'Invalid language'}), 400
    else:
        # GET请求返回当前语言
        lang = get_language()
        return jsonify({'language': lang, 'translations': translations.get(lang, {})})

@app.route('/api/extract', methods=['POST'])
def extract():
    """提取视频信息API"""
    data = request.get_json()
    url = data.get('url', '').strip()
    lang = get_language()
    
    if not url:
        return jsonify({'error': t('error_url_empty', lang)}), 400
    
    if not is_valid_url(url):
        return jsonify({'error': t('error_invalid_url', lang)}), 400
    
    try:
        # 首先嘗試使用 yt-dlp
        info = extract_video_info(url)
        if info is not None:
            formats = get_video_formats(url)
            return jsonify({
                'success': True,
                'title': info['title'],
                'duration': info['duration'],
                'thumbnail': info.get('thumbnail', ''),
                'description': info.get('description', ''),
                'uploader': info.get('uploader', ''),
                'view_count': info.get('view_count', 0),
                'upload_date': info.get('upload_date', ''),
                'webpage_url': info.get('webpage_url', url),
                'formats': formats[:10],  # 限制返回前10个格式
                'method': 'yt-dlp'
            })
        
        # yt-dlp 失敗，檢查是否為 Instagram URL
        if 'instagram.com' in url.lower():
            instagram_info = extract_instagram_video(url)
            if instagram_info and instagram_info['video_urls']:
                formats = []
                for idx, video in enumerate(instagram_info['video_urls']):
                    formats.append({
                        'format_id': f'instagram_{idx}',
                        'ext': video['type'].split('/')[-1] if '/' in video['type'] else 'mp4',
                        'resolution': video.get('quality', 'unknown'),
                        'filesize': 0,
                        'quality': 0,
                        'video_url': video['url']
                    })
                
                return jsonify({
                    'success': True,
                    'title': instagram_info['title'],
                    'duration': instagram_info['duration'],
                    'thumbnail': '',
                    'description': '',
                    'uploader': '',
                    'view_count': 0,
                    'upload_date': '',
                    'webpage_url': url,
                    'formats': formats,
                    'method': 'instagram_parse',
                    'video_urls': instagram_info['video_urls']
                })
        
        # 使用備用方案：HTML解析
        html_info = extract_video_from_html(url)
        if html_info and html_info['video_urls']:
            # 轉換格式以匹配前端期望
            formats = []
            for idx, video in enumerate(html_info['video_urls']):
                formats.append({
                    'format_id': f'html_{idx}',
                    'ext': video['type'].split('/')[-1] if '/' in video['type'] else 'mp4',
                    'resolution': video.get('quality', 'unknown'),
                    'filesize': 0,
                    'quality': 0,
                    'video_url': video['url']  # 保存實際視頻URL
                })
            
            return jsonify({
                'success': True,
                'title': html_info['title'],
                'duration': html_info['duration'],
                'thumbnail': '',
                'description': '',
                'uploader': '',
                'view_count': 0,
                'upload_date': '',
                'webpage_url': url,
                'formats': formats,
                'method': 'html_parse',
                'video_urls': html_info['video_urls']
            })
        
        return jsonify({'error': t('error_extract_failed', lang)}), 400
        
    except Exception as e:
        return jsonify({'error': f"{t('extract_failed', lang)}: {str(e)}"}), 500

def download_video_async(task_id, url, format_id, video_url, method):
    """異步下載視頻"""
    file_id = str(uuid.uuid4())
    lang = get_language()
    format_id = normalize_format_id(format_id)
    try:
        update_status(task_id, 'processing', 'status_obtaining', 5, lang)
        
        # 如果提供了直接的視頻URL（來自HTML解析），使用直接下載
        if video_url:
            update_status(task_id, 'processing', 'status_preparing', 10, lang)
            downloaded_file = download_video_direct(url, video_url, file_id, task_id, lang)
            if downloaded_file:
                download_url = f'/api/file/{file_id}'
                filename = os.path.basename(downloaded_file)
                update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                return
            else:
                update_status(task_id, 'error', 'error_direct_download_failed', 0, lang)
                return
        
        # 嘗試使用 yt-dlp
        update_status(task_id, 'processing', 'status_initializing', 15, lang)
        try:
            output_path = os.path.join(DOWNLOAD_DIR, f'{file_id}.%(ext)s')
            
            downloaded_file = None
            
            def progress_hook(d):
                nonlocal downloaded_file
                if d['status'] == 'downloading':
                    # 更新下載進度
                    if 'downloaded_bytes' in d and 'total_bytes' in d:
                        progress = 15 + int((d['downloaded_bytes'] / d['total_bytes']) * 75)
                        msg = f"{t('status_downloading', lang)} ({d['downloaded_bytes'] // 1024 // 1024}MB / {d['total_bytes'] // 1024 // 1024}MB)"
                        update_status(task_id, 'downloading', msg, progress, lang)
                    elif 'downloaded_bytes' in d and 'total_bytes_estimate' in d:
                        progress = 15 + int((d['downloaded_bytes'] / d['total_bytes_estimate']) * 75)
                        msg = f"{t('status_downloading', lang)} ({d['downloaded_bytes'] // 1024 // 1024}MB / {d['total_bytes_estimate'] // 1024 // 1024}MB estimated)"
                        update_status(task_id, 'downloading', msg, progress, lang)
                    elif '_percent_str' in d:
                        percent_str = d['_percent_str'].replace('%', '').strip()
                        try:
                            percent = float(percent_str)
                            progress = 15 + int(percent * 0.75)
                            msg = f"{t('status_downloading', lang)} {percent_str}%"
                            update_status(task_id, 'downloading', msg, progress, lang)
                        except:
                            update_status(task_id, 'downloading', 'status_downloading', 50, lang)
                elif d['status'] == 'finished':
                    downloaded_file = d.get('filename')
                    update_status(task_id, 'downloading', 'status_finalizing', 95, lang)
            
            ydl_opts = {
                'format': format_id,
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
                'merge_output_format': MERGE_OUTPUT_FORMAT,
                'progress_hooks': [progress_hook],
                'postprocessors': [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': MERGE_OUTPUT_FORMAT
                }]
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                update_status(task_id, 'processing', 'status_extracting', 20, lang)
                info = ydl.extract_info(url, download=True)
                
                # 如果progress_hook沒有捕獲，嘗試從info獲取
                if not downloaded_file:
                    downloaded_file = ydl.prepare_filename(info)
                
                # 確保文件存在
                if downloaded_file and os.path.exists(downloaded_file):
                    download_url = f'/api/file/{file_id}'
                    filename = os.path.basename(downloaded_file)
                    update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                    return
                else:
                    # 嘗試查找匹配的文件
                    for filename in os.listdir(DOWNLOAD_DIR):
                        if filename.startswith(file_id):
                            download_url = f'/api/file/{file_id}'
                            update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                            return
                    # yt-dlp 失敗，嘗試備用方案
                    raise Exception('yt-dlp download failed')
                    
        except Exception as e:
            # yt-dlp 失敗，使用備用方案
            update_status(task_id, 'processing', 'status_alternative', 30, lang)
            try:
                # 如果是 Instagram，使用專門的提取方法
                if 'instagram.com' in url.lower():
                    update_status(task_id, 'processing', 'status_instagram', 35, lang)
                    instagram_info = extract_instagram_video(url)
                    if instagram_info and instagram_info['video_urls']:
                        video_url_to_download = instagram_info['video_urls'][0]['url']
                        downloaded_file = download_video_direct(url, video_url_to_download, file_id, task_id, lang)
                        if downloaded_file:
                            download_url = f'/api/file/{file_id}'
                            filename = os.path.basename(downloaded_file)
                            update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                            return
                
                # 使用通用 HTML 解析
                update_status(task_id, 'processing', 'status_parsing', 40, lang)
                html_info = extract_video_from_html(url)
                if html_info and html_info['video_urls']:
                    # 選擇第一個可用的視頻URL
                    video_url_to_download = html_info['video_urls'][0]['url']
                    
                    # 如果是 YouTube 或 Vimeo URL，再次嘗試 yt-dlp
                    if 'youtube.com' in video_url_to_download or 'youtu.be' in video_url_to_download or 'vimeo.com' in video_url_to_download:
                        update_status(task_id, 'processing', 'status_retrying', 45, lang)
                        try:
                            output_path = os.path.join(DOWNLOAD_DIR, f'{file_id}.%(ext)s')
                            ydl_opts = {
                                'format': format_id,
                                'outtmpl': output_path,
                                'quiet': True,
                                'no_warnings': True,
                                'noplaylist': True,
                                'merge_output_format': MERGE_OUTPUT_FORMAT,
                                'postprocessors': [{
                                    'key': 'FFmpegVideoConvertor',
                                    'preferedformat': MERGE_OUTPUT_FORMAT
                                }]
                            }
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                                info = ydl.extract_info(video_url_to_download, download=True)
                                downloaded_file = ydl.prepare_filename(info)
                                if downloaded_file and os.path.exists(downloaded_file):
                                    download_url = f'/api/file/{file_id}'
                                    filename = os.path.basename(downloaded_file)
                                    update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                                    return
                        except Exception:
                            pass
                    
                    # 直接下載視頻文件
                    downloaded_file = download_video_direct(url, video_url_to_download, file_id, task_id, lang)
                    if downloaded_file:
                        download_url = f'/api/file/{file_id}'
                        filename = os.path.basename(downloaded_file)
                        update_status(task_id, 'completed', 'status_completed', 100, lang, file_id, filename, download_url)
                        return
                
                update_status(task_id, 'error', 'error_extract_or_download', 0, lang)
                
            except Exception as e2:
                update_status(task_id, 'error', f"{t('error_download_failed', lang)}: {str(e2)}", 0, lang)
    except Exception as e:
        update_status(task_id, 'error', f"{t('error_download_failed', lang)}: {str(e)}", 0, lang)

@app.route('/api/download', methods=['POST'])
def download():
    """下载视频API - 启动异步下载任务"""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = normalize_format_id(data.get('format_id', 'best'))
    video_url = data.get('video_url', None)
    method = data.get('method', 'yt-dlp')
    
    lang = get_language()
    
    if not url:
        return jsonify({'error': t('error_url_empty', lang)}), 400
    
    if not is_valid_url(url):
        return jsonify({'error': t('error_invalid_url', lang)}), 400
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    update_status(task_id, 'processing', 'status_starting', 0, lang)
    
    # 启动异步下载任务
    thread = threading.Thread(target=download_video_async, args=(task_id, url, format_id, video_url, method))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'success': True,
        'task_id': task_id
    })

@app.route('/api/status/<task_id>', methods=['GET'])
def get_status(task_id):
    """获取下载状态API"""
    lang = get_language()
    with status_lock:
        if task_id in download_status:
            status = download_status[task_id].copy()
            return jsonify(status)
        else:
            return jsonify({'error': t('error_task_not_found', lang)}), 404

@app.route('/api/file/<file_id>')
def serve_file(file_id):
    """提供文件下载"""
    # 查找匹配的文件
    for filename in os.listdir(DOWNLOAD_DIR):
        if filename.startswith(file_id):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(file_path):
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=filename
                )
    
    lang = get_language()
    return jsonify({'error': t('error_file_not_found', lang)}), 404

# ==================== API v1 Endpoints for External Services ====================

@app.route(f'/api/{API_VERSION}/info', methods=['GET'])
@require_api_key
def api_info():
    """API信息端点"""
    base_url = request.url_root.rstrip('/')
    return jsonify({
        'success': True,
        'api_version': API_VERSION,
        'endpoints': {
            'extract': f'{base_url}/api/{API_VERSION}/extract',
            'download': f'{base_url}/api/{API_VERSION}/download',
            'status': f'{base_url}/api/{API_VERSION}/status/<task_id>',
            'file': f'{base_url}/api/{API_VERSION}/file/<file_id>'
        },
        'authentication': 'X-API-Key header or api_key query parameter' if API_KEY else 'Not required'
    })

@app.route(f'/api/{API_VERSION}/extract', methods=['POST'])
@require_api_key
def api_extract():
    """提取视频信息API（供外部服务调用）"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    lang = data.get('language', 'en')  # API默认使用英文
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL is required'
        }), 400
    
    if not is_valid_url(url):
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    try:
        # 首先嘗試使用 yt-dlp
        info = extract_video_info(url)
        if info is not None:
            formats = get_video_formats(url)
            return jsonify({
                'success': True,
                'data': {
                    'title': info['title'],
                    'duration': info['duration'],
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', ''),
                    'uploader': info.get('uploader', ''),
                    'view_count': info.get('view_count', 0),
                    'upload_date': info.get('upload_date', ''),
                    'webpage_url': info.get('webpage_url', url),
                    'formats': formats[:10],
                    'method': 'yt-dlp'
                }
            })
        
        # yt-dlp 失敗，檢查是否為 Instagram URL
        if 'instagram.com' in url.lower():
            instagram_info = extract_instagram_video(url)
            if instagram_info and instagram_info['video_urls']:
                formats = []
                for idx, video in enumerate(instagram_info['video_urls']):
                    formats.append({
                        'format_id': f'instagram_{idx}',
                        'ext': video['type'].split('/')[-1] if '/' in video['type'] else 'mp4',
                        'resolution': video.get('quality', 'unknown'),
                        'filesize': 0,
                        'quality': 0,
                        'video_url': video['url']
                    })
                
                return jsonify({
                    'success': True,
                    'data': {
                        'title': instagram_info['title'],
                        'duration': instagram_info['duration'],
                        'thumbnail': '',
                        'description': '',
                        'uploader': '',
                        'view_count': 0,
                        'upload_date': '',
                        'webpage_url': url,
                        'formats': formats,
                        'method': 'instagram_parse',
                        'video_urls': instagram_info['video_urls']
                    }
                })
        
        # 使用備用方案：HTML解析
        html_info = extract_video_from_html(url)
        if html_info and html_info['video_urls']:
            formats = []
            for idx, video in enumerate(html_info['video_urls']):
                formats.append({
                    'format_id': f'html_{idx}',
                    'ext': video['type'].split('/')[-1] if '/' in video['type'] else 'mp4',
                    'resolution': video.get('quality', 'unknown'),
                    'filesize': 0,
                    'quality': 0,
                    'video_url': video['url']
                })
            
            return jsonify({
                'success': True,
                'data': {
                    'title': html_info['title'],
                    'duration': html_info['duration'],
                    'thumbnail': '',
                    'description': '',
                    'uploader': '',
                    'view_count': 0,
                    'upload_date': '',
                    'webpage_url': url,
                    'formats': formats,
                    'method': 'html_parse',
                    'video_urls': html_info['video_urls']
                }
            })
        
        return jsonify({
            'success': False,
            'error': 'Unable to extract video information'
        }), 400
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Extraction failed: {str(e)}'
        }), 500

@app.route(f'/api/{API_VERSION}/download', methods=['POST'])
@require_api_key
def api_download():
    """下载视频API（供外部服务调用）"""
    data = request.get_json() or {}
    url = data.get('url', '').strip()
    format_id = normalize_format_id(data.get('format_id', 'best'))
    video_url = data.get('video_url', None)
    method = data.get('method', 'yt-dlp')
    webhook_url = data.get('webhook_url', None)  # Optional webhook callback
    lang = data.get('language', 'en')
    
    if not url:
        return jsonify({
            'success': False,
            'error': 'URL is required'
        }), 400
    
    if not is_valid_url(url):
        return jsonify({
            'success': False,
            'error': 'Invalid URL format'
        }), 400
    
    # 生成任务ID
    task_id = str(uuid.uuid4())
    
    # 存储webhook回调URL
    if webhook_url:
        with webhook_lock:
            webhook_callbacks[task_id] = webhook_url
    
    update_status(task_id, 'processing', 'status_starting', 0, lang)
    
    # 启动异步下载任务
    thread = threading.Thread(target=download_video_async, args=(task_id, url, format_id, video_url, method))
    thread.daemon = True
    thread.start()
    
    base_url = request.url_root.rstrip('/')
    return jsonify({
        'success': True,
        'task_id': task_id,
        'status_url': f'{base_url}/api/{API_VERSION}/status/{task_id}',
        'message': 'Download task started'
    })

@app.route(f'/api/{API_VERSION}/status/<task_id>', methods=['GET'])
@require_api_key
def api_get_status(task_id):
    """获取下载状态API（供外部服务调用）"""
    with status_lock:
        if task_id in download_status:
            status = download_status[task_id].copy()
            base_url = request.url_root.rstrip('/')
            if 'download_url' in status:
                status['download_url'] = base_url + status['download_url']
            return jsonify({
                'success': True,
                'data': status
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Task not found'
            }), 404

@app.route(f'/api/{API_VERSION}/file/<file_id>', methods=['GET'])
@require_api_key
def api_get_file(file_id):
    """获取文件API（供外部服务调用）"""
    # 查找匹配的文件
    for filename in os.listdir(DOWNLOAD_DIR):
        if filename.startswith(file_id):
            file_path = os.path.join(DOWNLOAD_DIR, filename)
            if os.path.exists(file_path):
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=filename
                )
    
    return jsonify({
        'success': False,
        'error': 'File not found'
    }), 404

@app.route(f'/api/{API_VERSION}/docs', methods=['GET'])
def api_docs():
    """API文档端点"""
    base_url = request.url_root.rstrip('/')
    return jsonify({
        'title': 'Video Downloader API Documentation',
        'version': API_VERSION,
        'base_url': f'{base_url}/api/{API_VERSION}',
        'authentication': {
            'required': API_KEY is not None,
            'method': 'X-API-Key header or api_key query parameter',
            'example': 'X-API-Key: your-api-key-here'
        },
        'endpoints': {
            'GET /info': {
                'description': 'Get API information and available endpoints',
                'authentication': 'Required if API_KEY is set'
            },
            'POST /extract': {
                'description': 'Extract video information without downloading',
                'request_body': {
                    'url': 'string (required) - Video URL',
                    'language': 'string (optional) - Language code (en, zh-TW, zh-CN)'
                },
                'response': {
                    'success': 'boolean',
                    'data': {
                        'title': 'string',
                        'duration': 'number',
                        'thumbnail': 'string',
                        'description': 'string',
                        'uploader': 'string',
                        'view_count': 'number',
                        'upload_date': 'string',
                        'formats': 'array'
                    }
                }
            },
            'POST /download': {
                'description': 'Start video download task',
                'request_body': {
                    'url': 'string (required) - Video URL',
                    'format_id': 'string (optional) - Video format (default: best)',
                    'video_url': 'string (optional) - Direct video URL',
                    'method': 'string (optional) - Extraction method',
                    'webhook_url': 'string (optional) - Webhook callback URL',
                    'language': 'string (optional) - Language code'
                },
                'response': {
                    'success': 'boolean',
                    'task_id': 'string',
                    'status_url': 'string',
                    'message': 'string'
                }
            },
            'GET /status/<task_id>': {
                'description': 'Get download task status',
                'response': {
                    'success': 'boolean',
                    'data': {
                        'status': 'string (processing, downloading, completed, error)',
                        'message': 'string',
                        'progress': 'number (0-100)',
                        'download_url': 'string (if completed)',
                        'filename': 'string (if completed)'
                    }
                }
            },
            'GET /file/<file_id>': {
                'description': 'Download video file',
                'response': 'Binary file stream'
            }
        },
        'webhook': {
            'description': 'If webhook_url is provided in download request, a POST request will be sent when download completes or fails',
            'payload': {
                'task_id': 'string',
                'status': 'string',
                'message': 'string',
                'progress': 'number',
                'download_url': 'string',
                'filename': 'string',
                'timestamp': 'string (ISO 8601)'
            }
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

