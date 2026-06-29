import re
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

import boto3
from botocore.exceptions import ClientError

SSH_CONFIG_PATH = Path.home() / '.ssh' / 'config'


def get_session(access_key: str, secret_key: str, region: str) -> boto3.Session:
    return boto3.Session(
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
    )


def get_my_ip() -> str:
    for url in ['https://checkip.amazonaws.com', 'https://api.ipify.org', 'https://icanhazip.com']:
        try:
            return urllib.request.urlopen(url, timeout=5).read().decode().strip()
        except Exception:
            continue
    raise RuntimeError("Could not determine your public IP address.")


def _get_instance_name(instance: dict) -> str:
    for tag in instance.get('Tags', []):
        if tag['Key'] == 'Name':
            return tag['Value']
    return '(no name)'


def _get_tag(instance: dict, key: str) -> str:
    for tag in instance.get('Tags', []):
        if tag['Key'] == key:
            return tag['Value']
    return ''


def _get_root_volume_id(instance: dict) -> Optional[str]:
    root_device = instance.get('RootDeviceName', '/dev/xvda')
    for mapping in instance.get('BlockDeviceMappings', []):
        if mapping['DeviceName'] == root_device:
            return mapping['Ebs']['VolumeId']
    for mapping in instance.get('BlockDeviceMappings', []):
        if 'Ebs' in mapping:
            return mapping['Ebs']['VolumeId']
    return None


def _add_ip_to_sg(ec2, instance_id: str) -> str:
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
        if my_cidr not in existing:
            try:
                ec2.authorize_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[{
                        'IpProtocol': 'tcp',
                        'FromPort': 22,
                        'ToPort': 22,
                        'IpRanges': [{'CidrIp': my_cidr, 'Description': 'auto-added by EC2 Manager'}]
                    }]
                )
            except ClientError:
                pass
    return my_ip


def _find_alias_from_ssh_config(instance_name: str, public_ip: str) -> str:
    """Scan ~/.ssh/config and return the Host alias that matches by IP or instance name."""
    if not SSH_CONFIG_PATH.exists():
        return ''
    try:
        content = SSH_CONFIG_PATH.read_text(encoding='utf-8-sig')
    except Exception:
        return ''

    # Split into per-host blocks
    blocks = re.split(r'(?=^Host\s)', content, flags=re.MULTILINE)

    # First pass: match by HostName IP (most reliable — works for running instances)
    if public_ip:
        for block in blocks:
            m = re.match(r'^Host\s+(\S+)', block)
            hn = re.search(r'^\s+HostName\s+(\S+)', block, re.MULTILINE)
            if m and hn and hn.group(1) == public_ip:
                return m.group(1)

    # Second pass: match by instance name substring in alias (works for stopped instances)
    if instance_name and instance_name != '(no name)':
        for block in blocks:
            m = re.match(r'^Host\s+(\S+)', block)
            if m and instance_name.lower() in m.group(1).lower():
                return m.group(1)

    return ''


# ── Public API ────────────────────────────────────────────────────────────────

def list_instances(session: boto3.Session) -> list[dict]:
    ec2 = session.client('ec2')
    response = ec2.describe_instances(Filters=[
        {'Name': 'instance-state-name', 'Values': ['pending', 'running', 'stopping', 'stopped']}
    ])
    result = []
    for res in response['Reservations']:
        for inst in res['Instances']:
            name = _get_instance_name(inst)
            ip = inst.get('PublicIpAddress', '')
            ssh_alias = _get_tag(inst, 'SSHAlias') or _find_alias_from_ssh_config(name, ip)
            result.append({
                'id':        inst['InstanceId'],
                'name':      name,
                'type':      inst['InstanceType'],
                'state':     inst['State']['Name'],
                'ip':        ip or '—',
                'ssh_alias': ssh_alias,
            })
    return result


def set_ssh_alias_tag(session: boto3.Session, instance_id: str, alias: str) -> None:
    ec2 = session.client('ec2')
    ec2.create_tags(Resources=[instance_id], Tags=[{'Key': 'SSHAlias', 'Value': alias}])


