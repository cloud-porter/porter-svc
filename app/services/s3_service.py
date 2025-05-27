import boto3
from botocore.exceptions import BotoCoreError, ClientError
from utils.logger import logger

class S3Service:
    def __init__(self, ak, sk, bucket_name, region_name=None):
        session = boto3.session.Session()
        # self.s3 = boto3.client(
        #     "s3",
        #     aws_access_key_id=ak,
        #     aws_secret_access_key=sk,
        #     region_name=region_name,
        # )
        self.s3 = session.client("s3", region_name=region_name)
        self.bucket_name = bucket_name

    def upload_file(self, file_path, object_name=None):
        if object_name is None:
            object_name = file_path
        try:
            self.s3.upload_file(file_path, self.bucket_name, object_name)
            logger.info(f"File {file_path} uploaded to {self.bucket_name}/{object_name}")
            return True
        except (BotoCoreError, ClientError) as e:
            logger.error(f"Failed to upload {file_path}: {e}")
            return False