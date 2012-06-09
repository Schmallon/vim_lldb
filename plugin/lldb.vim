let s:plugin_path = escape(expand('<sfile>:p:h'), '\')

function! g:LLDBInit()
  exe 'pyfile ' . s:plugin_path . '/lldb.py'
endfunction
