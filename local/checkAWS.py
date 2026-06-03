import boto3
from botocore.exceptions import NoCredentialsError, ClientError

def check_identity():
    try:
        # STS (Security Token Service) handles caller identity
        sts_client = boto3.client('sts', region_name='ap-southeast-2')
        
        print("Checking AWS credentials...")
        response = sts_client.get_caller_identity()
        
        print("\n=== Connection Successful! ===")
        print(f"AWS Account ID: {response['Account']}")
        print(f"User ARN:       {response['Arn']}")
        print(f"User ID:        {response['UserId']}")
        print("==============================\n")
        print("You are safely authenticated and ready to build infrastructure.")

    except NoCredentialsError:
        print("\n[ERROR] No credentials found.")
        print("Please run 'aws configure' in your Anaconda Prompt to set your keys.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    check_identity()
