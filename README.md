# Firecracker Webmin Plugin

Webmin module for managing [Firecracker microVMs](https://firecracker-microvm.github.io/) from a web UI.

## Features

- List microVMs and current runtime state
- Create and boot new VMs from kernel + rootfs images
- Start, stop, and delete VMs
- Attach and detach TAP-based networking with NAT
- Read serial/Firecracker log output from the browser
- Update vCPU/memory and basic network/disk IOPS limits

## Repository Layout

- `firecracker/`: Installable Webmin module directory
- `docs/architecture-plan-firecracker-webmin-module.md`: Architecture and implementation plan

## Getting Started

### 1) Install host prerequisites

Debian/Ubuntu:

```bash
sudo apt update
sudo apt install -y webmin curl iptables iproute2 qemu-kvm cpu-checker
```

RHEL/Alma/Rocky:

```bash
sudo dnf install -y webmin curl iptables iproute qemu-kvm
```

### 2) Install Firecracker binary

```bash
sudo install -d -m 0755 /usr/local/bin
FCVER=$(curl -s https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest | sed -n 's/.*"tag_name": "\(.*\)".*/\1/p')
wget "https://github.com/firecracker-microvm/firecracker/releases/download/${FCVER}/firecracker-${FCVER}-x86_64.tgz"
tar xf "firecracker-${FCVER}-x86_64.tgz"
sudo mv release-*/firecracker-* /usr/local/bin/firecracker
sudo chmod +x /usr/local/bin/firecracker
firecracker --version
```

### 3) Create runtime directories

```bash
sudo mkdir -p /var/lib/firecracker-webmin/{vms,kernels,rootfs,network}
sudo mkdir -p /var/run/firecracker
sudo mkdir -p /var/log/firecracker
```

### 4) Add kernel and rootfs images

```bash
sudo wget "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/vmlinux-5.10.225" -O /var/lib/firecracker-webmin/kernels/vmlinux-5.10
sudo wget "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/ubuntu-22.04.ext4" -O /var/lib/firecracker-webmin/rootfs/ubuntu-22.04.ext4
```

### 5) Build Webmin package

From this repository root:

```bash
mkdir -p dist
tar czf dist/firecracker-0.1.wbm.gz firecracker
```

### 6) Install module in Webmin

1. Open `https://<your-host>:10000`
2. Go to `Webmin` -> `Webmin Configuration` -> `Webmin Modules`
3. Choose **Install Module** from local file
4. Select `dist/firecracker-0.1.wbm.gz`
5. Open **System -> Firecracker MicroVM Manager**

## Notes

- This module assumes root-level privileges for TAP and iptables operations.
- vCPU/RAM changes are persisted and applied through Firecracker API when possible.
- For production hardening, use a dedicated Firecracker runner user and sudo rules.

## License

GPL-3.0 (see `LICENSE`).
