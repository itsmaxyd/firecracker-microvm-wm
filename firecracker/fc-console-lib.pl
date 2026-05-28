# Firecracker console log helpers

sub get_log_size {
  my ($vm) = @_;
  my $path = vm_log_path($vm);
  return 0 if !-f $path;
  return -s $path;
}

sub get_log_tail {
  my ($vm, $offset, $max_bytes) = @_;
  $offset ||= 0;
  $max_bytes ||= 16384;
  my $path = vm_log_path($vm);
  return ('', $offset) if !-f $path;

  open(my $fh, '<', $path) || return ('', $offset);
  seek($fh, $offset, 0);
  read($fh, my $buf, $max_bytes);
  my $new_offset = tell($fh);
  close($fh);
  return ($buf || '', $new_offset);
}

1;
