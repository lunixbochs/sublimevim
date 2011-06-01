import sublime
import sublime_plugin
import string

class WithEdit:
	def __init__(self, view):
		self.view = view

	def __enter__(self):
		self.edit = self.view.begin_edit()
		return self.edit
	
	def __exit__(self, *args, **kwargs):
		self.view.end_edit(self.edit)

class Wrapper(object):
	static = {
		'obj': None
	}

	public = []

	def __init__(self):
		self.static = self.static.copy()

	def __getattribute__(self, key):
		if key in ('public', 'static'):
			return object.__getattribute__(self, key)

		if key in self.static:
			return self.static[key]
		elif key in self.public:
			return object.__getattribute__(self, key)
		else:
			return getattr(self.view, key)

	def __setattr__(self, key, value):
		if key == 'static':
			object.__setattr__(self, key, value)
		elif key in self.static:
			self.static[key] = value
		else:
			setattr(self.view, key, value)

class View(Wrapper): # this is where the logic happens
	static = {
		'mode': 'insert',
		'obj': None,
		'view': None,
		'cmd': '',
	}

	public = [
		'command',
		'delete_char',
		'delete_line',
		'edit',
		'key_escape',
		'key_slash',
		'key_colon',
		'key_char',
		'natural_insert',
		'set_mode'
	]

	def __init__(self, view):
		Wrapper.__init__(self)

		self.obj = self.view = view
		self.set_mode(self.mode)
	
	def edit(self):
		return WithEdit(self)

	def set_mode(self, mode):
		self.mode = mode
		self.obj.set_status('vim', '%s mode' % mode.upper())
	
	def natural_insert(self, string, edit=None):
		view = self.view

		if not edit:
			edit = view.begin_edit()
			self.natural_insert(string, edit)
			view.end_edit(edit)
			return

		sel = view.sel()
		for cur in sel:
			if cur.empty():
				view.insert(edit, cur.a, string)
			else:
				sel.subtract(cur)
				sel.add(sublime.Region(cur.a, cur.a))
				view.replace(edit, cur, string)
	
	def delete_line(self, edit, num=1):
		pass

	def delete_char(self, edit, num=1):
		for cur in self.sel():
			if cur.empty():
				next = sublime.Region(cur.a, cur.a+1)
				if self.line(cur) == self.line(next):
					self.erase(edit, next)
	
	def key_colon(self, edit, string):
		view = self.view
		window = view.window()
		sel = view.sel()
		line = None

		start = string[0]
		remains = string[1:]
		if start in ('+', '-') and remains.isdigit():
			view.run_command('single_selection')
			line = view.rowcol(sel[0].a)[0]
			shift = int(remains)

			if start == '+': line += shift
			else: line -= shift

		if string.isdigit():
			line = int(string)

		if string == 'w':
			view.save()

		if string == 'wq':
			view.run_command('save')
			window.run_command('close')
		
		if string == 'q!':
			if view.is_dirty():
				view.run_command('revert')
			
			window.run_command('close')

		if string == 'q':
			if not view.is_dirty():
				window.run_command('close')
		
		if string == 'x':
			if view.is_dirty():
				view.run_command('save')
			
			window.run_command('close')

		if line:
			point = view.text_point(line, 0)
			
			sel.clear()
			line = view.line(point)

			cur = sublime.Region(line.a, line.a)
			sel.add(cur)

			view.show(sel)
	
	def key_slash(self, edit, string):
		sublime.set_timeout(lambda: self.window().run_command('show_panel', {'panel':'replace'}), 0)
	
	def key_escape(self, edit):
		window = self.window()
		if self.mode != 'command':
			self.set_mode('command')
		else:
			self.run_command('single_selection')
			window.run_command('clear_fields')
			window.run_command('hide_panel')
			window.run_command('hide_overlay')
			window.run_command('hide_auto_complete')
		return True

	def key_char(self, edit, char):
		if self.mode == 'command':
			self.command(edit, char)
		
		elif self.mode == 'insert':
			self.natural_insert(char, edit)
		
		elif self.mode == 'replace':
			self.delete_char(edit)
			self.natural_insert(char, edit)
			self.set_mode('command')
	
	def command(self, edit, char):
		print 'command', char, self.cmd
		mode = self.mode
		view = self.view
		sel = view.sel()

		if char == 'a':
				mode = 'insert'
				for cur in sel:
					sel.subtract(cur)
					if cur.empty():
						next = sublime.Region(cur.b+1, cur.b+1)
					
					if not cur.empty() or not view.line(next).contains(cur):
						next = sublime.Region(cur.b, cur.b)

					sel.add(next)

		elif char == 'i':
			mode = 'insert'

		elif char == 'r':
			mode = 'replace'

		elif char == 'o':
			for cur in sel:
				line = view.full_line(cur.a)
				self.insert(edit, line.b, '\n')

				next = sublime.Region(line.b, line.b)
				sel.subtract(cur)
				sel.add(next)
				mode = 'insert'
		
		elif char == 'u':
			view.run_command('undo')
		
		elif char == 'x':
			for cur in sel:
				if cur.empty():
					if cur.a == view.line(cur).b:
						prev = sublime.Region(cur.a-1, cur.a-1)
						if view.line(prev).contains(cur):
							sel.subtract(cur)
							sel.add(prev)

			self.delete_char(edit)

		elif char in ('c', 'd'):
			if self.cmd:
				if self.cmd == char:
					print 'repeated %s' % char
				else:
					self.cmd = ''
			else:
				self.cmd = char
		elif char in string.digits:
			print 'number!'
		
		self.set_mode(mode)

