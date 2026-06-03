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
            print(f"Invalid choice.")

def get_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'

def list_running_instances(ec2):
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running']}
    ])
    instances = []
    for reservation in response['Reservations']:
        for instance in reservation['Instances']:
            instances.append(instance)
    return instances

def prompt_instance(instances):
    print("\nRunning instances:")
    print(f"  {'#':<4} {'Name':<20} {'Instance ID':<22} {'Type':<12} {'Public IP'}")
    print(f"  {'-'*4} {'-'*20} {'-'*22} {'-'*12} {'-'*15}")
    for i, inst in enumerate(instances, 1):
        name = get_instance_name(inst)
        public_ip = inst.get('PublicIpAddress', 'N/A')
        print(f"  {i:<4} {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']:<12} {public_ip}")

    while True:
        choice = input("\nEnter the number of the instance to stop: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(instances):
            return instances[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(instances)}.")

def stop_instance():
    try:
        print("=== EC2 Stop ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        print("\nFetching running instances...")
        instances = list_running_instances(ec2)

        if not instances:
            print("No running instances found in this region.")
            return

        instance = prompt_instance(instances)
        instance_id = instance['InstanceId']
        name = get_instance_name(instance)

        ec2.stop_instances(InstanceIds=[instance_id])
        print(f"\nStopping '{name}' ({instance_id})...")

        print("Waiting for instance to stop...")
        waiter = ec2.get_waiter('instance_stopped')
        waiter.wait(InstanceIds=[instance_id])

        print(f"\n=== Instance Stopped ===")
        print(f"'{name}' is now stopped.")
        print(f"Note: the public IP will change when you start it again.")
        print(f"Use 'python local/startEC2.py' to restart.")
        print(f"========================")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    stop_instance()
