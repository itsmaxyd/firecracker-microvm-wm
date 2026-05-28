#!/usr/bin/perl
require './firecracker-lib.pl';
require './fc-network-lib.pl';

&ReadParse();
my $name = $in{'vm_name'} || $in{'vm'} || '';
my $action = $in{'action'} || '';
&error(&text('create_err_name')) if !vm_name_valid($name);
my $state = load_vm_state($name) || &error(&text('vm_not_found', $name));
my $socket = vm_socket_path($name);

if ($action eq 'start') {
  if (!socket_alive($socket)) {
    my $pid = launch_fc_process($name) || &error(&text('create_err_launch'));
    wait_for_socket($socket, 4000) || &error(&text('create_err_socket'));
    configure_vm($socket, $state) || &error(&text('create_err_config'));
    start_vm($socket) || &error(&text('create_err_start'));
    $state->{'pid'} = $pid;
  }
  $state->{'status'} = 'running';
  save_vm_state($name, $state);
}
elsif ($action eq 'stop') {
  stop_vm_by_state($state);
  $state->{'status'} = 'stopped';
  $state->{'pid'} = undef;
  save_vm_state($name, $state);
}
elsif ($action eq 'delete') {
  stop_vm_by_state($state) if socket_alive($socket);
  remove_nat_rules($state->{'tap_iface'}, $state->{'ip'}) if $state->{'ip'};
  delete_tap($state->{'tap_iface'}) if $state->{'tap_iface'};
  release_ip($state->{'ip'}) if $state->{'ip'};
  unlink($socket) if -S $socket;
  unlink($state->{'log_file'}) if $state->{'log_file'} && -f $state->{'log_file'};
  delete_vm_state($name);
}
else {
  &error(&text('action_unsupported'));
}

&redirect('index.cgi');
