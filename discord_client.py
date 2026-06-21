# -*- coding: utf-8 -*-
"""
ByteForg Tool - Discord Client v2.0
TLS Spoofing với Chrome 120, quản lý session, headers, cookies
Gửi request đăng ký và xác thực token Discord
"""

import re
import json
import random
import string
import base64
import hashlib
import time
from typing import Dict, Optional, Tuple, Any
from datetime import datetime

import tls_client
from colorama import Fore, Style

class CaptchaParamsNotFoundError(Exception):
    """Ngoại lệ: Không tìm thấy tham số Captcha trên trang đăng ký"""
    pass

class DiscordRateLimitError(Exception):
    """Ngoại lệ: Rate limit từ Discord"""
    def __init__(self, retry_after: float = 5.0):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")

class DiscordClient:
    """
    Client tương tác với Discord API qua TLS Spoofing.
    Giả lập Chrome 120, quản lý headers, cookies, fingerprint.
    """

    # Danh sách User-Agent Chrome 120 (Windows)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.130 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.109 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.71 Safari/537.36",
    ]

    # Cấu hình TLS
    TLS_IDENTIFIER = "chrome_120"

    def __init__(self, proxy: Optional[Dict] = None):
        """
        Khởi tạo Discord Client.

        Args:
            proxy: Dict {http: url, https: url} hoặc None
        """
        self.proxy = proxy
        self.user_agent = random.choice(self.USER_AGENTS)

        # Tạo TLS session
        self.session = tls_client.Session(
            client_identifier=self.TLS_IDENTIFIER,
            random_tls_extension_order=True
        )

        # Gán proxy nếu có
        if proxy:
            self.session.proxies = proxy

        # Cookies lưu trữ
        self.cookies: Dict[str, str] = {}

        # Fingerprint ngẫu nhiên
        self.x_fingerprint = self._generate_x_fingerprint()
        self.x_track = self._generate_x_track()
        self.x_super_properties = self._generate_x_super_properties()

        # Thời gian timeout mặc định
        self.timeout = 30

    def set_proxy(self, proxy: Optional[Dict]):
        """Cập nhật proxy cho session"""
        self.proxy = proxy
        if proxy:
            self.session.proxies = proxy

    def _generate_x_fingerprint(self) -> str:
        """Tạo x-fingerprint ngẫu nhiên (32 ký tự hex)"""
        return hashlib.md5(
            f"{random.random()}{time.time()}{random.randint(0, 999999)}".encode()
        ).hexdigest()

    def _generate_x_track(self) -> str:
        """Tạo x-track ngẫu nhiên (base64, ~40 ký tự)"""
        random_bytes = bytes(random.getrandbits(8) for _ in range(30))
        return base64.b64encode(random_bytes).decode('utf-8')[:40]

    def _generate_x_super_properties(self) -> str:
        """
        Tạo x-super-properties (base64 JSON).
        Đây là thông tin về client mà Discord yêu cầu.
        """
        properties = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "vi-VN",
            "browser_user_agent": self.user_agent,
            "browser_version": "120.0.0.0",
            "os_version": "10",
            "referrer": "https://discord.com/register",
            "referring_domain": "discord.com",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": 264462,
            "client_event_source": None
        }
        return base64.b64encode(json.dumps(properties).encode()).decode()

    def build_headers(self, include_content_type: bool = True) -> Dict[str, str]:
        """
        Xây dựng bộ headers đầy đủ cho request.

        Args:
            include_content_type: Có thêm Content-Type: application/json không

        Returns:
            Dict các headers
        """
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "X-Discord-Timezone": "Asia/Ho_Chi_Minh",
            "X-Debug-Options": "bugReporterEnabled",
            "X-Discord-Locale": "vi",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/register",
            "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "x-fingerprint": self.x_fingerprint,
            "x-track": self.x_track,
            "x-super-properties": self.x_super_properties,
            "Connection": "keep-alive",
        }

        if include_content_type:
            headers["Content-Type"] = "application/json"

        # Thêm cookies nếu có
        if self.cookies:
            cookie_str = "; ".join([f"{k}={v}" for k, v in self.cookies.items()])
            headers["Cookie"] = cookie_str

        return headers

    def visit_register_page(self) -> Dict[str, str]:
        """
        Truy cập trang đăng ký Discord để lấy cookies và tham số Captcha.

        Returns:
            Dict: {sitekey, rqdata, rqtoken}

        Raises:
            CaptchaParamsNotFoundError: Nếu không tìm thấy sitekey
            ConnectionError: Nếu không kết nối được
        """
        url = "https://discord.com/register"
        headers = self.build_headers(include_content_type=False)

        try:
            print(f"{Fore.CYAN}[Discord] GET {url}")
            response = self.session.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()

            html = response.text
            print(f"{Fore.CYAN}[Discord] HTTP {response.status_code} | {len(html)} bytes")

            # Lưu cookies quan trọng
            important_cookies = ['__dcfduid', '__sdcfduid', '__cfruid', 'locale']
            for cookie_name in important_cookies:
                if cookie_name in response.cookies:
                    self.cookies[cookie_name] = response.cookies[cookie_name]
                    print(f"{Fore.CYAN}[Discord] Cookie: {cookie_name}={self.cookies[cookie_name][:20]}...")

            # Trích xuất tham số Captcha bằng regex
            # sitekey
            sitekey_patterns = [
                r'data-sitekey="([^"]+)"',
                r'sitekey["\s:]+["\']([^"\']+)["\']',
                r'"sitekey"\s*:\s*"([^"]+)"',
            ]
            sitekey = None
            for pattern in sitekey_patterns:
                match = re.search(pattern, html)
                if match:
                    sitekey = match.group(1)
                    break

            # rqdata
            rqdata_patterns = [
                r'data-rqdata="([^"]+)"',
                r'rqdata["\s:]+["\']([^"\']+)["\']',
                r'"rqdata"\s*:\s*"([^"]+)"',
            ]
            rqdata = None
            for pattern in rqdata_patterns:
                match = re.search(pattern, html)
                if match:
                    rqdata = match.group(1)
                    break

            # rqtoken
            rqtoken_patterns = [
                r"rqtoken:\s*'([^']+)'",
                r'rqtoken["\s:]+["\']([^"\']+)["\']',
                r'"rqtoken"\s*:\s*"([^"]+)"',
                r'data-rqtoken="([^"]+)"',
            ]
            rqtoken = None
            for pattern in rqtoken_patterns:
                match = re.search(pattern, html)
                if match:
                    rqtoken = match.group(1)
                    break

            if not sitekey:
                # Kiểm tra xem Discord có trả về Cloudflare challenge không
                if 'cf-challenge' in html.lower() or 'cloudflare' in html.lower():
                    raise CaptchaParamsNotFoundError(
                        "Discord đang chặn Cloudflare. Proxy không sạch hoặc IP bị flag."
                    )
                raise CaptchaParamsNotFoundError(
                    "Không tìm thấy sitekey trên trang đăng ký Discord."
                )

            captcha_params = {
                'sitekey': sitekey,
                'rqdata': rqdata or '',
                'rqtoken': rqtoken or ''
            }

            print(f"{Fore.GREEN}[Discord] ✓ Sitekey: {sitekey[:50]}...")
            if rqdata:
                print(f"{Fore.GREEN}[Discord] ✓ rqdata: {rqdata[:50]}...")
            if rqtoken:
                print(f"{Fore.GREEN}[Discord] ✓ rqtoken: {rqtoken[:50]}...")

            return captcha_params

        except requests.exceptions.Timeout:
            raise ConnectionError("Timeout khi kết nối đến Discord.")
        except requests.exceptions.ConnectionError:
            raise ConnectionError("Không thể kết nối đến Discord. Kiểm tra proxy/mạng.")
        except CaptchaParamsNotFoundError:
            raise
        except Exception as e:
            raise ConnectionError(f"Lỗi không xác định: {e}")

    def register(self, email: str, username: str, password: str,
                 dob: str, captcha_token: Optional[str] = None) -> Optional[Dict]:
        """
        Gửi POST request đăng ký tài khoản Discord.

        Args:
            email: Email đăng ký
            username: Tên người dùng
            password: Mật khẩu
            dob: Ngày sinh (YYYY-MM-DD)
            captcha_token: Token Captcha đã giải (có thể None)

        Returns:
            Dict response từ Discord (chứa token) hoặc None nếu thất bại
        """
        url = "https://discord.com/api/v9/auth/register"
        headers = self.build_headers(include_content_type=True)

        payload = {
            "email": email,
            "username": username,
            "password": password,
            "date_of_birth": dob,
            "consent": True,
            "gift_code_sku_id": None,
            "invite": None,
        }

        if captcha_token:
            payload["captcha_key"] = captcha_token

        print(f"{Fore.CYAN}[Discord] POST {url}")
        print(f"{Fore.CYAN}[Discord] Payload: email={email}, username={username}, captcha={'Yes' if captcha_token else 'No'}")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout
                )

                print(f"{Fore.CYAN}[Discord] HTTP {response.status_code}")

                # Xử lý Rate Limit
                if response.status_code == 429:
                    try:
                        retry_after = response.json().get('retry_after', 5)
                    except:
                        retry_after = 5
                    print(f"{Fore.YELLOW}[Discord] Rate limit! Đợi {retry_after}s...")
                    time.sleep(float(retry_after) + 1)
                    continue

                # Parse response
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    print(f"{Fore.RED}[Discord] Response không phải JSON: {response.text[:200]}")
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return None

                # Xử lý các mã lỗi
                if response.status_code in [200, 201]:
                    token = data.get('token')
                    if token:
                        print(f"{Fore.GREEN}[Discord] ✓ Đăng ký thành công!")
                        return data
                    else:
                        print(f"{Fore.RED}[Discord] ✗ Response không có token: {data}")
                        return None

                # Lỗi validation (50035)
                if data.get('code') == 50035:
                    errors = data.get('errors', {})
                    error_fields = list(errors.keys())
                    print(f"{Fore.YELLOW}[Discord] Lỗi validation ở: {error_fields}")

                    # Nếu lỗi username, thử lại với username khác
                    if 'username' in errors:
                        print(f"{Fore.YELLOW}[Discord] Username không hợp lệ, cần đổi.")
                        return None  # Sẽ được retry với username mới từ bên ngoài

                    return None

                # Lỗi Captcha
                if data.get('code') == 60002 or 'captcha' in str(data.get('errors', {})).lower():
                    print(f"{Fore.RED}[Discord] ✗ Captcha không hợp lệ hoặc hết hạn.")
                    return None

                # Lỗi email
                if 'email' in str(data.get('errors', {})).lower():
                    print(f"{Fore.RED}[Discord] ✗ Email không hợp lệ hoặc đã được sử dụng.")
                    return None

                # Lỗi khác
                error_code = data.get('code', 'unknown')
                error_msg = data.get('message', str(data))
                print(f"{Fore.RED}[Discord] ✗ Lỗi {error_code}: {error_msg}")

                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None

            except requests.exceptions.Timeout:
                print(f"{Fore.YELLOW}[Discord] Timeout (lần {attempt+1}). Thử lại...")
                time.sleep(2)
            except requests.exceptions.ConnectionError:
                print(f"{Fore.YELLOW}[Discord] Lỗi kết nối (lần {attempt+1}). Thử lại...")
                time.sleep(3)
            except Exception as e:
                print(f"{Fore.RED}[Discord] Lỗi không xác định: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                return None

        return None

    def validate_token(self, token: str) -> bool:
        """
        Kiểm tra token còn sống không bằng cách gọi API /users/@me.

        Args:
            token: Token Discord cần kiểm tra

        Returns:
            True nếu token hoạt động, False nếu không
        """
        url = "https://discord.com/api/v9/users/@me"
        headers = {
            "Authorization": token,
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "vi-VN,vi;q=0.9",
        }

        try:
            response = self.session.get(url, headers=headers, timeout=15)

            if response.status_code == 200:
                user_data = response.json()
                user_id = user_data.get('id', 'N/A')
                username = user_data.get('username', 'N/A')
                email = user_data.get('email', 'N/A')
                verified = user_data.get('verified', False)
                print(f"{Fore.GREEN}[Validate] ✓ Token OK - ID: {user_id} | {username} | Verified: {verified}")
                return True

            elif response.status_code == 401:
                print(f"{Fore.RED}[Validate] ✗ 401 Unauthorized - Token bị vô hiệu hóa")
                return False

            elif response.status_code == 403:
                print(f"{Fore.RED}[Validate] ✗ 403 Forbidden - Token bị khóa")
                return False

            elif response.status_code == 429:
                print(f"{Fore.YELLOW}[Validate] Rate limit khi kiểm tra token")
                time.sleep(5)
                # Thử lại 1 lần
                response2 = self.session.get(url, headers=headers, timeout=15)
                return response2.status_code == 200

            else:
                print(f"{Fore.YELLOW}[Validate] HTTP {response.status_code} - Không xác định")
                return False

        except Exception as e:
            print(f"{Fore.RED}[Validate] Lỗi: {e}")
            return False

    def set_email_verified(self, token: str, verification_link: str) -> bool:
        """
        Xác nhận email bằng cách truy cập link xác nhận từ Discord.

        Args:
            token: Token Discord
            verification_link: Link xác nhận từ email

        Returns:
            True nếu xác nhận thành công
        """
        headers = {
            "Authorization": token,
            "User-Agent": self.user_agent,
        }

        try:
            response = self.session.get(verification_link, headers=headers, timeout=30, allow_redirects=True)
            if response.status_code == 200:
                print(f"{Fore.GREEN}[Email] ✓ Đã xác nhận email thành công.")
                return True
            else:
                print(f"{Fore.YELLOW}[Email] Xác nhận email trả về HTTP {response.status_code}")
                return False
        except Exception as e:
            print(f"{Fore.RED}[Email] Lỗi xác nhận email: {e}")
            return False
