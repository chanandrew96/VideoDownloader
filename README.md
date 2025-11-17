# Video Downloader

一個簡單易用的網頁影片下載器，支援多種影片平台。可以部署到 Render 等雲端平台。

## 功能特點

- 🎬 支援多種影片平台（YouTube、Vimeo、Twitter 等）
- 🔍 自動檢測並提取影片資訊
- ⬇️ 一鍵下載影片
- 🎨 現代化的使用者介面
- ☁️ 支援雲端部署（Render）
- 🔄 **智能備用方案**：當 yt-dlp 不支援時，自動使用 HTML 解析方式提取影片

## 技術棧

- **後端**: Python Flask
- **前端**: HTML, CSS, JavaScript
- **影片提取**: 
  - 主要方式：yt-dlp（支援大多數主流平台）
  - 備用方式：HTML 解析（使用 BeautifulSoup 和正則表達式）
- **部署**: Gunicorn

## 工作原理

應用程式採用雙重策略來提取和下載影片：

1. **主要方式（yt-dlp）**：首先嘗試使用 yt-dlp 提取影片，支援 YouTube、Vimeo、Twitter 等主流平台
2. **Instagram 專門處理**：當檢測到 Instagram URL 時，使用專門的解析方法：
   - 解析 `window._sharedData` 中的 JSON 數據
   - 提取 `video_url` 和 `video_versions` 中的影片連結
   - 從 meta 標籤中提取 og:video 內容
   - 使用正則表達式查找 Instagram CDN 的影片 URL

3. **備用方式（HTML 解析）**：當 yt-dlp 無法處理時，自動切換到 HTML 解析模式，透過以下方法提取影片：
   - 解析 `<video>` 標籤和 `<source>` 標籤
   - 提取 JSON-LD 結構化數據中的影片資訊
   - 使用正則表達式查找常見的影片 URL 模式
   - 從 iframe 嵌入中提取 YouTube/Vimeo 連結

## 本地開發

### 安裝依賴

```bash
pip install -r requirements.txt
```

### 運行應用

```bash
python app.py
```

應用將在 `http://localhost:5000` 啟動。

## 部署到 Render

### 方法一：使用 render.yaml（推薦）

1. 將此專案推送到 GitHub
2. 在 Render 中選擇 "New Blueprint"
3. 連接你的 GitHub 倉庫
4. Render 會自動讀取 `render.yaml` 並部署

### 方法二：手動部署

1. 在 Render 中創建新的 Web Service
2. 連接你的 GitHub 倉庫
3. 設置以下配置：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Environment**: Python 3

## 使用說明

1. 在輸入框中貼上影片網址
2. 點擊「搜尋影片」按鈕
3. 查看影片資訊（標題、時長等）
   - 如果使用備用方案，會顯示「(使用HTML解析)」提示
4. 點擊「下載影片」按鈕開始下載

### 支援的網站類型

- **yt-dlp 支援的網站**：YouTube、Vimeo、Twitter、Facebook 等（完整列表請參考 [yt-dlp 文檔](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)）
- **Instagram 專門支援**：
  - ✅ Instagram 貼文影片（`instagram.com/p/...`）
  - ✅ Instagram Reels（`instagram.com/reel/...`）
  - ✅ Instagram IGTV（`instagram.com/tv/...`）
  - 使用專門的解析方法從頁面 JSON 數據中提取影片 URL
- **HTML 解析備用方案**：任何包含直接影片連結的網頁（如 `<video>` 標籤、直接 MP4/WebM 連結等）

## 注意事項

- 請遵守各平台的服務條款和使用政策
- 僅下載您有權下載的內容
- 下載的檔案會暫時儲存在伺服器上，請及時下載

## 授權

請查看 LICENSE 檔案了解詳細授權資訊。