def start_instance(session: boto3.Session, instance_id: str,
                   progress_cb: Optional[Callable] = None) -> str:
    ec2 = session.client('ec2')
    if progress_cb:
        progress_cb("Starting instance…")
    ec2.start_instances(InstanceIds=[instance_id])

    if progress_cb:
        progress_cb("Waiting for instance to be running…")
    ec2.get_waiter('instance_running').wait(InstanceIds=[instance_id])

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

    if progress_cb:
        progress_cb("Updating security group with your IP…")
    _add_ip_to_sg(ec2, instance_id)

    return public_ip


def stop_instance(session: boto3.Session, instance_id: str,
                  progress_cb: Optional[Callable] = None) -> None:
    ec2 = session.client('ec2')
    if progress_cb:
        progress_cb("Stopping instance…")
    ec2.stop_instances(InstanceIds=[instance_id])

    if progress_cb:
        progress_cb("Waiting for instance to stop…")
    ec2.get_waiter('instance_stopped').wait(InstanceIds=[instance_id])


def add_my_ip(session: boto3.Session, instance_id: str,
              progress_cb: Optional[Callable] = None) -> str:
    ec2 = session.client('ec2')
    if progress_cb:
        progress_cb("Getting your public IP…")
    return _add_ip_to_sg(ec2, instance_id)


def snapshot_instance(session: boto3.Session, instance_id: str, description: str,
                      progress_cb: Optional[Callable] = None) -> str:
    ec2 = session.client('ec2')

    if progress_cb:
        progress_cb("Finding root volume…")
    desc = ec2.describe_instances(InstanceIds=[instance_id])
    instance = desc['Reservations'][0]['Instances'][0]
    volume_id = _get_root_volume_id(instance)
    if not volume_id:
        raise RuntimeError("Could not find root volume for this instance.")

    instance_name = _get_instance_name(instance)

    if progress_cb:
        progress_cb(f"Creating snapshot of {volume_id}…")
    response = ec2.create_snapshot(
        VolumeId=volume_id,
        Description=description,
        TagSpecifications=[{
            'ResourceType': 'snapshot',
            'Tags': [
                {'Key': 'Name',           'Value': f"{instance_name}-snapshot"},
                {'Key': 'SourceInstance', 'Value': instance_id},
            ]
        }]
    )
    snapshot_id = response['SnapshotId']

    if progress_cb:
        progress_cb(f"Waiting for {snapshot_id} to complete (may take a few minutes)…")
    ec2.get_waiter('snapshot_completed').wait(
        SnapshotIds=[snapshot_id],
        WaiterConfig={'Delay': 15, 'MaxAttempts': 180},
    )
    return snapshot_id


def list_snapshots(session: boto3.Session) -> list[dict]:
    ec2 = session.client('ec2')
    response = ec2.describe_snapshots(OwnerIds=['self'])
    snapshots = sorted(response['Snapshots'], key=lambda s: s['StartTime'], reverse=True)
    return [
        {
            'id':          s['SnapshotId'],
            'size':        s['VolumeSize'],
            'date':        s['StartTime'].strftime('%Y-%m-%d %H:%M'),
            'description': s.get('Description', ''),
        }
        for s in snapshots
    ]


