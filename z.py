import argparse
from sys import argv
from argparse import *
from oauth2client.tools import argparser
flags=''
def main(argv):
  global flags
  parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        parents=[argparser])
  flags = parser.parse_args(argv[1:])
  print flags

main(argv)
