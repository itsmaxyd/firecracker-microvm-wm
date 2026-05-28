#!/usr/bin/perl
require './firecracker-lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';
&error(&text('create_err_name')) if !vm_name_valid($name);
my $state = load_vm_state($name) || &error(&text('vm_not_found', $name));
my $socket = vm_socket_path($name);

if ($in{'save'}) {
  my $vcpus = int($in{'vcpus'} || $state->{'vcpus'});
  my $mem = int($in{'mem_mib'} || $state->{'mem_mib'});
  &error(&text('create_err_vcpus')) if $vcpus < 1 || $vcpus > 16;
  &error(&text('create_err_mem')) if $mem < 64 || $mem > 32768;
  $state->{'vcpus'} = $vcpus;
  $state->{'mem_mib'} = $mem;

  my $net_ops = int($in{'net_ops'} || 0);
  my $disk_ops = int($in{'disk_ops'} || 0);
  if (socket_alive($socket)) {
    fc_patch($socket, '/machine-config', {
      vcpu_count => $vcpus,
      mem_size_mib => $mem,
    });
    if ($state->{'tap_iface'} && $net_ops > 0) {
      fc_put($socket, '/network-interfaces/eth0', {
        iface_id => 'eth0',
        host_dev_name => $state->{'tap_iface'},
        guest_mac => ($state->{'mac'} || generate_mac($name)),
        rx_rate_limiter => {
          ops => { size => $net_ops, refill_time => 1000 },
        },
        tx_rate_limiter => {
          ops => { size => $net_ops, refill_time => 1000 },
        },
      });
    }
    if ($disk_ops > 0) {
      fc_patch($socket, '/drives/rootfs', {
        rate_limiter => {
          ops => { size => $disk_ops, refill_time => 1000 },
        },
      });
    }
  }
  $state->{'net_ops'} = $net_ops;
  $state->{'disk_ops'} = $disk_ops;
  save_vm_state($name, $state);
  &redirect("resources.cgi?vm=$name");
  exit;
}

&ui_print_header(undef, &text('resources_title', $name), '');
print &ui_form_start('resources.cgi');
print &ui_hidden('vm', $name);
print &ui_hidden('save', 1);
print &ui_table_start(&text('resources_title', $name), undef, 2);
print &ui_table_row(&text('create_vcpus'), &ui_textbox('vcpus', $state->{'vcpus'} || 1, 6));
print &ui_table_row(&text('create_mem'), &ui_textbox('mem_mib', $state->{'mem_mib'} || 256, 8));
print &ui_table_row(&text('resources_net_ops'), &ui_textbox('net_ops', $state->{'net_ops'} || 0, 10));
print &ui_table_row(&text('resources_disk_ops'), &ui_textbox('disk_ops', $state->{'disk_ops'} || 0, 10));
print &ui_table_end();
print &ui_form_end([ [ undef, &text('resources_save') ] ]);
&ui_print_footer();
