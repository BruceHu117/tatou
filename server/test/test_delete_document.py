import io
import sys
from pathlib import Path
import pytest # 确保已导入
from unittest.mock import patch, MagicMock # 确保已导入

# 让 Python 能找到 server/src/server.py
THIS_FILE = Path(__file__).resolve()      # .../server/test/test_delete_document.py
SERVER_ROOT = THIS_FILE.parents[1]        # .../server

if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

# from src.server import app   # 这里对应 server/src/server.py 里的 app


def _sample_pdf_bytes():
    # 构造一个极简合法 PDF
    return (
        b"%PDF-1.4\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"xref\n0 2\n0000000000 65535 f \n0000000010 00000 n \n"
        b"trailer\n<<>>\nstartxref\n20\n%%EOF"
    )


def _signup_and_login(client):
    email = "testdel@example.com"
    login = "del_user"
    password = "Passw0rd!"

    # create-user（用户已存在时 409 也接受）
    r = client.post(
        "/api/create-user",
        json={"email": email, "login": login, "password": password},
    )
    assert r.status_code in (201, 409)

    # login
    r = client.post(
        "/api/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200
    token = r.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_delete_document_roundtrip(client,mocker):
    # client = app.test_client()
    headers = _signup_and_login(client)

    # 1. 上传一个 PDF
    resp = client.post(
        "/api/upload-document",
        data={"file": (io.BytesIO(_sample_pdf_bytes()), "deltest.pdf")},
        headers=headers,
        content_type="multipart/form-data",
    )
    assert resp.status_code == 201
    doc_id = resp.get_json()["id"]

# 获取原始的 Path.exists 方法
    original_exists = Path.exists
    
    def mock_exists(self):
        # 如果路径包含我们上传的特定文件名，则返回 False，模拟文件丢失
        if 'missing_on_disk.pdf' in str(self): 
            return False 
        # 否则，调用原始方法，确保其他文件路径检查 (如目录创建) 正常
        return original_exists(self)

    # 打补丁替换 Path.exists
    mocker.patch('pathlib.Path.exists', side_effect=mock_exists)

    # 2. 删除此 PDF
    resp = client.delete(f"/api/delete-document/{doc_id}", headers=headers)
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["deleted"] is True
    assert body["id"] == doc_id

    # 3. 再次 list-documents → 此文件应该消失
    resp = client.get("/api/list-documents", headers=headers)
    assert resp.status_code == 200
    docs = resp.get_json()["documents"]
    assert all(d["id"] != doc_id for d in docs)

    # 4. 再尝试删除 → 应该返回 404
    resp = client.delete(f"/api/delete-document/{doc_id}", headers=headers)
    assert resp.status_code == 404




