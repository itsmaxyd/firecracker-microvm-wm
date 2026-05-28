#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
require './firecracker_lib.pl';
require './fc_network_lib.pl';

&ReadParse();

if ($in{'save'}) {
  my $name = lc($in{'name'} || '');
  &error('Invalid VM name') if !firecracker_lib::vm_name_valid($name);
  &error($text{'err_vm_exists'} || 'VM already exists') if firecracker_lib::load_vm_state($name);

  my $kernel = $in{'kernel'};
  my $rootfs = $in{'rootfs'};
  my $vcpus = int($in{'vcpus'} || 1);
  my $mem = int($in{'mem_mib'} || 256);
  my $boot_args = $in{'boot_args'} || 'console=ttyS0 reboot=k panic=1 pci=off';
  &error('Kernel file not found') if !$kernel || !-f $kernel;
  &error('Rootfs file not found') if !$rootfs || !-f $rootfs;
  &error('vCPU count out of range') if $vcpus < 1 || $vcpus > 16;
  &error('Memory out of range') if $mem < 64 || $mem > 32768;

  my ($tap, $ip);
  if ($in{'attach_network'}) {
    fc_network_lib::ensure_ip_forwarding();
    $ip = fc_network_lib::allocate_ip() || &error('No free IP available');
    $tap = fc_network_lib::next_tap_name() || &error('No free TAP interface name');
    fc_network_lib::create_tap($tap) || &error("Failed to create TAP $tap");
    fc_network_lib::add_nat_rule($tap, $ip);
  }

  my $state = {
    name => $name,
    kernel => $kernel,
    rootfs => $rootfs,
    vcpus => $vcpus,
    mem_mib => $mem,
    boot_args => $boot_args,
    tap_iface => $tap,
    ip => $ip,
    mac => firecracker_lib::generate_mac($name),
    status => 'creating',
    created_at => firecracker_lib::iso_timestamp(),
    log_file => firecracker_lib::vm_log_path($name),
  };
  firecracker_lib::save_vm_state($name, $state);

  my $pid = firecracker_lib::launch_fc_process($name) || &error('Failed to launch Firecracker process');
  my $socket = firecracker_lib::vm_socket_path($name);
  firecracker_lib::wait_for_socket($socket, 4000) || &error('Firecracker socket did not become ready');
  firecracker_lib::configure_vm($socket, $state) || &error('Failed configuring VM over Firecracker API');
  firecracker_lib::start_vm($socket) || &error('Failed to start VM');

  $state->{'pid'} = $pid;
  $state->{'status'} = 'running';
  firecracker_lib::save_vm_state($name, $state);
  &redirect('index.cgi');
  exit;
}

sub _files_from {
  my ($dir, $re) = @_;
  opendir(my $dh, $dir) || return ();
  my @files = sort grep { /$re/ && -f "$dir/$_" } readdir($dh);
  closedir($dh);
  return map { "$dir/$_" } @files;
}

my @kernels = _files_from($config{'kernel_dir'}, qr/\.(bin|vmlinux|img)$/);
my @rootfs  = _files_from($config{'rootfs_dir'}, qr/\.(ext4|img)$/);

&ui_print_header(undef, $text{'create_title'}, '');
print &ui_form_start('create.cgi');
print &ui_table_start($text{'create_title'}, undef, 2);
print &ui_table_row($text{'create_name'}, &ui_textbox('name', '', 32));
print &ui_table_row($text{'create_kernel'}, &ui_select('kernel', $kernels[0] || '', \@kernels));
print &ui_table_row($text{'create_rootfs'}, &ui_select('rootfs', $rootfs[0] || '', \@rootfs));
print &ui_table_row($text{'create_vcpus'}, &ui_textbox('vcpus', 1, 6));
print &ui_table_row($text{'create_mem'}, &ui_textbox('mem_mib', 256, 6));
print &ui_table_row($text{'create_net'}, &ui_yesno_radio('attach_network', 1));
print &ui_table_row('Boot Args', &ui_textbox('boot_args', 'console=ttyS0 reboot=k panic=1 pci=off', 60));
print &ui_table_end();
print &ui_hidden('save', 1);
print &ui_form_end([ [ undef, $text{'create_submit'} || 'Create' ] ]);
&ui_print_footer();
