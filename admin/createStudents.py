import boto3
import json
import csv
import string
import secrets
from botocore.exceptions import ClientError, NoCredentialsError

STUDENT_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "EC2Access",
            "Effect": "Allow",
            "Action": [
                "ec2:RunInstances",
                "ec2:TerminateInstances",
                "ec2:StopInstances",
                "ec2:StartInstances",
                "ec2:DescribeInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeImages",
                "ec2:DescribeKeyPairs",
                "ec2:DescribeSecurityGroups",
                "ec2:AuthorizeSecurityGroupIngress",
                "ec2:RevokeSecurityGroupIngress",
                "ec2:CreateSnapshot",
                "ec2:DeleteSnapshot",
                "ec2:DescribeSnapshots",
                "ec2:DescribeVolumes",
                "ec2:RegisterImage",
                "ec2:DeregisterImage",
                "ec2:DescribeTags",
                "ec2:CreateTags"
            ],
            "Resource": "*"
        },
        {
            "Sid": "SSMAccess",
            "Effect": "Allow",
            "Action": ["ssm:GetParameter"],
            "Resource": "*"
        }
    ]
}

def generate_password(length=16):
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(chars) for _ in range(length))

def create_student(iam, username):
    try:
        iam.create_user(UserName=username)
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"  User '{username}' already exists, skipping creation.")
        else:
            raise

    # Attach inline policy
    iam.put_user_policy(
        UserName=username,
        PolicyName='StudentEC2Policy',
        PolicyDocument=json.dumps(STUDENT_POLICY)
    )

    # Enable console access
    password = generate_password()
    iam.create_login_profile(
        UserName=username,
        Password=password,
        PasswordResetRequired=True
    )

    # Create access keys for CLI
    keys = iam.create_access_key(UserName=username)['AccessKey']

    return {
        'username': username,
        'password': password,
        'access_key_id': keys['AccessKeyId'],
        'secret_access_key': keys['SecretAccessKey'],
    }

def get_account_id():
    sts = boto3.client('sts')
    return sts.get_caller_identity()['Account']

def create_students():
    try:
        print("=== Create Student IAM Users ===\n")

        raw = input("Enter student usernames separated by commas: ").strip()
        usernames = [u.strip() for u in raw.split(',') if u.strip()]

        if not usernames:
            print("No usernames entered.")
            return

        iam = boto3.client('iam')
        account_id = get_account_id()
        console_url = f"https://{account_id}.signin.aws.amazon.com/console"

        output_file = 'student_credentials.csv'
        results = []

        print()
        for username in usernames:
            print(f"Creating user: {username}...")
            creds = create_student(iam, username)
            creds['console_url'] = console_url
            results.append(creds)
            print(f"  Done.")

        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['username', 'password', 'access_key_id', 'secret_access_key', 'console_url'])
            writer.writeheader()
            writer.writerows(results)

        print(f"\n=== Done! ===")
        print(f"Credentials saved to: {output_file}")
        print(f"Console login URL: {console_url}")
        print(f"\nShare each student's row from the CSV with them.")
        print(f"They will be prompted to change their password on first login.")
        print(f"=============")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    create_students()
