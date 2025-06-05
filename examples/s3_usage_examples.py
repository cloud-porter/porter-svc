"""
S3 服務使用範例
"""
import asyncio
from pathlib import Path
from app.config import settings
from app.services.s3_service import S3Service


async def basic_upload_example():
    """基本檔案上傳範例"""
    print("=== 基本檔案上傳範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 上傳本地檔案
        result = await s3.upload_file(
            file_path="test_file.txt",
            object_key="uploads/test_file.txt",
            metadata={"author": "test_user", "version": "1.0"}
        )
        print(f"上傳結果: {result}")


async def multipart_upload_example():
    """多部分上傳範例"""
    print("=== 多部分上傳範例 ===")
    
    def progress_callback(progress_info):
        """進度回調函式"""
        print(f"上傳進度: {progress_info['progress_percentage']:.1f}% "
              f"({progress_info['speed_readable']})")
    
    async with S3Service(settings.s3_config) as s3:
        # 上傳大檔案（會自動使用多部分上傳）
        result = await s3.upload_file(
            file_path="large_file.zip",
            object_key="uploads/large_file.zip",
            progress_callback=progress_callback
        )
        print(f"多部分上傳結果: {result}")


async def stream_upload_example():
    """串流上傳範例"""
    print("=== 串流上傳範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 上傳位元組資料
        data = b"Hello, S3 World!"
        result = await s3.upload_stream(
            data_stream=data,
            object_key="uploads/hello.txt",
            content_type="text/plain",
            metadata={"type": "greeting"}
        )
        print(f"串流上傳結果: {result}")


async def download_example():
    """檔案下載範例"""
    print("=== 檔案下載範例 ===")
    
    def progress_callback(progress_info):
        """進度回調函式"""
        print(f"下載進度: {progress_info['progress_percentage']:.1f}%")
    
    async with S3Service(settings.s3_config) as s3:
        # 下載檔案
        result = await s3.download_file(
            object_key="uploads/test_file.txt",
            local_path="downloads/test_file.txt",
            progress_callback=progress_callback
        )
        print(f"下載結果: {result}")


async def stream_download_example():
    """串流下載範例"""
    print("=== 串流下載範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 串流下載檔案
        async for chunk in s3.download_stream("uploads/test_file.txt"):
            print(f"收到資料塊，大小: {len(chunk)} 位元組")


async def presigned_url_example():
    """預簽名 URL 範例"""
    print("=== 預簽名 URL 範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 產生下載用預簽名 URL
        download_url = await s3.generate_presigned_url(
            object_key="uploads/test_file.txt",
            operation="get_object",
            expiry_seconds=3600  # 1 小時
        )
        print(f"下載 URL: {download_url}")
        
        # 產生上傳用預簽名 URL
        upload_url = await s3.generate_presigned_url(
            object_key="uploads/new_file.txt",
            operation="put_object",
            expiry_seconds=1800  # 30 分鐘
        )
        print(f"上傳 URL: {upload_url}")


async def file_management_example():
    """檔案管理範例"""
    print("=== 檔案管理範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 檢查檔案是否存在
        exists = await s3.file_exists("uploads/test_file.txt")
        print(f"檔案存在: {exists}")
        
        # 取得檔案資訊
        if exists:
            file_info = await s3.get_file_info("uploads/test_file.txt")
            print(f"檔案資訊: {file_info}")
        
        # 列出檔案
        file_list = await s3.list_files(prefix="uploads/", max_keys=10)
        print(f"檔案列表: {file_list}")
        
        # 複製檔案
        copy_result = await s3.copy_file(
            source_key="uploads/test_file.txt",
            destination_key="backup/test_file_copy.txt"
        )
        print(f"複製結果: {copy_result}")
        
        # 更新檔案 metadata
        update_result = await s3.update_file_metadata(
            object_key="uploads/test_file.txt",
            metadata={"updated": "true", "timestamp": "2025-06-05"}
        )
        print(f"更新結果: {update_result}")


async def batch_operations_example():
    """批次操作範例"""
    print("=== 批次操作範例 ===")
    
    async with S3Service(settings.s3_config) as s3:
        # 批次刪除檔案
        files_to_delete = [
            "backup/test_file_copy.txt",
            "uploads/old_file1.txt",
            "uploads/old_file2.txt"
        ]
        
        delete_results = await s3.delete_files(files_to_delete)
        print(f"批次刪除結果: {delete_results}")


async def error_handling_example():
    """錯誤處理範例"""
    print("=== 錯誤處理範例 ===")
    
    from app.services.s3_exceptions import S3FileNotFoundError, S3PermissionError
    
    async with S3Service(settings.s3_config) as s3:
        try:
            # 嘗試下載不存在的檔案
            await s3.download_file("nonexistent/file.txt", "temp/file.txt")
        except S3FileNotFoundError as e:
            print(f"檔案不存在錯誤: {e}")
        
        try:
            # 嘗試訪問權限不足的檔案
            await s3.get_file_info("restricted/secret.txt")
        except S3PermissionError as e:
            print(f"權限不足錯誤: {e}")
        
        except Exception as e:
            print(f"其他錯誤: {e}")


async def performance_test():
    """效能測試範例"""
    print("=== 效能測試範例 ===")
    
    import time
    
    async with S3Service(settings.s3_config) as s3:
        # 並行上傳多個檔案
        start_time = time.time()
        
        tasks = []
        for i in range(5):
            task = s3.upload_stream(
                data_stream=f"Test file {i} content".encode(),
                object_key=f"performance_test/file_{i}.txt",
                content_type="text/plain"
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        print(f"並行上傳 5 個檔案耗時: {end_time - start_time:.2f} 秒")
        print(f"上傳結果: {results}")


async def main():
    """主函式 - 執行所有範例"""
    examples = [
        basic_upload_example,
        stream_upload_example,
        download_example,
        presigned_url_example,
        file_management_example,
        error_handling_example,
        performance_test
    ]
    
    for example in examples:
        try:
            await example()
            print()
        except Exception as e:
            print(f"範例執行失敗: {example.__name__}, 錯誤: {e}")
            print()


if __name__ == "__main__":
    # 設定環境變數或 .env 檔案中的 S3 配置
    print("S3 服務使用範例")
    print("請確保已設定正確的 AWS 認證資訊和 S3 Bucket")
    print()
    
    asyncio.run(main())
