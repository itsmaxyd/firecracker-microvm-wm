package firecracker_lib;

use strict;
use warnings;
use JSON::PP qw(encode_json decode_json);
use POSIX qw(strftime WNOHANG);
use Time::HiRes qw(usleep);
use WebminCore;

our (%config, %text, %access);
&init_config();

sub _ensure_dirs {
  for my $dir ($config{'state_dir'}, $config{'socket_dir'}, $config{'log_dir'}, $config{'network_dir'}) {
    next if !$dir;
    mkdir($dir, 0755) if !-d $dir;
  }
}

sub vm_name_valid {
  my ($name) = @_;
  return defined($name) && $name =~ /^[a-z0-9-]{1,32}$/;
}

sub vm_state_path {
  my ($name) = @_;
  return "$config{'state_dir'}/$name.json";
}

sub vm_socket_path {
  my ($name) = @_;
  return "$config{'socket_dir'}/$name.socket";
}

sub vm_log_path {
  my ($name) = @_;
  return "$config{'log_dir'}/$name.log";
}

sub _json_read {
  my ($path) = @_;
  return undef if !-f $path;
  open(my $fh, '<', $path) || return undef;
  local $/ = undef;
  my $raw = <$fh>;
  close($fh);
  return decode_json($raw || '{}');
}

sub _json_write {
  my ($path, $obj) = @_;
  open(my $fh, '>', $path) || &error("Failed to write $path: $!");
  print {$fh} encode_json($obj);
  close($fh);
}

sub load_vm_state {
  my ($name) = @_;
  return undef if !vm_name_valid($name);
  return _json_read(vm_state_path($name));
}

sub save_vm_state {
  my ($name, $state) = @_;
  _ensure_dirs();
  _json_write(vm_state_path($name), $state);
}

sub delete_vm_state {
  my ($name) = @_;
  my $path = vm_state_path($name);
  unlink($path) if -f $path;
}

sub list_all_vms {
  _ensure_dirs();
  opendir(my $dh, $config{'state_dir'}) || return ();
  my @vms = sort map { s/\.json$//r } grep { $_ =~ /\.json$/ } readdir($dh);
  closedir($dh);
  return @vms;
}

sub _run_cmd {
  my ($cmd) = @_;
  my $out = `$cmd 2>&1`;
  my $rc  = $? >> 8;
  return ($rc, $out);
}

sub fc_request {
  my ($method, $socket, $path, $payload) = @_;
  my $cmd = qq(curl -sS --unix-socket "$socket" -X $method );
  if (defined $payload) {
    my $json = encode_json($payload);
    $json =~ s/'/'"'"'/g;
    $cmd .= qq(-H "Content-Type: application/json" -d '$json' );
  }
  $cmd .= qq("http://localhost$path");
  my ($rc, $out) = _run_cmd($cmd);
  return undef if $rc != 0;
  return $out;
}

sub fc_get {
  my ($socket, $path) = @_;
  my $out = fc_request('GET', $socket, $path, undef);
  return undef if !defined $out || $out eq '';
  my $decoded = eval { decode_json($out) };
  return $decoded if !$@;
  return undef;
}

sub fc_put {
  my ($socket, $path, $payload) = @_;
  my $out = fc_request('PUT', $socket, $path, $payload);
  return defined $out;
}

sub fc_patch {
  my ($socket, $path, $payload) = @_;
  my $out = fc_request('PATCH', $socket, $path, $payload);
  return defined $out;
}

sub socket_alive {
  my ($socket) = @_;
  return 0 if !-S $socket;
  my $info = fc_get($socket, '/');
  return defined($info) ? 1 : 0;
}

sub generate_mac {
  my ($name) = @_;
  my $hash = 0;
  foreach my $c (split(//, $name)) {
    $hash = (($hash * 33) + ord($c)) & 0xFFFFFF;
  }
  return sprintf('AA:FC:%02X:%02X:%02X:%02X',
    ($hash >> 16) & 0xFF, ($hash >> 8) & 0xFF, $hash & 0xFF, int(rand(256)));
}

sub configure_vm {
  my ($socket, $cfg) = @_;
  return 0 if !fc_put($socket, '/boot-source', {
    kernel_image_path => $cfg->{'kernel'},
    boot_args => ($cfg->{'boot_args'} || 'console=ttyS0 reboot=k panic=1 pci=off'),
  });
  return 0 if !fc_put($socket, '/drives/rootfs', {
    drive_id => 'rootfs',
    path_on_host => $cfg->{'rootfs'},
    is_root_device => JSON::PP::true,
    is_read_only => JSON::PP::false,
  });
  return 0 if !fc_put($socket, '/machine-config', {
    vcpu_count => int($cfg->{'vcpus'}),
    mem_size_mib => int($cfg->{'mem_mib'}),
  });
  if ($cfg->{'tap_iface'}) {
    return 0 if !fc_put($socket, '/network-interfaces/eth0', {
      iface_id => 'eth0',
      host_dev_name => $cfg->{'tap_iface'},
      guest_mac => ($cfg->{'mac'} || generate_mac($cfg->{'name'})),
    });
  }
  return 1;
}

sub start_vm {
  my ($socket) = @_;
  return fc_put($socket, '/actions', { action_type => 'InstanceStart' });
}

sub shutdown_vm {
  my ($socket) = @_;
  return fc_put($socket, '/actions', { action_type => 'SendCtrlAltDel' });
}

sub launch_fc_process {
  my ($name) = @_;
  my $socket = vm_socket_path($name);
  my $log = vm_log_path($name);
  my $bin = $config{'firecracker_bin'};
  return undef if !$bin || !-x $bin;

  unlink($socket) if -e $socket;
  my $pid = fork();
  return undef if !defined $pid;
  if ($pid == 0) {
    open(STDIN, '<', '/dev/null');
    open(STDOUT, '>>', $log);
    open(STDERR, '>>', $log);
    exec($bin, '--api-sock', $socket, '--log-path', $log);
    exit(1);
  }
  return $pid;
}

sub wait_for_socket {
  my ($socket, $timeout_ms) = @_;
  my $tries = int(($timeout_ms || 2000) / 100);
  for (my $i = 0; $i < $tries; $i++) {
    return 1 if socket_alive($socket);
    usleep(100_000);
  }
  return 0;
}

sub stop_vm_by_state {
  my ($state) = @_;
  my $socket = vm_socket_path($state->{'name'});
  shutdown_vm($socket) if socket_alive($socket);
  for (my $i = 0; $i < 10; $i++) {
    return 1 if !socket_alive($socket);
    usleep(1_000_000);
  }
  if ($state->{'pid'}) {
    kill('TERM', int($state->{'pid'}));
  }
  return !socket_alive($socket);
}

sub iso_timestamp {
  return strftime('%Y-%m-%dT%H:%M:%SZ', gmtime());
}

sub can_do {
  my ($perm) = @_;
  return 1 if !defined $perm;
  return $access{$perm} if defined $access{$perm};
  return 1;
}

1;
