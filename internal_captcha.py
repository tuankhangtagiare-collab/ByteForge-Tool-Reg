# -*- coding: utf-8 -*-
"""
ByteForg Tool - Internal hCaptcha Solver v2.0
Giải hCaptcha nội bộ bằng ONNX Model, không cần API bên thứ ba
Yêu cầu: Model ONNX trong thư mục models/
Fallback: Tự động chuyển sang API nếu có key
"""

import os
import re
import time
import json
import random
import string
import base64
from typing import Optional, Dict, List, Tuple
from io import BytesIO
from urllib.parse import urlencode

import requests
from colorama import Fore, Style

# Thử import thư viện ML
HAS_CV2 = False
HAS_ONNX = False

try:
    import cv2
    HAS_CV2 = True
except ImportError:
    pass

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import onnxruntime as ort
    HAS_ONNX = True
except ImportError:
    pass

class InternalHCaptchaSolver:
    """
    Bộ giải hCaptcha nội bộ không cần API bên thứ ba.
    
    Quy trình:
    1. GET checksiteconfig → lấy cấu hình challenge
    2. POST getcaptcha → lấy danh sách ảnh và câu hỏi
    3. Phân loại từng ảnh qua ONNX Model
    4. POST checkcaptcha → gửi đáp án, nhận token
    
    Yêu cầu model: models/hcaptcha_classifier.onnx
    """

    # Đường dẫn model mặc định
    MODEL_PATH = os.path.join("models", "hcaptcha_classifier.onnx")
    
    # Danh sách nhãn (phải khớp với model đã train)
    LABELS = [
        "airplane", "bicycle", "bird", "boat", "bus", "car", "cat",
        "dog", "horse", "motorcycle", "train", "truck", "traffic_light",
        "fire_hydrant", "stop_sign", "parking_meter", "crosswalk",
        "bridge", "palm_tree", "chimney"
    ]

    # Mapping nhãn hCaptcha → nhãn model
    LABEL_MAPPING = {
        'máy bay': 'airplane',
        'airplane': 'airplane',
        'plane': 'airplane',
        'xe đạp': 'bicycle',
        'bicycle': 'bicycle',
        'bike': 'bicycle',
        'chim': 'bird',
        'bird': 'bird',
        'thuyền': 'boat',
        'boat': 'boat',
        'ship': 'boat',
        'xe buýt': 'bus',
        'bus': 'bus',
        'ô tô': 'car',
        'car': 'car',
        'xe hơi': 'car',
        'mèo': 'cat',
        'cat': 'cat',
        'chó': 'dog',
        'dog': 'dog',
        'ngựa': 'horse',
        'horse': 'horse',
        'xe máy': 'motorcycle',
        'motorcycle': 'motorcycle',
        'motorbike': 'motorcycle',
        'tàu hỏa': 'train',
        'train': 'train',
        'xe tải': 'truck',
        'truck': 'truck',
        'đèn giao thông': 'traffic_light',
        'traffic light': 'traffic_light',
        'traffic_light': 'traffic_light',
        'vòi cứu hỏa': 'fire_hydrant',
        'fire hydrant': 'fire_hydrant',
        'fire_hydrant': 'fire_hydrant',
        'biển báo dừng': 'stop_sign',
        'stop sign': 'stop_sign',
        'stop_sign': 'stop_sign',
        'đồng hồ đỗ xe': 'parking_meter',
        'parking meter': 'parking_meter',
        'parking_meter': 'parking_meter',
        'crosswalk': 'crosswalk',
        'bridge': 'bridge',
        'cầu': 'bridge',
        'cây cọ': 'palm_tree',
        'palm tree': 'palm_tree',
        'ống khói': 'chimney',
        'chimney': 'chimney',
    }

    def __init__(self, fallback_api_key: str = "", max_retries: int = 3, timeout: int = 180):
        """
        Khởi tạo Internal Captcha Solver.

        Args:
            fallback_api_key: API key dự phòng nếu model không hoạt động
            max_retries: Số lần thử lại tối đa
            timeout: Timeout cho mỗi lần giải (giây)
        """
        self.fallback_api_key = fallback_api_key
        self.max_retries = max_retries
        self.timeout = timeout
        
        # Trạng thái model
        self.model_loaded = False
        self.ort_session = None
        
        # Kiểm tra và tải model
        self._check_dependencies()
        if HAS_ONNX and HAS_CV2 and HAS_NUMPY:
            self._load_model()
        
        if self.model_loaded:
            print(f"{Fore.GREEN}[InternalCaptcha] ✓ Model ONNX đã sẵn sàng.")
        elif fallback_api_key:
            print(f"{Fore.YELLOW}[InternalCaptcha] ⚠️ Không có model, sẽ dùng API fallback.")
        else:
            print(f"{Fore.RED}[InternalCaptcha] ✗ Không có model và không có API key fallback!")

    def _check_dependencies(self):
        """Kiểm tra các thư viện cần thiết"""
        if not HAS_ONNX:
            print(f"{Fore.YELLOW}[InternalCaptcha] ⚠️ Thiếu onnxruntime. Cài: pip install onnxruntime")
        if not HAS_CV2:
            print(f"{Fore.YELLOW}[InternalCaptcha] ⚠️ Thiếu opencv-python-headless. Cài: pip install opencv-python-headless")
        if not HAS_NUMPY:
            print(f"{Fore.YELLOW}[InternalCaptcha] ⚠️ Thiếu numpy. Cài: pip install numpy")

    def _load_model(self):
        """Tải ONNX model từ file"""
        if not os.path.exists(self.MODEL_PATH):
            print(f"{Fore.YELLOW}[InternalCaptcha] Không tìm thấy model tại: {self.MODEL_PATH}")
            print(f"{Fore.YELLOW}[InternalCaptcha] Vui lòng tải model hcaptcha_classifier.onnx vào thư mục models/")
            return

        try:
            self.ort_session = ort.InferenceSession(self.MODEL_PATH)
            self.model_loaded = True
            input_shape = self.ort_session.get_inputs()[0].shape
            print(f"{Fore.GREEN}[InternalCaptcha] Model loaded. Input shape: {input_shape}")
        except Exception as e:
            print(f"{Fore.RED}[InternalCaptcha] Lỗi tải model: {e}")
            self.model_loaded = False

    def _preprocess_image(self, img_bytes: bytes, target_size: Tuple[int, int] = (224, 224)) -> np.ndarray:
        """
        Tiền xử lý ảnh cho ONNX model.

        Args:
            img_bytes: Dữ liệu ảnh (bytes)
            target_size: Kích thước đầu ra (width, height)

        Returns:
            numpy array đã chuẩn hóa, shape (1, 3, H, W)
        """
        # Decode ảnh
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Không thể decode ảnh")
        
        # Resize
        img = cv2.resize(img, target_size)
        
        # BGR → RGB
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Normalize về [0, 1]
        img = img.astype(np.float32) / 255.0
        
        # Chuẩn hóa (ImageNet stats)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        img = (img - mean) / std
        
        # Chuyển vị: (H, W, C) → (C, H, W)
        img = np.transpose(img, (2, 0, 1))
        
        # Thêm batch dimension: (C, H, W) → (1, C, H, W)
        img = np.expand_dims(img, axis=0)
        
        return img.astype(np.float32)

    def _classify_image(self, img_bytes: bytes, target_label: str) -> bool:
        """
        Phân loại một ảnh: có chứa đối tượng cần tìm không?

        Args:
            img_bytes: Dữ liệu ảnh
            target_label: Nhãn cần tìm (vd: "bus", "car")

        Returns:
            True nếu ảnh chứa đối tượng
        """
        if not self.model_loaded:
            # Fallback: random (50/50)
            return random.choice([True, False])

        try:
            # Map nhãn hCaptcha → nhãn model
            mapped_label = self.LABEL_MAPPING.get(target_label.lower(), target_label.lower())
            
            # Tiền xử lý ảnh
            input_tensor = self._preprocess_image(img_bytes)
            
            # Chạy inference
            input_name = self.ort_session.get_inputs()[0].name
            outputs = self.ort_session.run(None, {input_name: input_tensor})
            predictions = outputs[0][0]
            
            # Lấy top-3 dự đoán
            top3_indices = np.argsort(predictions)[-3:]
            
            # Kiểm tra xem nhãn mục tiêu có trong top-3 không
            for idx in top3_indices:
                if idx < len(self.LABELS):
                    pred_label = self.LABELS[idx].lower()
                    if pred_label == mapped_label.lower():
                        return True
            
            return False
            
        except Exception as e:
            print(f"{Fore.RED}[InternalCaptcha] Lỗi phân loại: {e}")
            return random.choice([True, False])

    def _get_site_config(self, session: requests.Session, sitekey: str, 
                         host: str = "discord.com") -> Optional[Dict]:
        """Lấy cấu hình site từ hCaptcha"""
        url = f"https://hcaptcha.com/checksiteconfig?host={host}&sitekey={sitekey}&sc=1&swa=1"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept": "application/json",
        }
        
        try:
            resp = session.get(url, headers=headers, timeout=15)
            data = resp.json()
            print(f"{Fore.CYAN}[InternalCaptcha] Site config: {json.dumps(data, ensure_ascii=False)[:200]}")
            return data
        except Exception as e:
            print(f"{Fore.RED}[InternalCaptcha] Lỗi lấy site config: {e}")
            return None

    def _get_challenge(self, session: requests.Session, sitekey: str,
                       rqdata: str = '', rqtoken: str = '') -> Optional[Dict]:
        """Lấy challenge (danh sách ảnh) từ hCaptcha"""
        url = "https://hcaptcha.com/getcaptcha"
        
        post_data = {
            "sitekey": sitekey,
            "host": "discord.com",
            "hl": "vi",
            "mobile": "false",
            "n": "1",
            "c": json.dumps({"type": "hsl"}),  # Hoặc "type": "image"
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
            data = resp.json()
            
            print(f"{Fore.CYAN}[InternalCaptcha] Challenge response keys: {list(data.keys())}")
            
            if data.get('tasklist'):
                print(f"{Fore.CYAN}[InternalCaptcha] Số ảnh: {len(data['tasklist'])}")
            
            return data
        except Exception as e:
            print(f"{Fore.RED}[InternalCaptcha] Lỗi lấy challenge: {e}")
            return None

    def _submit_answer(self, session: requests.Session, task_key: str,
                       answers: List[int], job_mode: str = "image_label_binary") -> Optional[str]:
        """Gửi đáp án và nhận token"""
        url = f"https://hcaptcha.com/checkcaptcha/{task_key}"
        
        # Format đáp án
        post_data = {}
        for i, ans in enumerate(answers):
            post_data[f"answer_{i}"] = str(ans)
        post_data["task_key"] = task_key
        post_data["job_mode"] = job_mode
        post_data["serverdomain"] = "discord.com"
        post_data["sitekey"] = ""
        
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
                print(f"{Fore.GREEN}[InternalCaptcha] ✓ Token: {token[:50]}...")
                return token
            
            # Có thể cần làm thêm challenge
            if data.get('tasklist'):
                print(f"{Fore.YELLOW}[InternalCaptcha] Cần giải thêm challenge phụ...")
                return None  # Sẽ được xử lý đệ quy
            
            print(f"{Fore.RED}[InternalCaptcha] Response không có token: {data}")
            return None
            
        except Exception as e:
            print(f"{Fore.RED}[InternalCaptcha] Lỗi gửi đáp án: {e}")
            return None

    def solve(self, sitekey: str, rqdata: str = '', rqtoken: str = '',
              user_agent: str = '', proxy: Optional[Dict] = None) -> Optional[str]:
        """
        Giải hCaptcha nội bộ.

        Args:
            sitekey: Sitekey từ Discord
            rqdata: Tham số rqdata
            rqtoken: Tham số rqtoken
            user_agent: User-Agent
            proxy: Proxy dict {http, https}

        Returns:
            Token Captcha hoặc None nếu thất bại
        """
        # Nếu không có model, dùng fallback API
        if not self.model_loaded:
            if self.fallback_api_key:
                print(f"{Fore.YELLOW}[InternalCaptcha] Dùng API fallback...")
                from captcha_solver import CaptchaSolver
                solver = CaptchaSolver(
                    service='capmonster',
                    api_key=self.fallback_api_key,
                    max_retries=self.max_retries,
                    timeout=self.timeout
                )
                return solver.solve(sitekey, rqdata, rqtoken, user_agent, proxy)
            else:
                print(f"{Fore.RED}[InternalCaptcha] ✗ Không có model và không có API key.")
                return None

        # Tạo session
        session = requests.Session()
        if proxy:
            session.proxies = proxy
        
        session.headers.update({
            "User-Agent": user_agent or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
            "Accept-Language": "vi-VN,vi;q=0.9",
        })

        for attempt in range(self.max_retries):
            try:
                print(f"{Fore.YELLOW}[InternalCaptcha] Giải nội bộ (lần {attempt+1}/{self.max_retries})...")
                
                # Bước 1: Lấy site config
                site_config = self._get_site_config(session, sitekey)
                if not site_config:
                    continue

                # Bước 2: Lấy challenge
                challenge = self._get_challenge(session, sitekey, rqdata, rqtoken)
                if not challenge:
                    continue

                task_key = challenge.get('task_key') or challenge.get('key')
                tasklist = challenge.get('tasklist', [])
                
                if not tasklist:
                    print(f"{Fore.RED}[InternalCaptcha] Không có tasklist trong challenge.")
                    continue
                
                if not task_key:
                    print(f"{Fore.RED}[InternalCaptcha] Không có task_key.")
                    continue

                print(f"{Fore.CYAN}[InternalCaptcha] Task Key: {task_key}")
                print(f"{Fore.CYAN}[InternalCaptcha] Số ảnh cần phân loại: {len(tasklist)}")

                # Bước 3: Phân loại từng ảnh
                target_label = ""
                answers = []
                
                for task_item in tasklist:
                    task_label = task_item.get('task_label', '')
                    image_url = task_item.get('datapoint_uri', '')
                    task_index = task_item.get('task_index', -1)
                    
                    if not target_label and task_label:
                        target_label = task_label
                        print(f"{Fore.CYAN}[InternalCaptcha] Câu hỏi: Tìm '{target_label}'")
                    
                    if image_url and task_index >= 0:
                        try:
                            img_resp = session.get(image_url, timeout=10)
                            is_match = self._classify_image(img_resp.content, target_label)
                            
                            if is_match:
                                answers.append(task_index)
                                print(f"{Fore.GREEN}[InternalCaptcha]   Ảnh {task_index}: ✓ CÓ '{target_label}'")
                            else:
                                print(f"{Fore.RED}[InternalCaptcha]   Ảnh {task_index}: ✗ KHÔNG có '{target_label}'")
                                
                        except Exception as e:
                            print(f"{Fore.RED}[InternalCaptcha] Lỗi tải ảnh {task_index}: {e}")
                            continue
                
                print(f"{Fore.CYAN}[InternalCaptcha] Số ảnh được chọn: {len(answers)}/{len(tasklist)}")
                
                if not answers:
                    print(f"{Fore.YELLOW}[InternalCaptcha] Không có ảnh nào được chọn! Thử chọn ngẫu nhiên 2 ảnh...")
                    answers = random.sample([t['task_index'] for t in tasklist if t['task_index'] >= 0], 
                                           min(2, len(tasklist)))
                
                # Bước 4: Gửi đáp án
                token = self._submit_answer(session, task_key, answers)
                if token:
                    return token
                
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                    
            except Exception as e:
                print(f"{Fore.RED}[InternalCaptcha] Lỗi (lần {attempt+1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2)
                    continue
        
        print(f"{Fore.RED}[InternalCaptcha] ✗ Thất bại sau {self.max_retries} lần thử.")
        
        # Thử fallback API
        if self.fallback_api_key:
            print(f"{Fore.YELLOW}[InternalCaptcha] Dùng API fallback...")
            from captcha_solver import CaptchaSolver
            solver = CaptchaSolver(
                service='capmonster',
                api_key=self.fallback_api_key,
                max_retries=self.max_retries,
                timeout=self.timeout
            )
            return solver.solve(sitekey, rqdata, rqtoken, user_agent, proxy)
        
        return None
