Param(
    [string]$Browser = "chrome",
    [string]$Domain = "youtube.com",
    [string]$Output = "cookies.txt"
)

Write-Host "=== YouTube Cookies Export Helper ==="
Write-Host "Browser : $Browser"
Write-Host "Domain  : $Domain"
Write-Host "Output  : $Output"

function Ensure-Python {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        Write-Error "Python is required but was not found on PATH. Please install Python 3 and try again."
        exit 1
    }
}

function Install-Dependencies {
    Write-Host "Installing browser-cookie3 (if needed)..."
    try {
        python -m pip install --user --upgrade browser-cookie3 | Out-Null
    } catch {
        Write-Error "Failed to install browser-cookie3: $_"
        exit 1
    }
}

function Run-Exporter {
    $pythonScript = @"
import argparse
import os
import browser_cookie3

BROWSER_LOADERS = {
    'chrome': browser_cookie3.chrome,
    'chromium': browser_cookie3.chrome,
    'edge': browser_cookie3.edge,
    'brave': browser_cookie3.brave,
    'opera': browser_cookie3.opera,
    'vivaldi': browser_cookie3.brave,
    'firefox': browser_cookie3.firefox,
    'safari': browser_cookie3.safari,
}

def cookiejar_to_netscape(cj, output_path, domain_filter=None):
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('# Netscape HTTP Cookie File\\n')
        for cookie in cj:
            if domain_filter and domain_filter not in cookie.domain:
                continue
            domain = cookie.domain
            flag = 'TRUE' if domain.startswith('.') else 'FALSE'
            path = cookie.path
            secure = 'TRUE' if cookie.secure else 'FALSE'
            expires = str(int(cookie.expires or 0))
            name = cookie.name
            value = cookie.value
            if not name:
                continue
            f.write(f"{domain}\\t{flag}\\t{path}\\t{secure}\\t{expires}\\t{name}\\t{value}\\n")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', default='chrome')
    parser.add_argument('--domain', default='youtube.com')
    parser.add_argument('--output', default='cookies.txt')
    args = parser.parse_args()

    loader = BROWSER_LOADERS.get(args.browser.lower())
    if not loader:
        raise SystemExit(f'Unsupported browser: {args.browser}')

    cj = loader(domain_name=args.domain)
    if not len(cj):
        raise SystemExit(f'No cookies found for domain "{args.domain}".')

    output_path = os.path.abspath(args.output)
    cookiejar_to_netscape(cj, output_path, args.domain)
    print(f'Cookies exported to {output_path}')

if __name__ == '__main__':
    main()
"@

    $tempPy = Join-Path $env:TEMP "export_cookies_runner.py"
    $pythonScript | Set-Content -Path $tempPy -Encoding UTF8
    try {
        python $tempPy --browser $Browser --domain $Domain --output $Output
    } finally {
        Remove-Item $tempPy -ErrorAction SilentlyContinue
    }
}

Ensure-Python
Install-Dependencies
Run-Exporter

Write-Host "Done. Upload '$Output' in the Video Downloader UI to reuse your cookies."

