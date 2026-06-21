# -*- coding: utf-8 -*-
"""
ByteForg Tool - Internal Captcha Solver v3.0
Sử dụng hcaptcha-challenger để giải hCaptcha
Không cần API bên thứ ba, dùng model ONNX có sẵn
"""

import os
import time
import json
import random
import base64
import requests
from typing import Optional, Dict, List
from io import BytesIO
from colorama import Fore, Style

# Import hcaptcha-challenger
try:
    from hcaptcha_challenger import (
        HolyChallenger,
        NewChallenger,
        ModelHub,
        DataLoader,
    )
    HAS_CHALLENGER = True
    print(f"{Fore.GREEN}[Challenger] ✓ hcaptcha-challenger đã sẵn sàng.")
except ImportError:
    HAS_CHALLENGER = False
    print(f"{Fore.RED}[Challenger] ✗ Chưa cài hcaptcha-challenger.")
    print(f"{Fore.YELLOW}[Challenger] Chạy: pip install hcaptcha-challenger==0.19.0")

class InternalHCaptchaSolver:
    """
    Bộ giải hCaptcha nội bộ dùng hcaptcha-challenger.
    
    Hỗ trợ:
    - image_label_binary: Phân loại ảnh (chọn ảnh có vật thể X)
    - image_label_area_select: Chọn vùng trên ảnh
    
    Fallback: Tự động chuyển sang API nếu có key.
    """

    def __init__(self, fallback_api_key: str = "", max_retries: int = 3, timeout: int = 180):
        self.fallback_api_key = fallback_api_key
        self.max_retries = max_retries
        self.timeout = timeout
        self.challenger = None
        
        if HAS_CHALLENGER:
            self._init_challenger()
        
        if self.challenger:
            print(f"{Fore.GREEN}[Challenger] ✓ Bộ giải nội bộ đã sẵn sàng.")
        elif fallback_api_key:
            print(f"{Fore.YELLOW}[Challenger] ⚠️ Sẽ dùng API fallback.")
        else:
            print(f"{Fore.RED}[Challenger] ✗ Không có bộ giải và không có API key!")

    def _init_challenger(self):
        """Khởi tạo hcaptcha-challenger với model có sẵn"""
        try:
            # Tạo challenger mới
            self.challenger = NewChallenger()
            
            # Tải model từ ModelHub (tự động tải nếu chưa có)
            print(f"{Fore.CYAN}[Challenger] Đang tải model từ ModelHub...")
            
            # Model cho image_label_binary (chọn ảnh)
            self.challenger.apply_executor(
                ModelHub.fetch_register(
                    "image_label_binary",
                    model_name="resnet50_binary_classification"
                )
            )
            
            # Model cho image_label_area_select (chọn vùng)
            self.challenger.apply_executor(
                ModelHub.fetch_register(
                    "image_label_area_select",
                    model_name="yolov8_detection"
                )
            )
            
            print(f"{Fore.GREEN}[Challenger] ✓ Đã tải model thành công.")
            
        except Exception as e:
            print(f"{Fore.RED}[Challenger] Lỗi khởi tạo: {e}")
            self.challenger = None

    def _get_site_config(self, session: requests.Session, sitekey: str) -> Optional[Dict]:
        """Lấy cấu hình site từ hCaptcha"""
        url = f"https://hcaptcha.com/checksiteconfig?host=discord.com&sitekey={sitekey}&sc=1&swa=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json",
        }
        try:
            resp = session.get(url, headers=headers, timeout=15)
            return resp.json()
        except Exception as e:
            print(f"{Fore.RED}[Challenger] Lỗi lấy site config: {e}")
            return None

    def _get_challenge(self, session: requests.Session, sitekey: str,
                       rqdata: str = '') -> Optional[Dict]:
        """Lấy challenge từ hCaptcha"""
        url = "https://hcaptcha.com/getcaptcha"
        post_data = {
            "sitekey": sitekey,
            "host": "discord.com",
            "hl": "vi",
            "mobile": "false",
            "n": "1",
            "c": json.dumps({"type": "hsl"}),
        }
        if rqdata:
            post_data["rqdata"] = rqdata
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        try:
            resp = session.post(url, data=post_data, headers=headers, timeout=15)
            return resp.json()
        except Exception as e:
            print(f"{Fore.RED}[Challenger] Lỗi lấy challenge: {e}")
            return None

    def _solve_with_challenger(self, challenge_data: Dict, session: requests.Session) -> Optional[str]:
        """Dùng hcaptcha-challenger để giải challenge"""
        if not self.challenger:
            return None
        
        try:
            tasklist = challenge_data.get('tasklist', [])
            task_key = challenge_data.get('task_key') or challenge_data.get('key')
            
            if not tasklist or not task_key:
                return None
            
            # Xác định loại challenge
            task_type = tasklist[0].get('task_type', 'image_label_binary')
            
            print(f"{Fore.CYAN}[Challenger] Loại challenge: {task_type}")
            print(f"{Fore.CYAN}[Challenger] Số ảnh: {len(tasklist)}")
            
            if task_type == 'image_label_binary':
                return self._solve_binary(tasklist, task_key, session)
            elif task_type == 'image_label_area_select':
                return self._solve_area_select(tasklist, task_key, session)
            else:
                print(f"{Fore.YELLOW}[Challenger] Loại {task_type} chưa hỗ trợ.")
                return None
                
        except Exception as e:
            print(f"{Fore.RED}[Challenger] Lỗi giải: {e}")
            return None

    def _solve_binary(self, tasklist: List[Dict], task_key: str,
                      session: requests.Session) -> Optional[str]:
        """Giải challenge dạng chọn ảnh (image_label_binary)"""
        
        target_label = tasklist[0].get('task_label', '')
        print(f"{Fore.CYAN}[Challenger] Câu hỏi: Tìm '{target_label}'")
        
        answers = []
        
        for task_item in tasklist:
            image_url = task_item.get('datapoint_uri', '')
            task_index = task_item.get('task_index', -1)
            
            if not image_url or task_index < 0:
                continue
            
            try:
                # Tải ảnh
                img_resp = session.get(image_url, timeout=10)
                img_bytes = img_resp.content
                
                # Dùng challenger để phân loại
                # hcaptcha-challenger dùng ResNet ONNX model
                result = self.challenger.classify_image(
                    img_bytes,
                    challenge_type="image_label_binary",
                    target_label=target_label
                )
                
                # result: True nếu ảnh chứa vật thể, False nếu không
                if result:
                    answers.append(task_index)
                    print(f"{Fore.GREEN}[Challenger]   Ảnh {task_index}: ✓ CÓ '{target_label}'")
                else:
                    print(f"{Fore.RED}[Challenger]   Ảnh {task_index}: ✗ KHÔNG có '{target_label}'")
                    
            except Exception as e:
                print(f"{Fore.RED}[Challenger] Lỗi ảnh {task_index}: {e}")
                continue
        
        if not answers:
            print(f"{Fore.YELLOW}[Challenger] Không chọn được ảnh nào!")
            # Fallback: chọn 2-3 ảnh ngẫu nhiên
            indices = [t['task_index'] for t in tasklist if t['task_index'] >= 0]
            answers = random.sample(indices, min(3, len(indices)))
        
        # Gửi đáp án
        return self._submit_answer(session, task_key, answers)

    def _solve_area_select(self, tasklist: List[Dict], task_key: str,
                           session: requests.Session) -> Optional[str]:
        """Giải challenge dạng chọn vùng (image_label_area_select)"""
        # Tương tự, dùng YOLOv8 để detect vùng
        print(f"{Fore.YELLOW}[Challenger] Area select chưa triển khai đầy đủ.")
        return None

    def _submit_answer(self, session: requests.Session, task_key: str,
                       answers: List[int]) -> Optional[str]:
        """Gửi đáp án lên hCaptcha"""
        url = f"https://hcaptcha.com/checkcaptcha/{task_key}"
        
        post_data = {}
        for i, ans in enumerate(answers):
            post_data[f"answer_{i}"] = str(ans)
        post_data["task_key"] = task_key
        post_data["job_mode"] = "image_label_binary"
        post_data["serverdomain"] = "discord.com"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            resp = session.post(url, data=post_data, headers=headers, timeout=15)
            data = resp.json()
            
            generated_pass = data.get('generated_pass_UUID')
            if generated_pass:
                token = f"P1_{generated_pass}"
                print(f"{Fore.GREEN}[Challenger] ✓ Token: {token[:50]}...")
                return token
            
            print(f"{Fore.RED}[Challenger] Không có token: {data}")
            return None
        except Exception as e:
            print(f"{Fore.RED}[Challenger] Lỗi gửi đáp án: {e}")
            return None

    def solve(self, sitekey: str, rqdata: str = '', rqtoken: str = '',
              user_agent: str = '', proxy: Optional[Dict] = None) -> Optional[str]:
        """
        Giải hCaptcha.
        
        Args:
            sitekey: Sitekey từ Discord
            rqdata: Tham số rqdata
            rqtoken: Tham số rqtoken
            user_agent: User-Agent
            proxy: Proxy dict {http, https}
            
        Returns:
            Token Captcha hoặc None
        """
        # Nếu không có challenger, dùng API fallback
        if not self.challenger:
            if self.fallback_api_key:
                print(f"{Fore.YELLOW}[Challenger] Dùng API fallback...")
                from captcha_solver import CaptchaSolver
                solver = CaptchaSolver(
                    service='capmonster',
                    api_key=self.fallback_api_key,
                    max_retries=self.max_retries,
                    timeout=self.timeout
                )
                return solver.solve(sitekey, rqdata, rqtoken, user_agent, proxy)
            else:
                print(f"{Fore.RED}[Challenger] ✗ Không có bộ giải nào.")
                return None

        # Tạo session
        session = requests.Session()
        if proxy:
            session.proxies = proxy
        session.headers.update({
            "User-Agent": user_agent or "Mozilla/5.0 Chrome/120.0.0.0",
        })

        for attempt in range(self.max_retries):
            try:
                print(f"{Fore.YELLOW}[Challenger] Giải (lần {attempt+1}/{self.max_retries})...")
                
                # Lấy challenge
                challenge = self._get_challenge(session, sitekey, rqdata)
                if not challenge:
                    continue
                
                # Giải
                token = self._solve_with_challenger(challenge, session)
                if token:
                    return token
                
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                    
            except Exception as e:
                print(f"{Fore.RED}[Challenger] Lỗi: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
        
        # Fallback API
        if self.fallback_api_key:
            print(f"{Fore.YELLOW}[Challenger] Dùng API fallback...")
            from captcha_solver import CaptchaSolver
            solver = CaptchaSolver(
                service='capmonster',
                api_key=self.fallback_api_key,
                max_retries=self.max_retries,
                timeout=self.timeout
            )
            return solver.solve(sitekey, rqdata, rqtoken, user_agent, proxy)
        
        return None
