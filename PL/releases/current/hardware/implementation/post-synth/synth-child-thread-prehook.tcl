set_param general.maxThreads 16
set_param synth.maxThreads 8
if {[get_param general.maxThreads] != 16} {error {child general.maxThreads readback mismatch}}
if {[get_param synth.maxThreads] != 8} {error {child synth.maxThreads readback mismatch}}
set child_thread_evidence E:/AIProject/FPGAVibecoding/artifacts/board-debug-20261008/acceleration/jtag/cnn-v10.5-a0005-fastbufgdiv-platform-synth-001/synth-child-thread-readback.txt
set child_thread_parameter_report E:/AIProject/FPGAVibecoding/artifacts/board-debug-20261008/acceleration/jtag/cnn-v10.5-a0005-fastbufgdiv-platform-synth-001/synth-child-thread-parameters.rpt
set child_thread_fh [open $child_thread_evidence w]
puts $child_thread_fh "scope=synth_design_child_pre_hook"
puts $child_thread_fh "child_process_id=[pid]"
puts $child_thread_fh "general_threads_readback=[get_param general.maxThreads]"
puts $child_thread_fh "synth_threads_readback=[get_param synth.maxThreads]"
puts $child_thread_fh "effective_algorithm_threads_proven=false"
close $child_thread_fh
report_param -file $child_thread_parameter_report {general.maxThreads}
report_param -append -file $child_thread_parameter_report {synth.maxThreads}
puts "CNN_V10_PLATFORM_SYNTH_CHILD_THREADS general=[get_param general.maxThreads] synth=[get_param synth.maxThreads] pid=[pid]"
