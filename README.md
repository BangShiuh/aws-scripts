# AWS Scripts

A set of scripts to create, manage, and connect to EC2 instances on AWS.

---

## Folder Structure

```
aws-scripts/
├── local/        # Run on your local machine (Windows)
├── ec2/          # Run on the EC2 instance
└── admin/        # Run by the instructor only
```

---

## Prerequisites

### 1. Install Miniconda (Windows)
Download and install from: https://docs.anaconda.com/miniconda/

### 2. Create the conda environment and install boto3
```powershell
conda create -n aws-env python=3.11 -y
conda activate aws-env
pip install boto3
```

### 3. Configure AWS credentials
Get your Access Key ID and Secret Access Key from your instructor, then run:
```powershell
aws configure
```
Enter:
- AWS Access Key ID
- AWS Secret Access Key
- Default region: `ap-southeast-2`
- Default output format: `json`

### 4. Verify your credentials
```powershell
conda activate aws-env
python local/checkAWS.py
```

---

## Local Scripts

> Run these on your **Windows machine** with `conda activate aws-env` first.

### Create an EC2 instance
```powershell
python local/createEC2.py
```
- Choose a region, key pair, instance type, OS, and volume size
- Optionally restore from a previous snapshot
- Automatically adds your IP to the security group
- Updates your SSH config so you can connect with `ssh <alias>`

### Delete an EC2 instance
```powershell
python local/deleteEC2.py
```
- Lists your running instances
- Optionally creates a snapshot before terminating (recommended)
- Requires typing `yes` to confirm

### Add your IP to SSH access
```powershell
python local/addMyIP.py
```
Run this when you **switch networks** (e.g. office to lab) on an already running instance.

### Check AWS credentials
```powershell
python local/checkAWS.py
```

---

## Connecting via SSH

After running `createEC2.py`, connect with:
```powershell
ssh <your-alias>
```

Your SSH config is updated automatically. The alias is whatever you entered when prompted.

### Fix permissions on your .pem file (first time only)
```powershell
icacls "C:\Users\<you>\.ssh\<key>.pem" /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

---

## EC2 Scripts

> Copy `setup.sh` to your EC2 and run it after first login.

```powershell
# From your local machine
scp ec2/setup.sh <alias>:~/
```

```bash
# On the EC2
bash setup.sh
```

Select a mode:
- **1. Fresh setup** — installs conda, git, vim, htop, and sets up your GitHub SSH key
- **2. Health check** — verifies conda, GitHub SSH, and disk space on a restarted instance

After fresh setup, activate conda:
```bash
source ~/.bashrc
```

---

## Typical Workflow

### Starting a new project
1. `python local/createEC2.py` — create a fresh EC2
2. `scp ec2/setup.sh <alias>:~/` — copy setup script
3. `ssh <alias>` — connect
4. `bash setup.sh` — install tools and set up GitHub
5. `cd ~/repos && git clone git@github.com:<user>/<repo>.git` — clone your repo

### Saving your work and shutting down
1. Push your code to GitHub
2. `python local/deleteEC2.py` — create a snapshot and terminate

### Resuming from a snapshot
1. `python local/createEC2.py` — select "Restore from snapshot"
2. `ssh <alias>` — connect (run `bash setup.sh` and select health check to verify)

### Changing networks (office ↔ lab)
```powershell
python local/addMyIP.py
```

---

## Admin (Instructor Only)

### Create IAM users for students
```powershell
python admin/createStudents.py
```
Enter student usernames separated by commas. Credentials are saved to `student_credentials.csv` — send each student their own row.

Students are given EC2-only permissions and cannot access billing, IAM, or other AWS services.
