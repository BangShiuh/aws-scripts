import boto3
import re
import urllib.request
from pathlib import Path
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

SSH_CONFIG_PATH = Path.home() / '.ssh' / 'config'

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

def get_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'

def list_stopped_instances(ec2):
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['stopped']}
    ])
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance)
    return instances

def prompt_instance(instances):
    print("\nStopped instances:")
    print(f"  {'#':<4} {'Name':<20} {'Instance ID':<22} {'Type'}")
    print(f"  {'-'*4} {'-'*20} {'-'*22} {'-'*12}")
    for i, inst in enumerate(instances, 1):
        name = get_instance_name(inst)
        print(f"  {i:<4} {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']}")

    while True:
        choice = input("\nEnter the number of the instance to start: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(instances):
            return instances[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(instances)}.")

def get_my_ip():
    return urllib.request.urlopen('https://checkip.amazonaws.com').read().decode().strip()

def add_my_ip_to_sg(ec2, instance_id):
    my_ip = get_my_ip()
    my_cidr = f'{my_ip}/32'

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    sg_ids = [sg['GroupId'] for sg in desc['Reservations'][0]['Instances'][0]['SecurityGroups']]

    for sg_id in sg_ids:
        sg = ec2.describe_security_groups(GroupIds=[sg_id])['SecurityGroups'][0]
        existing = [
            ip['CidrIp']
            for rule in sg['IpPermissions'] if rule.get('FromPort') == 22
            for ip in rule.get('IpRanges', [])
        ]
        if my_cidr in existing:
            print(f"SSH already allowed from {my_ip}.")
        else:
            try:
                ec2.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[{
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': my_cidr, 'Description': 'auto-added by startEC2'}]
                    }]
                )
                print(f"SSH access granted for {my_ip}.")
            except ClientError as e:
                print(f"Could not add SSH rule: {e.response['Error']['Message']}")

def update_ssh_config(alias, hostname):
    if not SSH_CONFIG_PATH.exists():
        return

    content = SSH_CONFIG_PATH.read_text(encoding='utf-8-sig')
    pattern = rf'^Host {re.escape(alias)}\s*\n(?:[ \t]+.*\n?)*'
    match = re.search(pattern, content, re.MULTILINE)

    if match:
        updated_block = re.sub(r'([ \t]+HostName[ \t]+)\S+', rf'\g<1>{hostname}', match.group(0))
        new_content = content[:match.start()] + updated_block + content[match.end():]
        SSH_CONFIG_PATH.write_text(new_content, encoding='utf-8')
        print(f"Updated '{alias}' in SSH config with new IP {hostname}.")
    else:
        print(f"No SSH alias '{alias}' found in config — skipping SSH config update.")

def start_instance():
    try:
        print("=== EC2 Start ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        print("\nFetching stopped instances...")
        instances = list_stopped_instances(ec2)

        if not instances:
            print("No stopped instances found in this region.")
            return

        instance = prompt_instance(instances)
        instance_id = instance['InstanceId']
        name = get_instance_name(instance)

        default_alias = name if name != '(no name)' else ''
        alias_prompt = f"\nEnter your SSH alias for '{name}' (press Enter for '{default_alias}'): " if default_alias else f"\nEnter your SSH alias for '{name}' (press Enter to skip): "
        ssh_alias = input(alias_prompt).strip() or (default_alias or None)

        print(f"\nStarting '{name}' ({instance_id})...")
        ec2.start_instances(InstanceIds=[instance_id])

        print("Waiting for instance to be running...")
        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        desc = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

        print(f"\nAdding your IP to the security group...")
        add_my_ip_to_sg(ec2, instance_id)

        if ssh_alias and public_ip != 'N/A':
            update_ssh_config(ssh_alias, public_ip)

        print(f"\n=== Instance is Running! ===")
        print(f"Public IP: {public_ip}")
        if ssh_alias:
            print(f"\nTo connect: ssh {ssh_alias}")
        else:
            print(f"\nTo connect: ssh <user>@{public_ip}")
        print(f"============================")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    start_instance()
