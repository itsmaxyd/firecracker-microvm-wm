#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
require './firecracker_lib.pl';
require './fc_network_lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';
&error('Invalid VM name') if !firecracker_lib::vm_name_valid($name);
my $state = firecracker_lib::load_vm_state($name) || &error("VM $name not found");
my $socket = firecracker_lib::vm_socket_path($name);

if ($in{'do'} && $in{'do'} eq 'attach') {
  &error('VM already has a network interface') if $state->{'tap_iface'};
  fc_network_lib::ensure_ip_forwarding();
  my $ip = fc_network_lib::allocate_ip() || &error('No free IP available');
  my $tap = fc_network_lib::next_tap_name() || &error('No free TAP name');
  fc_network_lib::create_tap($tap) || &error('Failed to create TAP');
  fc_network_lib::add_nat_rule($tap, $ip);
  if (firecracker_lib::socket_alive($socket)) {
    firecracker_lib::fc_put($socket, '/network-interfaces/eth0', {
      iface_id => 'eth0',
      host_dev_name => $tap,
      guest_mac => ($state->{'mac'} || firecracker_lib::generate_mac($name)),
    }) || &error('Failed to attach network to running VM');
  }
  $state->{'tap_iface'} = $tap;
  $state->{'ip'} = $ip;
  firecracker_lib::save_vm_state($name, $state);
  &redirect("network.cgi?vm=$name");
  exit;
}

if ($in{'do'} && $in{'do'} eq 'detach') {
  if ($state->{'ip'}) {
    fc_network_lib::remove_nat_rules($state->{'tap_iface'}, $state->{'ip'});
    fc_network_lib::delete_tap($state->{'tap_iface'}) if $state->{'tap_iface'};
    fc_network_lib::release_ip($state->{'ip'});
  }
  $state->{'tap_iface'} = undef;
  $state->{'ip'} = undef;
  firecracker_lib::save_vm_state($name, $state);
  &redirect("network.cgi?vm=$name");
  exit;
}

&ui_print_header(undef, "Network - $name", '');
print &ui_table_start("Network settings for $name", undef, 2);
print &ui_table_row('TAP Interface', $state->{'tap_iface'} || '-');
print &ui_table_row('Guest IP', $state->{'ip'} || '-');
print &ui_table_end();

print &ui_form_start('network.cgi');
print &ui_hidden('vm', $name);
if ($state->{'tap_iface'}) {
  print &ui_hidden('do', 'detach');
  print &ui_submit('Detach Interface');
}
else {
  print &ui_hidden('do', 'attach');
  print &ui_submit('Attach Interface');
}
print &ui_form_end();
&ui_print_footer();
