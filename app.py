from flask import Flask, render_template, request, jsonify, send_file
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

app = Flask(__name__)
CORS(app)

# 配置临时文件目录
TEMP_DIR = tempfile.gettempdir()
DOWNLOAD_DIR = os.path.join(TEMP_DIR, 'video_downloads')
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def is_valid_url(url):
    """验证URL是否有效"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def extract_video_info(url):
    """提取视频信息"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
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

def download_video_direct(url, video_url, file_id):
    """直接下載視頻文件"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(video_url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()
        
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
        
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return file_path if os.path.exists(file_path) else None
        
    except Exception as e:
        return None

@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')

@app.route('/api/extract', methods=['POST'])
def extract():
    """提取视频信息API"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL不能为空'}), 400
    
    if not is_valid_url(url):
        return jsonify({'error': '无效的URL格式'}), 400
    
    try:
        # 首先嘗試使用 yt-dlp
        info = extract_video_info(url)
        if info is not None:
            formats = get_video_formats(url)
            return jsonify({
                'success': True,
                'title': info['title'],
                'duration': info['duration'],
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
                'formats': formats,
                'method': 'html_parse',
                'video_urls': html_info['video_urls']
            })
        
        return jsonify({'error': '无法提取视频信息，请检查URL是否有效或包含视频'}), 400
        
    except Exception as e:
        return jsonify({'error': f'提取失败: {str(e)}'}), 500

@app.route('/api/download', methods=['POST'])
def download():
    """下载视频API"""
    data = request.get_json()
    url = data.get('url', '').strip()
    format_id = data.get('format_id', 'best')
    video_url = data.get('video_url', None)  # 用於HTML解析方式
    
    if not url:
        return jsonify({'error': 'URL不能为空'}), 400
    
    if not is_valid_url(url):
        return jsonify({'error': '无效的URL格式'}), 400
    
    # 如果提供了直接的視頻URL（來自HTML解析），使用直接下載
    if video_url:
        try:
            file_id = str(uuid.uuid4())
            downloaded_file = download_video_direct(url, video_url, file_id)
            if downloaded_file:
                return jsonify({
                    'success': True,
                    'download_url': f'/api/file/{file_id}',
                    'filename': os.path.basename(downloaded_file)
                })
            else:
                return jsonify({'error': '直接下載失敗'}), 500
        except Exception as e:
            return jsonify({'error': f'下載失敗: {str(e)}'}), 500
    
    # 嘗試使用 yt-dlp
    try:
        # 生成唯一文件名
        file_id = str(uuid.uuid4())
        output_path = os.path.join(DOWNLOAD_DIR, f'{file_id}.%(ext)s')
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        downloaded_file = None
        
        def progress_hook(d):
            nonlocal downloaded_file
            if d['status'] == 'finished':
                downloaded_file = d.get('filename')
        
        ydl_opts['progress_hooks'] = [progress_hook]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # 如果progress_hook沒有捕獲，嘗試從info獲取
            if not downloaded_file:
                downloaded_file = ydl.prepare_filename(info)
            
            # 確保文件存在
            if downloaded_file and os.path.exists(downloaded_file):
                return jsonify({
                    'success': True,
                    'download_url': f'/api/file/{file_id}',
                    'filename': os.path.basename(downloaded_file)
                })
            else:
                # 嘗試查找匹配的文件
                for filename in os.listdir(DOWNLOAD_DIR):
                    if filename.startswith(file_id):
                        file_path = os.path.join(DOWNLOAD_DIR, filename)
                        return jsonify({
                            'success': True,
                            'download_url': f'/api/file/{file_id}',
                            'filename': filename
                        })
                # yt-dlp 失敗，嘗試備用方案
                raise Exception('yt-dlp download failed')
                
    except Exception as e:
        # yt-dlp 失敗，使用備用方案
        try:
            # 如果是 Instagram，使用專門的提取方法
            if 'instagram.com' in url.lower():
                instagram_info = extract_instagram_video(url)
                if instagram_info and instagram_info['video_urls']:
                    file_id = str(uuid.uuid4())
                    video_url_to_download = instagram_info['video_urls'][0]['url']
                    downloaded_file = download_video_direct(url, video_url_to_download, file_id)
                    if downloaded_file:
                        return jsonify({
                            'success': True,
                            'download_url': f'/api/file/{file_id}',
                            'filename': os.path.basename(downloaded_file)
                        })
            
            # 使用通用 HTML 解析
            html_info = extract_video_from_html(url)
            if html_info and html_info['video_urls']:
                file_id = str(uuid.uuid4())
                # 選擇第一個可用的視頻URL
                video_url_to_download = html_info['video_urls'][0]['url']
                
                # 如果是 YouTube 或 Vimeo URL，再次嘗試 yt-dlp
                if 'youtube.com' in video_url_to_download or 'youtu.be' in video_url_to_download or 'vimeo.com' in video_url_to_download:
                    try:
                        output_path = os.path.join(DOWNLOAD_DIR, f'{file_id}.%(ext)s')
                        ydl_opts = {
                            'format': format_id,
                            'outtmpl': output_path,
                            'quiet': True,
                            'no_warnings': True,
                        }
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(video_url_to_download, download=True)
                            downloaded_file = ydl.prepare_filename(info)
                            if downloaded_file and os.path.exists(downloaded_file):
                                return jsonify({
                                    'success': True,
                                    'download_url': f'/api/file/{file_id}',
                                    'filename': os.path.basename(downloaded_file)
                                })
                    except:
                        pass
                
                # 直接下載視頻文件
                downloaded_file = download_video_direct(url, video_url_to_download, file_id)
                if downloaded_file:
                    return jsonify({
                        'success': True,
                        'download_url': f'/api/file/{file_id}',
                        'filename': os.path.basename(downloaded_file)
                    })
            
            return jsonify({'error': f'下載失敗: 無法從頁面提取視頻或下載視頻文件'}), 500
            
        except Exception as e2:
            return jsonify({'error': f'下載失敗: {str(e2)}'}), 500

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
    
    return jsonify({'error': '文件未找到'}), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

