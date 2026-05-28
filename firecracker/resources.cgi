#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
require './firecracker_lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';
&error('Invalid VM name') if !firecracker_lib::vm_name_valid($name);
my $state = firecracker_lib::load_vm_state($name) || &error("VM $name not found");
my $socket = firecracker_lib::vm_socket_path($name);

if ($in{'save'}) {
  my $vcpus = int($in{'vcpus'} || $state->{'vcpus'});
  my $mem = int($in{'mem_mib'} || $state->{'mem_mib'});
  &error('vCPU out of range') if $vcpus < 1 || $vcpus > 16;
  &error('Memory out of range') if $mem < 64 || $mem > 32768;
  $state->{'vcpus'} = $vcpus;
  $state->{'mem_mib'} = $mem;

  my $net_ops = int($in{'net_ops'} || 0);
  my $disk_ops = int($in{'disk_ops'} || 0);
  if (firecracker_lib::socket_alive($socket)) {
    firecracker_lib::fc_patch($socket, '/machine-config', {
      vcpu_count => $vcpus,
      mem_size_mib => $mem,
    });
    if ($state->{'tap_iface'} && $net_ops > 0) {
      firecracker_lib::fc_put($socket, '/network-interfaces/eth0', {
        iface_id => 'eth0',
        host_dev_name => $state->{'tap_iface'},
        guest_mac => ($state->{'mac'} || firecracker_lib::generate_mac($name)),
        rx_rate_limiter => {
          ops => { size => $net_ops, refill_time => 1000 },
        },
        tx_rate_limiter => {
          ops => { size => $net_ops, refill_time => 1000 },
        },
      });
    }
    if ($disk_ops > 0) {
      firecracker_lib::fc_patch($socket, '/drives/rootfs', {
        rate_limiter => {
          ops => { size => $disk_ops, refill_time => 1000 },
        },
      });
    }
  }
  $state->{'net_ops'} = $net_ops;
  $state->{'disk_ops'} = $disk_ops;
  firecracker_lib::save_vm_state($name, $state);
  &redirect("resources.cgi?vm=$name");
  exit;
}

&ui_print_header(undef, "Resources - $name", '');
print &ui_form_start('resources.cgi');
print &ui_hidden('vm', $name);
print &ui_hidden('save', 1);
print &ui_table_start("Resource limits for $name", undef, 2);
print &ui_table_row('vCPU Count', &ui_textbox('vcpus', $state->{'vcpus'} || 1, 6));
print &ui_table_row('Memory (MiB)', &ui_textbox('mem_mib', $state->{'mem_mib'} || 256, 8));
print &ui_table_row('Network IOPS (0=unlimited)', &ui_textbox('net_ops', $state->{'net_ops'} || 0, 10));
print &ui_table_row('Disk IOPS (0=unlimited)', &ui_textbox('disk_ops', $state->{'disk_ops'} || 0, 10));
print &ui_table_end();
print &ui_form_end([ [ undef, 'Save Resources' ] ]);
&ui_print_footer();
