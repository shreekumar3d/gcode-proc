#!/usr/bin/python
#
# Post-processing script that changes filament
# at required certain layer height in a gcode file
#
# Written for & tested with :
#   - Slic3r 1.30.0.25-prusa3d-release_candidate_1_3-win64
#   - Prusa i3 MK2 with Firmware 3.0.8
# 
# This uses the M600 gcode to effect the filament
# change.
#
# Pre-requisites:
#
# This script depends on python & wxpython. Ensure that both
# are installed before trying to use this script.  Else you
# might see silent failures.
#
# Python 2.7.10 & wxPython 3.0.2 were tested during develop 
#
# Usage:
#
# Use it as as a post-processing script in Slic3r:
#   a. Under "Print Settings" | "Output Options", add the full
#      path of this script under "Post-processing scripts"
#   b. Under "Printer Settings" | "Custom G-code", add the following
#      line to "Before layer change G-code". 
#
#      ; Layer Z=[layer_z]
#   c. Export g-code
#   d. In the next dialog, select the layer(s)
#
# Script can also be used from the command line. More than
# one layer heights can be specified.  If none are specified,
# then the UI will popup.

import sys
import re
import wx
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("gcode", help="gcode filename")
parser.add_argument("Z", nargs='*', help="filament change Z")
args = parser.parse_args()

print sys.argv
outFile = sys.argv[1]
allLines = open(outFile, 'r').readlines()

# Enumerate all layers
layerZ = []
reLayerStart = re.compile('^\s*;\s*Layer\s+Z\s*=\s*([0-9\.]+)\s*')
for line in allLines:
	ob = reLayerStart.match(line)
	if ob:
		layerZ.append(ob.groups()[0])

# User Interface
app = wx.App()

# Flag an error if we don't detect any layers
# This indicates improper setup in the slicer
if len(layerZ)==0:
	dlg2 = wx.MessageDialog(
	            None, 
		    'No layers were detected in the gcode.\nPlease ensure that you have setup the "Before layer change G-code" to "; Layer Z=[layer_z]"',
                    'gcode setup Error',
                    wx.OK | wx.ICON_ERROR)
	dlg2.ShowModal()
	sys.exit(-1)

def getMultiFilamentChange(layerZ):
	layerChange = []
	dlg = wx.MultiChoiceDialog(None, "Pick filament change layers:", "Change Filament At?", layerZ)
	if dlg.ShowModal() == wx.ID_OK:
		selections = dlg.GetSelections()
		layerChange = [layerZ[x] for x in selections]
	return layerChange

def getSingleFilamentChange(layerZ):
	dlg = wx.TextEntryDialog(None, 'Enter color change Z','Color change')
	if dlg.ShowModal() == wx.ID_OK:
		changeZ = dlg.GetValue()
		changeZf = float(changeZ)
		if changeZf in map(float, layerZ):
			return [changeZ]
		else:
			dlg2 = wx.MessageDialog(None, 'Please enter a valid layer value',
                               'Invalid layer value',
                               wx.OK | wx.ICON_ERROR
                               #wx.YES_NO | wx.NO_DEFAULT | wx.CANCEL | wx.ICON_INFORMATION
                               )
			dlg2.ShowModal()
			dlg2.Destroy()
	return []

# If Z values are passed in the command line, use it.
if len(args.Z)==0:
	# Choose one of the following UIs
	changeLayers = getMultiFilamentChange(layerZ)
	#changeLayers = getSingleFilamentChange(layerZ)
else:
	changeLayers = args.Z
	# Validate user value -- anything could get passed in the command line
	for z in changeLayers:
		if float(z) not in map(float, layerZ):
			print 'Invalid Z value %s . Z value must exactly correspond to any valid layer height in the gcode file.'%(z)
			sys.exit(-1)

if len(changeLayers)==0:
	dlg = wx.MessageDialog(
		None, 'No valid layer(s) have been selected', 'gcode is unchanged!',
		wx.OK | wx.ICON_ERROR)
	dlg.ShowModal()
	sys.exit(-1)

gcodeExtrude = re.compile('^G1\s+.*E0') # positive extrude
gcodeExtrudeNoMove = re.compile('^G1\s+E0')
lidx = 0
outLines = []
# Generated gcode looks like this:
#  ; Layer Z=2.15 N=20 
#  G1 F5760
#  G1 X80.515 Y98.846 E-0.76000
#  G1 E-0.04000 F2100.00000
#  G1 Z2.200 F7200.000
#  G1 X102.308 Y109.134 F7200.000 ; Move to first perimeter point
#  G1 Z2.150 F7200.000 ; restore layer Z
#  G1 E0.80000 F2100.00000 ; Unretract
#
# We need to insert M600 at the appropriate place, which
# is just prior to the layer change
#
while lidx < len(allLines):
	thisLine = allLines[lidx]
	ob = reLayerStart.match(thisLine)
	if ob and (float(ob.groups()[0]) in map(float, changeLayers)):
		# Layer of interest - so add the M600
		outLines.append('; %s %s'%('Change Filament at this layer ', thisLine))
		i = 1
		# Copy to output all lines, till the first extrude of this layer
		while not gcodeExtrude.search(allLines[lidx+i]):
			outLines.append(allLines[lidx+i])
			i = i+1

		# Then change filament
		outLines.append('M600 ; Filament change gcode\n') # filament change
		if gcodeExtrudeNoMove.search(allLines[lidx+i]):
			outLines.append('; Prevent blob - Ignore extrude gcode - %s'%(allLines[lidx+i])) # Extrude line
		else:
			outLines.append(allLines[lidx+i])
		lidx = lidx+i+1
	else:
		outLines.append(thisLine)
		lidx = lidx + 1

# Write out all the output lines
f = open(outFile, 'w')
for l in outLines:
	print >>f, l,
