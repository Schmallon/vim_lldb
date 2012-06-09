import unittest
import tempfile
import os


c_source = """int main()
{
  return 0;
}
"""

class TestLLDBPlugin(unittest.TestCase):
  def test(self):
    temp_dir = tempfile.mkdtemp()
    source_file = tempfile.NamedTemporaryFile(dir = temp_dir)

    source_file.write(c_source)
    source_file.flush()

    out_name = os.path.join(temp_dir, "binary")
    os.system("clang -g -x c %s -o %s" % (source_file.name, out_name))
    os.system("""PYTHONPATH=/Applications/Xcode.app/Contents/SharedFrameworks/LLDB.framework/Versions/A/Resources/Python vim -f -c 'call g:LLDBInit()' -c 'python run_target("%s")' -c x""" % out_name)

