from pydantic.v1 import BaseSettings
from .services.s3_config import S3Config


class Settings(BaseSettings):
    app_name: str = "Porter"
    app_version: str = "0.1.0"
    
    # AWS S3 設定
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = ""
    s3_endpoint_url: str = None
    
    # 向後相容的設定別名
    ak: str = ""
    sk: str = ""
    bucket_name: str = ""
    region_name: str = ""
    
    class Config:
        env_file = ".env"
    
    @property
    def s3_config(self) -> S3Config:
        """取得 S3 服務配置"""
        return S3Config(
            aws_access_key_id=self.aws_access_key_id or self.ak,
            aws_secret_access_key=self.aws_secret_access_key or self.sk,
            aws_region=self.aws_region or self.region_name or "us-east-1",
            bucket_name=self.s3_bucket_name or self.bucket_name,
            endpoint_url=self.s3_endpoint_url
        )


settings = Settings()