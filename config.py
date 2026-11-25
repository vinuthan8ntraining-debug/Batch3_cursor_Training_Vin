import os

SECRET_KEY = os.environ.get("SECRET_KEY", "demo-local-secret-change-me")

ADMIN_USERNAME = "admin"
# Demo password: admin (override via ADMIN_PASSWORD_HASH)
ADMIN_PASSWORD_HASH = os.environ.get(
    "ADMIN_PASSWORD_HASH",
    "scrypt:32768:8:1$Q5ZrcJkhASmaGqBz$7d82fdb4cf03ae88ca0f920aa27fa8fe48baff4216d83f47517964cbc5f78121d8c040caa939819b5c204f781134a0d22349083ec47a938a582a6144c75ab01b",
)

SSH_CONNECT_TIMEOUT = int(os.environ.get("SSH_CONNECT_TIMEOUT", "5"))
METRICS_REFRESH_SECONDS = 10
