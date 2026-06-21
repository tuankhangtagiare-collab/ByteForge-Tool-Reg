# -*- coding: utf-8 -*-
"""
ByteForg Tool - Proxy Manager v2.0
Quản lý proxy từ API (proxy.vn, proxyxoay.shop) và file proxy.txt
Hỗ trợ: HTTP, HTTPS, SOCKS4, SOCKS5 (có hoặc không có user:pass)
"""

import os
import re
import random
import time
import threading
from typing import Dict, Optional, List, Tuple
from urllib.parse import urlparse

import requests
from colorama import Fore, Style

class ProxyManager:
    """
    Quản lý proxy: nạp từ file, lấy từ API, chọn ngẫu nhiên, kiểm tra trạng thái.
    Hỗ trợ định dạng:
      - ip:port
      - http://ip:port
      - https://ip:port
      - socks4://ip:port
      - socks5://ip:port
      - socks5://ip:port:user:pass
      - ip:port:user:pass
    """

    # Regex để parse các định dạng proxy
    PATTERN_WITH_SCHEME = re.compile(
        r'^(?P<scheme>socks5|socks4|https?|HTTP|HTTPS|SOCKS5|SOCKS4)://'
        r'(?:(?P<user>[^:@]+):(?P<pass>[^@]+)@)?'
        r'(?P<host>[^:]+):(?P<port>\d+)$'
    )
    PATTERN_SIMPLE = re.compile(
        r'^(?P<host>[^:]+):(?P<port>\d+)(?::(?P<user>[^:]+):(?P<pass>.+))?$'
    )

    def __init__(self, api_key_vn: str = "", api_key_xoay: str = "",
                 use_file: bool = True, file_path: str = "proxy.txt",
                 proxy_type: str = "all"):
        """
        Khởi tạo Proxy Manager.

        Args:
            api_key_vn: API key từ proxy.vn
            api_key_xoay: API key từ proxyxoay.shop
            use_file: Có sử dụng file proxy.txt không
            file_path: Đường dẫn đến file proxy.txt
            proxy_type: Loại proxy được phép dùng (http, socks5, all)
        """
        self.api_key_vn = api_key_vn
        self.api_key_xoay = api_key_xoay
        self.use_file = use_file
        self.file_path = file_path
        self.proxy_type = proxy_type.lower()

        # Pool proxy (list of dict: {http: url, https: url, scheme: str, host: str, port: int})
        self._pool: List[Dict] = []
        self._pool_lock = threading.Lock()

        # Đếm số lần dùng mỗi proxy để tránh dùng quá nhiều
        self._usage_count: Dict[str, int] = {}
        self._max_usage = 5  # Mỗi proxy dùng tối đa 5 lần

        # Nạp proxy từ file
        if self.use_file:
            self._load_from_file()

        # Nạp proxy từ API
        self._fetch_from_apis()

        print(f"{Fore.CYAN}[ProxyManager] Tổng cộng {len(self._pool)} proxy khả dụng.")

    def _load_from_file(self):
        """Đọc và parse proxy từ file proxy.txt"""
        if not os.path.exists(self.file_path):
            print(f"{Fore.YELLOW}[ProxyManager] Không tìm thấy {self.file_path}. Đang tạo file mẫu...")
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write("# ByteForg Tool - File Proxy\n")
                f.write("# Hỗ trợ định dạng:\n")
                f.write("#   ip:port\n")
                f.write("#   http://ip:port\n")
                f.write("#   socks5://ip:port\n")
                f.write("#   socks5://ip:port:user:pass\n")
                f.write("#   ip:port:user:pass\n")
                f.write("# Ví dụ:\n")
                f.write("# socks5://208.102.51.6:58208\n")
                f.write("# 192.168.1.1:8080:username:password\n")
            return

        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip() and not l.strip().startswith('#')]

            count = 0
            for line in lines:
                proxy_dict = self._parse_line(line)
                if proxy_dict:
                    self._add_to_pool(proxy_dict)
                    count += 1

            print(f"{Fore.GREEN}[ProxyManager] Đã nạp {count} proxy từ {self.file_path}")
        except Exception as e:
            print(f"{Fore.RED}[ProxyManager] Lỗi đọc file proxy: {e}")

    def _parse_line(self, line: str) -> Optional[Dict]:
        """
        Parse một dòng proxy thành dictionary.

        Args:
            line: Chuỗi proxy (vd: socks5://208.102.51.6:58208)

        Returns:
            Dict: {http: url, https: url, scheme: str, host: str, port: int}
            hoặc None nếu không parse được
        """
        line = line.strip()
        if not line:
            return None

        # Thử parse với scheme
        match = self.PATTERN_WITH_SCHEME.match(line)
        if match:
            scheme = match.group('scheme').lower()
            host = match.group('host')
            port = int(match.group('port'))
            user = match.group('user')
            password = match.group('pass')

            # Kiểm tra loại proxy được phép
            if self.proxy_type != 'all' and scheme != self.proxy_type:
                return None

            if user and password:
                proxy_url = f"{scheme}://{user}:{password}@{host}:{port}"
            else:
                proxy_url = f"{scheme}://{host}:{port}"

            return {
                'http': proxy_url,
                'https': proxy_url,
                'scheme': scheme,
                'host': host,
                'port': port,
                'url': proxy_url
            }

        # Thử parse định dạng ip:port hoặc ip:port:user:pass
        match = self.PATTERN_SIMPLE.match(line)
        if match:
            host = match.group('host')
            port = int(match.group('port'))
            user = match.group('user')
            password = match.group('pass')

            # Mặc định dùng http nếu không có scheme
            scheme = 'http'
            if self.proxy_type != 'all' and scheme != self.proxy_type:
                return None

            if user and password:
                proxy_url = f"http://{user}:{password}@{host}:{port}"
            else:
                proxy_url = f"http://{host}:{port}"

            return {
                'http': proxy_url,
                'https': proxy_url,
                'scheme': scheme,
                'host': host,
                'port': port,
                'url': proxy_url
            }

        print(f"{Fore.YELLOW}[ProxyManager] Không parse được: {line}")
        return None

    def _fetch_from_apis(self):
        """Lấy proxy từ API proxy.vn và proxyxoay.shop"""
        proxies = []

        # Lấy từ proxy.vn
        if self.api_key_vn:
            try:
                url = f"https://proxy.vn/api/v1/proxy?key={self.api_key_vn}&type=http&count=10"
                resp = requests.get(url, timeout=15)
                data = resp.json()
                if data.get('data'):
                    for item in data['data'].get('proxies', []):
                        ip = item.get('ip', '')
                        port = item.get('port', '')
                        if ip and port:
                            proxy_str = f"http://{ip}:{port}"
                            proxies.append(proxy_str)
                print(f"{Fore.GREEN}[ProxyManager] Lấy {len(proxies)} proxy từ proxy.vn")
            except Exception as e:
                print(f"{Fore.YELLOW}[ProxyManager] Lỗi proxy.vn: {e}")

        # Lấy từ proxyxoay.shop
        if self.api_key_xoay:
            try:
                url = f"https://proxyxoay.shop/api/proxy?key={self.api_key_xoay}&count=10"
                resp = requests.get(url, timeout=15)
                data = resp.json()
                for item in data.get('proxies', []):
                    proxy_str = f"http://{item['ip']}:{item['port']}"
                    proxies.append(proxy_str)
                print(f"{Fore.GREEN}[ProxyManager] Lấy {len(proxies)} proxy từ proxyxoay.shop")
            except Exception as e:
                print(f"{Fore.YELLOW}[ProxyManager] Lỗi proxyxoay.shop: {e}")

        # Parse và thêm vào pool
        for p in proxies:
            proxy_dict = self._parse_line(p)
            if proxy_dict:
                self._add_to_pool(proxy_dict)

    def _add_to_pool(self, proxy_dict: Dict):
        """Thêm proxy vào pool (thread-safe)"""
        with self._pool_lock:
            # Kiểm tra trùng lặp
            url = proxy_dict.get('url', '')
            if not any(p.get('url') == url for p in self._pool):
                self._pool.append(proxy_dict)
                self._usage_count[url] = 0

    def get_proxy(self) -> Optional[Dict[str, str]]:
        """
        Lấy một proxy ngẫu nhiên từ pool.
        Ưu tiên proxy chưa dùng quá số lần cho phép.

        Returns:
            Dict: {http: url, https: url} hoặc None nếu hết proxy
        """
        with self._pool_lock:
            if not self._pool:
                # Thử nạp lại từ API
                self._fetch_from_apis()
                if not self._pool:
                    print(f"{Fore.RED}[ProxyManager] HẾT PROXY! Không còn proxy nào.")
                    return None

            # Lọc proxy còn hạn sử dụng
            available = [p for p in self._pool
                        if self._usage_count.get(p['url'], 0) < self._max_usage]

            if not available:
                # Reset tất cả usage count
                print(f"{Fore.YELLOW}[ProxyManager] Tất cả proxy đã dùng quá {self._max_usage} lần. Reset...")
                for key in self._usage_count:
                    self._usage_count[key] = 0
                available = list(self._pool)

            # Chọn ngẫu nhiên
            proxy = random.choice(available)
            self._usage_count[proxy['url']] += 1

            return {'http': proxy['http'], 'https': proxy['https']}

    def remove_proxy(self, proxy_url: str):
        """Xóa proxy khỏi pool (nếu proxy chết)"""
        with self._pool_lock:
            self._pool = [p for p in self._pool if p.get('url') != proxy_url]
            if proxy_url in self._usage_count:
                del self._usage_count[proxy_url]
            print(f"{Fore.YELLOW}[ProxyManager] Đã xóa proxy: {proxy_url}")

    def get_all_proxies_count(self) -> int:
        """Trả về tổng số proxy hiện có trong pool"""
        with self._pool_lock:
            return len(self._pool)

    def get_stats(self) -> Dict:
        """Trả về thống kê proxy"""
        with self._pool_lock:
            return {
                'total': len(self._pool),
                'available': sum(1 for p in self._pool
                               if self._usage_count.get(p['url'], 0) < self._max_usage),
                'max_usage': self._max_usage,
                'schemes': list(set(p['scheme'] for p in self._pool))
            }
