#  framework/interface.py
#
#  Copyright 2011 Spencer J. McIntyre <SMcIntyre [at] SecureState [dot] net>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.

import cmd
import code
import logging
import os
import platform
from random import randint
import subprocess
import socket
import sys
import traceback

from framework import its
from framework.core import Framework
from framework.errors import FrameworkRuntimeError
from framework.templates import TermineterModuleOptical

__version__ = '0.1.0'

class OverrideCmd(cmd.Cmd, object):
	__doc__ = 'OverrideCmd class is meant to override methods from cmd.Cmd so they can\nbe imported into the base interpreter class.'
	def __init__(self, *args, **kwargs):
		cmd.Cmd.__init__(self, *args, **kwargs)

		self.__hidden_commands__ = ['EOF']
		self.__disabled_commands__ = []
		self.__package__ = '.'.join(self.__module__.split('.')[:-1])

	def cmdloop(self):
		while True:
			try:
				super(OverrideCmd, self).cmdloop()
				return
			except KeyboardInterrupt:
				self.print_line('')
				self.print_error('Please use the \'exit\' command to quit')
				continue

	def get_names(self):
		commands = super(OverrideCmd, self).get_names()
		for name in self.__hidden_commands__:
			if 'do_' + name in commands:
				commands.remove('do_' + name)
		for name in self.__disabled_commands__:
			if 'do_' + name in commands:
				commands.remove('do_' + name)
		return commands

	def emptyline(self): 					# Don't do anything on a blank line being passed
		pass								# stupid repeats are annoying

	def help_help(self): 					# Get help out of the undocumented section, stupid python
		self.do_help('')

	def precmd(self, line):					# use this to allow using '?' after the command for help
		tmp_line = line.split()
		if len(tmp_line) == 0:
			return line
		if tmp_line[0] in self.__disabled_commands__:
			self.default(tmp_line[0])
			return ''
		if len(tmp_line) == 1:
			return line
		if tmp_line[1] == '?':
			self.do_help(tmp_line[0])
			return ''
		return line

	def do_exit(self, args):
		return True

	def do_EOF(self, args):
		"""Exit The Interpreter"""
		self.print_line('')
		return self.do_exit('')

