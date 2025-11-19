# Video Downloader

一個簡單易用的網頁影片下載器，支援多種影片平台。可以部署到 Render 等雲端平台。

## 功能特點

- 🎬 支援多種影片平台（YouTube、Vimeo、Twitter 等）
- 🔍 自動檢測並提取影片資訊
- ⬇️ 一鍵下載影片
- 🎨 現代化的使用者介面
- ☁️ 支援雲端部署（Render）
- 🔄 **智能備用方案**：當 yt-dlp 不支援時，自動使用 HTML 解析方式提取影片
- 📱 **多語言支援**：繁體中文、簡體中文、英文
- 🎯 **影片預覽**：下載前可預覽影片資訊、縮略圖、描述等
- 📊 **下載進度顯示**：實時顯示下載進度和狀態訊息
- 🎚️ **格式/解析度選擇**：可自選影片格式與解析度進行下載
- 🔌 **RESTful API**：完整的 API 接口，可被其他服務調用
- 🔔 **Webhook 回調**：支持下載完成後自動回調通知
- 🔐 **API 認證**：可選的 API 密鑰認證機制

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

### 前置準備

1. **確保專案已推送到 GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/你的用戶名/VideoDownloader.git
   git push -u origin main
   ```

2. **註冊 Render 帳號**
   - 前往 [Render](https://render.com)
   - 使用 GitHub 帳號登入（推薦）

### 方法一：使用 render.yaml 自動部署（推薦）

1. **登入 Render Dashboard**
   - 前往 https://dashboard.render.com

2. **創建 Blueprint**
   - 點擊左側選單的 "Blueprints"
   - 點擊 "New Blueprint"
   - 選擇 "Public Git repository"
   - 輸入你的 GitHub 倉庫 URL（例如：`https://github.com/你的用戶名/VideoDownloader`）
   - 點擊 "Apply"

3. **自動部署**
   - Render 會自動讀取 `render.yaml` 配置文件
   - 自動設置所有必要的配置
   - 部署完成後會提供一個 URL（例如：`https://video-downloader.onrender.com`）

### 方法二：手動部署

1. **創建新的 Web Service**
   - 在 Render Dashboard 點擊 "New +"
   - 選擇 "Web Service"

2. **連接 GitHub 倉庫**
   - 選擇 "Connect GitHub"
   - 授權 Render 訪問你的 GitHub 帳號
   - 選擇 `VideoDownloader` 倉庫

3. **配置服務設置**
   - **Name**: `video-downloader`（或你喜歡的名稱）
   - **Region**: 選擇離你最近的區域（例如：Singapore）
   - **Branch**: `main`（或你的主分支名稱）
   - **Root Directory**: 留空（如果專案在根目錄）
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`

4. **設置環境變數（可選）**
   - 點擊 "Advanced" → "Add Environment Variable"
   - 如果需要，可以設置：
     - `PYTHON_VERSION`: `3.11.0`
     - `PORT`: Render 會自動設置，無需手動配置

5. **選擇方案**
   - **Free Tier**: 適合測試，但服務會在 15 分鐘無活動後休眠
   - **Starter/Pro**: 付費方案，服務始終運行

6. **部署**
   - 點擊 "Create Web Service"
   - Render 會開始構建和部署你的應用
   - 等待部署完成（通常需要 5-10 分鐘）

### 部署後檢查

1. **查看部署日誌**
   - 在 Render Dashboard 中點擊你的服務
   - 查看 "Logs" 標籤頁確認沒有錯誤

2. **測試應用**
   - 訪問 Render 提供的 URL
   - 測試影片下載功能

### 常見問題

**Q: 部署失敗，顯示 "Module not found" 錯誤**
- 確保 `requirements.txt` 包含所有依賴
- 檢查 Build Command 是否正確執行

**Q: 服務啟動後立即崩潰**
- 檢查 Start Command 是否為 `gunicorn app:app`
- 確認 `app.py` 中的 Flask 應用實例名稱為 `app`

**Q: 下載功能無法使用**
- 檢查 Render 服務的日誌查看錯誤訊息
- 確認臨時文件目錄權限正確

**Q: Free Tier 服務休眠**
- Free Tier 在 15 分鐘無活動後會休眠
- 首次訪問休眠服務需要約 30-60 秒喚醒時間
- 考慮升級到付費方案以保持服務始終運行

### 更新部署

當你推送新的更改到 GitHub 時：
- Render 會自動檢測並重新部署
- 你可以在 Dashboard 中手動觸發重新部署
- 點擊 "Manual Deploy" → "Deploy latest commit"

## 使用說明

### 網頁介面使用

1. 在輸入框中貼上影片網址
2. 點擊「搜尋影片」按鈕
3. 查看影片預覽資訊（標題、縮略圖、描述等）
   - 如果使用備用方案，會顯示「(使用HTML解析)」提示
4. 從「下載格式」下拉選單中選擇想要的格式與解析度
5. 點擊「下載影片」按鈕開始下載
6. 查看下載進度條和狀態訊息

### API 使用

本應用程式提供完整的 RESTful API，可被其他服務或應用程式調用。

**API 文檔**: 請查看 [API.md](API.md) 獲取詳細的 API 文檔

**快速開始**:
```bash
# 獲取 API 信息
curl https://your-domain.com/api/v1/info

# 提取影片信息
curl -X POST https://your-domain.com/api/v1/extract \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=..."}'

# 下載影片（支持 webhook 回調）
curl -X POST https://your-domain.com/api/v1/download \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "webhook_url": "https://your-service.com/webhook"
  }'
```

**API 認證**（可選）:
- 設置環境變數 `API_KEY` 以啟用 API 認證
- 使用 `X-API-Key` header 或 `api_key` query parameter 進行認證

### yt-dlp Cookies（可選）

若下載需登入的影片（例如受限 YouTube 內容），可提供 cookies：

- `YTDLP_COOKIES_FILE`: 指定伺服器上的 cookies.txt 檔案路徑
- `YTDLP_COOKIES`: 直接在環境變數中提供 cookies 文字（會寫入暫存檔）

上述任一方式提供即足夠；若兩者皆未設定，預設僅能下載公開影片。

#### 使用 UI 上傳 cookies（推薦）
1. 在本地電腦登入 YouTube
2. 導出 cookies.txt（可使用下方自動化腳本）
3. 於網頁介面「上傳 cookies.txt」區塊上傳檔案
4. 該 cookies 僅限目前瀏覽器 session 使用，可隨時按「清除」移除

#### 使用自動化腳本導出 cookies
專案提供 `tools/export_cookies.py`，可自動讀取瀏覽器 cookies 並輸出 cookies.txt：

```bash
pip install browser-cookie3
python tools/export_cookies.py --browser chrome --domain youtube.com --output cookies.txt
```

支援的瀏覽器包含 Chrome / Edge / Brave / Firefox 等，詳細參數請執行 `-h` 查看說明。

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
