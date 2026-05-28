#!/usr/bin/perl
require './firecracker-lib.pl';
require './fc-network-lib.pl';

&ReadParse();

if ($in{'save'}) {
  my $name = lc($in{'name'} || '');
  &error(&text('create_err_name')) if !vm_name_valid($name);
  &error(&text('err_vm_exists')) if load_vm_state($name);

  my $kernel = $in{'kernel'};
  my $rootfs = $in{'rootfs'};
  my $vcpus = int($in{'vcpus'} || 1);
  my $mem = int($in{'mem_mib'} || 256);
  my $boot_args = $in{'boot_args'} || 'console=ttyS0 reboot=k panic=1 pci=off';
  &error(&text('create_err_kernel')) if !$kernel || !-f $kernel;
  &error(&text('create_err_rootfs')) if !$rootfs || !-f $rootfs;
  &error(&text('create_err_vcpus')) if $vcpus < 1 || $vcpus > 16;
  &error(&text('create_err_mem')) if $mem < 64 || $mem > 32768;

  my ($tap, $ip);
  if ($in{'attach_network'}) {
    ensure_ip_forwarding();
    $ip = allocate_ip() || &error(&text('create_err_ip'));
    $tap = next_tap_name() || &error(&text('create_err_tap'));
    create_tap($tap) || &error(&text('create_err_tap_create', $tap));
    add_nat_rule($tap, $ip);
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
    mac => generate_mac($name),
    status => 'creating',
    created_at => iso_timestamp(),
    log_file => vm_log_path($name),
  };
  save_vm_state($name, $state);

  my $pid = launch_fc_process($name) || &error(&text('create_err_launch'));
  my $socket = vm_socket_path($name);
  wait_for_socket($socket, 4000) || &error(&text('create_err_socket'));
  configure_vm($socket, $state) || &error(&text('create_err_config'));
  start_vm($socket) || &error(&text('create_err_start'));

  $state->{'pid'} = $pid;
  $state->{'status'} = 'running';
  save_vm_state($name, $state);
  &redirect('index.cgi');
  exit;
}

my @kernels = list_kernel_options();
my @rootfs = list_rootfs_options();

&ui_print_header(undef, &text('create_title'), '');

if (!@kernels) {
  print &ui_alert_box(&text('create_no_kernels', $config{'kernel_dir'}), 'warn');
}
if (!@rootfs) {
  print &ui_alert_box(&text('create_no_rootfs', $config{'rootfs_dir'}), 'warn');
}

print &ui_form_start('create.cgi');
print &ui_table_start(&text('create_title'), undef, 2);
print &ui_table_row(&text('create_name'), &ui_textbox('name', '', 32));
print &ui_table_row(&text('create_kernel'), &ui_select('kernel', $kernels[0] ? $kernels[0]->[0] : '', \@kernels, 1, 0, 1));
print &ui_table_row(&text('create_rootfs'), &ui_select('rootfs', $rootfs[0] ? $rootfs[0]->[0] : '', \@rootfs, 1, 0, 1));
print &ui_table_row(&text('create_vcpus'), &ui_textbox('vcpus', 1, 6));
print &ui_table_row(&text('create_mem'), &ui_textbox('mem_mib', 256, 6));
print &ui_table_row(&text('create_net'), &ui_yesno_radio('attach_network', 1));
print &ui_table_row(&text('create_bootargs'), &ui_textbox('boot_args', 'console=ttyS0 reboot=k panic=1 pci=off', 60));
print &ui_table_end();
print &ui_hidden('save', 1);
print &ui_form_end([ [ undef, &text('create_submit') ] ]);
&ui_print_footer();