# the core interpreter for the console
class InteractiveInterpreter(OverrideCmd):
	__doc__ = 'The core interpreter for the program'
	__name__ = 'termineter'
	prompt = __name__ + ' > '
	ruler = '+'
	doc_header = 'Type help <command> For Information\nList Of Available Commands:'
	def __init__(self, check_rc_file=True, stdin=None, stdout=None, log_handler=None):
		OverrideCmd.__init__(self, stdin=stdin, stdout=stdout)
		if stdin != None:
			self.use_rawinput = False
			# No 'use_rawinput' will cause problems with the ipy command so disable it for now
			self.__disabled_commands__.append('ipy')

		if not its.on_linux:
			self.__hidden_commands__.append('prep_driver')
		self.__hidden_commands__.append('cd')
		self.__hidden_commands__.append('exploit')
		self.log_handler = log_handler
		if self.log_handler == None:
			self.__disabled_commands__.append('logging')
		self.logger = logging.getLogger(self.__package__ + '.interpreter')
		self.frmwk = Framework(stdout=stdout)
		self.print_error = self.frmwk.print_error
		self.print_good = self.frmwk.print_good
		self.print_line = self.frmwk.print_line
		self.print_status = self.frmwk.print_status

		if check_rc_file:
			if check_rc_file == True:
				check_rc_file = self.frmwk.directories.user_data + 'console.rc'
				if os.path.isfile(check_rc_file) and os.access(check_rc_file, os.R_OK):
					self.print_status('Running commands from resource file: ' + check_rc_file)
					self.run_rc_file(check_rc_file)
			elif isinstance(check_rc_file, str):
				if os.path.isfile(check_rc_file) and os.access(check_rc_file, os.R_OK):
					self.print_status('Running commands from resource file: ' + check_rc_file)
					self.run_rc_file(check_rc_file)
				else:
					self.logger.error('could not access resource file: ' + check_rc_file)
					self.print_error('Could not access resource file: ' + check_rc_file)
		try:
			import readline
			readline.read_history_file(self.frmwk.directories.user_data + 'history.txt')
			readline.set_completer_delims(readline.get_completer_delims().replace('/', ''))
		except (ImportError, IOError):
			pass

	@property
	def intro(self):
		intro = os.linesep
		intro += '   ______              _          __         ' + os.linesep
		intro += '  /_  __/__ ______ _  (_)__  ___ / /____ ____' + os.linesep
		intro += '   / / / -_) __/  \' \/ / _ \/ -_) __/ -_) __/' + os.linesep
		intro += '  /_/  \__/_/ /_/_/_/_/_//_/\__/\__/\__/_/   ' + os.linesep
		intro += os.linesep
		fmt_string = "  <[ {0:<18} {1:>18}"
		intro += fmt_string.format(self.__name__, 'v' + __version__ + '') + os.linesep
		intro += fmt_string.format('model:', 'T-800') + os.linesep
		intro += fmt_string.format('loaded modules:', len(self.frmwk.modules)) + os.linesep
		#if self.frmwk.rfcat_available:
		#	intro += fmt_string.format('rfcat:', 'enabled') + os.linesep
		#else:
		#	intro += fmt_string.format('rfcat:', 'disabled') + os.linesep
		return intro

	@property
	def prompt(self):
		if self.frmwk.current_module:
			if self.frmwk.use_colors:
				return self.__name__ + ' (\033[1;33m' + self.frmwk.current_module.name + '\033[1;m) > '
			else:
				return self.__name__ + ' (' + self.frmwk.current_module.name + ') > '
		else:
			return self.__name__ + ' > '

	def run_rc_file(self, rc_file):
		if os.path.isfile(rc_file) and os.access(rc_file, os.R_OK):
			self.logger.info('processing "' + rc_file + '" for commands')
			for line in open(rc_file, 'r'):
				if not len(line):
					continue
				if line[0] == '#':
					continue
				self.print_line(self.prompt + line.strip())
				self.onecmd(line.strip())
		else:
			self.logger.error('invalid rc file: ' + rc_file)
			return False
		return True

	@staticmethod
	def serve(addr, run_once=False, log_level=None, use_ssl=False, ssl_cert=None):
		if use_ssl:
			import ssl
		__package__ = '.'.join(InteractiveInterpreter.__module__.split('.')[:-1])
		logger = logging.getLogger(__package__ + '.interpreter.server')

		srv_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		srv_sock.bind(addr)
		logger.debug('listening for connections on: ' + addr[0] + ':' + str(addr[1]))
		srv_sock.listen(1)
		while True:
			try:
				(clt_sock, clt_addr) = srv_sock.accept()
			except KeyboardInterrupt:
				break
			logger.info('received connection from: ' + clt_addr[0] + ':' + str(clt_addr[1]))

			if use_ssl:
				ssl_sock = ssl.wrap_socket(clt_sock, server_side=True, certfile=ssl_cert)
				ins = ssl_sock.makefile('r', 1)
				outs = ssl_sock.makefile('w', 1)
			else:
				ins = clt_sock.makefile('r', 1)
				outs = clt_sock.makefile('w', 1)

			log_stream = logging.StreamHandler(outs)
			if log_level != None:
				log_stream.setLevel(log_level)
			log_stream.setFormatter(logging.Formatter("%(levelname)-8s %(message)s"))
			logging.getLogger('').addHandler(log_stream)

			interpreter = InteractiveInterpreter(check_rc_file=False, stdin=ins, stdout=outs)
			try:
				interpreter.cmdloop()
			except socket.error:
				log_stream.close()
				logging.getLogger('').removeHandler(log_stream)
				logger.warning('received a socket error during the main interpreter loop')
				continue
			log_stream.flush()
			log_stream.close()
			logging.getLogger('').removeHandler(log_stream)

			outs.close()
			ins.close()
			clt_sock.shutdown(socket.SHUT_RDWR)
			clt_sock.close()
			del(clt_sock)
			if run_once:
				break
		srv_sock.shutdown(socket.SHUT_RDWR)
		srv_sock.close()
		del(srv_sock)

	def do_back(self, args):
		"""Stop using a module"""
		self.frmwk.current_module = None

	def do_banner(self, args):
		"""Print the banner"""
		self.print_line(self.intro)

	def do_cd(self, args):
		"""Change the current working directory"""
		path = args.split(' ')[0]
		if path == '':
			self.print_error('must specify a path')
			return
		if not os.path.isdir(path):
			self.print_error('invalid path')
			return
		os.chdir(path)

	def complete_cd(self, text, line, begidx, endidx):
		path = line.split(' ')[-1]
		if path[-1] != os.sep:
			text = path.split(os.sep)[-1]
			path = os.sep.join(path.split(os.sep)[:-1])
		else:
			text = ''
		if len(path):
			path = os.path.realpath(path)
		else:
			path = os.getcwd() + os.sep
		return [i for i in os.listdir(path) if i.startswith(text)]

	def do_connect(self, args):
		"""Connect the serial interface"""
		if self.frmwk.is_serial_connected():
			self.print_status('Already connected')
			return
		missing_options = self.frmwk.options.get_missing_options()
		if missing_options:
			self.print_error('The following options must be set: ' + ', '.join(missing_options))
			return
		try:
			result = self.frmwk.serial_connect()
		except Exception as error:
			self.print_error('Caught ' + error.__class__.__name__ + ': ' + str(error))
			return
		self.print_good('Successfully connected and the device is responding')

	def do_disconnect(self, args):
		"""Disconnect the serial interface"""
		args = args.split(' ')
		if not self.frmwk.is_serial_connected():
			self.print_error('Not connected')
			return
		result = self.frmwk.serial_disconnect()
		if result:
			self.print_good('Successfully disconnected')
		else:
			self.print_error('An error occured while closing the serial interface')
		if args[0] == '-r':
			missing_options = self.frmwk.options.get_missing_options()
			if missing_options:
				self.print_error('The following options must be set: ' + ', '.join(missing_options))
				return
			try:
				result = self.frmwk.serial_connect()
			except Exception as error:
				self.print_error('Caught ' + error.__class__.__name__ + ': ' + str(error))
				return
			self.print_good('Successfully reconnected and the device is responding')

	def do_exit(self, args):
		"""Exit The Interpreter"""
		QUOTES = [	'I\'ll be back.',
					'Hasta la vista, baby.',
					'Come with me if you want to live.',
					'Where\'s John Connor?'
					]
		self.logger.info('received exit command, now exiting')
		self.print_status(QUOTES[randint(0, (len(QUOTES) - 1))])
		try:
			import readline
			readline.write_history_file(self.frmwk.directories.user_data + 'history.txt')
		except (ImportError, IOError):
			pass
		return True

	def do_exploit(self, args):
		"""Run the currently selected module"""
		self.do_run(args)

	def do_help(self, args):
		super(InteractiveInterpreter, self).do_help(args)
		self.print_line('')

	def do_logging(self, args):
		"""Set and show logging options"""
		args = args.split(' ')
		if args[0] == '':
			args[0] = 'show'
		elif not args[0] in ['show', 'set', '-h']:
			self.print_error('Invalid parameter "' + args[0] + '", use "logging -h" for more information')
			return
		if args[0] == '-h':
			self.print_status('Valid parameters for the "logging" command are: show, set')
			return
		elif self.log_handler == None:
			self.print_error('No log handler is defined')
			return
		if args[0] == 'show':
			loglvl = self.log_handler.level
			self.print_status('Effective logging level is: ' + ({10: 'DEBUG', 20: 'INFO', 30: 'WARNING', 40: 'ERROR', 50: 'CRITICAL'}.get(loglvl) or 'UNKNOWN'))
		elif args[0] == 'set':
			if len(args) == 1:
				self.print_error('Missing log level, valid options are: debug, info, warning, error, critical')
				return
			new_lvl = args[1].upper()
			if new_lvl in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
				self.log_handler.setLevel(getattr(logging, new_lvl))
				self.print_status('Successfully changed the logging level to: ' + new_lvl)
			else:
				self.print_error('Missing log level, valid options are: debug, info, warning, error, critical')

	def complete_logging(self, text, line, begidx, endidx):
		return [i for i in ['set', 'show', 'debug', 'info', 'warning', 'error', 'critical'] if i.startswith(text)]

	def do_info(self, args):
		"""Show module information"""
		args = args.split(' ')
		if args[0] == '' and self.frmwk.current_module == None:
			self.print_error('Must select module to show information')
			return
		if args[0]:
			if args[0] in self.frmwk.modules.keys():
				module = self.frmwk.modules[args[0]]
			else:
				self.print_error('Invalid module name')
				return
		else:
			module = self.frmwk.current_module
		self.print_line('')
		self.print_line('     Name: ' + module.name)
		if len(module.author) == 1:
			self.print_line('   Author: ' + module.author[0])
		elif len(module.author) > 1:
			self.print_line('  Authors: ' + module.author[0])
			for additional_author in module.author[1:]:
				self.print_line('               ' + additional_author)
		self.print_line('  Version: ' + str(module.version))
		self.print_line('')
		self.print_line('Basic Options: ')
		longest_name = 16
		longest_value = 10
		for option_name, option_def in module.options.items():
			longest_name = max(longest_name, len(option_name))
			longest_value = max(longest_value, len(str(module.options[option_name])))
		fmt_string = "  {0:<" + str(longest_name) + "} {1:<" + str(longest_value) + "} {2}"
		self.print_line(fmt_string.format('Name', 'Value', 'Description'))
		self.print_line(fmt_string.format('----', '-----', '------------'))
		for option_name in module.options.keys():
			option_value = module.options[option_name]
			if option_value == None:
				option_value = ''
			option_desc = module.options.get_option_help(option_name)
			self.print_line(fmt_string.format(option_name, str(option_value), option_desc))
		self.print_line('')
		self.print_line('Description:')
		description_text = module.detailed_description.split()
		y, x = 0, 0
		while y < len(description_text):
			if len(' '.join(description_text[x:y])) <= 58:
				y += 1
			else:
				self.print_line('  ' + ' '.join(description_text[x:(y - 1)]))
				x = y - 1
				y += 1
		self.print_line('  ' + ' '.join(description_text[x:y]))
		self.print_line('')

	def complete_info(self, text, line, begidx, endidx):
		return [i for i in self.frmwk.modules.keys() if i.startswith(text)]

	def do_ipy(self, args):
		"""Start an interactive Python interpreter"""
		from c1218.data import C1218Packet
		from c1219.access.general import C1219GeneralAccess
		from c1219.access.security import C1219SecurityAccess
		from c1219.access.log import C1219LogAccess
		from c1219.access.telephone import C1219TelephoneAccess
		vars = {
			'__version__': __version__,
			'frmwk': self.frmwk,
			'C1218Packet': C1218Packet,
			'C1219GeneralAccess': C1219GeneralAccess,
			'C1219SecurityAccess': C1219SecurityAccess,
			'C1219LogAccess': C1219LogAccess,
			'C1219TelephoneAccess': C1219TelephoneAccess
		}
		banner = 'The Framework Instance Is In The Variable \'frmwk\'' + os.linesep
		if self.frmwk.is_serial_connected():
			vars['conn'] = self.frmwk.serial_connection
			banner = banner + 'The Connection Instance Is In The Variable \'conn\'' + os.linesep
		pyconsole = code.InteractiveConsole(vars)

		savestdin = os.dup(sys.stdin.fileno())
		savestdout = os.dup(sys.stdout.fileno())
		savestderr = os.dup(sys.stderr.fileno())
		try:
			pyconsole.interact(banner)
		except SystemExit:
			sys.stdin = os.fdopen(savestdin, 'r', 0)
			sys.stdout = os.fdopen(savestdout, 'w', 0)
			sys.stderr = os.fdopen(savestderr, 'w', 0)

	def do_prep_driver(self, args):
		"""Prep the optical probe driver"""
		args = args.split()
		if len(args) != 2:
			self.print_line('Usage:')
			self.print_line('  prep_driver VVVV PPPP')
			self.print_line('')
			self.print_line('Where VVVV and PPPP are the 4 hex digits of the vendor and product IDs respectively')
			return
		if os.getuid():
			self.print_error('Must be running as root to prep the driver')
			return
		vendor, product = args
		if vendor.startswith('0x'):
			vendor = vendor[2:]
		if product.startswith('0x'):
			product = product[2:]
		linux_kernel_version = platform.uname()[2].split('.')[:2]
		linux_kernel_version = tuple(int(part) for part in linux_kernel_version)
		if linux_kernel_version < (3, 12):
			proc_args = ['modprobe', 'ftdi-sio', "vendor=0x{0}".format(vendor), "product=0x{0}".format(product)]
		else:
			proc_args = ['modprobe', 'ftdi-sio']
		proc_h = subprocess.Popen(proc_args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, close_fds=True, shell=False)
		if proc_h.wait():
			self.print_error('modprobe exited with a non-zero status code')
			return
		if linux_kernel_version >= (3, 12) and os.path.isfile('/sys/bus/usb-serial/drivers/ftdi_sio/new_id'):
			with open('/sys/bus/usb-serial/drivers/ftdi_sio/new_id', 'w') as file_h:
				file_h.write("{0} {1}".format(vendor, product))
		self.print_status('Finished driver preparation')

	def do_reload(self, args):
		"""Reload a module in to the framework"""
		args = args.split(' ')
		if args[0] == '':
			if self.frmwk.current_module:
				module_path = self.frmwk.current_module.path
			else:
				self.print_error('Must \'use\' module first')
				return
		elif not args[0] in self.frmwk.modules.keys():
			self.print_error('Invalid Module Selected.')
			return
		else:
			module_path = args[0]
		try:
			self.frmwk.reload_module(module_path)
		except FrameworkRuntimeError as err:
			self.print_error('Failed to reload module')
			return
		self.print_status('Successfully reloaded module: ' + module_path)

	def complete_reload(self, text, line, begidx, endidx):
		return [i for i in self.frmwk.modules.keys() if i.startswith(text)]

	def do_resource(self, args):
		"""Run a resource file"""
		args = args.split(' ')
		for rc_file in args:
			if not os.path.isfile(rc_file):
				self.print_error('Invalid resource file: ' + rc_file + ' (not found)')
				continue
			if not os.access(rc_file, os.R_OK):
				self.print_error('Invalid resource file: ' + rc_file + ' (no read permissions)')
				continue
			self.print_status('Running commands from resource file: ' + rc_file)
			self.run_rc_file(rc_file)

	def do_run(self, args):
		"""Run the currently selected module"""
		args = args.split(' ')
		old_module = None
		if args[0] in self.frmwk.modules.keys():
			old_module = self.frmwk.current_module
			self.frmwk.current_module = self.frmwk.modules[args[0]]
		if self.frmwk.current_module == None:
			self.print_error('Must \'use\' module first')
			return
		module = self.frmwk.current_module
		missing_options = module.get_missing_options()
		if missing_options:
			self.print_error('The following options must be set: ' + ', '.join(missing_options))
			return
		del missing_options

		if isinstance(module, TermineterModuleOptical):
			if module.require_connection and not self.frmwk.is_serial_connected():
				try:
					result = self.frmwk.serial_connect()
				except Exception as error:
					self.print_error('Caught ' + error.__class__.__name__ + ': ' + str(error))
					return
				self.print_good('Successfully connected and the device is responding')
			else:
				try:
					self.frmwk.serial_get()
				except Exception as error:
					self.print_error('Caught ' + error.__class__.__name__ + ': ' + str(error))
					return
		try:
			self.frmwk.run()
		except KeyboardInterrupt:
			self.print_line('')
		except Exception as error:
			for x in traceback.format_exc().split(os.linesep):
				self.print_line(x)
			self.logger.error('caught ' + error.__class__.__name__ + ': ' + str(error))
			self.print_error('Caught ' + error.__class__.__name__ + ': ' + str(error))
			old_module = None
		if old_module:
			self.frmwk.current_module = old_module

	def complete_run(self, text, line, begidx, endidx):
		return [i for i in self.frmwk.modules.keys() if i.startswith(text)]

	def do_set(self, args):
		"""Set an option, usage: set [option] [value]"""
		args = args.split(' ')
		if len(args) < 2:
			self.print_error('set: [option] [value]')
			return
		name = args[0].upper()
		value = ' '.join(args[1:])

		if self.frmwk.current_module:
			options = self.frmwk.current_module.options
			advanced_options = self.frmwk.current_module.advanced_options
		else:
			options = self.frmwk.options
			advanced_options = self.frmwk.advanced_options
		if name in options:
			try:
				options.set_option(name, value)
				self.print_line(name + ' => ' + value)
			except TypeError:
				self.print_error('Invalid data type')
			return
		elif name in advanced_options:
			try:
				advanced_options.set_option(name, value)
				self.print_line(name + ' => ' + value)
			except TypeError:
				self.print_error('Invalid data type')
			return
		self.print_error('Unknown variable name')

	def complete_set(self, text, line, begidx, endidx):
		if self.frmwk.current_module:
			return [i for i in self.frmwk.current_module.options.keys() if i.startswith(text.upper())]
		else:
			return [i for i in self.frmwk.options.keys() if i.startswith(text.upper())]

	def do_show(self, args):
		"""Valid parameters for the "show" command are: modules, options"""
		args = args.split(' ')
		if args[0] == '':
			args[0] = 'options'
		elif not args[0] in ['advanced', 'modules', 'options', '-h']:
			self.print_error('Invalid parameter "' + args[0] + '", use "show -h" for more information')
			return
		if args[0] == 'modules':
			self.print_line('')
			self.print_line('Modules' + os.linesep + '=======')
			self.print_line('')
			longest_name = 18
			for module_name in self.frmwk.modules.keys():
				longest_name = max(longest_name, len(module_name))
			fmt_string = "  {0:" + str(longest_name) + "} {1}"
			self.print_line(fmt_string.format('Name', 'Description'))
			self.print_line(fmt_string.format('----', '-----------'))
			module_names = self.frmwk.modules.keys()
			module_names.sort()
			for module_name in module_names:
				module_obj = self.frmwk.modules[module_name]
				self.print_line(fmt_string.format(module_name, module_obj.description))
			self.print_line('')
			return
		elif args[0] == 'options' or args[0] == 'advanced':
			self.print_line('')
			if self.frmwk.current_module and args[0] == 'options':
				options = self.frmwk.current_module.options
				self.print_line('Module Options' + os.linesep + '==============')
			if self.frmwk.current_module and args[0] == 'advanced':
				options = self.frmwk.current_module.advanced_options
				self.print_line('Advanced Module Options' + os.linesep + '=======================')
			elif self.frmwk.current_module == None and args[0] == 'options':
				options = self.frmwk.options
				self.print_line('Framework Options' + os.linesep + '=================')
			elif self.frmwk.current_module == None and args[0] == 'advanced':
				options = self.frmwk.advanced_options
				self.print_line('Advanced Framework Options' + os.linesep + '==========================')
			self.print_line('')
			longest_name = 16
			longest_value = 10
			for option_name, option_def in options.items():
				longest_name = max(longest_name, len(option_name))
				longest_value = max(longest_value, len(str(options[option_name])))
			fmt_string = "  {0:<" + str(longest_name) + "} {1:<" + str(longest_value) + "} {2}"

			self.print_line(fmt_string.format('Name', 'Value', 'Description'))
			self.print_line(fmt_string.format('----', '-----', '-----------'))
			for option_name in options.keys():
				option_value = options[option_name]
				if option_value == None:
					option_value = ''
				option_desc = options.get_option_help(option_name)
				self.print_line(fmt_string.format(option_name, str(option_value), option_desc))
			self.print_line('')
		elif args[0] == '-h':
			self.print_status('Valid parameters for the "show" command are: modules, options')

	def complete_show(self, text, line, begidx, endidx):
		return [i for i in ['advanced', 'modules', 'options'] if i.startswith(text)]

	def do_use(self, args):
		"""Select a module to use"""
		args = args.split(' ')
		mod_name = args[0]
		if not mod_name:
			self.print_line('Usage:')
			self.print_line('  use [module name]')
			return
		if mod_name in self.frmwk.modules.keys():
			self.frmwk.current_module = self.frmwk.modules[mod_name]
		else:
			self.logger.error('failed to load module: ' + mod_name)
			self.print_error('Failed to load module: ' + mod_name)

	def complete_use(self, text, line, begidx, endidx):
		return [i for i in self.frmwk.modules.keys() if i.startswith(text)]
