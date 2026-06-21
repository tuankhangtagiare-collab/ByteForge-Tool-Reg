# -*- coding: utf-8 -*-
"""
ByteForg Tool - Captcha Solver v2.0
Giải hCaptcha qua API bên thứ ba: CapMonster, 2Captcha, Anti-Captcha
Hỗ trợ HCaptchaTask và HCaptchaTaskProxyless
"""

import time
import requests
from typing import Optional, Dict
from colorama import Fore, Style

class CaptchaSolverError(Exception):
    """Ngoại lệ chung cho lỗi giải Captcha"""
    pass

class CaptchaTimeoutError(CaptchaSolverError):
    """Ngoại lệ: Hết thời gian chờ giải Captcha"""
    pass

class CaptchaAPIError(CaptchaSolverError):
    """Ngoại lệ: Lỗi từ API Captcha"""
    pass

class CaptchaSolver:
    """
    Bộ giải hCaptcha qua dịch vụ API bên thứ ba.
    Hỗ trợ: CapMonster Cloud, 2Captcha, Anti-Captcha.
    """

    # Endpoint API cho từng dịch vụ
    ENDPOINTS = {
        'capmonster': {
            'create': 'https://api.capmonster.cloud/createTask',
            'result': 'https://api.capmonster.cloud/getTaskResult',
            'balance': 'https://api.capmonster.cloud/getBalance',
        },
        '2captcha': {
            'create': 'https://api.2captcha.com/createTask',
            'result': 'https://api.2captcha.com/getTaskResult',
            'balance': 'https://api.2captcha.com/getBalance',
        },
        'anti-captcha': {
            'create': 'https://api.anti-captcha.com/createTask',
            'result': 'https://api.anti-captcha.com/getTaskResult',
            'balance': 'https://api.anti-captcha.com/getBalance',
        },
    }

    def __init__(self, service: str = 'capmonster', api_key: str = '',
                 max_retries: int = 3, timeout: int = 180):
        """
        Khởi tạo Captcha Solver.

        Args:
            service: Tên dịch vụ (capmonster, 2captcha, anti-captcha)
            api_key: API key của dịch vụ
            max_retries: Số lần thử lại tối đa nếu thất bại
            timeout: Thời gian chờ tối đa cho mỗi lần giải (giây)
        """
        self.service = service.lower()
        self.api_key = api_key
        self.max_retries = max_retries
        self.timeout = timeout

        if self.service not in self.ENDPOINTS:
            raise ValueError(f"Dịch vụ không được hỗ trợ: {service}. "
                           f"Hỗ trợ: {list(self.ENDPOINTS.keys())}")

        self.endpoints = self.ENDPOINTS[self.service]

        if not self.api_key:
            print(f"{Fore.YELLOW}[CaptchaSolver] ⚠️ Không có API key! Sẽ không giải được Captcha.")

    def get_balance(self) -> Optional[float]:
        """Kiểm tra số dư tài khoản"""
        if not self.api_key:
            return None

        try:
            resp = requests.post(
                self.endpoints['balance'],
                json={"clientKey": self.api_key},
                timeout=15
            )
            data = resp.json()
            if data.get('errorId') == 0:
                balance = data.get('balance', 0)
                print(f"{Fore.CYAN}[CaptchaSolver] Số dư: ${balance:.2f}")
                return balance
            else:
                print(f"{Fore.RED}[CaptchaSolver] Lỗi kiểm tra số dư: {data.get('errorDescription')}")
                return None
        except Exception as e:
            print(f"{Fore.RED}[CaptchaSolver] Lỗi kết nối kiểm tra số dư: {e}")
            return None

    def _create_task(self, task_data: Dict) -> Optional[str]:
        """
        Tạo task giải Captcha trên dịch vụ.

        Args:
            task_data: Dict chứa thông tin task

        Returns:
            task_id (str) nếu thành công, None nếu thất bại
        """
        if not self.api_key:
            raise CaptchaAPIError("Chưa cấu hình API key Captcha.")

        payload = {
            "clientKey": self.api_key,
            "task": task_data
        }

        try:
            resp = requests.post(
                self.endpoints['create'],
                json=payload,
                timeout=30
            )
            data = resp.json()

            if data.get('errorId') != 0:
                error_code = data.get('errorCode', '')
                error_desc = data.get('errorDescription', 'Unknown error')
                print(f"{Fore.RED}[CaptchaSolver] Lỗi tạo task: [{error_code}] {error_desc}")

                # Xử lý lỗi cụ thể
                if 'ERROR_KEY_DOES_NOT_EXIST' in error_code or 'ERROR_WRONG_USER_KEY' in error_code:
                    raise CaptchaAPIError(f"API key không hợp lệ: {error_desc}")
                if 'ERROR_ZERO_BALANCE' in error_code:
                    raise CaptchaAPIError(f"Hết số dư: {error_desc}")
                if 'ERROR_NO_SUCH_CAPCHA' in error_code:
                    raise CaptchaAPIError(f"Loại Captcha không được hỗ trợ: {error_desc}")

                return None

            task_id = data.get('taskId')
            if task_id:
                print(f"{Fore.GREEN}[CaptchaSolver] ✓ Task created: {task_id}")
                return task_id
            else:
                print(f"{Fore.RED}[CaptchaSolver] Response không có taskId: {data}")
                return None

        except requests.exceptions.Timeout:
            raise CaptchaAPIError("Timeout khi tạo task Captcha.")
        except requests.exceptions.ConnectionError:
            raise CaptchaAPIError("Không thể kết nối đến dịch vụ Captcha.")
        except CaptchaAPIError:
            raise
        except Exception as e:
            raise CaptchaAPIError(f"Lỗi không xác định khi tạo task: {e}")

    def _get_result(self, task_id: str) -> Optional[str]:
        """
        Chờ và lấy kết quả giải Captcha.

        Args:
            task_id: ID của task đã tạo

        Returns:
            Token Captcha (str) nếu giải xong, None nếu thất bại
        """
        start_time = time.time()
        poll_interval = 2  # Thời gian giữa các lần poll (giây)

        while time.time() - start_time < self.timeout:
            try:
                resp = requests.post(
                    self.endpoints['result'],
                    json={
                        "clientKey": self.api_key,
                        "taskId": task_id
                    },
                    timeout=30
                )
                data = resp.json()

                if data.get('errorId') != 0:
                    error_desc = data.get('errorDescription', 'Unknown')
                    print(f"{Fore.RED}[CaptchaSolver] Lỗi lấy kết quả: {error_desc}")
                    return None

                status = data.get('status')

                if status == 'ready':
                    solution = data.get('solution', {}).get('gRecaptchaResponse', '')
                    if solution:
                        elapsed = time.time() - start_time
                        print(f"{Fore.GREEN}[CaptchaSolver] ✓ Đã giải xong! ({elapsed:.1f}s)")
                        return solution
                    else:
                        print(f"{Fore.RED}[CaptchaSolver] Response 'ready' nhưng không có solution: {data}")
                        return None

                elif status == 'processing':
                    elapsed = time.time() - start_time
                    print(f"{Fore.YELLOW}[CaptchaSolver] Đang giải... ({elapsed:.0f}s/{self.timeout}s)")
                    time.sleep(poll_interval)
                    # Tăng dần thời gian poll
                    poll_interval = min(poll_interval + 0.5, 5)

                else:
                    print(f"{Fore.RED}[CaptchaSolver] Trạng thái không xác định: {status}")
                    return None

            except requests.exceptions.Timeout:
                print(f"{Fore.YELLOW}[CaptchaSolver] Timeout poll, thử lại...")
                time.sleep(poll_interval)
            except requests.exceptions.ConnectionError:
                print(f"{Fore.YELLOW}[CaptchaSolver] Lỗi kết nối poll, thử lại...")
                time.sleep(poll_interval)
            except Exception as e:
                print(f"{Fore.RED}[CaptchaSolver] Lỗi poll: {e}")
                time.sleep(poll_interval)

        raise CaptchaTimeoutError(f"Hết thời gian chờ ({self.timeout}s) cho task {task_id}")

    def solve(self, sitekey: str, rqdata: str = '', rqtoken: str = '',
              user_agent: str = '', proxy: Optional[Dict] = None) -> Optional[str]:
        """
        Giải hCaptcha.

        Args:
            sitekey: Sitekey từ Discord
            rqdata: Tham số rqdata (cho Enterprise Captcha)
            rqtoken: Tham số rqtoken
            user_agent: User-Agent của client
            proxy: Dict proxy {http, https} (tùy chọn)

        Returns:
            Token Captcha đã giải (str) hoặc None nếu thất bại sau tất cả retry
        """
        if not self.api_key:
            print(f"{Fore.RED}[CaptchaSolver] ✗ Không có API key, không thể giải Captcha.")
            return None

        # Chuẩn bị task data
        if proxy:
            # Dùng HCaptchaTask (có proxy)
            task_type = "HCaptchaTask"
            task_data = {
                "type": task_type,
                "websiteURL": "https://discord.com",
                "websiteKey": sitekey,
            }

            # Parse proxy
            proxy_url = proxy.get('http', proxy.get('https', ''))
            if proxy_url:
                self._add_proxy_to_task(task_data, proxy_url)

        else:
            # Dùng HCaptchaTaskProxyless (không proxy)
            task_type = "HCaptchaTaskProxyless"
            task_data = {
                "type": task_type,
                "websiteURL": "https://discord.com",
                "websiteKey": sitekey,
            }

        # Thêm tham số Enterprise nếu có
        if rqdata:
            task_data["data"] = rqdata
        if rqtoken:
            task_data["rqtoken"] = rqtoken
        if user_agent:
            task_data["userAgent"] = user_agent

        # Thử giải với retry
        for attempt in range(self.max_retries):
            try:
                print(f"{Fore.YELLOW}[CaptchaSolver] Giải hCaptcha (lần {attempt+1}/{self.max_retries})...")
                print(f"{Fore.CYAN}[CaptchaSolver]   Type: {task_type}")
                print(f"{Fore.CYAN}[CaptchaSolver]   Sitekey: {sitekey[:40]}...")
                if rqdata:
                    print(f"{Fore.CYAN}[CaptchaSolver]   rqdata: {rqdata[:40]}...")
                if proxy:
                    print(f"{Fore.CYAN}[CaptchaSolver]   Proxy: Yes")
                else:
                    print(f"{Fore.CYAN}[CaptchaSolver]   Proxy: No (Proxyless)")

                # Tạo task
                task_id = self._create_task(task_data)
                if not task_id:
                    if attempt < self.max_retries - 1:
                        print(f"{Fore.YELLOW}[CaptchaSolver] Thử lại sau 3s...")
                        time.sleep(3)
                        continue
                    return None

                # Chờ kết quả
                result = self._get_result(task_id)
                if result:
                    print(f"{Fore.GREEN}[CaptchaSolver] ✓ Token: {result[:50]}...")
                    return result

                if attempt < self.max_retries - 1:
                    print(f"{Fore.YELLOW}[CaptchaSolver] Không có kết quả, thử lại sau 3s...")
                    time.sleep(3)

            except CaptchaTimeoutError as e:
                print(f"{Fore.RED}[CaptchaSolver] Timeout: {e}")
                if attempt < self.max_retries - 1:
                    print(f"{Fore.YELLOW}[CaptchaSolver] Thử lại lần {attempt+2}...")
                    time.sleep(2)
                    continue
                return None

            except CaptchaAPIError as e:
                print(f"{Fore.RED}[CaptchaSolver] Lỗi API: {e}")
                # Lỗi API nghiêm trọng (key sai, hết tiền) thì không retry
                if 'API key không hợp lệ' in str(e) or 'Hết số dư' in str(e):
                    return None
                if attempt < self.max_retries - 1:
                    time.sleep(3)
                    continue
                return None

            except Exception as e:
                print(f"{Fore.RED}[CaptchaSolver] Lỗi không xác định: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(3)
                    continue
                return None

        print(f"{Fore.RED}[CaptchaSolver] ✗ Thất bại sau {self.max_retries} lần thử.")
        return None

    def _add_proxy_to_task(self, task_data: Dict, proxy_url: str):
        """
        Parse proxy URL và thêm vào task data.
        Hỗ trợ: http://ip:port, http://user:pass@ip:port,
               socks5://ip:port, socks5://user:pass@ip:port
        """
        import re

        # Parse URL
        pattern = r'^(?P<scheme>socks5|socks4|https?|HTTP|HTTPS|SOCKS5|SOCKS4)://(?:(?P<user>[^:@]+):(?P<pass>[^@]+)@)?(?P<host>[^:]+):(?P<port>\d+)$'
        match = re.match(pattern, proxy_url)

        if not match:
            # Thử parse đơn giản ip:port
            simple = re.match(r'^(?P<host>[^:]+):(?P<port>\d+)$', proxy_url.replace('http://', '').replace('https://', ''))
            if simple:
                task_data["proxyType"] = "http"
                task_data["proxyAddress"] = simple.group('host')
                task_data["proxyPort"] = int(simple.group('port'))
                return
            print(f"{Fore.YELLOW}[CaptchaSolver] Không parse được proxy: {proxy_url}")
            return

        scheme = match.group('scheme').lower()
        host = match.group('host')
        port = int(match.group('port'))
        user = match.group('user')
        password = match.group('pass')

        # Map scheme sang proxyType
        if scheme in ['socks5', 'socks4']:
            task_data["proxyType"] = scheme
        else:
            task_data["proxyType"] = "http"

        task_data["proxyAddress"] = host
        task_data["proxyPort"] = port

        if user and password:
            task_data["proxyLogin"] = user
            task_data["proxyPassword"] = password
