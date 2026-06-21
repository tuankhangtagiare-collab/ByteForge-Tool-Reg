# -*- coding: utf-8 -*-
"""
ByteForg Tool - Email Verifier v2.0
Quản lý email tạm qua kopeechka.store API
Hỗ trợ: Lấy email, chờ email xác nhận từ Discord, trích xuất link verify
"""

import re
import time
import random
import string
import requests
from typing import Optional, Dict
from colorama import Fore, Style

class EmailVerifierError(Exception):
    """Ngoại lệ chung cho lỗi Email"""
    pass

class EmailTimeoutError(EmailVerifierError):
    """Ngoại lệ: Hết thời gian chờ email"""
    pass

class EmailVerifier:
    """
    Quản lý email tạm để đăng ký Discord.
    Sử dụng kopeechka.store API (hoặc email giả nếu không có API key).
    """

    # Base URL của kopeechka API
    BASE_URL = "https://api.kopeechka.store"

    # Domain email phổ biến để sinh email giả
    FAKE_DOMAINS = [
        "gmail.com", "outlook.com", "yahoo.com", "hotmail.com",
        "protonmail.com", "mail.com", "yandex.com",
    ]

    def __init__(self, api_key: str = "", use_temp_mail: bool = True,
                 verification_timeout: int = 120):
        """
        Khởi tạo Email Verifier.

        Args:
            api_key: API key kopeechka.store
            use_temp_mail: Có sử dụng email tạm thật không (False → email giả)
            verification_timeout: Thời gian chờ email xác nhận (giây)
        """
        self.api_key = api_key
        self.use_temp_mail = use_temp_mail
        self.verification_timeout = verification_timeout

        # Trạng thái email hiện tại
        self.email_id: Optional[str] = None
        self.email_address: Optional[str] = None
        self.is_fake_email: bool = False

        if use_temp_mail and not api_key:
            print(f"{Fore.YELLOW}[Email] ⚠️ Không có API key kopeechka. Sẽ dùng email giả.")
            self.use_temp_mail = False

    def get_email(self) -> str:
        """
        Lấy một địa chỉ email (thật hoặc giả).

        Returns:
            Email address string
        """
        if self.use_temp_mail and self.api_key:
            return self._get_real_email()
        else:
            return self._generate_fake_email()

    def _get_real_email(self) -> str:
        """
        Lấy email thật từ kopeechka.store API.

        Returns:
            Email address
        """
        url = f"{self.BASE_URL}/mailbox-get-email"
        params = {
            "api": "2.0",
            "key": self.api_key,
            "site": "discord.com",
            "mail_type": "REAL",
            "regex": "",
        }

        for attempt in range(3):
            try:
                print(f"{Fore.YELLOW}[Email] Đang lấy email từ kopeechka... (lần {attempt+1})")
                resp = requests.get(url, params=params, timeout=30)
                data = resp.json()

                if data.get('status') == 'OK':
                    self.email_id = data.get('id')
                    self.email_address = data.get('mail')
                    self.is_fake_email = False

                    print(f"{Fore.GREEN}[Email] ✓ Email: {self.email_address} (ID: {self.email_id})")

                    # Kiểm tra balance
                    balance = data.get('balance', 'N/A')
                    print(f"{Fore.CYAN}[Email] Số dư kopeechka: {balance}")

                    return self.email_address
                else:
                    error = data.get('error', data.get('message', 'Unknown'))
                    print(f"{Fore.RED}[Email] ✗ Lỗi: {error}")

                    # Lỗi hết tiền
                    if 'balance' in str(error).lower() or 'money' in str(error).lower():
                        print(f"{Fore.RED}[Email] Hết số dư kopeechka. Chuyển sang email giả.")
                        self.use_temp_mail = False
                        return self._generate_fake_email()

                    time.sleep(2)

            except requests.exceptions.Timeout:
                print(f"{Fore.YELLOW}[Email] Timeout lấy email, thử lại...")
                time.sleep(2)
            except Exception as e:
                print(f"{Fore.RED}[Email] Lỗi: {e}")
                time.sleep(2)

        print(f"{Fore.RED}[Email] ✗ Không lấy được email sau 3 lần thử. Dùng email giả.")
        self.use_temp_mail = False
        return self._generate_fake_email()

    def _generate_fake_email(self) -> str:
        """
        Sinh email giả ngẫu nhiên.

        Returns:
            Fake email address
        """
        self.is_fake_email = True

        # Sinh phần local
        patterns = [
            # firstname.lastname + số
            lambda: f"{random.choice(['nguyen','tran','le','pham','hoang','vo','dang','bui'])}"
                    f"{random.choice(['van','thi','minh','anh','duc','thanh','linh','quang'])}"
                    f"{random.randint(1, 9999)}",
            # Từ viết tắt + số
            lambda: f"{''.join(random.choices(string.ascii_lowercase, k=2))}{random.randint(10000, 99999)}",
            # Tên thông thường + số
            lambda: f"{random.choice(['john','jane','alex','emma','david','sarah','mike','lisa'])}"
                    f"{random.randint(1, 99999)}",
        ]

        local_part = random.choice(patterns)()
        domain = random.choice(self.FAKE_DOMAINS)

        email = f"{local_part}@{domain}"
        self.email_address = email
        self.email_id = None

        print(f"{Fore.YELLOW}[Email] Email giả: {email}")
        return email

    def wait_for_verification(self) -> Optional[str]:
        """
        Chờ email xác nhận từ Discord và trích xuất link verify.
        Chỉ hoạt động với email thật từ kopeechka.

        Returns:
            Verification URL string, hoặc None nếu không nhận được
        """
        if self.is_fake_email or not self.email_id:
            print(f"{Fore.YELLOW}[Email] Không thể chờ xác nhận (email giả hoặc không có ID).")
            print(f"{Fore.YELLOW}[Email] Discord thường vẫn tạo tài khoản với email giả.")
            return None

        if not self.api_key:
            return None

        print(f"{Fore.YELLOW}[Email] Đang chờ email xác nhận từ Discord...")
        print(f"{Fore.CYAN}[Email] Email: {self.email_address}")
        print(f"{Fore.CYAN}[Email] Timeout: {self.verification_timeout}s")

        start_time = time.time()
        poll_interval = 3

        while time.time() - start_time < self.verification_timeout:
            try:
                url = f"{self.BASE_URL}/mailbox-get-message"
                params = {
                    "api": "2.0",
                    "key": self.api_key,
                    "id": self.email_id,
                    "full": "1",
                }

                resp = requests.get(url, params=params, timeout=15)
                data = resp.json()

                if data.get('status') == 'OK' and data.get('full_message'):
                    full_message = data.get('full_message', '')

                    print(f"{Fore.CYAN}[Email] Có email mới! Độ dài: {len(full_message)} bytes")

                    # Tìm link xác nhận Discord
                    verify_link = self._extract_verification_link(full_message)

                    if verify_link:
                        print(f"{Fore.GREEN}[Email] ✓ Tìm thấy link xác nhận!")
                        print(f"{Fore.CYAN}[Email] Link: {verify_link[:80]}...")
                        return verify_link

                    # Có email nhưng không có link verify
                    print(f"{Fore.YELLOW}[Email] Email không chứa link xác nhận Discord.")
                    # Có thể là email quảng cáo, tiếp tục chờ
                    # Xóa email này để nhận email tiếp theo
                    self._delete_message()

                time.sleep(poll_interval)
                poll_interval = min(poll_interval + 0.5, 5)

            except Exception as e:
                print(f"{Fore.YELLOW}[Email] Lỗi kiểm tra: {e}")
                time.sleep(poll_interval)

        print(f"{Fore.RED}[Email] ✗ Hết thời gian chờ ({self.verification_timeout}s).")
        return None

    def _extract_verification_link(self, message: str) -> Optional[str]:
        """
        Trích xuất link xác nhận từ nội dung email.

        Args:
            message: Nội dung email (HTML hoặc text)

        Returns:
            Verification URL hoặc None
        """
        # Các pattern link xác nhận Discord
        patterns = [
            r'https://discord\.com/verify[^\s<>"\']+',
            r'https://discord\.com/api/v[0-9]+/auth/verify[^\s<>"\']+',
            r'https://discordapp\.com/verify[^\s<>"\']+',
            r'https://click\.discord\.com/[^\s<>"\']+',
            r'href=["\'](https://discord\.com/verify[^"\']+)["\']',
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                link = match.group(1) if match.lastindex else match.group(0)
                # Clean link
                link = link.strip().rstrip('.')
                return link

        # Nếu không tìm thấy link, in nội dung để debug
        print(f"{Fore.YELLOW}[Email] Không tìm thấy link trong email.")
        print(f"{Fore.CYAN}[Email] Nội dung: {message[:300]}...")

        return None

    def _delete_message(self):
        """Xóa email hiện tại khỏi hộp thư kopeechka"""
        if not self.email_id or not self.api_key:
            return

        try:
            url = f"{self.BASE_URL}/mailbox-delete"
            params = {
                "api": "2.0",
                "key": self.api_key,
                "id": self.email_id,
            }
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('status') == 'OK':
                print(f"{Fore.CYAN}[Email] Đã xóa email cũ khỏi hộp thư.")
        except Exception as e:
            print(f"{Fore.YELLOW}[Email] Lỗi xóa email: {e}")

    def get_balance(self) -> Optional[float]:
        """Kiểm tra số dư tài khoản kopeechka"""
        if not self.api_key:
            return None

        try:
            url = f"{self.BASE_URL}/balance"
            params = {
                "api": "2.0",
                "key": self.api_key,
            }
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get('status') == 'OK':
                return float(data.get('balance', 0))
        except Exception as e:
            print(f"{Fore.RED}[Email] Lỗi kiểm tra số dư: {e}")

        return None