def create_instance(session: boto3.Session, key_name: str, instance_name: str,
                    instance_type: str, os_option: Optional[tuple],
                    volume_size: int = 30, boot_source: str = 'fresh',
                    snapshot_id: Optional[str] = None,
                    ssh_alias: str = '',
                    progress_cb: Optional[Callable] = None) -> tuple[str, str, str]:
    ec2 = session.client('ec2')
    temp_ami_id = None

    if boot_source == 'snapshot':
        if progress_cb:
            progress_cb(f"Registering temporary AMI from snapshot {snapshot_id}…")
        resp = ec2.register_image(
            Name=f'restore-{snapshot_id}-{int(time.time())}',
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
        temp_ami_id = resp['ImageId']
        ami_id = temp_ami_id
        ssh_user = 'ubuntu'
    else:
        os_name, ssh_user, ssm_param = os_option
        if progress_cb:
            progress_cb(f"Looking up latest {os_name} AMI…")
        ssm = session.client('ssm')
        ami_id = ssm.get_parameter(Name=ssm_param)['Parameter']['Value']

    if progress_cb:
        progress_cb(f"Launching {instance_type} instance '{instance_name}'…")

    if boot_source == 'snapshot':
        block_devices = []
    else:
        ami_info = ec2.describe_images(ImageIds=[ami_id])['Images'][0]
        root_device = ami_info['RootDeviceName']
        block_devices = [{
            'DeviceName': root_device,
            'Ebs': {'VolumeSize': volume_size, 'VolumeType': 'gp3', 'DeleteOnTermination': True}
        }]

    tags = [{'Key': 'Name', 'Value': instance_name}]
    if ssh_alias:
        tags.append({'Key': 'SSHAlias', 'Value': ssh_alias})

    try:
        resp = ec2.run_instances(
            ImageId=ami_id,
            InstanceType=instance_type,
            KeyName=key_name,
            MinCount=1,
            MaxCount=1,
            BlockDeviceMappings=block_devices,
            TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags}]
        )
    except Exception:
        if temp_ami_id:
            try:
                ec2.deregister_image(ImageId=temp_ami_id)
            except Exception:
                pass
        raise

    instance_id = resp['Instances'][0]['InstanceId']

    if progress_cb:
        progress_cb("Waiting for instance to be running…")
    ec2.get_waiter('instance_running').wait(InstanceIds=[instance_id])

    if temp_ami_id:
        try:
            ec2.deregister_image(ImageId=temp_ami_id)
        except Exception:
            pass

    desc = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = desc['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'N/A')

    if progress_cb:
        progress_cb("Adding your IP to the security group…")
    _add_ip_to_sg(ec2, instance_id)

    return instance_id, public_ip, ssh_user


def delete_instance(session: boto3.Session, instance_id: str,
                    snapshot_first: bool = True, snapshot_desc: Optional[str] = None,
                    progress_cb: Optional[Callable] = None) -> Optional[str]:
    ec2 = session.client('ec2')
    snapshot_id = None

    if snapshot_first:
        if progress_cb:
            progress_cb("Creating snapshot before termination…")
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        instance = desc['Reservations'][0]['Instances'][0]
        volume_id = _get_root_volume_id(instance)
        if volume_id:
            resp = ec2.create_snapshot(
                VolumeId=volume_id,
                Description=snapshot_desc or 'pre-termination backup',
            )
            snapshot_id = resp['SnapshotId']
            if progress_cb:
                progress_cb(f"Snapshot {snapshot_id} started. Terminating instance…")

    if progress_cb:
        progress_cb("Terminating instance…")
    ec2.terminate_instances(InstanceIds=[instance_id])

    if progress_cb:
        progress_cb("Waiting for instance to terminate…")
    ec2.get_waiter('instance_terminated').wait(InstanceIds=[instance_id])

    return snapshot_id


def update_ssh_config(alias: str, hostname: str, pem_path: str, ssh_user: str) -> None:
    SSH_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_block = (
        f"Host {alias}\n"
        f"    HostName {hostname}\n"
        f"    User {ssh_user}\n"
        f"    IdentityFile {pem_path}\n"
        f"    ServerAliveInterval 60\n"
        f"    StrictHostKeyChecking accept-new\n"
    )

    if not SSH_CONFIG_PATH.exists():
        SSH_CONFIG_PATH.write_text(new_block, encoding='utf-8')
        return

    content = SSH_CONFIG_PATH.read_text(encoding='utf-8-sig')
    pattern = rf'^Host {re.escape(alias)}\s*\n(?:[ \t]+.*\n?)*'
    match = re.search(pattern, content, re.MULTILINE)

    if match:
        updated = content[:match.start()] + new_block + '\n' + content[match.end():]
        SSH_CONFIG_PATH.write_text(updated, encoding='utf-8')
    else:
        with open(SSH_CONFIG_PATH, 'a', encoding='utf-8') as f:
            f.write(f'\n{new_block}')
