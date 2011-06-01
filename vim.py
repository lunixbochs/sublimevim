import sublime
import sublime_plugin
import string

class View(object):
	static = {
		'mode': 'insert',
		'view': None
	}

	def __init__(self, view):
		self.static = self.static.copy()
		self.view = view
		self.set_mode(self.mode)

	def __getattribute__(self, key):
		if not key == 'static' and key in self.static:
			return self.static[key]
		elif key in ('static', 'set_mode', 'natural_insert'):
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

	def set_mode(self, mode):
		self.mode = mode
		self.view.set_status('vim', '%s mode' % mode.upper())
	
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

if not 'views' in globals():
	views = {}
else:
	for vid in list(views):
		static = views[vid].static
		view = views[vid] = View(views[vid].view)
		view.static = static

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
		if view.mode != 'command':
			view.set_mode('command')
		else:
			view.run_command('single_selection')
			view.window().run_command('clear_fields')
			view.window().run_command('hide_panel')
			view.window().run_command('hide_overlay')
			view.window().run_command('hide_auto_complete')
		return True

class VimColon(VimInsertHook):
	char = ':'

	def on_done(self, content):
		content = content.replace(':', '', 1)
		if not content: return

		view = self.view
		sel = view.sel()
		line = None

		start = content[0]
		remains = content[1:]
		if start in ('+', '-') and remains.isdigit():
			view.run_command('single_selection')
			line = view.rowcol(sel[0].a)[0]
			shift = int(remains)

			if start == '+': line += shift
			else: line -= shift

		if content.isdigit():
			line = int(content)

		if line:
			point = view.text_point(line, 0)
			
			sel.clear()
			line = view.line(point)

			cur = sublime.Region(line.a, line.a)
			sel.add(cur)

			view.show(sel)

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

		window = self.view.window()
		sublime.set_timeout(lambda: window.run_command('show_panel', {'panel':'replace'}), 0)

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