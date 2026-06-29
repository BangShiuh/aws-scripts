import json
from pathlib import Path

CONFIG_PATH = Path.home() / '.aws-ec2-gui.json'

DEFAULT_REGION = 'ap-southeast-2'

REGIONS = [
    ('ap-southeast-2', 'Asia Pacific (Sydney)'),
    ('ap-southeast-1', 'Asia Pacific (Singapore)'),
    ('ap-east-1',      'Asia Pacific (Hong Kong)'),
    ('us-east-1',      'US East (N. Virginia)'),
    ('us-west-2',      'US West (Oregon)'),
    ('eu-west-1',      'Europe (Ireland)'),
]

OS_OPTIONS = [
    ('Ubuntu 24.04 LTS',  'ubuntu',    '/aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id'),
    ('Ubuntu 22.04 LTS',  'ubuntu',    '/aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id'),
    ('Amazon Linux 2023', 'ec2-user',  '/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64'),
]

INSTANCE_TYPES = [
    't2.micro', 't3.micro', 't3.small', 't3.medium', 't3.xlarge',
    'g4dn.xlarge', 'g4dn.2xlarge', 'g5.xlarge', 'p3.2xlarge',
]

DEFAULT_VOLUME_SIZE = 30


def load() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {
        'access_key': '',
        'secret_key': '',
        'region': DEFAULT_REGION,
        'pem_path': '',
        'ssh_user': 'ubuntu',
    }


def save(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding='utf-8')


def is_configured(config: dict) -> bool:
    return bool(config.get('access_key') and config.get('secret_key') and config.get('region'))
