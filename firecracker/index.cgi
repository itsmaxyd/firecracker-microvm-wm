#!/usr/bin/perl
require './firecracker-lib.pl';

&ui_print_header(undef, &text('index_title'), '');

print &ui_links_row([ &ui_link('create.cgi', &text('index_create')) ]);

my @vms = list_all_vms();
my @rows;
foreach my $name (@vms) {
  my $state = load_vm_state($name) || {};
  my $alive = socket_alive(vm_socket_path($name));
  my $status = $alive ? &text('status_running') : &text('status_stopped');
  my $actions =
    '<a href="vm_action.cgi?action=start&vm_name='.$name.'">'.&text('action_start').'</a> | '.
    '<a href="vm_action.cgi?action=stop&vm_name='.$name.'">'.&text('action_stop').'</a> | '.
    '<a href="vm_action.cgi?action=delete&vm_name='.$name.'" onclick="return confirm(\'Delete '.$name.'?\')">'.&text('action_delete').'</a> | '.
    '<a href="console.cgi?vm='.$name.'">'.&text('action_console').'</a> | '.
    '<a href="network.cgi?vm='.$name.'">'.&text('action_network').'</a> | '.
    '<a href="resources.cgi?vm='.$name.'">'.&text('action_resources').'</a>';
  push @rows, [
    $name,
    $status,
    ($state->{'vcpus'} // '-'),
    ($state->{'mem_mib'} // '-'),
    ($state->{'ip'} // '-'),
    $actions,
  ];
}

print &ui_columns_table(
  [ &text('index_name'), &text('index_status'), &text('index_vcpus'), &text('index_memory'), &text('index_ip'), &text('index_actions') ],
  undef,
  \@rows,
  undef,
  1,
  undef,
  &text('index_empty'),
);

&ui_print_footer();
