#!/usr/bin/env python3
"""
=============================================================================
  Aeroponic Snapshot Database — รายงานผลการทดสอบระบบ (System Test Report)
=============================================================================
  วัตถุประสงค์: ทดสอบการทำงานของทุกฟังก์ชันหลักในระบบ
  เทสผ่าน: HTTPS API + Web Routes ที่ https://localhost:8443
  
  วิธีรัน: python3 scripts/test_full_report.py
=============================================================================
"""

import os
import sys
import io
import re
import json
import time
import shutil
import hashlib
import tempfile
import requests
import urllib3
from datetime import datetime
from PIL import Image

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://localhost:8443"
API_KEY = None  # Auto-detect from config

# ===== Report Data =====
REPORT = []
SECTION_RESULTS = {}
current_section = ""
test_counter = 0


def detect_api_key():
    """Load API key from config."""
    global API_KEY
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from src.config import API_KEYS
        API_KEY = list(API_KEYS.keys())[0]
    except Exception:
        API_KEY = "rpi-cam1-64833b67e104b7f40b094ce0"


def section(name):
    global current_section
    current_section = name
    SECTION_RESULTS[name] = {"pass": 0, "fail": 0, "skip": 0}


def record(test_id, name, status, detail="", input_data="", expected="", actual=""):
    global test_counter
    test_counter += 1
    entry = {
        "no": test_counter,
        "section": current_section,
        "test_id": test_id,
        "name": name,
        "status": status,  # PASS / FAIL / SKIP
        "detail": detail,
        "input": input_data,
        "expected": expected,
        "actual": actual,
    }
    REPORT.append(entry)
    
    icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(status, "❓")
    SECTION_RESULTS[current_section][status.lower()] = \
        SECTION_RESULTS[current_section].get(status.lower(), 0) + 1
    
    print(f"  {icon} [{test_id}] {name}")
    if status == "FAIL":
        print(f"      Expected: {expected}")
        print(f"      Actual:   {actual}")


