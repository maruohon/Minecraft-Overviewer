======================================
Minecraft Overviewer for FTB Unleashed
======================================

About
-----
This branch (ftb-152) has a version of Minecraft Overviewer that works with the FTB Unleashed mod pack.
This version of Overviewer aims to add support for most of the world generation/terrain that
is in the FTB Unleashed mod pack, so that people can have nice overviews of their FTB Unleashed worlds.

To be more specific, this version aims to add support for rendering most of the
"regular shaped/vanilla-like" blocks in the following mods:
 - Applied Energistics
 - Biomes O' Plenty
 - Buildcraft (mostly just Oil)
 - Dartcraft
 - Forestry
 - IC2
 - Magic Bees
 - Minefactory Reloaded
 - Mystcraft (mostly just crystals)
 - Natura
 - Railcraft
 - Thaumcraft
 - Thermal Expansion
 - Tinker's Construct

The block ids are according to the FTB Unleashed mod pack (v1.1.4). If your mod pack uses a different
set of ids, then they must be manually adjusted (see textures.py and base.c).

Some blocks might not be rendered quite correctly, either because the correct rendering would require
the use of tile entity data, which overviewer does not currently support(?), or because of my laziness.
I'm also using cobwebs as a placeholder for unimplemented/missing texture definitions, so if your
renderings have cobwebs in places that shouldn't have them, then it is most likely because that block
has not been added yet. This is mostly just with blocks that differentiate the type with the additional
4-bit data. This means that if there are supported block ids, but with unrecognized additional data values,
in the world data, then those will be rendered as cobwebs. Blocks with unknown block ids will be missing completely.

Installation
------------
Clone this repository, change to the ftb-152 branch, and then build overviewer:
 - git clone git@github.com:maruohon/Minecraft-Overviewer.git Minecraft-Overviewer.git
 - cd Minecraft-Overviewer.git
 - git checkout origin/ftb-152
 - python setup.py build

You will need to create and modify the render config file as usual.

You will also need to create the texture pack and point the config file to that.
To create the texture pack/file, you need to create a zip file, that contains the following:
 - textures directory from the 1.5.2 version of minecraft.jar
 - next, you need to copy the blocks directory from each of the mods' supported by this version of overviewer, texture directory, into the textures/blocks/ directory, renamed to the following names: ae, bc, bop, dartcraft, forestry, ic2, magicbees, mfr, mystcraft, natura, railcraft, te, thaumcraft, tic
 - inside the zip file, you would then have a directory structure such as the following:
  - textures/blocks/gravel.png (vanilla)
  - textures/blocks/bop/aloe.png (Biomes O' Plenty)
  - textures/blocks/te/Ore_Copper.png (Thermal Expansion)
  - etc.

After this, you should be able to render the world as per usual:
 - python overviewer.py --config=yourconfigfile.py


====================
Minecraft Overviewer  |Build Status|
====================
By Andrew Brown and contributors (see CONTRIBUTORS.rst).

Documentation:
    http://docs.overviewer.org

Github code repository:
    http://github.com/overviewer/Minecraft-Overviewer
	
Travis-CI:
    http://travis-ci.org/overviewer/Minecraft-Overviewer
	
Blog:
    http://overviewer.org/blog/


The Minecraft Overviewer is a command-line tool for rendering high-resolution
maps of Minecraft worlds. It generates a set of static html and image files and
uses the Google Maps API to display a nice interactive map.

The Overviewer has been in active development for over a year and has many
features, including day and night lighting, cave rendering, mineral overlays,
and many plugins for even more features! It is written mostly in Python with
critical sections in C as an extension module.

Getting Started
---------------
All documentation has been consolidated at our documentation site. For
information on downloading, compiling, installing, and running The Overviewer,
visit the docs site.

http://docs.overviewer.org

A few helpful tips are below, but everyone is going to want to visit the
documentation site for the most up-to-date and complete set of instructions!

Alternatively, the docs are also in the docs/ directory of the source download.
Look in there if you can't access the docs site.

Examples
--------
See examples of The Overviewer in action!

https://github.com/overviewer/Minecraft-Overviewer/wiki/Map-examples

Disclaimers
-----------
Before you dive into using this, just be aware that, for large maps, there is a
*lot* of data to parse through and process. If your world is very large, expect
the initial render to take at least an hour, possibly more. (Since Minecraft
maps are practically infinite, the maximum time this could take is also
infinite!)

If you press ctrl-C, it will stop. The next run will pick up where it left off.

Once your initial render is done, subsequent renderings will be MUCH faster due
to all the caching that happens behind the scenes. Just use the same output
directory and it will only update the tiles it needs to.

There are probably some other minor glitches along the way, hopefully they will
be fixed soon. See the `Bugs`_ section below.

Viewing the Results
-------------------
Within the output directory you will find two things: an index.html file, and a
directory hierarchy full of images. To view your world, simply open index.html
in a web browser. Internet access is required to load the Google Maps API
files, but you otherwise don't need anything else.

You can throw these files up to a web server to let others view your map. You
do *not* need a Google Maps API key (as was the case with older versions of the
API), so just copying the directory to your web server should suffice. You are,
however, bound by the Google Maps API terms of service.

http://code.google.com/apis/maps/terms.html

Bugs
====

For a current list of issues, visit
https://github.com/overviewer/Minecraft-Overviewer/issues

Feel free to comment on issues, report new issues, and vote on issues that are
important to you.

.. |Build Status| image:: https://secure.travis-ci.org/overviewer/Minecraft-Overviewer.png?branch=master
