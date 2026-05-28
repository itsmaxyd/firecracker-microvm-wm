#!/usr/bin/perl
use strict;
use warnings;
use WebminCore;
require './firecracker_lib.pl';

&ui_print_header(undef, $text{'index_title'}, '');

my @vms = firecracker_lib::list_all_vms();
print &ui_buttons_start();
print &ui_form_start('create.cgi');
print &ui_submit($text{'index_create'});
print &ui_form_end();
print &ui_buttons_end();

if (!@vms) {
  print &ui_message('No microVMs found. Create your first VM to get started.');
  &ui_print_footer();
  exit;
}

my @rows;
foreach my $name (@vms) {
  my $state = firecracker_lib::load_vm_state($name) || {};
  my $alive = firecracker_lib::socket_alive(firecracker_lib::vm_socket_path($name));
  my $status = $alive ? ($text{'status_running'} || 'Running') : ($text{'status_stopped'} || 'Stopped');
  my $actions = qq(
<a href="vm_action.cgi?action=start&vm_name=$name">$text{'action_start'}</a> |
<a href="vm_action.cgi?action=stop&vm_name=$name">$text{'action_stop'}</a> |
<a href="vm_action.cgi?action=delete&vm_name=$name" onclick="return confirm('Delete $name?')">$text{'action_delete'}</a> |
<a href="console.cgi?vm=$name">$text{'action_console'}</a> |
<a href="network.cgi?vm=$name">$text{'action_network'}</a> |
<a href="resources.cgi?vm=$name">$text{'action_resources'}</a>
  );
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
  [ $text{'index_name'}, $text{'index_status'}, $text{'index_vcpus'}, $text{'index_memory'}, $text{'index_ip'}, $text{'index_actions'} ],
  undef,
  \@rows,
  undef,
  1
);

&ui_print_footer();
