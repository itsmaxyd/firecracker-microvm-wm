#!/usr/bin/perl
require './firecracker-lib.pl';
require './fc-network-lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';
&error(&text('create_err_name')) if !vm_name_valid($name);
my $state = load_vm_state($name) || &error(&text('vm_not_found', $name));
my $socket = vm_socket_path($name);

if ($in{'do'} && $in{'do'} eq 'attach') {
  &error(&text('network_already')) if $state->{'tap_iface'};
  ensure_ip_forwarding();
  my $ip = allocate_ip() || &error(&text('create_err_ip'));
  my $tap = next_tap_name() || &error(&text('create_err_tap'));
  create_tap($tap) || &error(&text('create_err_tap_create', $tap));
  add_nat_rule($tap, $ip);
  if (socket_alive($socket)) {
    fc_put($socket, '/network-interfaces/eth0', {
      iface_id => 'eth0',
      host_dev_name => $tap,
      guest_mac => ($state->{'mac'} || generate_mac($name)),
    }) || &error(&text('network_attach_failed'));
  }
  $state->{'tap_iface'} = $tap;
  $state->{'ip'} = $ip;
  save_vm_state($name, $state);
  &redirect("network.cgi?vm=$name");
  exit;
}

if ($in{'do'} && $in{'do'} eq 'detach') {
  if ($state->{'ip'}) {
    remove_nat_rules($state->{'tap_iface'}, $state->{'ip'});
    delete_tap($state->{'tap_iface'}) if $state->{'tap_iface'};
    release_ip($state->{'ip'});
  }
  $state->{'tap_iface'} = undef;
  $state->{'ip'} = undef;
  save_vm_state($name, $state);
  &redirect("network.cgi?vm=$name");
  exit;
}

&ui_print_header(undef, &text('network_title', $name), '');
print &ui_table_start(&text('network_title', $name), undef, 2);
print &ui_table_row(&text('network_tap'), $state->{'tap_iface'} || '-');
print &ui_table_row(&text('network_ip'), $state->{'ip'} || '-');
print &ui_table_end();

print &ui_form_start('network.cgi');
print &ui_hidden('vm', $name);
if ($state->{'tap_iface'}) {
  print &ui_hidden('do', 'detach');
  print &ui_submit(&text('network_detach'));
}
else {
  print &ui_hidden('do', 'attach');
  print &ui_submit(&text('network_attach'));
}
print &ui_form_end();
&ui_print_footer();
