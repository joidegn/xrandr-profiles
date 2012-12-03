#!/usr/bin/env python3

import sys
from os.path import expanduser
import re
import subprocess
from configparser import ConfigParser
import argparse

current_profile = None
# load configuration file
config_file = expanduser('~/.xrandr-profiles')
config = ConfigParser()
with open(config_file) as config_fp:
    config.readfp(config_fp)

class NoEdidFoundError(Exception):
    """raised if no connected monitor with a configured profile was found"""
    def __init__(self):
        print("could not find a configuration matching the current setup")
        sys.exit(1)

class ParseXrandrArgAction(argparse.Action):
    """ parses xrandr calls to extract them and put them into the config file """
    def __call__(self, parser, namespace, values, option_string=None):
        if values:
            print('values: %s' % values)
            commands = values.split()
            if '--output' in values:
                # hopefully we have a proper --output command
                xrandr_command = {
                    'command': values,
                    'option': 'output',
                    'monitor': commands[1],  # the monitor should hopefully be after --output
                    'rest': " ".join(commands[2:]),
                    'cfg_line': '%s: %s' % (monitor, rest)
                }
            # TODO: parse all other commands

            setattr(namespace, self.dest, xrandr_command)

def match_configuration():
    """finds out current setup using xrandr and matches profile in ~/.xrandr-profiles file"""
    global current_profile

    # try to find one of our profiles using `xrandr --prop` which returns the
    # EDIDs of the connected monitros
    xrandr_output = subprocess.Popen(['xrandr', '--prop'], stdout=subprocess.PIPE).stdout.read().decode('utf-8')
    try:
        # connect EDIDs into a single string per EDID removing whitespaces
        connected_edids = ["".join(s.split()) for s in re.findall(r'EDID\:(.*?)\n(?!\t\t)', xrandr_output, re.DOTALL)]
    except AttributeError: # no EDID found
        pass

    current_profile = None
    for profile in [section for section in config.sections() if not section == 'general']:
        # load EDIDs and get rid of whitespaces
        print('profile: %s, config: %s' % (profile, config[profile]))
        configured_edids = "".join(config[profile]['EDIDs'].split()).split(',')
        if configured_edids == connected_edids:
            current_profile = profile
            break


    return current_profile

def run_xrandr(profile=None, args=None):
    """ do steps found e.g. here: https://wiki.archlinux.org/index.php/Xrandr#Use_cvt.2Fxrandr_tool_to_add_the_highest_mode_the_LCD_can_do
    """
    print("running xrandr for: %s" % profile)
    if not profile is None:
        print("adding modes: %s" % config[profile]['add_modes'].split(','))
        for mode in config[profile]['add_modes'].strip('\n').split(','):
            # extract monitor, mode_line and resolution from config file
            monitor, mode_line = mode.split(':')
            nothing, resolution, mode_line = re.split(r'"([0-9xR]+)"', mode_line) # TODO: maybe add a check for a valid resolution here
            # print ('monitor: %s\tmode_line: %s\tresolution: %s' % (monitor, mode_line, resolution))
            cmd_list = ['xrandr', '--newmode'] + mode.split()
            process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.stderr.read():
                print("an error occurred while newmode: %s" % process.stderr.read().decode('utf-8'))
            process = subprocess.Popen(['xrandr', '--addmode', monitor, resolution], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.stderr.read():
                print("an error occurred while adding mode: %s" % process.stderr.read().decode('utf-8'))

        print("choosing outputs: %s" % config[profile]['outputs'])
        for output in config[profile]['outputs'].split(','):
            monitor, output_line = output.strip().split(':')
            #print ('monitor: %s\toutput_line: %s' % (monitor, output_line))
            cmd_list = ['xrandr', '--output', monitor] + output_line.split()
            process = subprocess.Popen(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if process.stderr.read():
                print("an error occurred while choosing output: %s" % process.stderr.read().decode('utf-8'))
    else:
        # we are running xrandr-profile with a xrandr command so we record that string and then run it
        if args.xrandr:
            record_command(args.xrandr)

def record_command(parsed_command):
    """ puts the command in the config file for the current monitor setup 
        parsed_command: {
            'command': command,
            'option': 'output',
            'monitor': commands[1],  # the monitor should hopefully be after --output
            'rest': " ".join(commands[2:]),
            'cfg_line': '%s: %s' % (monitor, rest)
        }
    """
    global current_profile
    print('parsed_command: %s' % parsed_command)
    if config.has_option(current_profile, parsed_command['option']): # check if option is already set
        config.set(current_profile, parsed_command['option'], '%s,\n%s' % (config.get(current_profile, parsed_command['option']), parsed_command['cfg_line']))
    else:
        config.set(current_profile, parsed_command['option'], parsed_command['config_line'])

def add_profile(args):
    """ add a new profile from the given arguments"""
    print('command should add a profile from the args: %s' % args)
    with open(config_file, 'a') as config_fp:
        pass

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Create xrandr profiles for each monitor setup')
    parser.add_argument('xrandr', nargs='*', help='xrandr command e.g. "xrandr --output, LVDS1, --below, DP1"', action=ParseXrandrArgAction)
    parser.add_argument('--record', '-r', nargs='?', help='only record and dont execute xrandr command')
    # TODO: add an argument to create a new profile entry in the config file with the current EDIDS
    subparsers = parser.add_subparsers(help='subcommands: \nadd-profile', title='add a current setup', dest='subparser')
    parser_add_profile = subparsers.add_parser('add-profile', help='adds a profile for the current monitor setup')
    parser_add_profile.add_argument('name', nargs=1, help='insert the name of the new profile')
    parser_add_profile.add_argument('xrandr', nargs='*', help='xrandr command e.g. "xrandr --output, LVDS1, --below, DP1"', action=ParseXrandrArgAction)
    parser_profile = subparsers.add_parser('profile', help='uses a profile (runs xrandr with given settings)')
    parser_profile.add_argument('profile_name', nargs=1, help='name of the profile to use')
    # load the config for the current setup from the config file
    current_profile = match_configuration()

    args = parser.parse_args()
    print('args: %s' % args)
    if args.subparser == 'add-profile':
        add_profile(args)
    elif args.subparser == 'profile':
        run_xrandr(args.profile_name[0])
    else:
        if current_profile is None:
            raise NoEdidFoundError
        else:
            run_xrandr(args=args)

if __name__ == '__main__':
    main()
