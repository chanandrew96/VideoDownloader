# Video Downloader API Documentation

## Overview

The Video Downloader API allows external services and applications to programmatically extract video information and download videos from various platforms.

## Base URL

```
https://your-domain.com/api/v1
```

## Authentication

If `API_KEY` environment variable is set, all API endpoints require authentication using one of the following methods:

1. **Header** (Recommended):
   ```
   X-API-Key: your-api-key-here
   ```

2. **Query Parameter**:
   ```
   ?api_key=your-api-key-here
   ```

If `API_KEY` is not set, authentication is not required.

## Endpoints

### 1. Get API Information

**GET** `/api/v1/info`

Returns API version and available endpoints.

**Response:**
```json
{
  "success": true,
  "api_version": "v1",
  "endpoints": {
    "extract": "https://your-domain.com/api/v1/extract",
    "download": "https://your-domain.com/api/v1/download",
    "status": "https://your-domain.com/api/v1/status/<task_id>",
    "file": "https://your-domain.com/api/v1/file/<file_id>"
  },
  "authentication": "X-API-Key header or api_key query parameter"
}
```

### 2. Extract Video Information

**POST** `/api/v1/extract`

Extract video information without downloading the video.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "language": "en"  // Optional: en, zh-TW, zh-CN
}
```

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "title": "Video Title",
    "duration": 120,
    "thumbnail": "https://...",
    "description": "Video description...",
    "uploader": "Channel Name",
    "view_count": 1000000,
    "upload_date": "20240101",
    "webpage_url": "https://...",
    "formats": [
      {
        "format_id": "best",
        "ext": "mp4",
        "resolution": "1920x1080",
        "filesize": 50000000,
        "quality": 5
      }
    ],
    "method": "yt-dlp"
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Error message"
}
```

### 3. Download Video

**POST** `/api/v1/download`

Start an asynchronous video download task.

**Request Body:**
```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "format_id": "best",  // Optional: video format (default: "best")
  "video_url": null,    // Optional: direct video URL
  "method": "yt-dlp",   // Optional: extraction method
  "webhook_url": "https://your-service.com/webhook",  // Optional: webhook callback URL
  "language": "en"      // Optional: language code
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "uuid-here",
  "status_url": "https://your-domain.com/api/v1/status/uuid-here",
  "message": "Download task started"
}
```

### 4. Get Download Status

**GET** `/api/v1/status/<task_id>`

Get the status of a download task.

**Response (Success):**
```json
{
  "success": true,
  "data": {
    "status": "completed",  // processing, downloading, completed, error
    "message": "Download completed!",
    "progress": 100,
    "download_url": "https://your-domain.com/api/v1/file/file-id",
    "filename": "video.mp4",
    "timestamp": 1234567890.0
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": "Task not found"
}
```

### 5. Download Video File

**GET** `/api/v1/file/<file_id>`

Download the video file. Returns binary file stream.

**Response:**
- Success: Binary file stream with appropriate content-type
- Error: JSON error response

### 6. API Documentation

**GET** `/api/v1/docs`

Get detailed API documentation in JSON format.

## Webhook Callbacks

If you provide a `webhook_url` in the download request, the API will send a POST request to that URL when the download completes or fails.

**Webhook Payload:**
```json
{
  "task_id": "uuid-here",
  "status": "completed",  // or "error"
  "message": "Download completed!",
  "progress": 100,
  "download_url": "https://your-domain.com/api/v1/file/file-id",
  "filename": "video.mp4",
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

## Usage Examples

### Python Example

```python
import requests

API_BASE = "https://your-domain.com/api/v1"
API_KEY = "your-api-key"  # Optional

headers = {"X-API-Key": API_KEY} if API_KEY else {}

# Extract video information
response = requests.post(
    f"{API_BASE}/extract",
    json={"url": "https://www.youtube.com/watch?v=..."},
    headers=headers
)
info = response.json()

# Start download
response = requests.post(
    f"{API_BASE}/download",
    json={
        "url": "https://www.youtube.com/watch?v=...",
        "webhook_url": "https://your-service.com/webhook"
    },
    headers=headers
)
task = response.json()
task_id = task["task_id"]

# Check status
response = requests.get(
    f"{API_BASE}/status/{task_id}",
    headers=headers
)
status = response.json()

# Download file when completed
if status["data"]["status"] == "completed":
    file_url = status["data"]["download_url"]
    response = requests.get(file_url, headers=headers)
    with open("video.mp4", "wb") as f:
        f.write(response.content)
```

### cURL Example

```bash
# Extract video info
curl -X POST https://your-domain.com/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"url": "https://www.youtube.com/watch?v=..."}'

# Start download
curl -X POST https://your-domain.com/api/v1/download \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "https://www.youtube.com/watch?v=...",
    "webhook_url": "https://your-service.com/webhook"
  }'

# Check status
curl -X GET https://your-domain.com/api/v1/status/task-id \
  -H "X-API-Key: your-api-key"

# Download file
curl -X GET https://your-domain.com/api/v1/file/file-id \
  -H "X-API-Key: your-api-key" \
  -o video.mp4
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const API_BASE = 'https://your-domain.com/api/v1';
const API_KEY = 'your-api-key'; // Optional

const headers = API_KEY ? { 'X-API-Key': API_KEY } : {};

// Extract video information
async function extractVideo(url) {
  const response = await axios.post(
    `${API_BASE}/extract`,
    { url },
    { headers }
  );
  return response.data;
}

// Download video
async function downloadVideo(url, webhookUrl) {
  const response = await axios.post(
    `${API_BASE}/download`,
    {
      url,
      webhook_url: webhookUrl
    },
    { headers }
  );
  return response.data;
}

// Check status
async function checkStatus(taskId) {
  const response = await axios.get(
    `${API_BASE}/status/${taskId}`,
    { headers }
  );
  return response.data;
}

// Usage
(async () => {
  const info = await extractVideo('https://www.youtube.com/watch?v=...');
  console.log('Video info:', info);
  
  const task = await downloadVideo('https://www.youtube.com/watch?v=...');
  console.log('Task ID:', task.task_id);
  
  // Poll for status
  const interval = setInterval(async () => {
    const status = await checkStatus(task.task_id);
    console.log('Status:', status.data.status, status.data.progress + '%');
    
    if (status.data.status === 'completed') {
      clearInterval(interval);
      console.log('Download URL:', status.data.download_url);
    }
  }, 2000);
})();
```

## Error Handling

All API endpoints return standard HTTP status codes:

- `200 OK`: Request successful
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Invalid or missing API key (if required)
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

Error responses follow this format:
```json
{
  "success": false,
  "error": "Error message"
}
```

## Rate Limiting

Currently, there is no rate limiting implemented. However, it's recommended to:
- Implement reasonable delays between requests
- Use webhook callbacks instead of polling when possible
- Respect the server's resources

## Notes

- Video files are stored temporarily and may be deleted after a period of time
- Download tasks are processed asynchronously
- Use webhook callbacks to avoid polling for status
- All timestamps are in UTC ISO 8601 format
- File downloads are available for a limited time after completion

