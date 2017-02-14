#!/usr/bin/python3

# This program is free software under the terms of the GPL v.3 (see LICENSE file)
# python version 3.3 or greater is required

import os
import sys
import re
import bibtexparser
import bibsonomy
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase

CONFIG_FILE_NAME = '.bibfetch'
NUM_TERMINAL_LINES = 25

# Commands (type ids)
CMD_ADD = 0
CMD_RELIST = 1
CMD_QUIT = 2

class Command:
    def __init__(self, type_id, args=[]):
        self.type_id = type_id
        self.args = args

class CommandDesc:
    def __init__(self, cmd_str, type_id, description, num_args=0,
                 arg_parser=lambda x: []):
        self.cmd_str = cmd_str
        self.type_id = type_id
        self.description = description
        self.num_args = num_args
        self.arg_parser = arg_parser

def load_config(config_file_name, config):
    """Parse configuration file and fill specified config dict with defined 
       properties"""
        
    if os.path.exists(config_file_name):
        with open(config_file_name, 'r') as file:
            line_n = 0
            for line in file:
                line = line.strip()

                # Ignore blank lines and comments (start with '#')
                if len(line) > 0 and not line.startswith('#'):
                    components = line.split('=')
                    if len(components) < 2:
                        raise BadFormatError('Error occured parsing '
                                             'configuration file at line %d' %
                                             line_n)
                    key = components[0].strip()
                    val = '='.join(components[1:]).strip()
                    config[key] = val

                line_n += 1

def render_post(post):
    lines = []
    lines.append("title: " + post.title)
    lines.append("year: " + post.year)
    if hasattr(post, 'author'):
        lines.append("author: " + post.author)
    if hasattr(post, 'journal'):
        lines.append("journal: " + post.journal)
    elif hasattr(post, 'booktitle'):
        lines.append("book: " + post.booktitle)

    return lines

def display_posts(posts):
    index = 1
    lines_printed = 0
    for post in posts:
        lines = render_post(post.resource)
        total_entry_lines = len(lines) + 2 # 1 line for index, 1 empty line
        if lines_printed + total_entry_lines >= NUM_TERMINAL_LINES:
            input('Press <Enter> to continue')
            lines_printed = 0
        print("%d:" % index)
        for line in lines:
            print(line)
        print()
        lines_printed += total_entry_lines
        index += 1

def single_int_arg_parser(val_range, args):
    (lower, upper) = val_range
    try:
        val = int(args[0])
        if val < lower or val > upper:
            raise Exception('Out of range: expected integer between %d and %d'
                            % (lower, upper))
        return [val]
    except ValueError:
        raise Exception('Invalid integer')

def display_command_menu(cmd_descs):
    print('Commands:')
    for cmd_desc in cmd_descs:
        print('%s - %s' % (cmd_desc.cmd_str, cmd_desc.description))    

def read_command(cmd_descs):
    cmd = None
    while cmd is None:
        s = input('Command: ')
        components = s.split()
        try:
            if len(components) == 0:
                raise Exception('No command entered')
            for desc in cmd_descs:
                if components[0] == desc.cmd_str:
                    if len(components) - 1 != desc.num_args:
                        raise Exception('Invalid number of arguments')
                    arg_strs = components[1:]
                    args = desc.arg_parser(arg_strs)
                    cmd = Command(desc.type_id, args)
            if cmd is None:
                raise Exception('Unknown command')
        except Exception as e:
            print('Error: ' + str(e))
    return cmd


# Handle commands

def handle_add(bib_path, post):
    with open(bib_path) as bib_file:
        bibtex_str = bib_file.read()
    bib_db = bibtexparser.loads(bibtex_str)
    existing_entries = bib_db.get_entry_dict()

    print('\nEntry to add:')
    lines = render_post(post)
    for line in lines:
        print(line)
    print()

    have_valid_key = False
    while not have_valid_key:
        key = input('New BibTex Key: ')
        if not re.match('[^{},]+', key):
            print('Invalid BibTex key')
        elif key in existing_entries:
            print('That BibTex key already exists in bibliography')
        else:
            have_valid_key = True

    entry = dict(filter(lambda t: t[0] != 'bibtex_key' and t[0] != 'entry_type',
                        post.__dict__.items()))
    entry['ENTRYTYPE'] = post.entry_type
    entry['ID'] = key

    new_db = BibDatabase()
    new_db.entries = [entry]

    writer = BibTexWriter()    
    with open(bib_path, 'a') as bib_file:
        bib_file.write(writer.write(new_db))

    print('Entry added')
    
                
def run():
    home_dir = os.path.expanduser('~')
    config_file_path = os.path.join(home_dir, CONFIG_FILE_NAME)
    if not os.path.exists(config_file_path):
        raise Exception('config file not found')
    config = {} # this is in case we ever need defaults
    load_config(config_file_path, config)
    if 'bib' not in config:
        raise Exception('bibliography not specified in config file')
    bib_path = config['bib']
    if not os.path.exists(bib_path):
        raise Exception('bibliography %s not found' % bib_path)

    if 'bibsonomy_username' not in config or 'bibsonomy_api_key' not in config:
        raise Exception('bibsonomy username or api key not in config file')

    rest = bibsonomy.REST(config['bibsonomy_username'],
                          config['bibsonomy_api_key'])
    bibs = bibsonomy.BibSonomy(rest)

    # Search
    search_str = ''
    while len(search_str) == 0:
        search_str = input('Search: ')

    posts = bibs.searchPosts('publication', '"%s"' % search_str)
    display_posts(posts)

    # Available commands
    add_cmd_arg_parser = lambda args: single_int_arg_parser((1, len(posts)),
                                                             args)
    cmd_descs = [CommandDesc('a', CMD_ADD,
                             'Add entry to bibliography. Takes index argument.',
                             num_args=1, arg_parser=add_cmd_arg_parser),
                 CommandDesc('r', CMD_RELIST, 'Relist entries'),
                 CommandDesc('q', CMD_QUIT, 'Quit')
    ]
    
    if len(posts) > 0:
        display_command_menu(cmd_descs)
        cmd = read_command(cmd_descs)
        while cmd.type_id == CMD_RELIST:
            display_posts(posts)
            cmd = read_command(cmd_descs)
        
        if cmd.type_id == CMD_ADD:
            handle_add(bib_path, posts[cmd.args[0] - 1].resource)
    else:
        print('No results found')
    
    

try:
    run()
except Exception as e:
    print(str(e))
