# Firecracker networking helpers
use JSON::PP qw(encode_json decode_json);
our (%config, %text, %access);

sub _alloc_path {
  return "$config{'network_dir'}/ip_allocations.json";
}

sub _run {
  my ($cmd) = @_;
  system($cmd);
  return ($? >> 8) == 0;
}

sub _load_allocs {
  my $path = _alloc_path();
  if (!-f $path) {
    _init_allocs();
  }
  open(my $fh, '<', $path) || return {};
  local $/ = undef;
  my $raw = <$fh>;
  close($fh);
  return decode_json($raw || '{}');
}

sub _save_allocs {
  my ($obj) = @_;
  my $path = _alloc_path();
  mkdir($config{'network_dir'}, 0755) if !-d $config{'network_dir'};
  open(my $fh, '>', $path) || &error("Failed to write $path: $!");
  print {$fh} encode_json($obj);
  close($fh);
}

sub _init_allocs {
  my ($base) = split('/', $config{'network_subnet'});
  my @parts = split(/\./, $base);
  my %allocs = ();
  for my $i (2 .. 254) {
    my $ip = "$parts[0].$parts[1].$parts[2].$i";
    $allocs{$ip} = JSON::PP::false;
  }
  $allocs{$config{'network_gateway'}} = JSON::PP::true;
  _save_allocs(\%allocs);
}

sub allocate_ip {
  my $allocs = _load_allocs();
  foreach my $ip (sort keys %$allocs) {
    next if $allocs->{$ip};
    $allocs->{$ip} = JSON::PP::true;
    _save_allocs($allocs);
    return $ip;
  }
  return undef;
}

sub release_ip {
  my ($ip) = @_;
  my $allocs = _load_allocs();
  return if !exists $allocs->{$ip};
  return if $ip eq $config{'network_gateway'};
  $allocs->{$ip} = JSON::PP::false;
  _save_allocs($allocs);
}

sub next_tap_name {
  my %used;
  foreach my $name (list_all_vms()) {
    my $s = load_vm_state($name);
    $used{$s->{'tap_iface'}} = 1 if $s && $s->{'tap_iface'};
  }
  for my $i (0 .. 4096) {
    my $tap = "$config{'tap_prefix'}$i";
    return $tap if !$used{$tap};
  }
  return undef;
}

sub create_tap {
  my ($tap) = @_;
  return 0 if !$tap;
  return 0 if !_run("ip tuntap add dev $tap mode tap");
  return _run("ip link set $tap up");
}

sub delete_tap {
  my ($tap) = @_;
  return 1 if !$tap;
  _run("ip tuntap del dev $tap mode tap");
  return 1;
}

sub add_nat_rule {
  my ($tap, $ip) = @_;
  _run("iptables -t nat -C POSTROUTING -s $ip -j MASQUERADE || iptables -t nat -A POSTROUTING -s $ip -j MASQUERADE");
  _run("iptables -C FORWARD -i $tap -j ACCEPT || iptables -A FORWARD -i $tap -j ACCEPT");
  _run("iptables -C FORWARD -o $tap -j ACCEPT || iptables -A FORWARD -o $tap -j ACCEPT");
}

sub remove_nat_rules {
  my ($tap, $ip) = @_;
  _run("iptables -t nat -D POSTROUTING -s $ip -j MASQUERADE 2>/dev/null");
  _run("iptables -D FORWARD -i $tap -j ACCEPT 2>/dev/null") if $tap;
  _run("iptables -D FORWARD -o $tap -j ACCEPT 2>/dev/null") if $tap;
}

sub ensure_ip_forwarding {
  _run("sysctl -w net.ipv4.ip_forward=1 >/dev/null");
}

1;
