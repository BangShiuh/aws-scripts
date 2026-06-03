import boto3
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

def get_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'

def list_instances(ec2):
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
    ])
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance)
    return instances

def prompt_instance(instances):
    print("\nYour EC2 instances:")
    print(f"  {'#':<4} {'Name':<20} {'Instance ID':<22} {'Type':<12} {'State':<10} {'Public IP'}")
    print(f"  {'-'*4} {'-'*20} {'-'*22} {'-'*12} {'-'*10} {'-'*15}")
    for i, inst in enumerate(instances, 1):
        name = get_instance_name(inst)
        public_ip = inst.get('PublicIpAddress', 'N/A')
        print(f"  {i:<4} {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']:<12} {inst['State']['Name']:<10} {public_ip}")

    while True:
        choice = input("\nEnter the number of the instance to terminate: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(instances):
            return instances[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(instances)}.")

def get_root_volume_id(ec2, instance_id):
    response = ec2.describe_instances(InstanceIds=[instance_id])
    instance = response['Reservations'][0]['Instances'][0]
    for mapping in instance.get('BlockDeviceMappings', []):
        if mapping['DeviceName'] == instance.get('RootDeviceName', '/dev/xvda'):
            return mapping['Ebs']['VolumeId']
    return None

def prompt_snapshot(instance_name):
    print("\nWould you like to create a snapshot before terminating?")
    print("  1. Yes — create a snapshot first (recommended)")
    print("  2. No  — terminate immediately")

    while True:
        choice = input("\nEnter number: ").strip()
        if choice == '1':
            desc = input(f"Enter snapshot description (press Enter for default: '{instance_name} backup'): ").strip()
            return desc if desc else f"{instance_name} backup"
        elif choice == '2':
            return None
        else:
            print("Please enter 1 or 2.")

def create_snapshot(ec2, volume_id, description):
    print(f"\nCreating snapshot of volume {volume_id}...")
    response = ec2.create_snapshot(VolumeId=volume_id, Description=description)
    snapshot_id = response['SnapshotId']
    print(f"Snapshot {snapshot_id} is being created (this runs in the background).")
    print(f"You can monitor it in the AWS Console under EC2 -> Snapshots.")
    return snapshot_id

def confirm_termination(instance):
    name = get_instance_name(instance)
    instance_id = instance['InstanceId']
    print(f"\n[WARNING] You are about to TERMINATE:")
    print(f"  Name:        {name}")
    print(f"  Instance ID: {instance_id}")
    print(f"  Type:        {instance['InstanceType']}")
    print(f"  State:       {instance['State']['Name']}")
    print(f"\nThis action is IRREVERSIBLE. The instance and its data will be lost.")
    confirm = input("\nType 'yes' to confirm: ").strip().lower()
    return confirm == 'yes'

def delete_instance():
    try:
        print("=== EC2 Instance Terminator ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        print("\nFetching your instances...")
        instances = list_instances(ec2)

        if not instances:
            print("No active instances found in this region.")
            return

        instance = prompt_instance(instances)
        instance_id = instance['InstanceId']
        instance_name = get_instance_name(instance)

        snapshot_desc = prompt_snapshot(instance_name)

        if snapshot_desc:
            volume_id = get_root_volume_id(ec2, instance_id)
            if volume_id:
                create_snapshot(ec2, volume_id, snapshot_desc)
            else:
                print("[WARNING] Could not find root volume. Skipping snapshot.")

        if not confirm_termination(instance):
            print("\nCancelled. No instances were terminated.")
            return

        print(f"\nTerminating {instance_id}...")
        ec2.terminate_instances(InstanceIds=[instance_id])

        print("Waiting for instance to terminate...")
        waiter = ec2.get_waiter('instance_terminated')
        waiter.wait(InstanceIds=[instance_id])

        print(f"\n=== Instance Terminated ===")
        print(f"Instance ID: {instance_id} has been terminated.")
        if snapshot_desc:
            print(f"Your snapshot is saved and can be used to restore this instance later.")
        print(f"==========================")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    delete_instance()
