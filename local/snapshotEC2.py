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

    while True:
        choice = input(f"\nEnter number or region code (press Enter for default: {DEFAULT_REGION}): ").strip()
        if choice == '':
            return DEFAULT_REGION
        elif choice.isdigit() and 1 <= int(choice) <= len(REGIONS):
            return REGIONS[int(choice) - 1][0]
        elif choice in [r[0] for r in REGIONS]:
            return choice
        else:
            print("Invalid choice.")

def get_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'

def list_stoppable_instances(ec2):
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
    ])
    return [inst for res in response['Reservations'] for inst in res['Instances']]

def prompt_instance(instances):
    print("\nInstances:")
    print(f"  {'#':<4} {'Name':<20} {'Instance ID':<22} {'Type':<12} {'State':<10} {'Public IP'}")
    print(f"  {'-'*4} {'-'*20} {'-'*22} {'-'*12} {'-'*10} {'-'*15}")
    for i, inst in enumerate(instances, 1):
        name = get_instance_name(inst)
        state = inst['State']['Name']
        public_ip = inst.get('PublicIpAddress', 'N/A')
        print(f"  {i:<4} {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']:<12} {state:<10} {public_ip}")

    while True:
        choice = input("\nEnter the number of the instance to snapshot: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(instances):
            return instances[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(instances)}.")

def get_root_volume(ec2, instance):
    root_device = instance['RootDeviceName']
    for mapping in instance.get('BlockDeviceMappings', []):
        if mapping['DeviceName'] == root_device:
            return mapping['Ebs']['VolumeId']
    # fallback: return first volume
    for mapping in instance.get('BlockDeviceMappings', []):
        if 'Ebs' in mapping:
            return mapping['Ebs']['VolumeId']
    return None

def create_snapshot():
    try:
        print("=== EC2 Snapshot Creator ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        print("\nFetching instances...")
        instances = list_stoppable_instances(ec2)

        if not instances:
            print("No instances found in this region.")
            return

        instance = prompt_instance(instances)
        instance_id = instance['InstanceId']
        instance_name = get_instance_name(instance)

        volume_id = get_root_volume(ec2, instance)
        if not volume_id:
            print("[ERROR] Could not find root volume for this instance.")
            return

        print(f"\nRoot volume: {volume_id}")

        default_desc = f"snapshot of {instance_name} ({instance_id})"
        desc_input = input(f"\nSnapshot description (press Enter for default: '{default_desc}'): ").strip()
        description = desc_input if desc_input else default_desc

        print(f"\nCreating snapshot of {volume_id}...")
        response = ec2.create_snapshot(
            VolumeId=volume_id,
            Description=description,
            TagSpecifications=[{
                'ResourceType': 'snapshot',
                'Tags': [
                    {'Key': 'Name', 'Value': f"{instance_name}-snapshot"},
                    {'Key': 'SourceInstance', 'Value': instance_id},
                ]
            }]
        )

        snapshot_id = response['SnapshotId']
        print(f"\nSnapshot initiated: {snapshot_id}")
        print("Snapshots run in the background — this takes a few minutes for a 30 GB volume.")
        print("\nWaiting for snapshot to complete...")

        waiter = ec2.get_waiter('snapshot_completed')
        waiter.wait(
            SnapshotIds=[snapshot_id],
            WaiterConfig={'Delay': 15, 'MaxAttempts': 180}  # 45 min max
        )

        print(f"\n=== Snapshot Complete ===")
        print(f"Snapshot ID:  {snapshot_id}")
        print(f"Description:  {description}")
        print(f"\nTo launch a new instance from this snapshot:")
        print(f"  python local/createEC2.py  → choose 'Restore from snapshot' → select {snapshot_id}")
        print(f"=========================")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    create_snapshot()
