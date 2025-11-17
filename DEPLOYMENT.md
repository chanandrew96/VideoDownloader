# Render 部署完整指南

這份文件提供將 Video Downloader 部署到 Render 的詳細步驟。

## 📋 目錄

1. [前置準備](#前置準備)
2. [方法一：使用 Blueprint 自動部署（推薦）](#方法一使用-blueprint-自動部署推薦)
3. [方法二：手動部署](#方法二手動部署)
4. [部署後檢查](#部署後檢查)
5. [常見問題解決](#常見問題解決)
6. [維護和更新](#維護和更新)

## 前置準備

### 1. 準備 GitHub 倉庫

如果還沒有將專案推送到 GitHub：

```bash
# 初始化 Git（如果還沒有）
git init

# 添加所有文件
git add .

# 提交更改
git commit -m "Initial commit: Video Downloader app"

# 在 GitHub 創建新倉庫後，添加遠程倉庫
git remote add origin https://github.com/你的用戶名/VideoDownloader.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

### 2. 註冊 Render 帳號

1. 前往 [Render.com](https://render.com)
2. 點擊 "Get Started for Free"
3. 使用 GitHub 帳號登入（推薦，方便連接倉庫）

## 方法一：使用 Blueprint 自動部署（推薦）

這是最簡單的方法，Render 會自動讀取 `render.yaml` 配置文件。

### 步驟

1. **登入 Render Dashboard**
   - 前往 https://dashboard.render.com
   - 使用 GitHub 帳號登入

2. **創建 Blueprint**
   - 點擊左側選單的 **"Blueprints"**
   - 點擊 **"New Blueprint"** 按鈕
   - 選擇 **"Public Git repository"**
   - 輸入你的 GitHub 倉庫 URL：
     ```
     https://github.com/你的用戶名/VideoDownloader
     ```
   - 點擊 **"Apply"**

3. **等待自動部署**
   - Render 會自動：
     - 讀取 `render.yaml` 配置文件
     - 設置所有必要的配置
     - 構建和部署應用
   - 部署過程通常需要 5-10 分鐘

4. **獲取應用 URL**
   - 部署完成後，Render 會提供一個 URL
   - 格式：`https://video-downloader.onrender.com`
   - 點擊 URL 即可訪問你的應用

## 方法二：手動部署

如果你想手動控制每個設置：

### 步驟

1. **創建新的 Web Service**
   - 在 Render Dashboard 點擊 **"New +"**
   - 選擇 **"Web Service"**

2. **連接 GitHub 倉庫**
   - 選擇 **"Connect GitHub"**
   - 如果第一次使用，需要授權 Render 訪問你的 GitHub 帳號
   - 選擇你的 `VideoDownloader` 倉庫
   - 點擊 **"Connect"**

3. **配置服務設置**
   
   填寫以下信息：
   
   - **Name**: `video-downloader`（或你喜歡的名稱）
   - **Region**: 選擇離你最近的區域
     - 例如：`Singapore`（亞洲）、`Oregon`（美國西部）
   - **Branch**: `main`（或你的主分支名稱）
   - **Root Directory**: 留空（如果專案在根目錄）
   - **Runtime**: `Python 3`
   - **Build Command**: 
     ```bash
     pip install -r requirements.txt
     ```
   - **Start Command**: 
     ```bash
     gunicorn app:app --bind 0.0.0.0:$PORT
     ```

4. **設置環境變數（可選）**
   - 點擊 **"Advanced"** 展開高級選項
   - 點擊 **"Add Environment Variable"**
   - 可以添加：
     - `PYTHON_VERSION`: `3.11.0`
     - 注意：`PORT` 變數由 Render 自動設置，無需手動配置

5. **選擇方案**
   - **Free Tier**（免費）：
     - 適合測試和小型專案
     - 服務會在 15 分鐘無活動後自動休眠
     - 首次訪問休眠服務需要 30-60 秒喚醒時間
   - **Starter/Pro**（付費）：
     - 服務始終運行，不會休眠
     - 更好的性能和穩定性
     - 適合生產環境

6. **創建服務**
   - 檢查所有設置是否正確
   - 點擊 **"Create Web Service"**
   - Render 會開始構建和部署

7. **監控部署過程**
   - 在 Dashboard 中可以看到實時構建日誌
   - 等待部署完成（通常 5-10 分鐘）

## 部署後檢查

### 1. 檢查部署狀態

- 在 Render Dashboard 中點擊你的服務
- 查看 **"Events"** 標籤頁確認部署成功
- 狀態應該顯示為 **"Live"**

### 2. 查看日誌

- 點擊 **"Logs"** 標籤頁
- 檢查是否有錯誤訊息
- 正常情況下應該看到：
  ```
  [INFO] Starting gunicorn
  [INFO] Listening at: http://0.0.0.0:XXXX
  ```

### 3. 測試應用

1. 訪問 Render 提供的 URL
2. 測試基本功能：
   - 輸入一個 YouTube 影片 URL
   - 點擊「搜尋影片」
   - 確認可以提取影片資訊
   - 測試下載功能

## 常見問題解決

### ❌ 問題 1: 部署失敗 - "Module not found"

**原因**: 依賴包未正確安裝

**解決方法**:
1. 檢查 `requirements.txt` 是否包含所有依賴
2. 確認 Build Command 為：`pip install -r requirements.txt`
3. 查看構建日誌確認所有包都成功安裝

### ❌ 問題 2: 服務啟動後立即崩潰

**原因**: Start Command 配置錯誤或應用代碼問題

**解決方法**:
1. 確認 Start Command 為：`gunicorn app:app --bind 0.0.0.0:$PORT`
2. 檢查 `app.py` 中 Flask 應用實例名稱是否為 `app`
3. 查看日誌中的錯誤訊息

### ❌ 問題 3: 下載功能無法使用

**原因**: 文件權限或臨時目錄問題

**解決方法**:
1. 檢查 Render 服務的日誌查看錯誤
2. 確認代碼中使用的臨時目錄路徑正確
3. Render 的臨時目錄通常有寫入權限

### ❌ 問題 4: Free Tier 服務休眠

**原因**: Free Tier 在無活動 15 分鐘後會自動休眠

**解決方法**:
1. 這是正常行為，首次訪問需要等待 30-60 秒喚醒
2. 考慮使用外部服務（如 UptimeRobot）定期訪問以保持服務運行
3. 或升級到付費方案

### ❌ 問題 5: 構建時間過長

**原因**: yt-dlp 等依賴包較大

**解決方法**:
1. 這是正常現象，首次構建需要下載所有依賴
2. 後續更新部署會更快（使用緩存）
3. 通常構建時間為 5-10 分鐘

### ❌ 問題 6: 某些網站無法下載

**原因**: 網站可能有反爬蟲保護或需要認證

**解決方法**:
1. 檢查日誌中的錯誤訊息
2. 某些網站可能需要特定的 User-Agent 或 Cookie
3. 可以考慮在代碼中添加更多請求頭

## 維護和更新

### 自動更新

當你推送新的更改到 GitHub 時：
- Render 會自動檢測到更改
- 自動觸發重新部署
- 你可以在 Dashboard 中看到部署進度

### 手動重新部署

1. 在 Render Dashboard 中點擊你的服務
2. 點擊 **"Manual Deploy"**
3. 選擇 **"Deploy latest commit"**
4. 等待部署完成

### 查看日誌

- 點擊服務的 **"Logs"** 標籤頁
- 可以查看實時日誌
- 幫助調試問題

### 環境變數管理

如果需要添加或修改環境變數：
1. 點擊服務的 **"Environment"** 標籤頁
2. 添加或編輯環境變數
3. 保存後服務會自動重啟

## 安全建議

1. **不要提交敏感信息**
   - 確保 `.gitignore` 包含敏感文件
   - 使用環境變數存儲 API 密鑰等

2. **定期更新依賴**
   - 定期更新 `requirements.txt` 中的包版本
   - 修復安全漏洞

3. **監控使用情況**
   - 定期檢查 Render Dashboard 的使用統計
   - 注意資源使用情況

## 成本估算

### Free Tier
- **費用**: 免費
- **限制**: 
  - 服務會在 15 分鐘無活動後休眠
  - 適合測試和小型專案

### Starter Plan
- **費用**: 約 $7/月
- **優勢**:
  - 服務始終運行
  - 更好的性能
  - 適合生產環境

## 需要幫助？

如果遇到問題：
1. 查看 Render 的 [官方文檔](https://render.com/docs)
2. 檢查應用日誌
3. 在 GitHub Issues 中提問

---

**祝部署順利！** 🚀

