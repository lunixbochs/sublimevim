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

class InsertView(Wrapper):
	static = {
		'mode': 'insert',
		'obj': None,
		'view': None,
	}

	public = [
		'escape',
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
		self.set_mode()
	
	def natural_insert(self, string, edit=None):
		view = self.view

		lines = string.split('\n')

		if not edit:
			edit = view.begin_edit()
			self.natural_insert(string, edit)
			view.end_edit(edit)
			return

		sel = view.sel()
		if len(lines) == len(sel):
			inserts = lines
		else:
			inserts = [string]*len(sel)

		for cur in sel:
			ins = inserts.pop(0)
			if cur.empty():
				view.insert(edit, cur.a, ins)
			else:
				sel.subtract(cur)
				sel.add(sublime.Region(cur.a, cur.a))
				view.replace(edit, cur, ins)
	
	def escape(self):
		window = self.window()
		if len(self.sel()) > 1:
			self.run_command('single_selection')
		else:
			window.run_command('clear_fields')
			window.run_command('hide_panel')
			window.run_command('hide_overlay')
			window.run_command('hide_auto_complete')

	def key_escape(self, edit): self.escape()
	def key_slash(self, edit): self.key_char(edit, '/')
	def key_colon(self, edit): self.key_char(edit, ':')
	def key_char(self, edit, char): self.natural_insert(char, edit)
	def set_mode(self, mode=None): return

class View(InsertView): # this is where the logic happens
	static = {
		'mode': 'command',
		'obj': None,
		'view': None,
		'cmd': '',
		'yank': [],
		'marks': {}
	}

	public = [
		'command',
		'delete_char',
		'delete_line',
		'edit',
		'escape',
		'save',
		'find_replace',
		'key_escape',
		'key_slash',
		'key_colon',
		'key_char',
		'natural_insert',
		'set_mode'
	]

	def set_mode(self, mode=None):
		if mode and mode != self.mode:
			self.cmd = ''
			self.mode = mode
		
		self.obj.set_status('vim', '%s mode' % self.mode.upper())
	
	def edit(self):
		return WithEdit(self)
	
	def find_replace(self, edit, string):
		view.run_command('single_selection')
		sel = self.sel()
		print sel[0].b
		found = self.find(string, sel[0].b)
		if found:
			sel.subtract(sel[0])
			sel.add(found)
	
	def save(self):
		self.run_command('save')
	
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
		
		elif string == '$':
			line = view.visible_region().b

		elif string.isdigit():
			line = int(string)

		elif string == 'w':
			view.save()

		elif string == 'wq':
			view.run_command('save')
			window.run_command('close')
		
		elif string == 'q!':
			if view.is_dirty():
				view.run_command('revert')
			
			window.run_command('close')

		elif string == 'q':
			if not view.is_dirty():
				window.run_command('close')
		
		elif string == 'x':
			if view.is_dirty():
				view.run_command('save')
			
			window.run_command('close')
		
		elif string == 'n':
			window.run_command('next_view')
		
		elif string == 'N':
			window.run_command('prev_view')

		if line != None:
			point = view.text_point(line, 0)
			
			sel.clear()
			line = view.line(point)

			cur = sublime.Region(line.a, line.a)
			sel.add(cur)

			view.show(sel)
	
	def key_slash(self, edit, string):
		self.find_replace(edit, string)
	
	def key_escape(self, edit):
		if self.mode != 'command' and len(self.sel()) == 1:
			self.set_mode('command')
		else:
			self.escape()
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

		elif char in ('O', 'o'):
			for cur in sel:
				line = view.line(cur.a)
				if char == 'o':
					p = view.line(line.b+1).a
				else:
					p = line.a
					line = view.line(p-1)

				next = sublime.Region(p, p)

				if view.visible_region().contains(next):
					sel.subtract(cur)
					self.insert(edit, line.b, '\n')
					sel.add(next)
				else:
					self.insert(edit, line.b, '\n')
					sel.add(next)
				mode = 'insert'

			view.run_command('reindent')
		
		elif char == 'v':
			mode = 'visual'

		elif char == 'V':
			mode = 'visual line'
			
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

		elif char == 'p':
			if self.yank:
				for cur in sel:
					sel.subtract(cur)
					p = view.full_line(cur.b).b
					sel.add(sublime.Region(p, p))
				self.natural_insert('\n'.join(self.yank))

				for cur in sel:
					sel.subtract(cur)
					p = view.line(view.line(cur.b).a-1).a
					sel.add(sublime.Region(p, p))
		
		elif char == 'P':
			if self.yank:
				old = [cur for cur in sel]
				self.natural_insert('\n'.join(self.yank))

				sel.clear()
				for cur in old:
					sel.add(cur)

		elif char == 'b':
			view.run_command('move', {'by': 'subwords', 'forward': False})

		elif char == 'e':
			view.run_command('move', {'by': 'subword_ends', 'forward':True})

		elif char == 'h': view.run_command('move', {"by": "characters", "forward": False})
		elif char == 'j': view.run_command('move', {"by": "lines", "forward": True})
		elif char == 'k': view.run_command('move', {"by": "lines", "forward": False})
		elif char == 'l': view.run_command('move', {"by": "characters", "forward": True})

		elif char in ('c', 'd', 'y'):
			if self.cmd:
				if self.cmd == char:
					if char == 'd':
						self.yank = []
						for cur in sel:
							self.yank.append(view.substr(view.full_line(cur.b)))

						points = set()
						for cur in sel:
							points.add(cur.b)
						
						for point in points:
							line = view.full_line(point)
							view.replace(edit, line, '')

					elif char == 'y':
						self.yank = []
						for cur in sel:
							self.yank.append(view.substr(view.full_line(cur.b)))

					self.cmd = ''
				else:
					self.cmd = ''
			else:
				self.cmd = char
		elif char == '$':
			for cur in sel:
				sel.subtract(cur)
				p = view.line(cur.b).b
				sel.add(sublime.Region(p, p))
		elif char == '0':
			for cur in sel:
				sel.subtract(cur)
				p = view.line(cur.b).a
				sel.add(sublime.Region(p, p))
		elif char in string.digits:
			print 'number handling later!'
		
		self.set_mode(mode)

if not 'views' in globals():
	views = {}
else:
	for vid in list(views):
		static = views[vid].static
		view = views[vid] = View(views[vid].view)
		view.static.update(static)
		view.set_mode()

class VimBase(sublime_plugin.TextCommand):
	def get_view(self):
		view = self.view
		vid = view.id()
		if not vid in views:
			view = views[vid] = InsertView(view)
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

class VimChar(VimInsertHook):
	def hook(self, view, edit):
		self.get_view().key_char(edit, self.char)
		return True

# tracks open views
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

# automatic letter classes
def add_hook(name, cls, **kwargs):
	globals()[name] = type(name, (cls,), kwargs)

for char in string.letters:
	name = 'Vim' + char.upper()
	if char == char.upper():
		name += '_upper'
	
	add_hook(name, VimChar, char=char)

for num in string.digits:
	name = 'Vim_' + num
	add_hook(name, VimChar, char=num)

add_hook('Vim_dollar', VimChar, char='$')