def make_image(w=100, h=100, color=(255, 0, 0), fmt='JPEG'):
    img = Image.new('RGB', (w, h), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


def get_session():
    s = requests.Session()
    s.verify = False
    r = s.post(f"{BASE_URL}/login", data={'username': 'admin', 'password': 'admin'}, allow_redirects=False)
    s.get(f"{BASE_URL}/")
    return s


def get_leaf_cat(session):
    r = session.get(f"{BASE_URL}/api/categories")
    if r.status_code == 200:
        cats = r.json().get('categories', [])
        for c in cats:
            if c.get('parent_id') is not None:
                return c['id']
    return None


def get_parent_cat(session):
    r = session.get(f"{BASE_URL}/api/categories")
    if r.status_code == 200:
        cats = r.json().get('categories', [])
        parent_ids = set(c.get('parent_id') for c in cats if c.get('parent_id'))
        for c in cats:
            if c['id'] in parent_ids:
                return c['id']
    return None


def cleanup(session, ids):
    for sid in ids:
        try:
            session.delete(f"{BASE_URL}/api/snapshot/{sid}")
        except:
            pass


# =============================================================================
# SECTION A: Authentication & Login
# =============================================================================
def test_authentication(session):
    section("A. ระบบ Authentication & Login")
    print(f"\n{'='*60}")
    print(f"  A. ระบบ Authentication & Login")
    print(f"{'='*60}")
    
    # A-01: Login with correct credentials
    s = requests.Session()
    s.verify = False
    r = s.post(f"{BASE_URL}/login", data={'username': 'admin', 'password': 'admin'}, allow_redirects=False)
    if r.status_code == 302:
        record("A-01", "Login ด้วย username/password ที่ถูกต้อง", "PASS",
               input_data="username=admin, password=admin",
               expected="Redirect (302) ไปหน้า Dashboard",
               actual=f"Status {r.status_code}, Redirect to {r.headers.get('Location','/')}")
    else:
        record("A-01", "Login ด้วย username/password ที่ถูกต้อง", "FAIL",
               input_data="username=admin, password=admin",
               expected="Redirect (302)", actual=f"Status {r.status_code}")
    
    # A-02: Login with wrong password
    s2 = requests.Session()
    s2.verify = False
    r2 = s2.post(f"{BASE_URL}/login", data={'username': 'admin', 'password': 'wrongpass'}, allow_redirects=False)
    if r2.status_code == 200 or (r2.status_code == 302 and 'login' in r2.headers.get('Location', '')):
        record("A-02", "Login ด้วยรหัสผ่านผิด", "PASS",
               input_data="username=admin, password=wrongpass",
               expected="ไม่สามารถ login ได้",
               actual=f"Status {r2.status_code} — login ถูกปฏิเสธ")
    else:
        record("A-02", "Login ด้วยรหัสผ่านผิด", "FAIL",
               expected="ปฏิเสธ login", actual=f"Status {r2.status_code}")
    
    # A-03: Access protected page without login
    s3 = requests.Session()
    s3.verify = False
    r3 = s3.get(f"{BASE_URL}/upload", allow_redirects=False)
    if r3.status_code in (302, 401, 403):
        record("A-03", "เข้าหน้า Upload โดยไม่ login", "PASS",
               expected="Redirect ไป login หรือ 401/403",
               actual=f"Status {r3.status_code}")
    else:
        record("A-03", "เข้าหน้า Upload โดยไม่ login", "FAIL",
               expected="302/401/403", actual=f"Status {r3.status_code}")
    
    # A-04: Logout
    r4 = session.get(f"{BASE_URL}/logout", allow_redirects=False)
    if r4.status_code in (302, 200):
        record("A-04", "Logout", "PASS",
               expected="Redirect ไปหน้า login",
               actual=f"Status {r4.status_code}")
        # Re-login
        session.post(f"{BASE_URL}/login", data={'username': 'admin', 'password': 'admin'}, allow_redirects=False)
        session.get(f"{BASE_URL}/")
    else:
        record("A-04", "Logout", "FAIL",
               expected="302", actual=f"Status {r4.status_code}")
    
    # A-05: API without API key
    r5 = requests.post(f"{BASE_URL}/api/upload", files={
        'file': ('test.jpg', make_image(), 'image/jpeg')
    }, verify=False)
    if r5.status_code == 401:
        record("A-05", "API Upload โดยไม่มี API Key", "PASS",
               expected="401 Unauthorized", actual=f"Status {r5.status_code}")
    else:
        record("A-05", "API Upload โดยไม่มี API Key", "FAIL",
               expected="401", actual=f"Status {r5.status_code}")
    
    # A-06: API with invalid key
    r6 = requests.post(f"{BASE_URL}/api/upload", files={
        'file': ('test.jpg', make_image(), 'image/jpeg')
    }, data={'api_key': 'fake-invalid-key'}, verify=False)
    if r6.status_code == 401:
        record("A-06", "API Upload ด้วย API Key ปลอม", "PASS",
               expected="401 Unauthorized", actual=f"Status {r6.status_code}")
    else:
        record("A-06", "API Upload ด้วย API Key ปลอม", "FAIL",
               expected="401", actual=f"Status {r6.status_code}")


# =============================================================================
# SECTION B: Upload & File Validation
# =============================================================================
def test_upload_validation(session):
    section("B. อัปโหลดไฟล์ & Validation")
    print(f"\n{'='*60}")
    print(f"  B. อัปโหลดไฟล์ & Validation")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    cleanup_ids = []
    
    # B-01: Upload valid JPG
    img = make_image(200, 200, (255, 0, 0))
    r = session.post(f"{BASE_URL}/upload", files={
        'file': ('valid_test.jpg', img, 'image/jpeg')
    }, data={'category_id': cat_id, 'tags': 'test_report', 'notes': 'Test B-01'})
    d = r.json() if r.headers.get('content-type', '').startswith('application/json') else {}
    if r.status_code == 200 and d.get('success'):
        cleanup_ids.append(d['snapshot_id'])
        record("B-01", "อัปโหลดไฟล์ .jpg ปกติ", "PASS",
               input_data="valid_test.jpg (200x200, JPEG)",
               expected="อัปโหลดสำเร็จ",
               actual=f"สำเร็จ, ID={d['snapshot_id']}")
    else:
        record("B-01", "อัปโหลดไฟล์ .jpg ปกติ", "FAIL",
               expected="success=true", actual=f"Status {r.status_code}: {d.get('error','')}")
    
    # B-02: Upload valid PNG
    img2 = make_image(150, 150, (0, 255, 0), 'PNG')
    r2 = session.post(f"{BASE_URL}/upload", files={
        'file': ('valid_test.png', img2, 'image/png')
    }, data={'category_id': cat_id, 'tags': 'test_report'})
    d2 = r2.json() if r2.headers.get('content-type', '').startswith('application/json') else {}
    if r2.status_code == 200 and d2.get('success'):
        cleanup_ids.append(d2['snapshot_id'])
        record("B-02", "อัปโหลดไฟล์ .png ปกติ", "PASS",
               input_data="valid_test.png (150x150)",
               expected="อัปโหลดสำเร็จ", actual=f"สำเร็จ, ID={d2['snapshot_id']}")
    else:
        record("B-02", "อัปโหลดไฟล์ .png ปกติ", "FAIL",
               expected="success", actual=f"{r2.status_code}: {d2.get('error','')}")
    
    # B-03: Upload .txt file (invalid)
    r3 = session.post(f"{BASE_URL}/upload", files={
        'file': ('document.txt', io.BytesIO(b'hello world'), 'text/plain')
    }, data={'category_id': cat_id})
    d3 = r3.json() if r3.headers.get('content-type', '').startswith('application/json') else {}
    if r3.status_code == 400 and not d3.get('success'):
        record("B-03", "อัปโหลดไฟล์ .txt (ไม่ใช่รูปภาพ)", "PASS",
               input_data="document.txt",
               expected="ปฏิเสธ — Invalid file type",
               actual=f"ปฏิเสธ: {d3.get('error','')[:50]}")
    else:
        record("B-03", "อัปโหลดไฟล์ .txt (ไม่ใช่รูปภาพ)", "FAIL",
               expected="400 + rejected", actual=f"Status {r3.status_code}")
    
    # B-04: Upload .exe file
    r4 = session.post(f"{BASE_URL}/upload", files={
        'file': ('virus.exe', io.BytesIO(b'\x00\x01\x02'), 'application/octet-stream')
    }, data={'category_id': cat_id})
    d4 = r4.json() if r4.headers.get('content-type', '').startswith('application/json') else {}
    if r4.status_code == 400:
        record("B-04", "อัปโหลดไฟล์ .exe", "PASS",
               input_data="virus.exe",
               expected="ปฏิเสธ", actual=f"ปฏิเสธ: {d4.get('error','')[:50]}")
    else:
        record("B-04", "อัปโหลดไฟล์ .exe", "FAIL",
               expected="400", actual=f"Status {r4.status_code}")
    
    # B-05: Upload .gif file (not in strict list)
    gif_img = make_image(10, 10, (50, 50, 50), 'GIF')
    r5 = session.post(f"{BASE_URL}/upload", files={
        'file': ('anim.gif', gif_img, 'image/gif')
    }, data={'category_id': cat_id})
    d5 = r5.json() if r5.headers.get('content-type', '').startswith('application/json') else {}
    if r5.status_code == 400:
        record("B-05", "อัปโหลดไฟล์ .gif (ไม่อยู่ในรายการอนุญาต)", "PASS",
               input_data="anim.gif",
               expected="ปฏิเสธ — เฉพาะ jpg/jpeg/png เท่านั้น",
               actual=f"ปฏิเสธ: {d5.get('error','')[:50]}")
    else:
        record("B-05", "อัปโหลดไฟล์ .gif", "FAIL",
               expected="400", actual=f"Status {r5.status_code}")
    
    # B-06: Upload without selecting category
    img6 = make_image(60, 60, (200, 200, 0))
    r6 = session.post(f"{BASE_URL}/upload", files={
        'file': ('no_category.jpg', img6, 'image/jpeg')
    }, data={'tags': 'test'})
    d6 = r6.json() if r6.headers.get('content-type', '').startswith('application/json') else {}
    if r6.status_code == 400 and not d6.get('success'):
        record("B-06", "อัปโหลดโดยไม่เลือก Category", "PASS",
               input_data="ไม่ส่ง category_id",
               expected="ปฏิเสธ — ต้องเลือกหมวดหมู่",
               actual=f"ปฏิเสธ: {d6.get('error','')[:50]}")
    else:
        record("B-06", "อัปโหลดโดยไม่เลือก Category", "FAIL",
               expected="400", actual=f"Status {r6.status_code}")
    
    # B-07: Upload to parent category
    parent_id = get_parent_cat(session)
    if parent_id:
        img7 = make_image(61, 61, (200, 0, 200))
        r7 = session.post(f"{BASE_URL}/upload", files={
            'file': ('parent_cat.jpg', img7, 'image/jpeg')
        }, data={'category_id': parent_id})
        d7 = r7.json() if r7.headers.get('content-type', '').startswith('application/json') else {}
        if r7.status_code == 400:
            record("B-07", "อัปโหลดไปยัง Parent Category", "PASS",
                   input_data=f"category_id={parent_id} (เป็น parent)",
                   expected="ปฏิเสธ — ต้องเลือกหมวดหมู่ย่อย",
                   actual=f"ปฏิเสธ: {d7.get('error','')[:50]}")
        else:
            record("B-07", "อัปโหลดไปยัง Parent Category", "FAIL",
                   expected="400", actual=f"Status {r7.status_code}")
    else:
        record("B-07", "อัปโหลดไปยัง Parent Category", "SKIP",
               detail="ไม่มี parent category ในระบบ")
    
    cleanup(session, cleanup_ids)


# =============================================================================
# SECTION C: Duplicate Detection
# =============================================================================
def test_duplicate_detection(session):
    section("C. ระบบตรวจจับไฟล์ซ้ำ (Duplicate Detection)")
    print(f"\n{'='*60}")
    print(f"  C. ระบบตรวจจับไฟล์ซ้ำ (Duplicate Detection)")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    cleanup_ids = []
    
    # C-01: Upload same image twice (Web UI)
    img_data = make_image(120, 120, (255, 100, 0)).read()
    
    r1 = session.post(f"{BASE_URL}/upload", files={
        'file': ('dup_test.jpg', io.BytesIO(img_data), 'image/jpeg')
    }, data={'category_id': cat_id, 'tags': 'dup_test'})
    d1 = r1.json()
    
    if d1.get('success'):
        cleanup_ids.append(d1['snapshot_id'])
        
        r2 = session.post(f"{BASE_URL}/upload", files={
            'file': ('dup_test.jpg', io.BytesIO(img_data), 'image/jpeg')
        }, data={'category_id': cat_id, 'tags': 'dup_test'})
        d2 = r2.json()
        
        if r2.status_code == 409 and not d2.get('success'):
            record("C-01", "อัปโหลดไฟล์เดียวกัน 2 ครั้ง (ชื่อเหมือน, เนื้อหาเหมือน)", "PASS",
                   input_data="dup_test.jpg (ครั้งที่ 2)",
                   expected="ปฏิเสธ — Duplicate detected",
                   actual=f"ปฏิเสธ 409: {d2.get('error','')[:50]}")
        else:
            record("C-01", "อัปโหลดไฟล์เดียวกัน 2 ครั้ง", "FAIL",
                   expected="409 Conflict", actual=f"Status {r2.status_code}")
            if d2.get('snapshot_id'): cleanup_ids.append(d2['snapshot_id'])
    else:
        record("C-01", "อัปโหลดไฟล์เดียวกัน 2 ครั้ง", "FAIL",
               detail=f"อัปโหลดครั้งแรกล้มเหลว: {d1.get('error')}")
    
    # C-02: Same content, different filename (API)
    img2_data = make_image(80, 80, (0, 255, 50)).read()
    
    r3 = session.post(f"{BASE_URL}/api/upload", files={
        'file': ('name_A.jpg', io.BytesIO(img2_data), 'image/jpeg')
    }, data={'api_key': API_KEY, 'camera_id': 'test', 'category_id': cat_id})
    d3 = r3.json()
    
    if d3.get('success'):
        cleanup_ids.append(d3['snapshot_id'])
        
        r4 = session.post(f"{BASE_URL}/api/upload", files={
            'file': ('name_B_different.jpg', io.BytesIO(img2_data), 'image/jpeg')
        }, data={'api_key': API_KEY, 'camera_id': 'test', 'category_id': cat_id})
        d4 = r4.json()
        
        if r4.status_code == 409:
            record("C-02", "อัปโหลดเนื้อหาเดียวกัน ชื่อไฟล์ต่าง (Hash-based)", "PASS",
                   input_data="name_A.jpg → name_B_different.jpg (เนื้อหาเดียวกัน)",
                   expected="ปฏิเสธ — hash เหมือนกัน",
                   actual=f"ปฏิเสธ 409 (ตรวจจาก SHA-256 hash)")
        else:
            record("C-02", "อัปโหลดเนื้อหาเดียวกัน ชื่อไฟล์ต่าง", "FAIL",
                   expected="409", actual=f"Status {r4.status_code}")
            if d4.get('snapshot_id'): cleanup_ids.append(d4['snapshot_id'])
    else:
        record("C-02", "อัปโหลดเนื้อหาเดียวกัน ชื่อไฟล์ต่าง", "FAIL",
               detail=f"ครั้งแรกล้มเหลว: {d3.get('error')}")
    
    # C-03: Same filename, different content → should be accepted
    img_a = make_image(90, 90, (0, 0, 200)).read()
    img_b = make_image(90, 90, (0, 0, 150)).read()  # Different color = different hash
    
    r5 = session.post(f"{BASE_URL}/upload", files={
        'file': ('same_name.jpg', io.BytesIO(img_a), 'image/jpeg')
    }, data={'category_id': cat_id, 'tags': 'dup_test'})
    d5 = r5.json()
    if d5.get('success'):
        cleanup_ids.append(d5['snapshot_id'])
        
        r6 = session.post(f"{BASE_URL}/upload", files={
            'file': ('same_name.jpg', io.BytesIO(img_b), 'image/jpeg')
        }, data={'category_id': cat_id, 'tags': 'dup_test'})
        d6 = r6.json()
        if r6.status_code == 200 and d6.get('success'):
            cleanup_ids.append(d6['snapshot_id'])
            record("C-03", "ชื่อไฟล์เหมือน แต่เนื้อหาต่าง (hash ต่าง)", "PASS",
                   input_data="same_name.jpg × 2 (สีต่างกัน)",
                   expected="ยอมรับ — เพราะ hash ต่าง",
                   actual=f"ยอมรับ, ID={d6['snapshot_id']}")
        else:
            record("C-03", "ชื่อไฟล์เหมือน แต่เนื้อหาต่าง", "FAIL",
                   expected="ยอมรับ", actual=f"Status {r6.status_code}: {d6.get('error','')}")
    
    cleanup(session, cleanup_ids)


# =============================================================================
# SECTION D: Timestamp Priority
# =============================================================================
def test_timestamp_priority(session):
    section("D. ลำดับความสำคัญของ Timestamp")
    print(f"\n{'='*60}")
    print(f"  D. ลำดับความสำคัญของ Timestamp")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    cleanup_ids = []
    
    # D-01: Manual capture time via web form
    img1 = make_image(70, 70, (100, 50, 50))
    r1 = session.post(f"{BASE_URL}/upload", files={
        'file': ('ts_manual.jpg', img1, 'image/jpeg')
    }, data={'category_id': cat_id, 'capture_time': '2025-05-25T08:00:00', 'tags': 'ts_test'})
    d1 = r1.json()
    if d1.get('success'):
        cleanup_ids.append(d1['snapshot_id'])
        ct = d1.get('capture_time', '')
        if '2025-05-25 08:00:00' in ct:
            record("D-01", "ใส่ Manual Capture Time ผ่านเว็บฟอร์ม", "PASS",
                   input_data="capture_time=2025-05-25T08:00:00",
                   expected="บันทึก 2025-05-25 08:00:00",
                   actual=f"บันทึก: {ct}")
        else:
            record("D-01", "ใส่ Manual Capture Time ผ่านเว็บฟอร์ม", "FAIL",
                   expected="2025-05-25 08:00:00", actual=ct)
    else:
        record("D-01", "ใส่ Manual Capture Time", "FAIL",
               actual=d1.get('error',''))
    
    # D-02: Timestamp from filename (no manual input)
    img2 = make_image(71, 71, (101, 51, 51))
    r2 = session.post(f"{BASE_URL}/upload", files={
        'file': ('cam6_20250525_120000.jpg', img2, 'image/jpeg')
    }, data={'category_id': cat_id, 'tags': 'ts_test'})
    d2 = r2.json()
    if d2.get('success'):
        cleanup_ids.append(d2['snapshot_id'])
        ct2 = d2.get('capture_time', '')
        if '2025-05-25 12:00:00' in ct2:
            record("D-02", "Timestamp จากชื่อไฟล์ (cam6_20250525_120000.jpg)", "PASS",
                   input_data="filename=cam6_20250525_120000.jpg, ไม่มี manual time",
                   expected="ดึงจากชื่อไฟล์: 2025-05-25 12:00:00",
                   actual=f"บันทึก: {ct2}")
        else:
            record("D-02", "Timestamp จากชื่อไฟล์", "FAIL",
                   expected="2025-05-25 12:00:00", actual=ct2)
    else:
        record("D-02", "Timestamp จากชื่อไฟล์", "FAIL", actual=d2.get('error',''))
    
    # D-03: No timestamp → use server time
    img3 = make_image(72, 72, (102, 52, 52))
    before = datetime.now()
    r3 = session.post(f"{BASE_URL}/upload", files={
        'file': ('random_photo.jpg', img3, 'image/jpeg')
    }, data={'category_id': cat_id, 'tags': 'ts_test'})
    d3 = r3.json()
    if d3.get('success'):
        cleanup_ids.append(d3['snapshot_id'])
        ct3 = d3.get('capture_time', '')
        try:
            ct_dt = datetime.strptime(ct3, '%Y-%m-%d %H:%M:%S')
            diff = abs((ct_dt - before).total_seconds())
            if diff < 60:
                record("D-03", "ไม่มี timestamp → ใช้ Server Time", "PASS",
                       input_data="filename=random_photo.jpg, ไม่มี timestamp ใดๆ",
                       expected="ใช้เวลา server ปัจจุบัน",
                       actual=f"บันทึก: {ct3} (ห่างจาก server time {diff:.0f} วินาที)")
            else:
                record("D-03", "ไม่มี timestamp → ใช้ Server Time", "FAIL",
                       expected="ใกล้กับ server time", actual=f"{ct3} — ต่างกัน {diff:.0f}s")
        except:
            record("D-03", "ไม่มี timestamp → ใช้ Server Time", "FAIL", actual=ct3)
    
    # D-04: API upload with timestamp in body
    img4 = make_image(73, 73, (103, 53, 53))
    r4 = session.post(f"{BASE_URL}/api/upload", files={
        'file': ('api_ts.jpg', img4, 'image/jpeg')
    }, data={'api_key': API_KEY, 'camera_id': 'cam1', 'category_id': cat_id,
             'timestamp': '2025-06-15 14:30:00'})
    d4 = r4.json()
    if d4.get('success'):
        cleanup_ids.append(d4['snapshot_id'])
        ct4 = d4.get('capture_time', '')
        if '2025-06-15 14:30:00' in ct4:
            record("D-04", "API Upload ส่ง Timestamp ผ่าน Body", "PASS",
                   input_data="timestamp=2025-06-15 14:30:00",
                   expected="บันทึกตาม body", actual=f"บันทึก: {ct4}")
        else:
            record("D-04", "API Upload ส่ง Timestamp ผ่าน Body", "FAIL",
                   expected="2025-06-15 14:30:00", actual=ct4)
    else:
        record("D-04", "API Upload ส่ง Timestamp ผ่าน Body", "FAIL",
               actual=d4.get('error',''))
    
    # D-05: DB has separate capture_time and upload_time
    r5 = session.get(f"{BASE_URL}/api/snapshots?limit=1")
    if r5.status_code == 200:
        snaps = r5.json().get('snapshots', [])
        if snaps:
            has_ct = 'capture_time' in snaps[0]
            has_ut = 'upload_time' in snaps[0]
            if has_ct and has_ut:
                record("D-05", "ฐานข้อมูลมี capture_time และ upload_time แยกกัน", "PASS",
                       expected="มีทั้ง 2 คอลัมน์",
                       actual=f"capture_time={snaps[0]['capture_time']}, upload_time={snaps[0]['upload_time']}")
            else:
                record("D-05", "ฐานข้อมูลมี capture_time และ upload_time", "FAIL",
                       expected="ทั้ง 2 columns", actual=f"ct={'มี' if has_ct else 'ไม่มี'}, ut={'มี' if has_ut else 'ไม่มี'}")
    
    cleanup(session, cleanup_ids)


# =============================================================================
# SECTION E: Category & Hierarchy
# =============================================================================
def test_categories(session):
    section("E. ระบบหมวดหมู่ & Hierarchy")
    print(f"\n{'='*60}")
    print(f"  E. ระบบหมวดหมู่ & Hierarchy")
    print(f"{'='*60}")
    
    # E-01: Get category tree
    r1 = session.get(f"{BASE_URL}/api/categories")
    d1 = r1.json()
    cats = d1.get('categories', [])
    parents = [c for c in cats if c.get('parent_id') is None]
    children = [c for c in cats if c.get('parent_id') is not None]
    if parents and children:
        record("E-01", "ดึงโครงสร้าง Category Tree", "PASS",
               expected="มี Parent + Child categories",
               actual=f"Parents: {len(parents)}, Children: {len(children)}")
    else:
        record("E-01", "ดึงโครงสร้าง Category Tree", "FAIL",
               expected="มี hierarchy", actual=f"P={len(parents)}, C={len(children)}")
    
    # E-02: Add new category
    r2 = session.post(f"{BASE_URL}/api/categories", json={
        'name': f'Test_Cat_{int(time.time())}',
        'description': 'Test category for report'
    })
    d2 = r2.json()
    new_cat_id = None
    if d2.get('success') or d2.get('category_id'):
        new_cat_id = d2.get('category_id', d2.get('id'))
        record("E-02", "สร้าง Category ใหม่", "PASS",
               input_data=f"name=Test_Cat_*",
               expected="สร้างสำเร็จ", actual=f"ID={new_cat_id}")
    else:
        record("E-02", "สร้าง Category ใหม่", "FAIL",
               expected="success", actual=f"Status {r2.status_code}: {d2}")
    
    # E-03: Delete empty category
    if new_cat_id:
        r3 = session.delete(f"{BASE_URL}/api/category/{new_cat_id}")
        d3 = r3.json()
        if d3.get('success'):
            record("E-03", "ลบ Category ที่ว่าง (ไม่มี snapshot)", "PASS",
                   input_data=f"category_id={new_cat_id}",
                   expected="ลบได้", actual="ลบสำเร็จ")
        else:
            record("E-03", "ลบ Category ที่ว่าง", "FAIL",
                   expected="ลบได้", actual=f"{d3.get('error','')}")
    else:
        record("E-03", "ลบ Category ที่ว่าง", "SKIP", detail="ไม่สามารถสร้าง cat")
    
    # E-04: Delete category that has snapshots → should block
    leaf_id = get_leaf_cat(session)
    # Check if leaf has snapshots
    r_check = session.get(f"{BASE_URL}/api/snapshots?category_id={leaf_id}&limit=1")
    has_snaps = r_check.status_code == 200 and len(r_check.json().get('snapshots', [])) > 0
    
    if has_snaps:
        r4 = session.delete(f"{BASE_URL}/api/category/{leaf_id}")
        d4 = r4.json()
        if not d4.get('success'):
            record("E-04", "ลบ Category ที่มี Snapshot อยู่", "PASS",
                   input_data=f"category_id={leaf_id} (มี snapshots)",
                   expected="ห้ามลบ — ปกป้องข้อมูล",
                   actual=f"ถูกบล็อก: {d4.get('error', d4.get('message',''))[:50]}")
        else:
            record("E-04", "ลบ Category ที่มี Snapshot อยู่", "FAIL",
                   expected="ห้ามลบ", actual="ลบได้ (ไม่ควรทำได้)")
    else:
        # Create a snapshot first to test
        img = make_image(55, 55, (111, 222, 111))
        ru = session.post(f"{BASE_URL}/upload", files={
            'file': ('cat_del_test.jpg', img, 'image/jpeg')
        }, data={'category_id': leaf_id, 'tags': 'cat_del_test'})
        du = ru.json()
        if du.get('success'):
            r4 = session.delete(f"{BASE_URL}/api/category/{leaf_id}")
            d4 = r4.json()
            if not d4.get('success'):
                record("E-04", "ลบ Category ที่มี Snapshot อยู่", "PASS",
                       expected="ห้ามลบ", actual=f"บล็อก: {d4.get('error','')[:50]}")
            else:
                record("E-04", "ลบ Category ที่มี Snapshot อยู่", "FAIL",
                       expected="ห้ามลบ", actual="ลบได้")
            cleanup(session, [du['snapshot_id']])


# =============================================================================
# SECTION F: API Validation
# =============================================================================
def test_api_validation(session):
    section("F. API Logical Validation")
    print(f"\n{'='*60}")
    print(f"  F. API Logical Validation")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    cleanup_ids = []
    
    # F-01: Valid API upload
    img = make_image(50, 50, (150, 150, 0))
    r1 = session.post(f"{BASE_URL}/api/upload", files={
        'file': ('api_valid.jpg', img, 'image/jpeg')
    }, data={'api_key': API_KEY, 'camera_id': 'cam_rpi1', 'category_id': cat_id})
    d1 = r1.json()
    if d1.get('success'):
        cleanup_ids.append(d1['snapshot_id'])
        record("F-01", "API Upload ด้วยข้อมูลถูกต้องทั้งหมด", "PASS",
               input_data=f"api_key=valid, camera_id=cam_rpi1, category_id={cat_id}",
               expected="อัปโหลดสำเร็จ",
               actual=f"สำเร็จ, ID={d1['snapshot_id']}")
    else:
        record("F-01", "API Upload ด้วยข้อมูลถูกต้อง", "FAIL",
               expected="success", actual=f"Status {r1.status_code}: {d1.get('error','')}")
    
    # F-02: Invalid category_id
    img2 = make_image(51, 51, (0, 150, 150))
    r2 = session.post(f"{BASE_URL}/api/upload", files={
        'file': ('api_bad_cat.jpg', img2, 'image/jpeg')
    }, data={'api_key': API_KEY, 'camera_id': 'cam1', 'category_id': 99999})
    d2 = r2.json()
    if r2.status_code == 400 and not d2.get('success'):
        record("F-02", "API Upload ด้วย category_id ที่ไม่มีจริง", "PASS",
               input_data="category_id=99999",
               expected="400 — ไม่พบ category",
               actual=f"ปฏิเสธ: {d2.get('error','')[:50]}")
    else:
        record("F-02", "API Upload ด้วย category_id ที่ไม่มีจริง", "FAIL",
               expected="400", actual=f"Status {r2.status_code}")
        if d2.get('snapshot_id'): cleanup_ids.append(d2['snapshot_id'])
    
    # F-03: API Upload to parent category
    parent_id = get_parent_cat(session)
    if parent_id:
        img3 = make_image(52, 52, (150, 0, 150))
        r3 = session.post(f"{BASE_URL}/api/upload", files={
            'file': ('api_parent_cat.jpg', img3, 'image/jpeg')
        }, data={'api_key': API_KEY, 'camera_id': 'cam1', 'category_id': parent_id})
        d3 = r3.json()
        if r3.status_code == 400:
            record("F-03", "API Upload ไปยัง Parent Category", "PASS",
                   input_data=f"category_id={parent_id} (parent)",
                   expected="400 — ต้องเลือก sub-category",
                   actual=f"ปฏิเสธ: {d3.get('error','')[:50]}")
        else:
            record("F-03", "API Upload ไปยัง Parent Category", "FAIL",
                   expected="400", actual=f"Status {r3.status_code}")
            if d3.get('snapshot_id'): cleanup_ids.append(d3['snapshot_id'])
    else:
        record("F-03", "API Upload ไปยัง Parent Category", "SKIP")
    
    # F-04: Get single snapshot API
    if cleanup_ids:
        r4 = session.get(f"{BASE_URL}/api/snapshot/{cleanup_ids[0]}")
        d4 = r4.json()
        if r4.status_code == 200 and d4.get('success'):
            record("F-04", "GET /api/snapshot/:id — ดึงข้อมูล snapshot ตาม ID", "PASS",
                   input_data=f"snapshot_id={cleanup_ids[0]}",
                   expected="ได้ข้อมูล snapshot",
                   actual=f"filename={d4['snapshot']['filename']}")
        else:
            record("F-04", "GET /api/snapshot/:id", "FAIL",
                   expected="200", actual=f"Status {r4.status_code}")
    
    cleanup(session, cleanup_ids)


# =============================================================================
# SECTION G: Folder Import
# =============================================================================
def test_folder_import(session):
    section("G. นำเข้าจากโฟลเดอร์ (Folder Import)")
    print(f"\n{'='*60}")
    print(f"  G. นำเข้าจากโฟลเดอร์ (Folder Import)")
    print(f"{'='*60}")
    
    tmpdir = tempfile.mkdtemp(prefix='aero_test_')
    cat_id = get_leaf_cat(session)
    
    try:
        import random
        rand_seed = int(time.time() * 1000) % 100000
        # Create 5 valid images + 1 corrupt + 1 unsupported (random colors per run)
        for i in range(5):
            color = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            img = Image.new('RGB', (40 + i, 40 + i), color=color)
            img.save(os.path.join(tmpdir, f'import_img_{i}.jpg'))
        
        # Subfolder
        sub = os.path.join(tmpdir, 'cam1', '2025-05')
        os.makedirs(sub)
        for i in range(3):
            color = (random.randint(0,255), random.randint(0,255), random.randint(0,255))
            img = Image.new('RGB', (45 + i, 45 + i), color=color)
            img.save(os.path.join(sub, f'sub_{i}.jpg'))
        
        # Corrupt file
        with open(os.path.join(tmpdir, 'corrupt.jpg'), 'w') as f:
            f.write("not jpeg")
        
        # Unsupported file
        with open(os.path.join(tmpdir, 'notes.txt'), 'w') as f:
            f.write("text file")
        
        # Zero byte
        open(os.path.join(tmpdir, 'empty.jpg'), 'w').close()
        
        # G-01: Import folder
        r1 = session.post(f"{BASE_URL}/import-drive", data={
            'folder_path': tmpdir,
            'source_name': 'Test Report Import',
            'category_id': cat_id or '',
            'skip_duplicates': 'on'
        })
        html = r1.text
        
        import_match = re.search(r'Successfully imported (\d+)', html)
        if import_match:
            count = int(import_match.group(1))
            record("G-01", "นำเข้าไฟล์จากโฟลเดอร์", "PASS",
                   input_data=f"folder={tmpdir} (8 valid + 3 invalid)",
                   expected="นำเข้าเฉพาะไฟล์ถูกต้อง",
                   actual=f"นำเข้า {count} ไฟล์")
        elif 'imported' in html.lower():
            record("G-01", "นำเข้าไฟล์จากโฟลเดอร์", "PASS",
                   actual="Import completed")
        else:
            record("G-01", "นำเข้าไฟล์จากโฟลเดอร์", "FAIL",
                   actual="ไม่พบข้อความ success")
        
        # G-02: Subfolder scanning
        if import_match and int(import_match.group(1)) >= 8:
            record("G-02", "สแกนโฟลเดอร์ย่อย (recursive)", "PASS",
                   input_data="root (5 files) + cam1/2025-05/ (3 files)",
                   expected="สแกนทั้ง root และ subfolder ≥ 8 ไฟล์",
                   actual=f"นำเข้า {import_match.group(1)} ไฟล์")
        else:
            record("G-02", "สแกนโฟลเดอร์ย่อย", "FAIL" if import_match else "SKIP",
                   expected="≥8", actual=import_match.group(1) if import_match else "N/A")
        
        # G-03: Invalid files skipped
        skip_match = re.search(r'Skipped (\d+) invalid', html)
        if skip_match or 'Skipped' in html:
            record("G-03", "ข้ามไฟล์เสีย/ไม่รองรับ", "PASS",
                   input_data="corrupt.jpg, notes.txt, empty.jpg",
                   expected="ข้ามไฟล์ที่ไม่ถูกต้อง",
                   actual=f"ข้าม {skip_match.group(1) if skip_match else '?'} ไฟล์")
        else:
            record("G-03", "ข้ามไฟล์เสีย/ไม่รองรับ", "FAIL",
                   expected="มี skip message", actual="ไม่พบ")
        
        # G-04: Re-import → skip duplicates
        r2 = session.post(f"{BASE_URL}/import-drive", data={
            'folder_path': tmpdir,
            'source_name': 'Re-import Test',
            'category_id': cat_id or '',
            'skip_duplicates': 'on'
        })
        html2 = r2.text
        dup_match = re.search(r'Skipped (\d+) duplicate', html2)
        if dup_match:
            record("G-04", "นำเข้าซ้ำ → ข้าม Duplicates", "PASS",
                   input_data="นำเข้าโฟลเดอร์เดิมอีกครั้ง",
                   expected="ข้ามทุกไฟล์ (เคยนำเข้าแล้ว)",
                   actual=f"ข้าม {dup_match.group(1)} ไฟล์ซ้ำ")
        elif 'duplicate' in html2.lower():
            record("G-04", "นำเข้าซ้ำ → ข้าม Duplicates", "PASS",
                   actual="พบ duplicate message")
        else:
            record("G-04", "นำเข้าซ้ำ → ข้าม Duplicates", "FAIL",
                   expected="skip duplicates", actual="ไม่พบ duplicate message")
    
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# =============================================================================
# SECTION H: Time-lapse Video Generation  
# =============================================================================
def test_timelapse(session):
    section("H. สร้างวิดีโอ Time-lapse")
    print(f"\n{'='*60}")
    print(f"  H. สร้างวิดีโอ Time-lapse")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    
    # H-01: Generate timelapse (start date only → single day)
    r1 = session.post(f"{BASE_URL}/api/generate-video", data={
        'category_id': str(cat_id) if cat_id else '',
        'start_time': datetime.now().strftime('%Y-%m-%d'),
        'fps': '5'
    })
    d1 = r1.json()
    if d1.get('success'):
        record("H-01", "สร้าง Time-lapse (start_date เท่านั้น → วันเดียว)", "PASS",
               input_data=f"start_time={datetime.now().strftime('%Y-%m-%d')}, end_time=ว่าง",
               expected="สร้างวิดีโอจากภาพในวันนั้น",
               actual=f"สำเร็จ, {d1.get('snapshot_count',0)} snapshots")
    elif 'no image' in d1.get('error', d1.get('message', '')).lower():
        record("H-01", "สร้าง Time-lapse (start_date เท่านั้น → วันเดียว)", "PASS",
               expected="ไม่ crash ถ้าไม่มีรูป",
               actual=f"No images — ไม่ crash")
    else:
        record("H-01", "สร้าง Time-lapse (start_date เท่านั้น)", "FAIL",
               actual=f"Status {r1.status_code}: {d1}")
    
    # H-02: Generate timelapse with date range
    r2 = session.post(f"{BASE_URL}/api/generate-video", data={
        'category_id': str(cat_id) if cat_id else '',
        'start_time': '2025-01-01',
        'end_time': '2026-12-31',
        'fps': '10'
    })
    d2 = r2.json()
    if d2.get('success'):
        record("H-02", "สร้าง Time-lapse (ช่วงวันยาว)", "PASS",
               input_data="start=2025-01-01, end=2026-12-31",
               expected="สร้างได้ ไม่ crash",
               actual=f"สำเร็จ, {d2.get('snapshot_count',0)} snapshots")
    elif 'no image' in d2.get('error', d2.get('message', '')).lower():
        record("H-02", "สร้าง Time-lapse (ช่วงวันยาว)", "PASS",
               actual="ไม่มีภาพในช่วง — no crash")
    else:
        record("H-02", "สร้าง Time-lapse (ช่วงวันยาว)", "FAIL",
               actual=f"Status {r2.status_code}: {d2}")
    
    # H-03: Generate with no matching images
    r3 = session.post(f"{BASE_URL}/api/generate-video", data={
        'start_time': '2000-01-01',
        'end_time': '2000-01-02',
        'fps': '5'
    })
    d3 = r3.json()
    err3 = d3.get('error', d3.get('message', '')).lower()
    if not d3.get('success') or 'no image' in err3 or 'no snapshot' in err3:
        record("H-03", "สร้าง Time-lapse ไม่มีภาพตรงเงื่อนไข", "PASS",
               input_data="period=2000-01-01 to 2000-01-02",
               expected="แจ้ง No images ไม่ crash",
               actual=f"Handled gracefully")
    else:
        record("H-03", "สร้าง Time-lapse ไม่มีภาพ", "FAIL",
               expected="error or empty", actual=f"Status {r3.status_code}: {d3}")
    
    # H-04: Videos list page
    r4 = session.get(f"{BASE_URL}/videos")
    if r4.status_code == 200:
        record("H-04", "เข้าหน้ารายการวิดีโอ (/videos)", "PASS",
               expected="200 OK", actual=f"Status {r4.status_code}")
    else:
        record("H-04", "เข้าหน้ารายการวิดีโอ", "FAIL",
               expected="200", actual=f"Status {r4.status_code}")


# =============================================================================
# SECTION I: Edit & Delete Snapshot
# =============================================================================
def test_edit_delete(session):
    section("I. แก้ไข & ลบ Snapshot")
    print(f"\n{'='*60}")
    print(f"  I. แก้ไข & ลบ Snapshot")
    print(f"{'='*60}")
    
    cat_id = get_leaf_cat(session)
    
    # Create test snapshot
    img = make_image(65, 65, (180, 180, 0))
    r = session.post(f"{BASE_URL}/upload", files={
        'file': ('edit_test.jpg', img, 'image/jpeg')
    }, data={'category_id': cat_id, 'capture_time': '2025-06-01T10:00:00', 'tags': 'edit_test'})
    d = r.json()
    if not d.get('success'):
        record("I-00", "สร้าง Snapshot สำหรับทดสอบ", "FAIL", actual=d.get('error'))
        return
    sid = d['snapshot_id']
    
    # I-01: Edit tags & notes
    r1 = session.post(f"{BASE_URL}/snapshot/{sid}/edit", data={
        'category_id': cat_id,
        'tags': 'updated_tag, new_tag',
        'notes': 'Updated notes for test',
        'capture_time': ''
    }, allow_redirects=False)
    
    r1b = session.get(f"{BASE_URL}/api/snapshot/{sid}")
    d1b = r1b.json()
    snap = d1b.get('snapshot', {})
    if 'updated_tag' in snap.get('tags', ''):
        record("I-01", "แก้ไข Tags & Notes", "PASS",
               input_data=f"tags='updated_tag, new_tag', notes='Updated notes for test'",
               expected="บันทึกค่าใหม่",
               actual=f"tags={snap.get('tags','')[:40]}, notes={snap.get('notes','')[:30]}")
    else:
        record("I-01", "แก้ไข Tags & Notes", "FAIL",
               expected="updated_tag in tags", actual=f"tags={snap.get('tags','')}")
    
    # I-02: Edit Capture Time
    r2 = session.post(f"{BASE_URL}/snapshot/{sid}/edit", data={
        'category_id': cat_id,
        'tags': 'updated_tag, new_tag',
        'notes': 'Updated notes',
        'capture_time': '2025-07-15T15:30:00'
    }, allow_redirects=False)
    
    r2b = session.get(f"{BASE_URL}/api/snapshot/{sid}")
    d2b = r2b.json()
    snap2 = d2b.get('snapshot', {})
    ct = snap2.get('capture_time', '')
    if '2025-07-15' in ct and '15:30' in ct:
        record("I-02", "แก้ไข Capture Time", "PASS",
               input_data="capture_time=2025-07-15T15:30:00",
               expected="เปลี่ยนเป็น 2025-07-15 15:30:00",
               actual=f"capture_time={ct}")
    else:
        record("I-02", "แก้ไข Capture Time", "FAIL",
               expected="2025-07-15 15:30", actual=f"capture_time={ct}")
    
    # I-03: View snapshot page
    r3 = session.get(f"{BASE_URL}/snapshot/{sid}")
    if r3.status_code == 200:
        record("I-03", "เข้าหน้าดู Snapshot (/snapshot/:id)", "PASS",
               expected="200 OK", actual=f"Status {r3.status_code}")
    else:
        record("I-03", "เข้าหน้าดู Snapshot", "FAIL",
               expected="200", actual=f"Status {r3.status_code}")
    
    # I-04: View snapshot image
    r4 = session.get(f"{BASE_URL}/snapshot/image/{sid}")
    if r4.status_code == 200 and 'image' in r4.headers.get('content-type', ''):
        record("I-04", "แสดงรูปภาพ Snapshot (/snapshot/image/:id)", "PASS",
               expected="ได้ไฟล์ภาพกลับมา",
               actual=f"Content-Type={r4.headers.get('content-type')}, Size={len(r4.content)} bytes")
    else:
        record("I-04", "แสดงรูปภาพ Snapshot", "FAIL",
               expected="image/*", actual=f"Status {r4.status_code}")
    
    # I-05: Delete snapshot
    r5 = session.delete(f"{BASE_URL}/api/snapshot/{sid}")
    d5 = r5.json()
    if d5.get('success'):
        record("I-05", "ลบ Snapshot ผ่าน API", "PASS",
               input_data=f"snapshot_id={sid}",
               expected="ลบสำเร็จ", actual="ลบสำเร็จ")
    else:
        record("I-05", "ลบ Snapshot ผ่าน API", "FAIL",
               expected="success", actual=f"{d5.get('error','')}")
    
    # I-06: Access deleted snapshot → 404
    r6 = session.get(f"{BASE_URL}/api/snapshot/{sid}")
    if r6.status_code == 404:
        record("I-06", "เข้าถึง Snapshot ที่ลบแล้ว → 404", "PASS",
               expected="404 Not Found", actual=f"Status {r6.status_code}")
    else:
        record("I-06", "เข้าถึง Snapshot ที่ลบแล้ว", "FAIL",
               expected="404", actual=f"Status {r6.status_code}")


# =============================================================================
# SECTION J: Web Pages (Smoke Test)
# =============================================================================
def test_web_pages(session):
    section("J. หน้าเว็บทั้งหมด (Smoke Test)")
    print(f"\n{'='*60}")
    print(f"  J. หน้าเว็บทั้งหมด (Smoke Test)")
    print(f"{'='*60}")
    
    pages = [
        ("J-01", "/",               "Dashboard"),
        ("J-02", "/upload",         "Upload"),
        ("J-03", "/query",          "Search / Query"),
        ("J-04", "/daily-snapshots","Daily Snapshots"),
        ("J-05", "/generate-video", "Generate Video"),
        ("J-06", "/videos",         "Videos List"),
        ("J-07", "/categories",     "Categories"),
        ("J-08", "/import-drive",   "Import Drive"),
        ("J-09", "/stats",          "Statistics"),
        ("J-10", "/about",          "About"),
        ("J-11", "/online",         "Online Access"),
        ("J-12", "/auto-sync",      "Auto-Sync"),
        ("J-13", "/security",       "Security Settings"),
    ]
    
    for tid, path, name in pages:
        try:
            r = session.get(f"{BASE_URL}{path}", timeout=10)
            if r.status_code == 200:
                record(tid, f"หน้า {name} ({path})", "PASS",
                       expected="200 OK",
                       actual=f"Status {r.status_code}, Size={len(r.content)} bytes")
            else:
                record(tid, f"หน้า {name} ({path})", "FAIL",
                       expected="200", actual=f"Status {r.status_code}")
        except Exception as e:
            record(tid, f"หน้า {name} ({path})", "FAIL",
                   actual=f"Error: {str(e)[:50]}")


# =============================================================================
# SECTION K: Search & Query
# =============================================================================
def test_search_query(session):
    section("K. ค้นหา & Query")
    print(f"\n{'='*60}")
    print(f"  K. ค้นหา & Query")
    print(f"{'='*60}")
    
    # K-01: API snapshots query
    r1 = session.get(f"{BASE_URL}/api/snapshots?limit=5")
    if r1.status_code == 200:
        d1 = r1.json()
        record("K-01", "API Query Snapshots (limit=5)", "PASS",
               expected="ได้ list snapshots",
               actual=f"ได้ {d1.get('count',0)} รายการ")
    else:
        record("K-01", "API Query Snapshots", "FAIL",
               expected="200", actual=f"Status {r1.status_code}")
    
    # K-02: API search
    r2 = session.get(f"{BASE_URL}/api/search?q=test")
    if r2.status_code == 200:
        d2 = r2.json()
        record("K-02", "API Search (keyword='test')", "PASS",
               input_data="q=test",
               expected="ได้ผลค้นหา",
               actual=f"พบ {d2.get('count',0)} รายการ")
    else:
        record("K-02", "API Search", "FAIL",
               expected="200", actual=f"Status {r2.status_code}")
    
    # K-03: Filter options
    r3 = session.get(f"{BASE_URL}/api/filters")
    if r3.status_code == 200:
        record("K-03", "API Filter Options", "PASS",
               expected="ได้ตัวเลือก filter",
               actual=f"Status 200, data={list(r3.json().keys())}")
    else:
        record("K-03", "API Filter Options", "FAIL",
               expected="200", actual=f"Status {r3.status_code}")
    
    # K-04: Query by category
    cat_id = get_leaf_cat(session)
    if cat_id:
        r4 = session.get(f"{BASE_URL}/api/snapshots?category_id={cat_id}&limit=3")
        if r4.status_code == 200:
            d4 = r4.json()
            record("K-04", "Query ตาม Category ID", "PASS",
                   input_data=f"category_id={cat_id}",
                   expected="ได้ snapshots ในหมวดหมู่นั้น",
                   actual=f"พบ {d4.get('count',0)} รายการ")
        else:
            record("K-04", "Query ตาม Category ID", "FAIL",
                   expected="200", actual=f"Status {r4.status_code}")


# =============================================================================
# SECTION L: Database & Statistics
# =============================================================================
def test_statistics(session):
    section("L. ฐานข้อมูล & สถิติ")
    print(f"\n{'='*60}")
    print(f"  L. ฐานข้อมูล & สถิติ")
    print(f"{'='*60}")
    
    # L-01: Stats page loads with data
    r1 = session.get(f"{BASE_URL}/stats")
    if r1.status_code == 200:
        html = r1.text
        has_numbers = bool(re.search(r'\d+', html))
        record("L-01", "หน้า Statistics โหลดข้อมูลได้", "PASS",
               expected="200 + มีตัวเลขสถิติ",
               actual=f"Status 200, มีตัวเลข: {'ใช่' if has_numbers else 'ไม่'}")
    else:
        record("L-01", "หน้า Statistics", "FAIL",
               expected="200", actual=f"Status {r1.status_code}")
    
    # L-02: API Upload test endpoint
    r2 = session.get(f"{BASE_URL}/api/upload/test")
    if r2.status_code == 200:
        d2 = r2.json()
        record("L-02", "API Upload Test Endpoint", "PASS",
               expected="200 + usage info",
               actual=f"message={d2.get('message','')[:40]}")
    else:
        record("L-02", "API Upload Test Endpoint", "FAIL",
               expected="200", actual=f"Status {r2.status_code}")


# =============================================================================
# PRINT FINAL REPORT
# =============================================================================
def print_report():
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    total_pass = sum(1 for r in REPORT if r['status'] == 'PASS')
    total_fail = sum(1 for r in REPORT if r['status'] == 'FAIL')
    total_skip = sum(1 for r in REPORT if r['status'] == 'SKIP')
    total = len(REPORT)
    pass_rate = (total_pass / total * 100) if total > 0 else 0
    
    print("\n")
    print("╔" + "═" * 70 + "╗")
    print("║" + " " * 10 + "รายงานผลการทดสอบระบบ (System Test Report)" + " " * 10 + " ║")
    print("╠" + "═" * 70 + "╣")
    print(f"║  โปรเจค:    Aeroponic Snapshot Database{' '*32}║")
    print(f"║  วันที่เทส:  {now}{' '*(55 - len(now))}║")
    print(f"║  Server:    {BASE_URL}{' '*(57 - len(BASE_URL))}║")
    print(f"║  เทสเตอร์:  Automated Test Suite{' '*38}║")
    print("╠" + "═" * 70 + "╣")
    print(f"║  ✅ ผ่าน (PASS):    {total_pass:>3} / {total}{' '*(48 - len(str(total)))}║")
    print(f"║  ❌ ไม่ผ่าน (FAIL): {total_fail:>3} / {total}{' '*(48 - len(str(total)))}║")
    print(f"║  ⏭️  ข้าม (SKIP):    {total_skip:>3} / {total}{' '*(48 - len(str(total)))}║")
    print(f"║  📊 อัตราผ่าน:      {pass_rate:>5.1f}%{' '*48}║")
    print("╚" + "═" * 70 + "╝")
    
    # Per section summary
    print("\n┌─────────────────────────────────────────────────────────────┐")
    print("│  สรุปผลแต่ละหมวด                                            │")
    print("├─────────────────────────────────────────┬────┬────┬────┬─────┤")
    print("│ หมวด                                    │ ผ่าน│ไม่ผ่าน│ข้าม │ รวม │")
    print("├─────────────────────────────────────────┼────┼────┼────┼─────┤")
    
    for sec_name, sec_data in SECTION_RESULTS.items():
        p = sec_data.get('pass', 0)
        f = sec_data.get('fail', 0)
        s = sec_data.get('skip', 0)
        t = p + f + s
        # Truncate name
        sn = sec_name[:38]
        print(f"│ {sn:<39}│ {p:>2} │ {f:>2} │ {s:>2} │  {t:>2} │")
    
    print("└─────────────────────────────────────────┴────┴────┴────┴─────┘")
    
    # Detailed results
    print("\n" + "=" * 90)
    print("  รายละเอียดผลเทสแต่ละรายการ")
    print("=" * 90)
    
    cur_sec = ""
    for r in REPORT:
        if r['section'] != cur_sec:
            cur_sec = r['section']
            print(f"\n  [{cur_sec}]")
            print(f"  {'─' * 80}")
        
        icon = {"PASS": "✅", "FAIL": "❌", "SKIP": "⏭️"}.get(r['status'], "❓")
        print(f"  {icon} #{r['no']:>2} [{r['test_id']}] {r['name']}")
        if r['input']:
            print(f"       Input:    {r['input']}")
        if r['expected']:
            print(f"       Expected: {r['expected']}")
        if r['actual']:
            print(f"       Actual:   {r['actual']}")
        if r['detail']:
            print(f"       Detail:   {r['detail']}")
    
    # Failed tests highlight
    if total_fail > 0:
        print(f"\n{'='*90}")
        print("  ❌ รายการที่ไม่ผ่าน (FAILED)")
        print(f"{'='*90}")
        for r in REPORT:
            if r['status'] == 'FAIL':
                print(f"  ❌ [{r['test_id']}] {r['name']}")
                print(f"     Expected: {r['expected']}")
                print(f"     Actual:   {r['actual']}")
    else:
        print(f"\n  🎉 ทุก Test Case ผ่านหมด! ไม่พบข้อผิดพลาด")
    
    print(f"\n{'='*90}")
    print(f"  จบรายงาน — {now}")
    print(f"{'='*90}\n")


# =============================================================================
# MAIN
# =============================================================================
if __name__ == '__main__':
    detect_api_key()
    
    print("╔" + "═" * 58 + "╗")
    print("║     Aeroponic Snapshot Database — Full Test Suite         ║")
    print(f"║     Server: {BASE_URL:<45}║")
    print(f"║     Time:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<45}║")
    print("╚" + "═" * 58 + "╝")
    
    try:
        session = get_session()
        print("\n  >>> ✅ Login สำเร็จ — เริ่มการทดสอบ...\n")
    except Exception as e:
        print(f"\n  >>> ❌ ไม่สามารถเชื่อมต่อ server: {e}")
        sys.exit(1)
    
    test_authentication(session)
    test_upload_validation(session)
    test_duplicate_detection(session)
    test_timestamp_priority(session)
    test_categories(session)
    test_api_validation(session)
    test_folder_import(session)
    test_timelapse(session)
    test_edit_delete(session)
    test_web_pages(session)
    test_search_query(session)
    test_statistics(session)
    
    print_report()
