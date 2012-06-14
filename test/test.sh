rm -f test_log.txt
PYTHONPATH=/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Versions/A/Resources/Python vim -f -c 'call g:LLDBInit()' -c 'python run_lldb_tests()' -c 'qa!'
cat test_log.txt
