from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ats_id: str = ""
    ats_pw: str = ""
    ats_url: str = "https://a00992.pweb.kr"

    session_path: str = "data/storage_state.json"
    screenshot_dir: str = "data/screenshots"
    database_path: str = "data/parking_app.db"

    gsheet_id: str = ""
    gsheet_creds_path: str = "data/gsheet_creds.json"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email: str = ""

    api_key: str = ""
    secret_key: str = ""
    admin_username: str = "admin"
    admin_password: str = "admin1234"
    cors_origins: str = "*"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

