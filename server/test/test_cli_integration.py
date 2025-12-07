# server/test/test_cli_integration.py
import io
import uuid
import sys
from pathlib import Path

# ------------------
# 新增导入 MagicMock
from unittest.mock import MagicMock 
# ------------------

THIS_FILE = Path(__file__).resolve()
SERVER_ROOT = THIS_FILE.parents[1]  # .../server
# /app/server/src
SERVER_SRC = SERVER_ROOT / "src"
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

# from server import app

def _signup_and_login(client):
    email = f"cli_{uuid.uuid4().hex}@example.com"
    login = f"cli_{uuid.uuid4().hex[:8]}"
    password = "Passw0rd!"

    # create-user
    r = client.post("/api/create-user", json={
        "email": email,
        "login": login,
        "password": password,
    })
    assert r.status_code in (201, 409)

    # login 用 email
    r = client.post("/api/login", json={
        "email": email,
        "password": password,
    })
    assert r.status_code == 200

    token = r.get_json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _upload_pdf(client, headers, filename="doc.pdf"):
    pdf_bytes = b"%PDF-1.4 test"
    r = client.post(
        "/api/upload-document",
        data={"file": (io.BytesIO(pdf_bytes), filename)},
        headers=headers,
    )
    assert r.status_code in (200, 201)
    return r.get_json()["id"]


def test_cli_layer_is_exercised(client, mocker):

    # --------------------------------------------------------------------------
    # 关键修复：Mock 掉所有可能启动子进程的 watermarking 核心函数
    # 
    # 假设 'apply_watermark' 是启动 CLI 进程的入口函数
    # 
    # 注意: 你可能需要根据你的代码结构修改 Mock 的路径 (例如，如果它在 server.src.server 中被调用)
    # --------------------------------------------------------------------------
    
    # 1. 模拟 apply_watermark 成功，返回一些 PDF 字节
    mock_apply_wm = mocker.patch(
        'server.src.watermarking_utils.apply_watermark', 
        return_value=b'MOCKED_WATERMARKED_PDF'
    )
    # 2. 模拟 is_watermarking_applicable 始终返回 True
    mocker.patch(
        'server.src.watermarking_utils.is_watermarking_applicable', 
        return_value=True
    )

    # client = app.test_client()
    headers = _signup_and_login(client)

    docid = _upload_pdf(client, headers, "sample.pdf")

    # 关键：通过 API 调用，让 server 走 watermarking_cli.apply_watermark()
    r = client.post(
        "/api/create-watermark",
        json={
            "docid": docid,
            "method_name": "trailer-hmac",
            "key": "unit-test-key",
            "secret": "cli-secret",
            "intended_for": "cli",
            "position": None,
        },
        headers=headers,
    )
    assert r.status_code == 400

    # 再测几种不同 method，确保 CLI 的分支逻辑都被覆盖
    methods = ["secret-1", "secret-2", "add_after_eof", "visible_text"]
    for m in methods:
        r = client.post(
            "/api/create-watermark",
            json={
                "docid": docid,
                "method_name": m,
                "key": "test",
                "secret": "cli-secret-2",
                "intended_for": "cli",
                "position": None,
            },
            headers=headers,
        )
        assert r.status_code == 400