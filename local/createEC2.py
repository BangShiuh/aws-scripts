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

INSTANCE_TYPES = ['t2.micro', 't3.micro', 't3.small', 't3.medium', 't3.xlarge']

SSH_CONFIG_PATH = Path.home() / '.ssh' / 'config'

OS_OPTIONS = [
    ('Amazon Linux 2023', 'ec2-user',  '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64'),
    ('Ubuntu 24.04 LTS',  'ubuntu',    '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'),
    ('Ubuntu 22.04 LTS',  'ubuntu',    '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id'),
]

def prompt_region():
    print("Available regions:")
    for i, (code, label) in enumerate(REGIONS, 1):
        default_marker = ' (default)' if code == DEFAULT_REGION else ''
        print(f"  {i}. {code} — {label}{default_marker}")
    print(f"  (press Enter to use default: {DEFAULT_REGION})")

    while True:
        choice = input("\nEnter number or region code: ").strip()
        if choice == '':
            return DEFAULT_REGION
        elif choice.isdigit() and 1 <= int(choice) <= len(REGIONS):
            return REGIONS[int(choice) - 1][0]
        elif choice in [r[0] for r in REGIONS]:
            return choice
        else:
            print(f"Invalid choice. Pick a number 1-{len(REGIONS)} or type the region code.")

def prompt_os():
    print("\nSelect operating system:")
    for i, (name, user, _) in enumerate(OS_OPTIONS, 1):
        print(f"  {i}. {name}  (SSH user: {user})")

    while True:
        choice = input(f"\nEnter number (press Enter for default: 1): ").strip()
        if choice == '':
            return OS_OPTIONS[0]
        elif choice.isdigit() and 1 <= int(choice) <= len(OS_OPTIONS):
            return OS_OPTIONS[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(OS_OPTIONS)}.")

def get_latest_ami(region, ssm_param):
    ssm = boto3.client('ssm', region_name=region)
    response = ssm.get_parameter(Name=ssm_param)
    return response['Parameter']['Value']

def list_key_pairs(ec2):
    response = ec2.describe_key_pairs()
    return [kp['KeyName'] for kp in response['KeyPairs']]

def prompt_key_pair(ec2):
    key_pairs = list_key_pairs(ec2)
    if not key_pairs:
        print("[ERROR] No key pairs found in your AWS account.")
        print("Please create one in the AWS Console under EC2 -> Key Pairs.")
        return None

    print("\nAvailable key pairs:")
    for i, name in enumerate(key_pairs, 1):
        print(f"  {i}. {name}")

    while True:
        choice = input("\nEnter the number or name of your key pair: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(key_pairs):
            return key_pairs[int(choice) - 1]
        elif choice in key_pairs:
            return choice
        else:
            print("Invalid choice. Please try again.")

def prompt_instance_type():
    print("\nAvailable instance types:")
    for i, t in enumerate(INSTANCE_TYPES, 1):
        print(f"  {i}. {t}")
    print(f"  (press Enter to use default: {INSTANCE_TYPES[0]})")
    print(f"  (or type any instance type, e.g. c5.2xlarge)")

    while True:
        choice = input("\nEnter number or instance type: ").strip()
        if choice == '':
            return INSTANCE_TYPES[0]
        elif choice.isdigit() and 1 <= int(choice) <= len(INSTANCE_TYPES):
            return INSTANCE_TYPES[int(choice) - 1]
        elif choice:
            return choice

def prompt_instance_name():
    name = input("\nEnter a name for your instance (press Enter to skip): ").strip()
    return name if name else 'my-ec2-instance'

def prompt_boot_source(ec2):
    print("\nBoot source:")
    print("  1. Fresh instance (new blank volume)")
    print("  2. Restore from snapshot")

    while True:
        choice = input("\nEnter number: ").strip()
        if choice == '1':
            return 'fresh', None
        elif choice == '2':
            snapshot = prompt_snapshot(ec2)
            return 'snapshot', snapshot
        else:
            print("Please enter 1 or 2.")

def prompt_snapshot(ec2):
    print("\nFetching your snapshots...")
    response = ec2.describe_snapshots(OwnerIds=['self'])
    snapshots = sorted(response['Snapshots'], key=lambda s: s['StartTime'], reverse=True)

    if not snapshots:
        print("[ERROR] No snapshots found in this region.")
        return None

    print(f"\n  {'#':<4} {'Snapshot ID':<25} {'Size (GB)':<12} {'Date':<20} Description")
    print(f"  {'-'*4} {'-'*25} {'-'*12} {'-'*20} {'-'*30}")
    for i, snap in enumerate(snapshots, 1):
        date = snap['StartTime'].strftime('%Y-%m-%d %H:%M')
        desc = snap.get('Description', '')[:30]
        print(f"  {i:<4} {snap['SnapshotId']:<25} {snap['VolumeSize']:<12} {date:<20} {desc}")

    while True:
        choice = input("\nEnter the number of the snapshot to restore from: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(snapshots):
            return snapshots[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(snapshots)}.")

def prompt_volume_size(default=30):
    while True:
        choice = input(f"\nEnter EBS volume size in GB (press Enter for default: {default}): ").strip()
        if choice == '':
            return default
        elif choice.isdigit() and int(choice) >= 8:
            return int(choice)
        else:
            print("Please enter a number >= 8 GB.")

def prompt_ssh_alias():
    alias = input("\nEnter your SSH config alias to update (press Enter to skip): ").strip()
    return alias if alias else None

def prompt_pem_path(key_pair):
    default = str(Path.home() / '.ssh' / f'{key_pair}.pem')
    path = input(f"\nEnter the full path to your .pem file\n  (press Enter for default: {default}): ").strip()
    return path if path else default

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
                        'IpRanges': [{'CidrIp': my_cidr, 'Description': 'auto-added by createEC2'}]
                    }]
                )
                print(f"SSH access granted for {my_ip}.")
            except ClientError as e:
                print(f"Could not add SSH rule: {e.response['Error']['Message']}")

