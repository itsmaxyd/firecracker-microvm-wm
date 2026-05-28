#!/usr/bin/perl
use JSON::PP qw(encode_json);
require './firecracker-lib.pl';
require './fc-console-lib.pl';

&ReadParse();
my $name = $in{'vm'} || '';

if ($in{'poll'}) {
  &error(&text('create_err_name')) if !vm_name_valid($name);
  my $offset = int($in{'offset'} || 0);
  my ($log_chunk, $new_offset) = get_log_tail($name, $offset, 32768);
  print "Content-type: application/json\n\n";
  print encode_json({ text => $log_chunk, offset => $new_offset });
  exit;
}

&error(&text('create_err_name')) if !vm_name_valid($name);
my $size = get_log_size($name);
my $log_path = vm_log_path($name);

&ui_print_header(undef, &text('console_title', $name), '');
print "<div style='margin:8px 0'><button onclick='clearConsole();return false;'>".&text('console_clear')."</button> ";
print "<a href='".&get_webprefix()."/download/".&urlize($log_path)."'>".&text('console_download')."</a></div>";
print "<pre id='console' style='height:420px;overflow:auto;background:#111;color:#ddd;padding:12px;'>";
print ($size ? '' : &text('console_empty')."\n");
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
