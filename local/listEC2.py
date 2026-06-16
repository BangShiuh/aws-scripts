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

STATES = ['pending', 'running', 'stopping', 'stopped']

def get_instance_name(instance):
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'

def list_instances():
    try:
        print("=== EC2 Instances ===\n")

        region = DEFAULT_REGION
        ec2 = boto3.client('ec2', region_name=region)

        response = ec2.describe_instances(Filters=[
            {'Name': 'instance-state-name', 'Values': STATES}
        ])

        instances = [
            inst
            for res in response['Reservations']
            for inst in res['Instances']
        ]

        if not instances:
            print(f"No instances found in {region}.")
            return

        print(f"  {'Name':<20} {'Instance ID':<22} {'Type':<12} {'State':<10} {'Public IP'}")
        print(f"  {'-'*20} {'-'*22} {'-'*12} {'-'*10} {'-'*15}")
        for inst in instances:
            name = get_instance_name(inst)
            state = inst['State']['Name']
            public_ip = inst.get('PublicIpAddress', 'N/A')
            print(f"  {name:<20} {inst['InstanceId']:<22} {inst['InstanceType']:<12} {state:<10} {public_ip}")

    except NoCredentialsError:
        print("\n[ERROR] No AWS credentials found.")
        print("Please run 'aws configure' to set up your credentials.")
    except ClientError as e:
        print(f"\n[AWS ERROR] {e.response['Error']['Message']}")
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")

if __name__ == "__main__":
    list_instances()
