"""Deploy ocr-service len Modal (serverless, scale-to-zero, free trong han muc
$30/thang credit cua goi Starter). Chon Modal thay vi HF Spaces/Render private
service vi image ~4 GB + ~2 GB RAM luc chay vuot goi free cua hai ben do, va
scale-to-zero khien dich vu chi ton credit khi that su co anh gui len.

Tai su dung NGUYEN Dockerfile hien co qua Image.from_dockerfile - khong doi logic
OCR/model, chi them 1 lop entrypoint de Modal chay duoc dung service da co.

Bao ve endpoint bang requires_proxy_auth=True (tinh nang co san cua Modal, khong
tu viet middleware): request toi phai kem 2 header "Modal-Key"/"Modal-Secret" lay
tu Modal dashboard -> Settings -> Proxy Tokens. Backend chinh (Render) gui kem 2
header nay khi goi sang, xem src/api/routes.py + src/config.py (modal_key_id/
modal_key_secret).

Cach deploy (chay tu thu muc ocr-service/):
    pip install modal
    modal token new          # dang nhap 1 lan, mo trinh duyet
    modal deploy modal_app.py

Sau khi deploy xong, Modal in ra URL dang https://<workspace>--medicheck-ocr-service-fastapi-app.modal.run
Dat URL do vao bien OCR_SERVICE_URL tren Render, kem MODAL_KEY_ID/MODAL_KEY_SECRET
lay tu Proxy Tokens.
"""

from pathlib import Path

import modal

SERVICE_DIR = Path(__file__).parent
REPO_ROOT = SERVICE_DIR.parent
DRUGS_CSV = REPO_ROOT / "data" / "raw" / "thuoc_final_project.csv"

# KHONG tu kiem tra DRUGS_CSV.is_file() o day - top-level code cua file nay bi Modal
# RE-IMPORT y het ben trong container luc khoi dong (de tim ham fastapi_app), va
# trong container __file__ tro toi /root/modal_app.py (SERVICE_DIR=/root,
# REPO_ROOT=/) nen duong dan nay luon sai ben trong container -> tung khien container
# crash lien tuc moi lan khoi dong that (loi nay da xay ra that, 2026-08-22). De
# add_local_file() ben duoi tu bao loi ro rang luc `modal deploy` (chi chay tren may
# local) neu thieu file - khong tu viet check thu cong nua.
image = (
    modal.Image.from_dockerfile(
        str(SERVICE_DIR / "Dockerfile"),
        context_dir=str(SERVICE_DIR),
    )
    .pip_install("modal")  # Dockerfile goc khong biet gi ve Modal - them client vao
    # docker-compose.yml mount file nay tu ngoai vao luc chay (khong bake vao
    # image, vi gitignore + dung chung voi backend chinh) - Modal khong ho tro
    # bind-mount tu host luc runtime nhu compose, nen phai bake han vao image
    # luc build. Duong dan phai khop APP_DIR/data/thuoc_final_project.csv trong
    # app/config.py (APP_DIR = ocr-service/app, WORKDIR /srv trong Dockerfile).
    .add_local_file(
        local_path=str(DRUGS_CSV),
        remote_path="/srv/app/data/thuoc_final_project.csv",
        copy=True,
    )
)

app = modal.App(name="medicheck-ocr-service", image=image)


@app.function(
    cpu=2,
    memory=2048,
    # Mac dinh cua Modal (60s) - ghi ro de sau nay muon doi thi thay doi ngay tai
    # day, khong phai di doan lai gia tri mac dinh. Tang gia tri nay se giu
    # container "am" lau hon nhung TON TIEN THAT cho phan thoi gian cho (xem tai
    # lieu huong dan deploy) - chi tang khi da chap nhan tra phi.
    scaledown_window=60,
    # OCR mat 4-7s/anh (CPU) + lan dau con phai nap model (cold start) - dat du
    # rong de khong bi Modal tu ngat giua chung mot request hop le.
    timeout=120,
)
@modal.asgi_app(requires_proxy_auth=True)
def fastapi_app():
    from app.main import app as ocr_fastapi_app

    return ocr_fastapi_app