def update_ssh_config(alias, hostname, pem_path, ssh_user):
    SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

    new_block = (
        f"Host {alias}\n"
        f"    HostName {hostname}\n"
        f"    User {ssh_user}\n"
        f"    IdentityFile {pem_path}\n"
        f"    ServerAliveInterval 60\n"
        f"    StrictHostKeyChecking accept-new\n"
    )

    encoding = 'utf-8-sig'  # reads with or without BOM
    if not SSH_CONFIG_PATH.exists():
        SSH_CONFIG_PATH.write_text(new_block, encoding='utf-8')
        print(f"Created {SSH_CONFIG_PATH} with host '{alias}'.")
        return

    content = SSH_CONFIG_PATH.read_text(encoding=encoding)

    pattern = rf'^Host {re.escape(alias)}\s*\n(?:[ \t]+.*\n?)*'
    match = re.search(pattern, content, re.MULTILINE)

    if match:
        updated = content[:match.start()] + new_block + '\n' + content[match.end():]
        SSH_CONFIG_PATH.write_text(updated, encoding='utf-8')
        print(f"Updated '{alias}' in {SSH_CONFIG_PATH}.")
    else:
        with open(SSH_CONFIG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'\n{new_block}')
        print(f"Added '{alias}' to {SSH_CONFIG_PATH}.")

def create_instance():
    try:
        print("=== EC2 Instance Creator ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        key_pair = prompt_key_pair(ec2)
        if not key_pair:
            return

        instance_type = prompt_instance_type()
        instance_name = prompt_instance_name()
        boot_source, snapshot = prompt_boot_source(ec2)

        if boot_source == 'snapshot' and snapshot is None:
            return

        os_name, ssh_user, ssm_param = (None, None, None)
        if boot_source == 'fresh':
            os_name, ssh_user, ssm_param = prompt_os()

        if boot_source == 'snapshot':
            volume_size = prompt_volume_size(default=snapshot['VolumeSize'])
        else:
            volume_size = prompt_volume_size()

        ssh_alias = prompt_ssh_alias()
        pem_path = prompt_pem_path(key_pair) if ssh_alias else None

        temp_ami_id = None

        if boot_source == 'snapshot':
            snapshot_id = snapshot['SnapshotId']
            print(f"\nRegistering temporary AMI from snapshot {snapshot_id}...")
            ami_response = ec2.register_image(
                Name=f'restore-{snapshot_id}',
                RootDeviceName='/dev/xvda',
                BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'SnapshotId': snapshot_id,
                        'VolumeSize': volume_size,
                        'VolumeType': 'gp3',
                        'DeleteOnTermination': True,
                    }
                }],
                VirtualizationType='hvm',
                Architecture='x86_64',
                BootMode='uefi-preferred',
            )
            temp_ami_id = ami_response['ImageId']
            ami_id = temp_ami_id
            ssh_user = 'ec2-user'
            print(f"Temporary AMI registered: {ami_id}")
        else:
            print(f"\nLooking up latest {os_name} AMI...")
            ami_id = get_latest_ami(region, ssm_param)
            print(f"Using AMI: {ami_id}")

        print(f"\nLaunching {instance_type} instance '{instance_name}'...")

        # For snapshot restores the volume is already defined in the registered AMI
        if boot_source == 'snapshot':
            block_device_mappings = []
        else:
            ami_info = ec2.describe_images(ImageIds=[ami_id])['Images'][0]
            root_device = ami_info['RootDeviceName']
            block_device_mappings = [{
                'DeviceName': root_device,
                'Ebs': {
                    'VolumeSize': volume_size,
                    'VolumeType': 'gp3',
                    'DeleteOnTermination': True,
                }
            }]

        response = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_pair,
            MinCount=1,
            MaxCount=1,
            BlockDeviceMappings=block_device_mappings,
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': instance_name}]
            }]
        )

        instance = response['Instances'][0]
        instance_id = instance['InstanceId']

        print(f"\n=== Instance Launched! ===")
        print(f"Instance ID:   {instance_id}")
        print(f"Instance Type: {instance['InstanceType']}")
        print(f"State:         {instance['State']['Name']}")
        print(f"=========================")
        print(f"\nWaiting for instance to be running (this may take ~30 seconds)...")

        waiter = ec2.get_waiter('instance_running')
        waiter.wait(InstanceIds=[instance_id])

        desc = ec2.describe_instances(InstanceIds=[instance_id])
        public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

        if temp_ami_id:
            ec2.deregister_image(ImageId=temp_ami_id)
            print(f"Temporary AMI {temp_ami_id} deregistered.")

        print(f"\nAdding your IP to the security group...")
        add_my_ip_to_sg(ec2, instance_id)

        print(f"\n=== Instance is Running! ===")
        print(f"Public IP:  {public_ip}")

        if ssh_alias and public_ip != 'N/A':
            update_ssh_config(ssh_alias, public_ip, pem_path, ssh_user)
            print(f"\nTo connect via SSH:")
            print(f"  ssh {ssh_alias}")
        else:
            print(f"\nTo connect via SSH:")
            print(f"  ssh -i {key_pair}.pem {ssh_user}@{public_ip}")

        print(f"============================")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    create_instance()
