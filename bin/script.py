#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
	if len(sys.argv) < 4:
		print "Format: python script.py pm_file image_file vm_types"
		exit(1)
	os.chdir("../src")
	os.system("python main.py " + sys.argv[1] + " " +sys.argv[2] + " " +sys.argv[3])