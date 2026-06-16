import boto3
import urllib.request
from botocore.exceptions import ClientError, NoCredentialsError

DEFAULT_REGION = 'ap-southeast-2'

REGIONS = [
    ('ap-southeast-2', 'Asia Pacific (Sydney)'),
    ('ap-southeast-1', 'Asia Pacific (Singapore)'),
    ('ap-east-1',      'Asia Pacific (Hong Kong)'),
    ('us-east-1',      'US East (N. Virginia)'),
    ('us-west-2',      'US West (Oregon)'),
    ('eu-west-1',      'Europe (Ireland)'),
]

def get_my_ip():
    for url in ['https://checkip.amazonaws.com', 'https://api.ipify.org', 'https://icanhazip.com']:
        try:
            return urllib.request.urlopen(url, timeout=5).read().decode().strip()
        except Exception:
            continue
    raise RuntimeError("Could not determine public IP from any source.")

def prompt_region():
    print("Available regions:")
    for i, (code, label) in enumerate(REGIONS, 1):
        default_marker = ' (default)' if code == DEFAULT_REGION else ''
        print(f"  {i}. {code} — {label}{default_marker}")

    while True:
        choice = input(f"\nEnter number or region code (press Enter for default: {DEFAULT_REGION}): ").strip()
        if choice == '':
            return DEFAULT_REGION
        elif choice.isdigit() and 1 <= int(choice) <= len(REGIONS):
            return REGIONS[int(choice) - 1][0]
        elif choice in [r[0] for r in REGIONS]:
            return choice
        else:
            print(f"Invalid choice.")

def list_security_groups(ec2):
    response = ec2.describe_security_groups()
    return response['SecurityGroups']

def prompt_security_group(security_groups):
    print("\nAvailable security groups:")
    print(f"  {'#':<4} {'Name':<30} {'ID'}")
    print(f"  {'-'*4} {'-'*30} {'-'*20}")
    for i, sg in enumerate(security_groups, 1):
        print(f"  {i:<4} {sg['GroupName']:<30} {sg['GroupId']}")

    while True:
        choice = input("\nEnter the number of the security group to update: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(security_groups):
            return security_groups[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(security_groups)}.")

def prompt_label():
    label = input("\nEnter a label for this location (e.g. office, lab, home): ").strip()
    return label if label else 'my location'

def get_existing_ssh_cidrs(ec2, sg_id):
    sg = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
    cidrs = []
    for rule in sg['IpPermissions']:
        if rule.get('FromPort') == 22 and rule.get('ToPort') == 22:
            for ip in rule.get('IpRanges', []):
                cidrs.append((ip['CidrIp'], ip.get('Description', '')))
    return cidrs

def add_my_ip():
    try:
        print("=== Add My IP to Security Group ===\n")

        my_ip = get_my_ip()
        my_cidr = f'{my_ip}/32'
        print(f"Your current IP: {my_ip}")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        security_groups = list_security_groups(ec2)
        sg = prompt_security_group(security_groups)
        sg_id = sg['GroupId']

        existing = get_existing_ssh_cidrs(ec2, sg_id)

        print(f"\nExisting SSH rules:")
        if existing:
            for cidr, desc in existing:
                print(f"  {cidr}  {desc}")
        else:
            print("  (none)")

        if any(cidr == my_cidr for cidr, _ in existing):
            print(f"\nYour IP {my_ip} is already allowed. Nothing to do.")
            return

        label = prompt_label()

        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[{
                'IpProtocol': 'tcp',
                'FromPort': 22,
                'ToPort': 22,
                'IpRanges': [{'CidrIp': my_cidr, 'Description': label}]
            }]
        )

        print(f"\nSSH access granted for {my_ip} ({label}).")
        print(f"You can now connect with: ssh <your-alias>")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    add_my_ip()
