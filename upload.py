import boto3
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError

def upload_to_s3(file_path, bucket_name, object_name=None):
    if object_name is None:
        object_name = os.path.basename(file_path)
    s3_client = boto3.client('s3')
    try:
        s3_client.upload_file(file_path, bucket_name, object_name)
    except NoCredentialsError:
        print("AWS credentials not available")
        return False
    except PartialCredentialsError:
        print("Incomplete AWS credentials")
        return False
    except ClientError as e:
        print(f"Unexpected error: {e}")
        return False
    return True
