# -*- coding: utf-8 -*-
"""
ByteForg Tool - Account Generator v2.0
Sinh dữ liệu tài khoản Discord tự động:
- Username (Tính từ + Danh từ + Số)
- Password (16+ ký tự an toàn)
- Date of Birth (18-30 tuổi)
- Avatar URL (DiceBear API)
- Bio ngẫu nhiên (Tiếng Việt)
"""

import random
import string
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Tuple

class AccountGenerator:
    """Sinh dữ liệu tài khoản Discord ngẫu nhiên, tự nhiên"""

    # Tính từ tiếng Việt (không dấu để tương thích username)
    ADJECTIVES = [
        "Vui", "Nhanh", "Manh", "Dep", "ThongMinh", "SangTao", "HaiHuoc", "NhietHuyet",
        "KienTri", "DungCam", "ThanThien", "HoaiBao", "QuyetTam", "TuTin", "SangSuot",
        "AnCan", "ChamChi", "TrungThuc", "HaoPhong", "KhonKheo", "BinhTinh", "LichSu",
        "NangDong", "KienNhan", "ChuDao", "TinhTe", "HaPhuc", "DangYeu", "PhongKhoang",
        "SauSac", "NhietTinh", "TruongThanh", "LePhep", "DamMe", "CanThan", "TotBung",
        "KhoiHai", "LangMan", "BacSi", "DucDo", "GiauCo", "NoiTieng", "YeuDoi",
        "VuiVe", "DamDang", "HocHoi", "SachSe", "NgayTho", "ManhLiet", "DuyenDang",
        "TichCuc", "VanMinh", "HienDai", "TaiNang", "QuyenRu", "QuyPhai", "LichLam",
        "ThanThien", "RongRai", "PhongPhu", "NgheThuat", "AmNhac", "TheThao",
        "Cool", "Fast", "Brave", "Happy", "Smart", "Epic", "Mega", "Super",
        "Ultra", "Pro", "Master", "Dark", "Fire", "Ice", "Storm", "Shadow",
        "Golden", "Silver", "Cyber", "Neon", "Pixel", "Quantum", "Turbo",
    ]

    # Danh từ
    NOUNS = [
        "Ho", "Cop", "DaiBang", "Soi", "Rong", "CaVoi", "SuTu", "Cao",
        "Meo", "Cho", "Tho", "Nai", "CaSau", "HaMa", "TeGiac", "Voi",
        "Khi", "Gau", "CaMap", "ChimUng", "BoCau", "ChimSe", "Qua", "Coc",
        "Rua", "Ran", "ThanLan", "Buom", "Ong", "Kien", "De", "Bo",
        "SaoBien", "Muc", "Tom", "Cua", "Oc", "Hien", "LinhDuong",
        "ThienNga", "Cong", "Vuon", "HoangTu", "CongChua", "ChienBinh",
        "HiepSi", "PhuThuy", "TienCa", "NguoiNhen", "NguoiDoi",
        "Tiger", "Eagle", "Wolf", "Dragon", "Phoenix", "Lion", "Shark",
        "Falcon", "Panther", "Cobra", "Viper", "Raven", "Fox", "Bear",
        "Ninja", "Samurai", "Wizard", "Knight", "King", "Queen", "Lord",
        "Demon", "Angel", "Ghost", "Reaper", "Hunter", "Warrior",
    ]

    # Bio tiếng Việt
    BIOS = [
        "Chào mừng đến với Discord của tôi! 👋",
        "Gamer chính hiệu 🎮 | Thích Minecraft, Valorant, LOL",
        "Yêu âm nhạc 🎵 | Chill cùng lofi mỗi tối",
        "Thích khám phá công nghệ mới 💻 | Developer in progress",
        "Học sinh - Sinh viên năng động 📚",
        "Đam mê lập trình 🤖 | Python lover",
        "Thích xem phim và đọc sách 📖 | Marvel fan",
        "Người yêu thích thể thao ⚽ | Đá bóng mỗi chiều",
        "Nghệ sĩ tự do 🎨 | Vẽ là đam mê",
        "Thích du lịch và khám phá ✈️ | Ước mơ đi vòng quanh thế giới",
        "Ẩm thực là tình yêu 🍜 | Food blogger tập sự",
        "Mọt phim chính hiệu 🎬 | Review phim mỗi tuần",
        "Coder by day, Gamer by night 🌙",
        "Chill thôi, đời còn dài lắm 😎",
        "Sống là phải vui, yêu là phải chất 💯",
        "Đam mê xe và tốc độ 🏍️",
        "Nhiếp ảnh gia nghiệp dư 📸",
        "Thích viết lách và chia sẻ ✍️",
        "Khám phá vũ trụ qua kính thiên văn 🔭",
        "Người yêu động vật 🐾 | Có 3 bé mèo",
        "Cà phê sáng, code trưa, game tối ☕",
        "Tự do - Sáng tạo - Đột phá 🚀",
    ]

    def __init__(self, prefix: str = "", suffix: str = ""):
        """
        Khởi tạo Account Generator.

        Args:
            prefix: Tiền tố thêm vào username (tùy chọn)
            suffix: Hậu tố thêm vào username (tùy chọn)
        """
        self.prefix = prefix
        self.suffix = suffix

    def generate_username(self) -> str:
        """
        Sinh username tự nhiên.
        Format: [Prefix] + Tính từ + Danh từ + 4 số [ + Suffix]
        
        Returns:
            Username string (2-32 ký tự)
        """
        max_attempts = 20
        for _ in range(max_attempts):
            adj = random.choice(self.ADJECTIVES)
            noun = random.choice(self.NOUNS)
            number = str(random.randint(100, 9999))
            
            # Tránh trùng adj và noun
            if adj.lower() == noun.lower():
                continue
            
            # Ghép username
            username = f"{self.prefix}{adj}{noun}{number}{self.suffix}"
            
            # Đảm bảo độ dài hợp lệ (Discord: 2-32 ký tự)
            if 2 <= len(username) <= 32:
                return username
            
            # Nếu quá dài, cắt bớt
            if len(username) > 32:
                username = f"{self.prefix}{adj}{noun}{self.suffix}"[:28] + str(random.randint(10, 99))
                if 2 <= len(username) <= 32:
                    return username
        
        # Fallback
        return f"User{random.randint(10000, 99999)}"

    def generate_password(self, length: int = 16) -> str:
        """
        Sinh mật khẩu an toàn.

        Args:
            length: Độ dài mật khẩu (tối thiểu 8)

        Returns:
            Password string
        """
        if length < 8:
            length = 16
        
        # Đảm bảo có đủ loại ký tự
        lowercase = random.choice(string.ascii_lowercase)
        uppercase = random.choice(string.ascii_uppercase)
        digit = random.choice(string.digits)
        special = random.choice("!@#$%^&*")
        
        # Phần còn lại
        remaining_length = length - 4
        all_chars = string.ascii_letters + string.digits + "!@#$%^&*"
        remaining = ''.join(random.choices(all_chars, k=remaining_length))
        
        # Trộn tất cả
        password_list = list(lowercase + uppercase + digit + special + remaining)
        random.shuffle(password_list)
        
        return ''.join(password_list)

    def generate_dob(self, min_age: int = 18, max_age: int = 30) -> str:
        """
        Sinh ngày sinh ngẫu nhiên trong khoảng tuổi.

        Args:
            min_age: Tuổi nhỏ nhất
            max_age: Tuổi lớn nhất

        Returns:
            Date string format YYYY-MM-DD
        """
        today = datetime.now()
        
        # Tính ngày sinh sớm nhất và muộn nhất
        earliest_dob = today - timedelta(days=max_age * 365)
        latest_dob = today - timedelta(days=min_age * 365)
        
        # Random ngày trong khoảng
        days_range = (latest_dob - earliest_dob).days
        random_days = random.randint(0, days_range)
        dob = earliest_dob + timedelta(days=random_days)
        
        return dob.strftime("%Y-%m-%d")

    def generate_avatar_url(self) -> str:
        """
        Sinh URL avatar qua DiceBear API.

        Returns:
            Avatar URL string
        """
        seed = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        
        # Các style của DiceBear
        styles = [
            "identicon",
            "bottts",
            "avataaars",
            "initials",
            "pixel-art",
            "thumbs",
        ]
        
        style = random.choice(styles)
        
        # Thêm tham số ngẫu nhiên
        params = {
            "seed": seed,
            "backgroundColor": f"{random.choice(['b6e3f4','c0aede','d1d4f9','ffd5dc','ffdfbf'])}",
        }
        
        if style == "bottts":
            params["color"] = random.choice(["blue", "green", "red", "purple", "orange"])
        
        param_str = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://api.dicebear.com/7.x/{style}/svg?{param_str}"

    def generate_bio(self) -> str:
        """
        Sinh bio ngẫu nhiên.

        Returns:
            Bio string
        """
        return random.choice(self.BIOS)

    def generate_all(self) -> dict:
        """
        Sinh tất cả dữ liệu tài khoản một lần.

        Returns:
            Dict: {username, password, dob, avatar_url, bio}
        """
        return {
            'username': self.generate_username(),
            'password': self.generate_password(),
            'dob': self.generate_dob(),
            'avatar_url': self.generate_avatar_url(),
            'bio': self.generate_bio(),
        }
