# -*- coding: utf-8 -*-
"""
ByteForg Tool Reg Acc Discord v2.0
Tác giả: ByteForg Team
Mô tả: Công cụ đăng ký tài khoản Discord tự động 100%
       Hỗ trợ proxy SOCKS5/HTTP/HTTPS, giải Captcha nội bộ, xác minh email
       Giao diện tiếng Việt, đa luồng, ghi log chi tiết
"""

import os
import sys
import json
import time
import random
import logging
import threading
import traceback
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Optional, List, Any

# Thư viện bên ngoài
import colorama
from colorama import Fore, Back, Style
from pydantic import BaseModel, ValidationError, Field

# Import module nội bộ
from proxy_manager import ProxyManager
from discord_client import DiscordClient, CaptchaParamsNotFoundError
from captcha_solver import CaptchaSolver
from internal_captcha import InternalHCaptchaSolver
from account_generator import AccountGenerator
from email_verifier import EmailVerifier

# Khởi tạo colorama
colorama.init(autoreset=True)

# ============================================================================
# CẤU HÌNH LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
    handlers=[
        logging.FileHandler('errors.log', encoding='utf-8', mode='a'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# LỚP CẤU HÌNH (Pydantic Model)
# ============================================================================
class ProxyConfig(BaseModel):
    """Cấu hình Proxy"""
    api_key_vn: str = Field(default="", description="API key từ proxy.vn")
    api_key_xoay: str = Field(default="", description="API key từ proxyxoay.shop")
    use_file: bool = Field(default=True, description="Sử dụng proxy từ file proxy.txt")
    file_path: str = Field(default="proxy.txt", description="Đường dẫn file proxy.txt")
    proxy_type: str = Field(default="all", description="Loại proxy: http, socks5, all")

class CaptchaConfig(BaseModel):
    """Cấu hình giải Captcha"""
    service: str = Field(default="internal", description="internal, capmonster, 2captcha, anti-captcha")
    api_key: str = Field(default="", description="API key dịch vụ captcha (fallback)")
    max_retries: int = Field(default=3, description="Số lần thử lại nếu giải thất bại")
    timeout: int = Field(default=180, description="Thời gian chờ tối đa (giây)")

class EmailConfig(BaseModel):
    """Cấu hình Email tạm"""
    api_key: str = Field(default="", description="API key kopeechka.store")
    use_temp_mail: bool = Field(default=True, description="Dùng email tạm (nếu false thì sinh email giả)")
    verification_timeout: int = Field(default=120, description="Thời gian chờ email xác nhận (giây)")

class AccountConfig(BaseModel):
    """Cấu hình sinh tài khoản"""
    avatar_enabled: bool = Field(default=True, description="Tạo avatar cho tài khoản")
    bio_enabled: bool = Field(default=False, description="Tạo bio cho tài khoản")
    username_prefix: str = Field(default="", description="Tiền tố thêm vào username (tùy chọn)")
    username_suffix: str = Field(default="", description="Hậu tố thêm vào username (tùy chọn)")

class SettingsConfig(BaseModel):
    """Cấu hình chung"""
    threads: int = Field(default=3, ge=1, le=50, description="Số luồng chạy đồng thời (1-50)")
    accounts_to_create: int = Field(default=10, ge=1, description="Tổng số tài khoản cần tạo")
    delay_between_accounts: float = Field(default=0.5, ge=0, description="Delay giữa các lần tạo (giây)")
    retry_failed: int = Field(default=2, ge=0, le=5, description="Số lần thử lại nếu thất bại")
    save_format: str = Field(default="email:pass:token", description="Định dạng lưu token")

class AppConfig(BaseModel):
    """Tổng hợp cấu hình ứng dụng"""
    proxy: ProxyConfig = Field(default_factory=ProxyConfig)
    captcha: CaptchaConfig = Field(default_factory=CaptchaConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    account: AccountConfig = Field(default_factory=AccountConfig)
    settings: SettingsConfig = Field(default_factory=SettingsConfig)

# ============================================================================
# HÀM TIỆN ÍCH
# ============================================================================
def print_banner():
    """In banner khởi động"""
    banner = f"""
{Fore.CYAN}{'=' * 70}
{Fore.MAGENTA}{Style.BRIGHT}
  ____        _          ____                     ____            _
 | __ ) _   _| |_ ___   |  ___|__  _ __ __ _    |  _ \ ___  __ _(_)___  ___
 |  _ \| | | | __/ _ \  | |_ / _ \| '__/ _` |   | |_) / _ \/ _` | / __|/ __|
 | |_) | |_| | ||  __/  |  _| (_) | | | (_| |   |  _ <  __/ (_| | \__ \ (__
 |____/ \__, |\__\___|  |_|  \___/|_|  \__, |   |_| \_\___|\__, |_|___/\___|
        |___/                          |___/               |___/
{Fore.CYAN}{'=' * 70}
{Fore.GREEN}  Tool Đăng Ký Tài Khoản Discord Tự Động - Phiên bản 2.0
{Fore.YELLOW}  Hỗ trợ: SOCKS5/HTTP Proxy | Internal Captcha | Email Verify | Đa luồng
{Fore.CYAN}{'=' * 70}
{Style.RESET_ALL}"""
    print(banner)

def print_stats(stats: Dict[str, int]):
    """In thống kê cuối cùng"""
    total = stats.get('total', 0)
    success = stats.get('success', 0)
    failed = stats.get('failed', 0)
    locked = stats.get('locked', 0)
    errors = stats.get('errors', 0)

    print(f"\n{Fore.CYAN}{'=' * 70}")
    print(f"{Fore.CYAN}{Style.BRIGHT}  📊 KẾT QUẢ CUỐI CÙNG")
    print(f"{Fore.CYAN}{'=' * 70}")
    print(f"  {Fore.WHITE}Tổng số nhiệm vụ:    {Fore.YELLOW}{total}")
    print(f"  {Fore.WHITE}Thành công:          {Fore.GREEN}{success} ({_calc_percent(success, total)}%)")
    print(f"  {Fore.WHITE}Thất bại:            {Fore.RED}{failed} ({_calc_percent(failed, total)}%)")
    print(f"  {Fore.WHITE}Bị khóa ngay:        {Fore.RED}{locked} ({_calc_percent(locked, total)}%)")
    print(f"  {Fore.WHITE}Lỗi hệ thống:        {Fore.YELLOW}{errors} ({_calc_percent(errors, total)}%)")
    print(f"{Fore.CYAN}{'=' * 70}")
    print(f"  {Fore.GREEN}✅ Token thành công lưu tại: tokens.txt")
    print(f"  {Fore.RED}🔒 Token bị khóa lưu tại:   locked.txt")
    print(f"  {Fore.YELLOW}⚠️  Log lỗi lưu tại:       errors.log")
    print(f"{Fore.CYAN}{'=' * 70}\n")

def _calc_percent(part: int, total: int) -> float:
    """Tính phần trăm"""
    if total == 0:
        return 0.0
    return round((part / total) * 100, 1)

def load_config(config_path: str = "config.json") -> AppConfig:
    """Đọc và validate file cấu hình, nếu không có thì tạo mới"""
    default_config = AppConfig()

    if not os.path.exists(config_path):
        print(f"{Fore.YELLOW}[!] Không tìm thấy {config_path}. Đang tạo file cấu hình mặc định...")
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(default_config.model_dump(), f, indent=4, ensure_ascii=False)
        print(f"{Fore.GREEN}[✓] Đã tạo {config_path}. Vui lòng chỉnh sửa và chạy lại.")
        sys.exit(0)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        config = AppConfig(**raw)
        print(f"{Fore.GREEN}[✓] Đã tải cấu hình từ {config_path}")
        return config
    except json.JSONDecodeError as e:
        print(f"{Fore.RED}[✗] Lỗi đọc JSON: {e}")
        sys.exit(1)
    except ValidationError as e:
        print(f"{Fore.RED}[✗] Cấu hình không hợp lệ:")
        for error in e.errors():
            print(f"    - {error['loc']}: {error['msg']}")
        sys.exit(1)

# ============================================================================
# LỚP CHÍNH - ByteForgDiscordReg
# ============================================================================
class ByteForgDiscordReg:
    """
    Lớp chính điều phối toàn bộ quá trình đăng ký tài khoản Discord.
    Quản lý proxy, captcha, email, đa luồng và lưu kết quả.
    """

    def __init__(self, config: AppConfig):
        """
        Khởi tạo tool với cấu hình từ AppConfig

        Args:
            config: Đối tượng AppConfig đã được validate
        """
        self.config = config

        # Khởi tạo các module thành phần
        self.proxy_manager = ProxyManager(
            api_key_vn=config.proxy.api_key_vn,
            api_key_xoay=config.proxy.api_key_xoay,
            use_file=config.proxy.use_file,
            file_path=config.proxy.file_path,
            proxy_type=config.proxy.proxy_type
        )

        self.captcha_solver = self._init_captcha_solver()
        self.account_generator = AccountGenerator(
            prefix=config.account.username_prefix,
            suffix=config.account.username_suffix
        )
        self.email_verifier = EmailVerifier(
            api_key=config.email.api_key,
            use_temp_mail=config.email.use_temp_mail,
            verification_timeout=config.email.verification_timeout
        )

        # Biến thống kê (thread-safe)
        self._lock = threading.Lock()
        self.stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'locked': 0,
            'errors': 0
        }

        # File output
        self.tokens_file = "tokens.txt"
        self.locked_file = "locked.txt"

    def _init_captcha_solver(self):
        """
        Khởi tạo bộ giải captcha dựa trên cấu hình.
        Hỗ trợ: internal (ONNX model), capmonster, 2captcha, anti-captcha
        """
        service = self.config.captcha.service.lower()
        api_key = self.config.captcha.api_key

        if service == "internal":
            print(f"{Fore.CYAN}[Captcha] Sử dụng bộ giải nội bộ (ONNX Model)")
            solver = InternalHCaptchaSolver(
                fallback_api_key=api_key,
                max_retries=self.config.captcha.max_retries,
                timeout=self.config.captcha.timeout
            )
        elif service in ["capmonster", "2captcha", "anti-captcha"]:
            print(f"{Fore.CYAN}[Captcha] Sử dụng dịch vụ: {service}")
            solver = CaptchaSolver(
                service=service,
                api_key=api_key,
                max_retries=self.config.captcha.max_retries,
                timeout=self.config.captcha.timeout
            )
        else:
            print(f"{Fore.RED}[Captcha] Dịch vụ không hợp lệ: {service}. Dùng internal.")
            solver = InternalHCaptchaSolver(
                fallback_api_key=api_key,
                max_retries=self.config.captcha.max_retries,
                timeout=self.config.captcha.timeout
            )

        return solver

    def _update_stats(self, key: str):
        """Cập nhật thống kê an toàn trong môi trường đa luồng"""
        with self._lock:
            self.stats[key] += 1

    def _save_result(self, filepath: str, line: str):
        """Ghi kết quả vào file an toàn trong môi trường đa luồng"""
        with self._lock:
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
                f.flush()

    # ========================================================================
    # QUY TRÌNH TẠO MỘT TÀI KHOẢN
    # ========================================================================
    def create_single_account(self, thread_id: int, account_index: int) -> Optional[Dict[str, Any]]:
        """
        Quy trình đầy đủ tạo 1 tài khoản Discord.

        Args:
            thread_id: ID của thread đang chạy
            account_index: Số thứ tự tài khoản (trong tổng số)

        Returns:
            Dict chứa thông tin tài khoản đã tạo, hoặc None nếu thất bại
        """
        thread_name = f"Thread-{thread_id}"
        current_thread = threading.current_thread()
        current_thread.name = thread_name

        logger.info(f"[#{account_index}] Bắt đầu tạo tài khoản...")

        retry_count = 0
        max_retries = self.config.settings.retry_failed

        while retry_count <= max_retries:
            try:
                # ------------------------------------------------------------
                # BƯỚC 1: Lấy Proxy
                # ------------------------------------------------------------
                print(f"{Fore.CYAN}[{thread_name}] [#{account_index}] 🔄 Đang lấy proxy...")
                proxy = self.proxy_manager.get_proxy()
                if proxy:
                    proxy_url = proxy.get('http', 'No Proxy')
                    print(f"{Fore.CYAN}[{thread_name}] [#{account_index}] 🌐 Proxy: {proxy_url}")
                else:
                    print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] ⚠️ Không có proxy, dùng IP thật.")

                # ------------------------------------------------------------
                # BƯỚC 2: Khởi tạo Discord Client với TLS Spoofing
                # ------------------------------------------------------------
                print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 🔐 Khởi tạo TLS Client (Chrome 120)...")
                client = DiscordClient(proxy=proxy)

                # ------------------------------------------------------------
                # BƯỚC 3: Truy cập trang đăng ký, thu thập cookies & captcha params
                # ------------------------------------------------------------
                print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 🌍 Đang truy cập Discord...")
                captcha_params = client.visit_register_page()
                print(f"{Fore.GREEN}[{thread_name}] [#{account_index}] ✓ Đã lấy thông số trang đăng ký.")

                # ------------------------------------------------------------
                # BƯỚC 4: Sinh dữ liệu tài khoản
                # ------------------------------------------------------------
                print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 👤 Đang sinh dữ liệu tài khoản...")
                username = self.account_generator.generate_username()
                password = self.account_generator.generate_password()
                dob = self.account_generator.generate_dob()
                avatar_url = self.account_generator.generate_avatar_url() if self.config.account.avatar_enabled else None
                bio = self.account_generator.generate_bio() if self.config.account.bio_enabled else None

                # Lấy email (thật hoặc giả tùy cấu hình)
                email = self.email_verifier.get_email()

                print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   ├─ Username : {username}")
                print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   ├─ Email    : {email}")
                print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   ├─ Password : {'*' * 12}")
                print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   └─ DOB      : {dob}")

                # ------------------------------------------------------------
                # BƯỚC 5: Giải hCaptcha
                # ------------------------------------------------------------
                captcha_token = None
                if captcha_params and captcha_params.get('sitekey'):
                    print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 🧩 Đang giải hCaptcha...")

                    sitekey = captcha_params['sitekey']
                    rqdata = captcha_params.get('rqdata', '')
                    rqtoken = captcha_params.get('rqtoken', '')
                    user_agent = client.user_agent

                    print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   ├─ Sitekey : {sitekey[:40]}...")
                    if rqdata:
                        print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   ├─ rqdata  : {rqdata[:40]}...")
                    if rqtoken:
                        print(f"{Fore.CYAN}[{thread_name}] [#{account_index}]   └─ rqtoken : {rqtoken[:40]}...")

                    captcha_token = self.captcha_solver.solve(
                        sitekey=sitekey,
                        rqdata=rqdata,
                        rqtoken=rqtoken,
                        user_agent=user_agent,
                        proxy=proxy
                    )

                    if captcha_token:
                        print(f"{Fore.GREEN}[{thread_name}] [#{account_index}] ✓ Captcha đã giải xong.")
                    else:
                        print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Không giải được Captcha.")
                        self._update_stats('errors')
                        retry_count += 1
                        continue
                else:
                    print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] ℹ️ Không phát hiện Captcha, thử đăng ký luôn...")

                # ------------------------------------------------------------
                # BƯỚC 6: Gửi yêu cầu đăng ký
                # ------------------------------------------------------------
                print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 📨 Đang gửi yêu cầu đăng ký...")
                register_result = client.register(
                    email=email,
                    username=username,
                    password=password,
                    dob=dob,
                    captcha_token=captcha_token
                )

                if register_result is None:
                    print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Đăng ký thất bại.")
                    self._update_stats('failed')
                    retry_count += 1
                    continue

                token = register_result.get('token')
                if not token:
                    print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Không có token trong response.")
                    self._update_stats('failed')
                    retry_count += 1
                    continue

                print(f"{Fore.GREEN}[{thread_name}] [#{account_index}] ✓ Nhận token: {token[:30]}...")

                # ------------------------------------------------------------
                # BƯỚC 7: Xác thực Token
                # ------------------------------------------------------------
                print(f"{Fore.YELLOW}[{thread_name}] [#{account_index}] 🔍 Đang xác thực token...")
                is_valid = client.validate_token(token)

                if not is_valid:
                    print(f"{Fore.RED}[{thread_name}] [#{account_index}] 🔒 Token bị khóa ngay lập tức!")
                    self._save_result(
                        self.locked_file,
                        f"{email}:{password}:{token}:{datetime.now().isoformat()}"
                    )
                    self._update_stats('locked')
                    retry_count += 1
                    continue

                # ------------------------------------------------------------
                # BƯỚC 8: Lưu kết quả thành công
                # ------------------------------------------------------------
                timestamp = datetime.now().isoformat()
                save_line = f"{email}:{password}:{token}:{timestamp}"

                if self.config.settings.save_format == "token_only":
                    save_line = token
                elif self.config.settings.save_format == "email:pass:token":
                    save_line = f"{email}:{password}:{token}"
                # Default: email:pass:token:timestamp

                self._save_result(self.tokens_file, save_line)

                account_data = {
                    'email': email,
                    'username': username,
                    'password': password,
                    'token': token,
                    'dob': dob,
                    'avatar_url': avatar_url,
                    'bio': bio,
                    'created_at': timestamp
                }

                print(f"{Fore.GREEN}{Style.BRIGHT}[{thread_name}] [#{account_index}] ✅ THÀNH CÔNG!")
                print(f"{Fore.GREEN}[{thread_name}] [#{account_index}]   └─ {username} | Token đã lưu.")
                self._update_stats('success')
                return account_data

            except CaptchaParamsNotFoundError as e:
                logger.error(f"[#{account_index}] Không tìm thấy tham số Captcha: {e}")
                print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Lỗi: {e}")
                self._update_stats('errors')
                retry_count += 1

            except ConnectionError as e:
                logger.error(f"[#{account_index}] Lỗi kết nối: {e}")
                print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Lỗi kết nối, thử lại ({retry_count+1}/{max_retries+1})...")
                time.sleep(3 * (retry_count + 1))
                retry_count += 1

            except Exception as e:
                logger.error(f"[#{account_index}] Lỗi không xác định: {e}\n{traceback.format_exc()}")
                print(f"{Fore.RED}[{thread_name}] [#{account_index}] ✗ Lỗi: {e}")
                self._update_stats('errors')
                retry_count += 1
                time.sleep(2)

        # Đã hết số lần retry
        print(f"{Fore.RED}{Style.BRIGHT}[{thread_name}] [#{account_index}] ❌ THẤT BẠI sau {max_retries+1} lần thử.")
        return None

    # ========================================================================
    # CHẠY ĐA LUỒNG
    # ========================================================================
    def run(self):
        """Chạy tool với đa luồng, tạo số lượng tài khoản theo cấu hình"""
        total_accounts = self.config.settings.accounts_to_create
        max_threads = self.config.settings.threads
        delay = self.config.settings.delay_between_accounts

        print(f"\n{Fore.CYAN}{'─' * 70}")
        print(f"{Fore.CYAN}  📋 THÔNG TIN TIẾN TRÌNH")
        print(f"{Fore.CYAN}{'─' * 70}")
        print(f"  {Fore.WHITE}Tổng tài khoản cần tạo: {Fore.YELLOW}{total_accounts}")
        print(f"  {Fore.WHITE}Số luồng đồng thời:    {Fore.YELLOW}{max_threads}")
        print(f"  {Fore.WHITE}Delay giữa các TK:     {Fore.YELLOW}{delay}s")
        print(f"  {Fore.WHITE}Giải Captcha:          {Fore.YELLOW}{self.config.captcha.service}")
        print(f"  {Fore.WHITE}Email tạm:             {Fore.YELLOW}{'Bật' if self.config.email.use_temp_mail else 'Tắt'}")
        print(f"{Fore.CYAN}{'─' * 70}\n")

        # Kiểm tra proxy trước khi chạy
        proxy_count = self.proxy_manager.get_all_proxies_count()
        if proxy_count == 0:
            print(f"{Fore.RED}[!] CẢNH BÁO: Không có proxy nào! Tỷ lệ thành công sẽ rất thấp.")
            print(f"{Fore.YELLOW}[!] Vui lòng thêm proxy vào proxy.txt hoặc cấu hình API key.")
            confirm = input(f"{Fore.YELLOW}Tiếp tục? (y/n): ")
            if confirm.lower() != 'y':
                print(f"{Fore.RED}Đã hủy.")
                return
        else:
            print(f"{Fore.GREEN}[✓] Có {proxy_count} proxy trong pool.\n")

        # Tạo thread pool và gửi tasks
        self.stats['total'] = total_accounts
        start_time = time.time()

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futures = []
            for i in range(total_accounts):
                thread_id = (i % max_threads) + 1
                account_index = i + 1
                future = executor.submit(self.create_single_account, thread_id, account_index)
                futures.append(future)
                time.sleep(delay)  # Delay giữa các lần gửi task

            # Đợi tất cả tasks hoàn thành
            for future in as_completed(futures):
                try:
                    result = future.result(timeout=300)  # Timeout 5 phút / task
                except Exception as e:
                    logger.error(f"Future error: {e}")
                    self._update_stats('errors')

        elapsed_time = time.time() - start_time

        # In thống kê
        print_stats(self.stats)
        print(f"{Fore.CYAN}  ⏱️  Tổng thời gian: {elapsed_time:.1f} giây")
        print(f"{Fore.CYAN}  ⚡ Tốc độ trung bình: {total_accounts/elapsed_time*60:.1f} TK/phút\n")

