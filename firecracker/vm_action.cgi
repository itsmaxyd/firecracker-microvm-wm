#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
require './firecracker_lib.pl';
require './fc_network_lib.pl';

&ReadParse();
my $name = $in{'vm_name'} || $in{'vm'} || '';
my $action = $in{'action'} || '';
&error('Invalid VM name') if !firecracker_lib::vm_name_valid($name);
my $state = firecracker_lib::load_vm_state($name) || &error("VM $name not found");
my $socket = firecracker_lib::vm_socket_path($name);

if ($action eq 'start') {
  if (!firecracker_lib::socket_alive($socket)) {
    my $pid = firecracker_lib::launch_fc_process($name) || &error('Failed to launch Firecracker');
    firecracker_lib::wait_for_socket($socket, 4000) || &error('Socket not ready');
    firecracker_lib::configure_vm($socket, $state) || &error('Failed to configure VM');
    firecracker_lib::start_vm($socket) || &error('Failed to start VM');
    $state->{'pid'} = $pid;
  }
  $state->{'status'} = 'running';
  firecracker_lib::save_vm_state($name, $state);
}
elsif ($action eq 'stop') {
  firecracker_lib::stop_vm_by_state($state);
  $state->{'status'} = 'stopped';
  $state->{'pid'} = undef;
  firecracker_lib::save_vm_state($name, $state);
}
elsif ($action eq 'delete') {
  firecracker_lib::stop_vm_by_state($state) if firecracker_lib::socket_alive($socket);
  fc_network_lib::remove_nat_rules($state->{'tap_iface'}, $state->{'ip'}) if $state->{'ip'};
  fc_network_lib::delete_tap($state->{'tap_iface'}) if $state->{'tap_iface'};
  fc_network_lib::release_ip($state->{'ip'}) if $state->{'ip'};
  unlink($socket) if -S $socket;
  unlink($state->{'log_file'}) if $state->{'log_file'} && -f $state->{'log_file'};
  firecracker_lib::delete_vm_state($name);
}
else {
  &error('Unsupported action');
}

&redirect('index.cgi');
