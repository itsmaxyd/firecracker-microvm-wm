#!/usr/bin/perl
use strict;
use warnings;
use JSON::PP qw(encode_json);
use WebminCore;
require './firecracker_lib.pl';
require './fc_console_lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';

if ($in{'poll'}) {
  &error('Invalid VM') if !firecracker_lib::vm_name_valid($name);
  my $offset = int($in{'offset'} || 0);
  my ($text, $new_offset) = fc_console_lib::get_log_tail($name, $offset, 32768);
  print "Content-type: application/json\n\n";
  print encode_json({ text => $text, offset => $new_offset });
  exit;
}

&error('Invalid VM') if !firecracker_lib::vm_name_valid($name);
my $size = fc_console_lib::get_log_size($name);

&ui_print_header(undef, "Console - $name", '');
print "<div style='margin:8px 0'><button onclick='clearConsole();return false;'>Clear</button> ";
print "<a href='/download$config{'log_dir'}/$name.log'>Download log</a></div>";
print "<pre id='console' style='height:420px;overflow:auto;background:#111;color:#ddd;padding:12px;'>";
print ($size ? '' : "No output yet.\n");
print "</pre>";

print <<'JS';
<script>
let offset = 0;
const pre = document.getElementById('console');
function clearConsole() { pre.textContent = ''; }
async function poll() {
  const params = new URLSearchParams(window.location.search);
  const vm = params.get('vm');
  const res = await fetch(`console.cgi?vm=${encodeURIComponent(vm)}&poll=1&offset=${offset}`);
  if (!res.ok) return;
  const data = await res.json();
  if (data.text) {
    const autoscroll = (pre.scrollTop + pre.clientHeight + 30) >= pre.scrollHeight;
    pre.textContent += data.text;
    if (autoscroll) pre.scrollTop = pre.scrollHeight;
  }
  offset = data.offset || offset;
}
setInterval(poll, 1000);
poll();
</script>
JS

&ui_print_footer();