# ============================================================================
# HÀM MAIN
# ============================================================================
def main():
    """Điểm vào chính của tool"""
    print_banner()

    # Tải cấu hình
    config = load_config("config.json")

    # Hiển thị thông tin cấu hình
    print(f"\n{Fore.CYAN}  📌 Cấu hình hiện tại:")
    print(f"     Proxy file: {config.proxy.file_path}")
    print(f"     Proxy type: {config.proxy.proxy_type}")
    print(f"     Captcha: {config.captcha.service}")
    print(f"     Threads: {config.settings.threads}")
    print(f"     Accounts: {config.settings.accounts_to_create}")
    print(f"     Retry: {config.settings.retry_failed} lần\n")

    # Khởi tạo và chạy tool
    try:
        tool = ByteForgDiscordReg(config)
        tool.run()
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[!] Người dùng đã dừng tool (Ctrl+C).")
        print_stats(tool.stats if hasattr(tool, 'stats') else {})
        sys.exit(0)
    except Exception as e:
        print(f"\n{Fore.RED}[✗] Lỗi nghiêm trọng: {e}")
        logger.critical(f"Fatal error: {e}\n{traceback.format_exc()}")
        sys.exit(1)

    # Dừng màn hình
    input(f"\n{Fore.YELLOW}Nhấn Enter để thoát...")

if __name__ == "__main__":
    main()