if not 'views' in globals():
	views = {}
else:
	for vid in list(views):
		static = views[vid].static
		view = views[vid] = View(views[vid].view)
		view.static.update(static)

class Vim(sublime_plugin.EventListener):
	def add(self, view):
		vid = view.id()
		views[vid] = View(view)

	def on_load(self, view):
		self.add(view)
	
	def on_new(self, view):
		self.add(view)
	
	def on_close(self, view):
		vid = view.id()
		if vid in views:
			del views[vid]

class VimBase(sublime_plugin.TextCommand):
	def get_view(self):
		view = self.view
		vid = view.id()
		if not vid in views:
			view = views[vid] = View(view)
		else:
			view = views[vid]
		
		return view
	
	def run(self, edit): pass

class VimHook(VimBase):
	def run(self, edit):
		view = self.get_view()

		if 'hook' in dir(self):
			return self.hook(view, edit)
		else:
			return False

class VimInsertHook(VimHook):
	def run(self, edit):
		if not VimHook.run(self, edit):
			self.get_view().natural_insert(self.char, edit)

class VimEscape(VimHook):
	def hook(self, view, edit):
		view.key_escape(edit)

class VimColon(VimInsertHook):
	char = ':'

	def on_done(self, content):
		content = content.replace(':', '', 1)
		if not content: return

		view = self.get_view()
		with view.edit() as edit:
			view.key_colon(edit, content)

	def on_change(self, content):
		if not content.startswith(':'):
			self.view.window().run_command('hide_panel')
		
	def on_cancel(self):
		print 'cancel'

	def hook(self, view, edit):
		if view.mode == 'command':
			view.window().show_input_panel('Line', ':', self.on_done, self.on_change, self.on_cancel)
			return True

class VimSlash(VimInsertHook):
	char = '/'

	def on_done(self, content):
		content = content.replace('/', '', 1)
		view = self.get_view()
		with view.edit() as edit:
			view.key_slash(content, edit)

	def on_change(self, content):
		if not content.startswith('/'):
			self.view.window().run_command('hide_panel')
		
	def on_cancel(self):
		print 'cancel'

	def hook(self, view, edit):
		if view.mode == 'command':
			view.window().show_input_panel('Search', '/', self.on_done, self.on_change, self.on_cancel)
			return True

class VimLetter(VimInsertHook):
	def hook(self, view, edit):
		mode = view.mode

		self.get_view().key_char(edit, self.char)
		return True

		if mode == 'insert':
			return False

		elif mode == 'replace':
			for cur in view.sel():
				if cur.empty():
					next = sublime.Region(cur.a, cur.a+1)
					if view.line(cur) == view.line(next):
						view.erase(edit, next)
						view.set_mode('command')

		elif mode == 'command':

			char = self.char
			if char == 'a':
				mode = 'insert'
				sel = view.sel()
				for cur in sel:
					sel.subtract(cur)
					if cur.empty():
						sel.add(sublime.Region(cur.b+1, cur.b+1))
					else:
						sel.add(sublime.Region(cur.b, cur.b))

			elif char == 'i':
				mode = 'insert'

			elif char == 'r':
				mode = 'replace'

			elif char == 'o':
				for cur in view.sel():
					if cur.empty():
						pass
					else:
						pass

			elif char == 'u':
				view.run_command('undo')

			view.set_mode(mode)
			
			return True

# automatic letter classes
def add_hook(name, cls, **kwargs):
	globals()[name] = type(name, (cls,), kwargs)

for char in string.letters:
	name = 'Vim' + char.upper()
	if char == char.upper():
		name += '_upper'
	
	add_hook(name, VimLetter, char=char)