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

def list_resizable_instances(ec2):
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['running', 'stopped']}
    ])
    return [inst for res in response['Reservations'] for inst in res['Instances']]

def prompt_instance(instances):
    print("\nInstances:")
    print(f"  {'#':<4} {'Name':<20} {'Instance ID':<22} {'Type':<14} {'State'}")
    print(f"  {'-'*4} {'-'*20} {'-'*22} {'-'*14} {'-'*10}")
    for i, inst in enumerate(instances, 1):
        name = get_instance_name(inst)
        state = inst['State']['Name']
        print(f"  {i:<4} {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']:<14} {state}")

    while True:
        choice = input("\nEnter the number of the instance to resize: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(instances):
            return instances[int(choice) - 1]
        else:
            print(f"Invalid choice. Enter a number between 1 and {len(instances)}.")

def resize_instance():
    try:
        print("=== EC2 Resize ===\n")

        region = prompt_region()
        ec2 = boto3.client('ec2', region_name=region)

        print("\nFetching instances...")
        instances = list_resizable_instances(ec2)

        if not instances:
            print("No instances found in this region.")
            return

        instance = prompt_instance(instances)
        instance_id = instance['InstanceId']
        name = get_instance_name(instance)
        current_type = instance['InstanceType']
        state = instance['State']['Name']

        new_type = input(f"\nNew instance type (current: {current_type}): ").strip()
        if not new_type:
            print("No instance type entered. Aborting.")
            return

        was_running = state == 'running'

        if was_running:
            print(f"\nStopping '{name}' ({instance_id})...")
            ec2.stop_instances(InstanceIds=[instance_id])
            waiter = ec2.get_waiter('instance_stopped')
            waiter.wait(InstanceIds=[instance_id])
            print("Instance stopped.")

        print(f"\nChanging instance type to {new_type}...")
        ec2.modify_instance_attribute(
            InstanceId=instance_id,
            InstanceType={'Value': new_type}
        )
        print(f"Instance type changed to {new_type}.")

        if was_running:
            print(f"\nStarting '{name}'...")
            ec2.start_instances(InstanceIds=[instance_id])
            waiter = ec2.get_waiter('instance_running')
            waiter.wait(InstanceIds=[instance_id])

            desc = ec2.describe_instances(InstanceIds=[instance_id])
            public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

            print(f"\n=== Done ===")
            print(f"'{name}' is running as {new_type}")
            print(f"New public IP: {public_ip}  (update SSH config if needed)")
            print(f"  python local/startEC2.py  — or update ~/.ssh/config manually")
            print(f"============")
        else:
            print(f"\n=== Done ===")
            print(f"'{name}' is stopped and ready to start as {new_type}.")
            print(f"  python local/startEC2.py")
            print(f"============")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    resize_instance()
