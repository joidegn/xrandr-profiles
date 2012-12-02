#!/usr/bin/env python3

import sys
from os.path import expanduser
import re
import subprocess
from configparser import ConfigParser
import argparse

# load configuration file
config = ConfigParser()
with open(expanduser('~/.xrandr-profiles')) as config_file:
    config.readfp(config_file)

class NoEdidFoundError(Exception):
    """raised if no connected monitor with a configured profile was found"""
    def __init__(self):
        print("could not find a configuration matching the current setup")
        sys.exit(1)

def match_configuration():
    """finds out current setup using xrandr and matches profile in ~/.xrandr-profiles file"""

    # try to find one of our profiles using `xrandr --prop` which returns the
    # EDIDs of the connected monitros
    xrandr_output = subprocess.Popen(['xrandr', '--prop'], stdout=subprocess.PIPE).stdout.read().decode('utf-8')
    try:
        # connect EDIDs into a single string per EDID removing whitespaces
        connected_edids = ["".join(s.split()) for s in re.findall(r'EDID\:(.*?)\n(?!\t\t)', xrandr_output, re.DOTALL)]
    except AttributeError: # no EDID found
        pass

    current_profile = None
    for profile in config.sections():
        # get rid of whitespaces
        configured_edids = "".join(config[profile]['EDIDs'].split()).split(',')
        if configured_edids == connected_edids:
            current_profile = profile
            break


    return current_profile

def run_xrandr_setup(profile):
    """ do steps found e.g. here: https://wiki.archlinux.org/index.php/Xrandr#Use_cvt.2Fxrandr_tool_to_add_the_highest_mode_the_LCD_can_do
    """
    print("running xrandr for: %s" % profile)
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

def add_profile(args):
    """ add a new profile from the given arguments"""
    print('command should add a profile from the args: %s' % args)

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Create xrandr profiles for each monitor setup')
    # TODO: add an argument to create a new profile entry in the config file with the current EDIDS
    subparsers = parser.add_subparsers(help='subcommands: \nadd-profile', title='add a current setup', dest='subparser')
    parser_add_profile = subparsers.add_parser('add-profile', help='adds a profile for the current monitor setup')
    parser_add_profile.add_argument('name', nargs=1, help='insert the name of the new profile')
    parser_add_profile.add_argument('xrandr', nargs='*', help='xrandr commands e.g. "xrandr --output, LVDS1, --below, DP1"')

    current_profile = match_configuration()

    print(parser.parse_args())
    args = parser.parse_args()
    if args.subparser == 'add-profile':
        add_profile(args)
    else:
        if current_profile is None:
            raise NoEdidFoundError
        else:
            run_xrandr_setup(current_profile)

if __name__ == '__main__':
    
    main()
