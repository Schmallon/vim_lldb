import lldb
import os
import time
import tempfile
import unittest

def run_target(target_filename):
  debugger = lldb.SBDebugger.Create()
  debugger.SetAsync(False)
  target = debugger.CreateTarget(target_filename)
  if not target:
    raise "Failed to get a target"

  process = target.LaunchSimple (None, None, os.getcwd())

class TestLLDBPlugin(unittest.TestCase):
  def test(self):
    c_source = """int main()
    {
      return 0;
    }
    """

    temp_dir = tempfile.mkdtemp()
    source_file = tempfile.NamedTemporaryFile(dir = temp_dir)

    source_file.write(c_source)
    source_file.flush()

    out_name = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (source_file.name, out_name))

    run_target(out_name)

def run_lldb_tests():
  suite = unittest.TestLoader().loadTestsFromTestCase(TestLLDBPlugin)
  with open("test_log.txt", "a") as f:
    unittest.TextTestRunner(stream=f, verbosity=2).run(suite)
