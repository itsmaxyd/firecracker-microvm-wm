# Firecracker microVM Plugin for Webmin
## Architecture Plan & Step-by-Step Implementation Guide

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture Diagram](#2-architecture-diagram)
3. [Module Directory Structure](#3-module-directory-structure)
4. [Component Breakdown](#4-component-breakdown)
5. [Feature Specifications](#5-feature-specifications)
6. [Data Flow & State Management](#6-data-flow--state-management)
7. [API Integration Design](#7-api-integration-design)
8. [Step-by-Step Implementation Plan](#8-step-by-step-implementation-plan)
9. [Host Prerequisites](#9-host-prerequisites)
10. [Security Considerations](#10-security-considerations)
11. [Testing Strategy](#11-testing-strategy)

---

## 1. Overview

### Purpose
A standalone Webmin module that provides a full graphical interface for managing **Firecracker microVMs** on a Linux host. Firecracker is controlled exclusively via a Unix domain socket REST API, so this module acts as a web-based front-end that translates UI actions into Firecracker API calls and system commands.

### Technology Stack

| Layer | Technology |
|---|---|
| Module Language | Perl (Webmin standard) |
| UI Rendering | Webmin CGI + `ui_*` helper functions |
| Firecracker Control | Unix socket REST API via `curl` or `HTTP::Tiny` |
| State Persistence | JSON flat files under `/var/lib/firecracker-webmin/` |
| Networking | Linux TAP devices + iptables NAT |
| Console Access | Named pipes / Unix sockets + AJAX polling |

### Scope of Features

- **List** all running and stopped microVMs with status
- **Create** a new microVM (kernel, rootfs, vCPU, RAM)
- **Start / Stop / Delete** individual VMs
- **Attach Network** (TAP interface, IP assignment, NAT)
- **Console / Serial Output** (live log tail via AJAX)
- **Resource Limits** (vCPU count, memory, disk I/O rate limiting)

---

## 2. Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        BROWSER (UI)                         │
│   index.cgi  create.cgi  vm_action.cgi  console.cgi         │
│   config.cgi  network.cgi  resources.cgi                    │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (Webmin port 10000)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                     WEBMIN CORE                             │
│            Authentication · ACL · Session                   │
└──────────────────────────┬──────────────────────────────────┘
                           │ Perl API
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              FIRECRACKER WEBMIN MODULE                      │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  firecracker │  │  fc_network  │  │   fc_console     │  │
│  │    _lib.pl   │  │    _lib.pl   │  │     _lib.pl      │  │
│  │              │  │              │  │                  │  │
│  │ - API calls  │  │ - TAP mgmt   │  │ - Serial pipe    │  │
│  │ - State I/O  │  │ - iptables   │  │ - Log tail       │  │
│  │ - VM CRUD    │  │ - IP alloc   │  │ - AJAX stream    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────┘  │
│         │                 │                  │              │
└─────────┼─────────────────┼──────────────────┼─────────────┘
          │                 │                  │
          ▼                 ▼                  ▼
┌─────────────────┐  ┌────────────────┐  ┌───────────────────┐
│ Firecracker API │  │  Linux Network │  │  Serial / Log     │
│  (Unix socket)  │  │  TAP + NAT     │  │  Named Pipe       │
│  /var/run/      │  │  iptables      │  │  /var/run/fc/     │
│  firecracker/   │  │  ip route      │  │  <vm>.console     │
│  <vm>.socket    │  │                │  │                   │
└────────┬────────┘  └────────────────┘  └───────────────────┘
         │
         ▼
┌─────────────────┐
│  Firecracker    │
│  Process (VMM)  │
│                 │
│  microVM Guest  │
│  ┌───────────┐  │
│  │  vCPU(s)  │  │
│  │  RAM      │  │
│  │  virtio   │  │
│  │  net/blk  │  │
│  └───────────┘  │
└─────────────────┘
         │
┌─────────────────────────────────────────────────────────────┐
│                   STATE STORE                               │
│   /var/lib/firecracker-webmin/                              │
│   ├── vms/                                                  │
│   │   ├── <vm-name>.json   (config + status)               │
│   │   └── ...                                               │
│   └── network/                                              │
│       └── ip_allocations.json                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Module Directory Structure

```
/usr/share/webmin/firecracker/
│
├── module.info                  # Module metadata (name, version, os_support)
├── config                       # Default runtime configuration values
├── config.info                  # Config field definitions (shown in Module Config UI)
│
├── index.cgi                    # Dashboard – list all microVMs
├── create.cgi                   # Create new microVM (form + POST handler)
├── vm_action.cgi                # Start / Stop / Delete (POST handler)
├── network.cgi                  # Attach / detach network interface
├── console.cgi                  # Serial console viewer (AJAX log stream)
├── resources.cgi                # Edit vCPU / memory / I/O limits
│
├── firecracker_lib.pl           # Core library: API calls, state CRUD, VM lifecycle
├── fc_network_lib.pl            # Network helpers: TAP, iptables, IP allocation
├── fc_console_lib.pl            # Console helpers: pipe management, log tail
│
├── images/
│   ├── firecracker.png          # Module icon (32×32)
│   ├── vm_running.png
│   ├── vm_stopped.png
│   └── vm_unknown.png
│
├── unauthenticated/             # (optional) assets served without auth check
│
├── acl/
│   └── firecracker.acl          # Default ACL (which users can use each feature)
│
└── lang/
    └── en                       # English UI strings (key=value format)
```

---

## 4. Component Breakdown

### 4.1 `module.info`
Declares the module to Webmin.

```ini
name=firecracker
desc=Firecracker MicroVM Manager
version=1.0
os_support=linux
category=system
depends=
```

### 4.2 `config`
Default configuration values editable via **Webmin → Module Config**.

```ini
firecracker_bin=/usr/local/bin/firecracker
socket_dir=/var/run/firecracker
state_dir=/var/lib/firecracker-webmin/vms
kernel_dir=/var/lib/firecracker-webmin/kernels
rootfs_dir=/var/lib/firecracker-webmin/rootfs
log_dir=/var/log/firecracker
network_bridge=fcbr0
network_subnet=172.16.100.0/24
network_gateway=172.16.100.1
tap_prefix=fctap
```

### 4.3 `config.info`
Describes each config key for the Webmin Module Config UI.

```ini
firecracker_bin=Firecracker binary path
socket_dir=Directory for VM Unix sockets
state_dir=VM state/config JSON directory
kernel_dir=Directory containing VM kernel images
rootfs_dir=Directory containing root filesystem images
log_dir=Directory for VM log files
network_bridge=Bridge interface name
network_subnet=MicroVM network subnet (CIDR)
network_gateway=Gateway IP for microVMs
tap_prefix=Prefix for TAP interface names
```

### 4.4 `lang/en`
All user-facing strings.

```ini
index_title=Firecracker MicroVM Manager
index_create=Create MicroVM
index_name=VM Name
index_status=Status
index_vcpus=vCPUs
index_memory=Memory (MiB)
index_ip=IP Address
index_actions=Actions
create_title=Create New MicroVM
create_name=VM Name
create_kernel=Kernel Image
create_rootfs=Root Filesystem
create_vcpus=vCPU Count
create_mem=Memory (MiB)
create_net=Attach Network
create_submit=Create MicroVM
action_start=Start
action_stop=Stop
action_delete=Delete
action_console=Console
action_network=Network
action_resources=Resources
status_running=Running
status_stopped=Stopped
status_unknown=Unknown
err_no_kvm=KVM not available. Check /dev/kvm permissions.
err_fc_notfound=Firecracker binary not found at configured path.
err_vm_exists=A VM with that name already exists.
```

---

## 5. Feature Specifications

### 5.1 List Running MicroVMs (`index.cgi`)

**Behaviour:**
- On load, scan `$state_dir` for `*.json` files (one per VM)
- For each, check if the corresponding `$socket_dir/<name>.socket` exists and is live
- Query Firecracker API `GET /` on each live socket to confirm `state`
- Render an HTML table with: Name, Status (badge), vCPUs, Memory, IP, Actions

**State file schema (`<vm-name>.json`):**
```json
{
  "name": "vm01",
  "kernel": "/var/lib/firecracker-webmin/kernels/vmlinux",
  "rootfs": "/var/lib/firecracker-webmin/rootfs/ubuntu.ext4",
  "vcpus": 2,
  "mem_mib": 512,
  "tap_iface": "fctap0",
  "ip": "172.16.100.10",
  "pid": 12345,
  "status": "running",
  "created_at": "2025-05-01T10:00:00Z",
  "log_file": "/var/log/firecracker/vm01.log"
}
```

---

### 5.2 Create MicroVM (`create.cgi`)

**Form fields:**
- VM Name (text, required, alphanumeric + dash)
- Kernel Image (select from `$kernel_dir` or file path)
- Root Filesystem (select from `$rootfs_dir` or file path)
- vCPU Count (1–16, default 1)
- Memory MiB (64–32768, default 256)
- Attach Network (checkbox, auto-assigns IP from pool)
- Boot args (text, pre-filled with safe defaults)

**On POST:**
1. Validate all fields
2. Check VM name is unique
3. Allocate TAP interface and IP if networking requested
4. Write state JSON to `$state_dir/<name>.json`
5. Build `firecracker --api-sock <socket> --log-path <log>` launch command
6. Execute via `system()` in background, capture PID
7. PUT kernel, rootfs, network, machine-config to Firecracker API
8. POST `/actions` with `InstanceStart`
9. Update state JSON with `pid` and `status: running`
10. Redirect to `index.cgi`

---

### 5.3 Start / Stop / Delete (`vm_action.cgi`)

**POST parameters:** `vm_name`, `action` (start|stop|delete)

**Start:**
1. Load state JSON
2. Relaunch firecracker process if not running
3. Replay config PUTs to socket
4. POST `InstanceStart` action
5. Update status to `running`

**Stop (graceful):**
1. PUT `/actions` `{ "action_type": "SendCtrlAltDel" }` to guest
2. Wait up to 10 seconds for process to exit
3. If still running, send SIGTERM to PID
4. Update status to `stopped`

**Delete:**
1. Stop the VM (as above) if running
2. Delete TAP interface: `ip tuntap del dev <tap>`
3. Remove iptables rules for this VM
4. Release IP back to pool
5. Delete socket file
6. Delete state JSON
7. Optionally delete log file

---

### 5.4 Attach Network (`network.cgi`)

**Operations:**
- Attach a new TAP interface to a running or stopped VM
- Detach / replace existing interface
- View current network config

**Implementation steps per VM:**
1. Allocate next free IP from subnet pool
2. Create TAP device: `ip tuntap add dev <tap> mode tap`
3. Bring it up: `ip link set <tap> up`
4. Add host route: `ip route add <guest_ip>/32 dev <tap>`
5. Add iptables MASQUERADE rule for this IP
6. PUT `/network-interfaces/eth0` to Firecracker API:
```json
{
  "iface_id": "eth0",
  "host_dev_name": "fctap0",
  "guest_mac": "AA:FC:00:00:00:01"
}
```
7. Update state JSON with `tap_iface` and `ip`

**IP Allocation Pool:**
- Managed in `/var/lib/firecracker-webmin/network/ip_allocations.json`
- Simple sequential allocation from the configured subnet
- Released on VM deletion

---

### 5.5 Console / Serial Output (`console.cgi`)

**Architecture:**
- Firecracker writes serial output to a log file (configured via `--log-path`)
- `console.cgi` tails this file and streams it to the browser via chunked HTTP / AJAX polling

**UI:**
- `<pre>` block styled as a terminal (dark background, monospace)
- JavaScript polls `console.cgi?vm=<name>&offset=<bytes>` every 1 second
- Returns new bytes since `offset`; client appends and updates offset
- "Clear" and "Download log" buttons

**Cgi handler:**
```perl
# console.cgi (polling endpoint)
my $vm   = param('vm');
my $offset = param('offset') || 0;
my $log  = "$config{log_dir}/$vm.log";
open(my $fh, '<', $log) or print_error("Cannot open log");
seek($fh, $offset, 0);
my $new_bytes = do { local $/; <$fh> };
my $new_offset = tell($fh);
close($fh);
print "Content-type: application/json\n\n";
print encode_json({ text => $new_bytes, offset => $new_offset });
```

---

### 5.6 Resource Limits (`resources.cgi`)

**Editable fields (live, on running VMs via API):**

| Resource | Firecracker API Endpoint | Notes |
|---|---|---|
| Memory (MiB) | `PATCH /machine-config` | Requires VM stop/start |
| vCPU Count | `PATCH /machine-config` | Requires VM stop/start |
| Network TX rate | `PUT /network-interfaces/<id>` with `rx_rate_limiter` | Live |
| Network RX rate | `PUT /network-interfaces/<id>` with `tx_rate_limiter` | Live |
| Disk read IOPS | `PUT /drives/<id>` with `rate_limiter` | Live |
| Disk write IOPS | `PUT /drives/<id>` with `rate_limiter` | Live |

**Rate limiter schema (Firecracker API):**
```json
{
  "bandwidth": {
    "size": 104857600,
    "refill_time": 1000
  },
  "ops": {
    "size": 500,
    "refill_time": 1000
  }
}
```

---

## 6. Data Flow & State Management

```
Browser Action            Module Layer               System Layer
─────────────────────────────────────────────────────────────────
POST /create.cgi  ──►  validate_input()          ──►  (nothing yet)
                  ──►  allocate_network()         ──►  ip tuntap add
                  ──►  write_state_json()         ──►  fs write
                  ──►  launch_fc_process()        ──►  fork firecracker
                  ──►  configure_vm_via_api()     ──►  PUT to socket
                  ──►  start_vm()                 ──►  POST /actions
                  ──►  update_state_json()        ──►  fs write
                  ◄──  redirect index.cgi

GET /index.cgi    ──►  list_state_files()         ──►  fs readdir
                  ──►  for each VM:               
                        check_socket_live()       ──►  stat() socket
                        get_vm_info_via_api()     ──►  GET / on socket
                  ◄──  render HTML table

POST /vm_action   ──►  load_state_json()          ──►  fs read
  (stop)          ──►  send_shutdown_signal()     ──►  PUT /actions
                  ──►  wait_for_exit()            ──►  waitpid / sleep
                  ──►  update_state_json()        ──►  fs write
                  ◄──  redirect index.cgi
```

---

## 7. API Integration Design

### Core API Wrapper (`firecracker_lib.pl`)

```perl
package FCLib;
use strict;
use warnings;
use JSON;

# Make a PUT request to Firecracker socket
sub fc_put {
    my ($socket, $path, $data_ref) = @_;
    my $json = encode_json($data_ref);
    my $cmd = qq{curl -s -o /dev/null -w "%{http_code}" }
            . qq{-X PUT --unix-socket "$socket" }
            . qq{-H "Content-Type: application/json" }
            . qq{-d '$json' }
            . qq{"http://localhost$path"};
    my $code = `$cmd`;
    return $code =~ /^2/;
}

# Make a PATCH request
sub fc_patch {
    my ($socket, $path, $data_ref) = @_;
    my $json = encode_json($data_ref);
    my $cmd = qq{curl -s -o /dev/null -w "%{http_code}" }
            . qq{-X PATCH --unix-socket "$socket" }
            . qq{-H "Content-Type: application/json" }
            . qq{-d '$json' }
            . qq{"http://localhost$path"};
    my $code = `$cmd`;
    return $code =~ /^2/;
}

# GET info from Firecracker
sub fc_get {
    my ($socket, $path) = @_;
    my $cmd = qq{curl -s -X GET --unix-socket "$socket" }
            . qq{"http://localhost$path"};
    my $out = `$cmd`;
    return decode_json($out);
}

# Check if a socket is live and responsive
sub socket_alive {
    my ($socket) = @_;
    return 0 unless -S $socket;
    my $result = fc_get($socket, '/');
    return defined($result->{state});
}

# Configure a new VM (call before InstanceStart)
sub configure_vm {
    my ($socket, $cfg) = @_;
    fc_put($socket, '/boot-source', {
        kernel_image_path => $cfg->{kernel},
        boot_args => $cfg->{boot_args} // 
            "console=ttyS0 reboot=k panic=1 pci=off"
    });
    fc_put($socket, '/drives/rootfs', {
        drive_id       => "rootfs",
        path_on_host   => $cfg->{rootfs},
        is_root_device => JSON::true,
        is_read_only   => JSON::false
    });
    fc_put($socket, '/machine-config', {
        vcpu_count   => $cfg->{vcpus} + 0,
        mem_size_mib => $cfg->{mem_mib} + 0
    });
    if ($cfg->{tap_iface}) {
        fc_put($socket, '/network-interfaces/eth0', {
            iface_id      => "eth0",
            host_dev_name => $cfg->{tap_iface},
            guest_mac     => $cfg->{mac} // generate_mac($cfg->{name})
        });
    }
}

# Start a configured VM
sub start_vm {
    my ($socket) = @_;
    return fc_put($socket, '/actions', { action_type => "InstanceStart" });
}

# Send graceful shutdown
sub shutdown_vm {
    my ($socket) = @_;
    return fc_put($socket, '/actions', { action_type => "SendCtrlAltDel" });
}

# Generate a deterministic MAC from VM name
sub generate_mac {
    my ($name) = @_;
    my $hash = 0;
    $hash = ($hash * 31 + ord($_)) & 0xFFFFFF foreach split //, $name;
    return sprintf("AA:FC:%02X:%02X:%02X:%02X",
        ($hash >> 16) & 0xFF, ($hash >> 8) & 0xFF,
        $hash & 0xFF, int(rand 256));
}

1;
```

---

## 8. Step-by-Step Implementation Plan

### Phase 0 — Environment Setup (Day 0)

**Goal:** Working Firecracker binary and KVM access on host.

```bash
# Step 0.1 – Verify KVM
sudo apt install cpu-checker
sudo kvm-ok
# Expected: INFO: /dev/kvm exists

# Step 0.2 – Download Firecracker
FCVER=$(curl -s https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest \
  | grep tag_name | cut -d'"' -f4)
wget "https://github.com/firecracker-microvm/firecracker/releases/download/${FCVER}/firecracker-${FCVER}-x86_64.tgz"
tar xf firecracker-*.tgz
mv release-*/firecracker-* /usr/local/bin/firecracker
chmod +x /usr/local/bin/firecracker

# Step 0.3 – Create directory structure
mkdir -p /var/lib/firecracker-webmin/{vms,kernels,rootfs,network}
mkdir -p /var/run/firecracker
mkdir -p /var/log/firecracker

# Step 0.4 – Test with a sample microVM (manual, verify Firecracker works)
# Download a test kernel + rootfs from Firecracker quickstart guide
```

---

### Phase 1 — Module Scaffold (Day 1)

**Goal:** Module appears in Webmin, loads without errors.

```
Step 1.1 – Create module directory
  mkdir -p /usr/share/webmin/firecracker/{lang,acl,images}

Step 1.2 – Write module.info
  (copy content from Section 4.1)

Step 1.3 – Write config and config.info
  (copy content from Section 4.2 and 4.3)

Step 1.4 – Write lang/en
  (copy content from Section 4.4)

Step 1.5 – Write a minimal index.cgi
  #!/usr/bin/perl
  require './firecracker-lib.pl';
  &ReadParse();
  &ui_print_header(undef, $text{'index_title'}, "");
  print "Module loaded successfully.<br>";
  &ui_print_footer();

Step 1.6 – Create placeholder firecracker_lib.pl
  (just load webmin libs and read config)

Step 1.7 – Load in Webmin
  Webmin → Webmin Configuration → Webmin Modules → Install from local directory
  Verify icon appears in System category
```

---

### Phase 2 — Core Library (`firecracker_lib.pl`) (Days 2–3)

**Goal:** All Firecracker API interactions working and tested.

```
Step 2.1 – Implement fc_put(), fc_patch(), fc_get()
  - Use curl with --unix-socket
  - Return HTTP status code
  - Log errors to /var/log/firecracker/webmin.log

Step 2.2 – Implement socket_alive()
  - stat() check + GET / attempt
  - Return 0/1

Step 2.3 – Implement state file CRUD
  - load_vm_state($name) → hashref
  - save_vm_state($name, $hashref)
  - list_all_vms() → array of names
  - delete_vm_state($name)
  - All backed by JSON files in $state_dir

Step 2.4 – Implement configure_vm() and start_vm()
  - Wrap all API PUTs: boot-source, drives, machine-config, network
  - Handle error cases: socket not ready, bad config

Step 2.5 – Implement launch_fc_process($name, $socket, $log)
  - Build command string with --api-sock and --log-path
  - Fork with system("... &") or open(my $fh, "|-", ...)
  - Capture PID from /proc or pidfile

Step 2.6 – Implement shutdown_vm() and kill_vm()
  - Graceful: SendCtrlAltDel + wait 10s
  - Forced: SIGTERM to PID

Step 2.7 – Unit test all functions
  - Run from command line: perl -e 'require "./firecracker_lib.pl"; ...'
```

---

### Phase 3 — VM List (`index.cgi`) (Day 4)

**Goal:** Dashboard shows all VMs with live status.

```
Step 3.1 – Call list_all_vms(), load each state file
Step 3.2 – For each VM call socket_alive() to determine live status
Step 3.3 – Build HTML table with ui_columns_start() / ui_columns_row()
Step 3.4 – Status badges: green (running), grey (stopped), yellow (unknown)
Step 3.5 – Action buttons: Start/Stop, Delete, Console, Network, Resources
  - Link to vm_action.cgi?vm=NAME&action=start etc.
Step 3.6 – Add "Create MicroVM" button linking to create.cgi
Step 3.7 – Handle empty state: display friendly "No VMs yet" message
```

---

### Phase 4 — Create VM (`create.cgi`) (Days 5–6)

**Goal:** User can create and boot a new microVM from the UI.

```
Step 4.1 – Render create form
  - Scan $kernel_dir for *.bin /*.vmlinux files → <select>
  - Scan $rootfs_dir for *.ext4 /*.img files → <select>
  - Number inputs for vCPUs (1–16) and Memory (64–32768)
  - Checkbox for "Attach Network"
  - Text field for extra boot args

Step 4.2 – On POST: input validation
  - VM name: /^[a-z0-9-]{1,32}$/ 
  - Check name uniqueness against state files
  - Verify kernel and rootfs files exist
  - Validate vcpus and mem_mib ranges

Step 4.3 – Network allocation (if checked)
  - Call allocate_ip() from fc_network_lib.pl
  - Create TAP interface

Step 4.4 – Persist state JSON with status: "creating"
Step 4.5 – Launch Firecracker process (background)
Step 4.6 – Wait up to 2s for socket to appear (poll with usleep)
Step 4.7 – PUT config via configure_vm()
Step 4.8 – POST InstanceStart via start_vm()
Step 4.9 – Update state JSON: status "running", pid
Step 4.10 – Redirect to index.cgi with success flash message
Step 4.11 – Error handling: cleanup TAP and state on any failure
```

---

### Phase 5 — VM Actions (`vm_action.cgi`) (Day 7)

**Goal:** Start, stop, and delete work reliably.

```
Step 5.1 – Dispatch on $action param: start | stop | delete | forceoff
Step 5.2 – Start action
  a) Load state JSON, check status != running
  b) Re-launch FC process if no socket present
  c) Replay configure_vm() + start_vm()
  d) Update state: running

Step 5.3 – Stop action (graceful)
  a) Call shutdown_vm() → SendCtrlAltDel
  b) Poll socket_alive() in loop (max 15 iterations × 1s)
  c) If still alive: SIGTERM to PID
  d) Update state: stopped, clear pid

Step 5.4 – Force Off action
  a) SIGKILL to PID immediately
  b) Update state: stopped

Step 5.5 – Delete action
  a) Stop VM if running
  b) Delete TAP device, release IP
  c) Remove iptables rules
  d) Unlink socket file
  e) Delete state JSON
  f) Optionally prompt to delete log file

Step 5.6 – All actions redirect to index.cgi with status message
```

---

### Phase 6 — Network Management (`network.cgi` + `fc_network_lib.pl`) (Days 8–9)

**Goal:** TAP creation, IP allocation, NAT rules all automated.

```
Step 6.1 – Write fc_network_lib.pl
  Functions:
  - allocate_ip()
      Read ip_allocations.json
      Find first unused IP in configured subnet
      Mark as used, write back JSON
  - release_ip($ip)
      Mark IP as free in ip_allocations.json
  - create_tap($iface_name)
      system("ip tuntap add dev $iface_name mode tap")
      system("ip link set $iface_name up")
  - delete_tap($iface_name)
      system("ip tuntap del dev $iface_name mode tap")
  - add_nat_rule($tap, $guest_ip)
      system("iptables -t nat -A POSTROUTING -s $guest_ip -j MASQUERADE")
      system("iptables -A FORWARD -i $tap -j ACCEPT")
      system("iptables -A FORWARD -o $tap -j ACCEPT")
  - remove_nat_rules($guest_ip)
      system("iptables -t nat -D POSTROUTING -s $guest_ip -j MASQUERADE")
      system("iptables -D FORWARD ... ")
  - ensure_ip_forwarding()
      Write 1 to /proc/sys/net/ipv4/ip_forward

Step 6.2 – Write network.cgi
  - GET: show current TAP and IP for VM, with attach/detach buttons
  - POST attach: call allocate_ip, create_tap, add_nat_rule,
                 PUT /network-interfaces/eth0 to FC API,
                 update state JSON
  - POST detach: release_ip, remove_nat_rules, delete_tap,
                 update state JSON

Step 6.3 – Initialize IP pool on first run
  - If ip_allocations.json missing, generate all IPs in subnet
  - Mark gateway IP as reserved
```

---

### Phase 7 — Console Output (`console.cgi` + `fc_console_lib.pl`) (Day 10)

**Goal:** Live scrolling serial console in the browser.

```
Step 7.1 – Configure Firecracker to write serial to log
  - In launch command: --log-path /var/log/firecracker/<name>.log
  - In boot args: console=ttyS0

Step 7.2 – Write fc_console_lib.pl
  - get_log_tail($vm, $offset, $max_bytes)
      Opens log file, seeks to offset, reads up to max_bytes
      Returns (new_text, new_offset)
  - get_log_size($vm)
      Returns current log file size in bytes

Step 7.3 – Write console.cgi (two modes)
  GET (no vm param): show list of VMs with console links
  GET ?vm=NAME: render terminal UI (HTML + JavaScript)
  GET ?vm=NAME&offset=N&poll=1: return JSON {text, offset} for AJAX

Step 7.4 – JavaScript terminal (inline in console.cgi output)
  - Poll endpoint every 1000ms
  - Append new text to <pre id="console">
  - Auto-scroll to bottom unless user has scrolled up
  - "Clear display" button (client-side only, clears <pre>)
  - "Download full log" link to /var/log/firecracker/<name>.log

Step 7.5 – Security: validate VM name param strictly (/^[a-z0-9-]+$/)
  to prevent path traversal in log file path
```

---

### Phase 8 — Resource Limits (`resources.cgi`) (Day 11)

**Goal:** Edit vCPU/RAM (requires restart) and live network/disk rate limits.

```
Step 8.1 – Render resources form
  - Load current values from state JSON
  - vCPU: number input, note "requires restart"
  - Memory: number input, note "requires restart"
  - Network TX/RX bandwidth (bytes/s): number inputs
  - Network TX/RX burst: number inputs
  - Disk read/write IOPS: number inputs
  - Disk read/write bandwidth: number inputs

Step 8.2 – On POST for compute resources (vcpus, mem)
  - Update state JSON
  - Show message: "Will apply on next start"

Step 8.3 – On POST for network rate limits (VM running)
  - Build rx_rate_limiter / tx_rate_limiter JSON
  - PATCH /network-interfaces/eth0 on socket
  - Update state JSON

Step 8.4 – On POST for disk rate limits (VM running)
  - Build rate_limiter JSON for drive
  - PATCH /drives/rootfs on socket
  - Update state JSON

Step 8.5 – Show "unlimited" option (send empty rate_limiter object)
Step 8.6 – Validate all inputs are positive integers
```

---

### Phase 9 — ACL & Security Hardening (Day 12)

**Goal:** Module respects Webmin access control.

```
Step 9.1 – Write acl/firecracker.acl
  create=1
  delete=1
  start=1
  stop=1
  network=1
  console=1
  resources=1

Step 9.2 – Add access checks at top of each CGI
  &error_block("Permission denied") unless &can_edit_module();
  # or per-action: &error_block(...) unless $access{create};

Step 9.3 – Sanitize all inputs
  - VM names: /^[a-z0-9-]{1,32}$/ only
  - File paths: only files within $kernel_dir and $rootfs_dir
  - Numeric params: verify are positive integers within bounds

Step 9.4 – Principle of least privilege for Firecracker process
  - Run as a dedicated fc-runner user, not root
  - Use Webmin's &run_as_user() or sudo rule
  - /dev/kvm group ownership: adduser fc-runner kvm

Step 9.5 – Socket permissions
  - Set $socket_dir ownership to fc-runner
  - Webmin process accesses via sudo if needed
```

---

### Phase 10 — Testing & Packaging (Days 13–14)

**Goal:** Module is installable, documented, and tested end-to-end.

```
Step 10.1 – Integration tests
  □ Create VM → appears in list with "running" status
  □ Stop VM → status changes to "stopped"
  □ Start VM → status changes to "running"
  □ Delete VM → removed from list, TAP deleted, IP released
  □ Console → serial output appears and updates live
  □ Network attach → ping from host to guest IP works
  □ Rate limits → apply without restarting VM

Step 10.2 – Edge case tests
  □ Create VM with name that already exists → error shown
  □ Start VM with missing kernel file → error shown
  □ Stop already-stopped VM → handled gracefully
  □ Delete running VM → auto-stops first
  □ Console for VM with empty log → shows "No output yet"

Step 10.3 – Package module for distribution
  cd /usr/share/webmin
  tar czf firecracker-1.0.wbm.gz firecracker/
  # .wbm.gz is the standard Webmin module distribution format

Step 10.4 – Write README.md
  - Prerequisites (Firecracker binary, KVM, curl)
  - Install steps
  - First-run setup (kernel/rootfs download links)
  - Configuration options reference
```

---

## 9. Host Prerequisites

### Required Packages

```bash
# Debian / Ubuntu
apt install curl iptables iproute2 kvm cpu-checker

# RHEL / AlmaLinux / Rocky Linux
dnf install curl iptables iproute kvm-tools
```

### Firecracker Binary

```bash
# Download latest release
FCVER=$(curl -s https://api.github.com/repos/firecracker-microvm/firecracker/releases/latest \
  | grep -Po '"tag_name": "\K[^"]+')

wget "https://github.com/firecracker-microvm/firecracker/releases/download/${FCVER}/firecracker-${FCVER}-x86_64.tgz"
tar xf firecracker-*.tgz
mv release-*/firecracker-v* /usr/local/bin/firecracker
chmod +x /usr/local/bin/firecracker
firecracker --version   # verify
```

### Kernel & RootFS Images

```bash
# Download pre-built images from Firecracker CI (for testing)
FCVER=v1.10.1
wget "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/vmlinux-5.10.225" \
     -O /var/lib/firecracker-webmin/kernels/vmlinux-5.10
wget "https://s3.amazonaws.com/spec.ccfc.min/firecracker-ci/v1.10/x86_64/ubuntu-22.04.ext4" \
     -O /var/lib/firecracker-webmin/rootfs/ubuntu-22.04.ext4
```

### Network Setup

```bash
# Enable IP forwarding (persistent)
echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf
sysctl -p

# Allow Webmin/root to manage tap devices without extra permissions
# (or configure sudo rules for the fc-runner user)
```

---

## 10. Security Considerations

| Risk | Mitigation |
|---|---|
| Path traversal in file inputs | Restrict kernel/rootfs selection to configured directories only |
| VM name injection in shell commands | Strict regex validation `/^[a-z0-9-]{1,32}$/` before any `system()` call |
| Unrestricted KVM access | Run Firecracker as a dedicated `fc-runner` user in the `kvm` group |
| Socket access by other users | Set `/var/run/firecracker/` permissions to `700`, owned by `fc-runner` |
| Log file traversal in console.cgi | Validate VM name strictly; construct path from `$log_dir . "/" . $vm . ".log"` |
| Webmin ACL bypass | Check `$access{action}` at the top of every POST handler |
| Denial of service via VM creation | Add max VM count config; check before creating |
| iptables rule accumulation | Track and clean rules explicitly on VM delete |

---

## 11. Testing Strategy

### Manual Smoke Test Checklist

```
[ ] Webmin module loads without Perl errors
[ ] index.cgi renders with empty state
[ ] create.cgi form renders kernel and rootfs dropdowns
[ ] Creating a VM with valid inputs boots a microVM
[ ] list shows VM as "running" after create
[ ] Stop action stops the VM; list shows "stopped"
[ ] Start action restarts the VM; list shows "running"
[ ] Delete action removes VM, TAP, and IP allocation
[ ] Console page shows serial output from guest
[ ] Network page shows correct TAP and IP details
[ ] Resources page shows current config values
[ ] Saving network rate limits applies via API (no restart)
[ ] ACL: restricted user cannot create or delete VMs
[ ] Invalid VM name shows validation error
[ ] Duplicate VM name shows error
```

### Useful Debug Commands

```bash
# Check Firecracker socket is alive
curl -s --unix-socket /var/run/firecracker/vm01.socket http://localhost/ | python3 -m json.tool

# List all TAP interfaces
ip tuntap show

# Check iptables NAT rules
iptables -t nat -L POSTROUTING -n -v

# Check running Firecracker processes
ps aux | grep firecracker

# View VM serial log
tail -f /var/log/firecracker/vm01.log

# Check IP allocations
cat /var/lib/firecracker-webmin/network/ip_allocations.json | python3 -m json.tool
```

---

*Generated for Webmin Firecracker Module v1.0 — Architecture & Implementation Guide*
