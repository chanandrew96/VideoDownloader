#!/usr/bin/env python3
"""
Helper script to export browser cookies for yt-dlp.

Usage:
    python export_cookies.py --browser chrome --output cookies.txt --domain youtube.com

Requires:
    pip install browser-cookie3
"""
import argparse
import os
import sys
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
        f.write('# Netscape HTTP Cookie File\n')
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
            f.write(f'{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n')


def main():
    parser = argparse.ArgumentParser(description='Export browser cookies to cookies.txt for yt-dlp.')
    parser.add_argument('--browser', default='chrome', choices=BROWSER_LOADERS.keys(),
                        help='Browser to extract cookies from')
    parser.add_argument('--domain', default='youtube.com', help='Only include cookies that match this domain')
    parser.add_argument('--output', default='cookies.txt', help='Output cookies file path')
    args = parser.parse_args()

    loader = BROWSER_LOADERS.get(args.browser.lower())
    if not loader:
        print(f'Unsupported browser: {args.browser}', file=sys.stderr)
        sys.exit(1)

    try:
        cj = loader(domain_name=args.domain)
    except Exception as e:
        print(f'Failed to load cookies: {e}', file=sys.stderr)
        sys.exit(1)

    if not len(cj):
        print(f'No cookies found for domain "{args.domain}".', file=sys.stderr)
        sys.exit(1)

    output_path = os.path.abspath(args.output)
    cookiejar_to_netscape(cj, output_path, args.domain)
    print(f'Cookies exported to {output_path}')


if __name__ == '__main__':
    main()

