=========================================
Minecraft Overviewer for FTB 1.6.4 packs
=========================================

About
-----
This branch (ftb-164) has a version of Minecraft Overviewer that works with the
FTB Direwolf20 1.6.4 mod pack. As FTB is using the universal configs in their
1.6.4 packs, this version should also be compatible (but not necessarily
complete!) with other FTB 1.6.4 packs as well. Some other non-FTB packs are also
using the FTB universal configs, and those packs should also be compatible,
but again, not complete. This version of Overviewer aims to add support for
most of the world generation/terrain that is in the FTB Direwolf20 1.6.4 mod
pack, so that people can have nice overviews of their modded worlds.

To be more specific, this version aims to add support for rendering most of the
"regular shaped/vanilla-like" blocks in the following mods:
 - Applied Energistics
 - Biomes O' Plenty
 - Buildcraft (mostly just Oil)
 - Dartcraft (although not in the DW20 pack)
 - Extra Bees
 - Extra Trees (only partial support due to lots of the stuff using tile entity data)
 - Extra Utilities
 - Factorization (barrels! ;D)
 - Forestry
 - IC2
 - Magic Bees
 - Minefactory Reloaded
 - Mystcraft (mostly just crystals and decay)
 - Natura
 - Railcraft
 - Thaumcraft
 - Thermal Expansion
 - Tinker's Construct

Do note that everything that would need tile entity data to be correctly rendered,
is either missing or has some placeholder approximation. Also no connected textures.

The block ids are according to the FTB Direwolf20 1.6.4 mod pack (v1.0.20) (FTB
universal configs). If your mod pack uses a different set of ids, then they must
be manually adjusted.

The files with modifications from vanilla to modded are:
 - overviewer_core/src/iterate.c
 - overviewer_core/src/primitives/base.c
 - overviewer_core/src/primitives/nether.c
 - overviewer_core/textures.py

You can view the changes and find out the parts that have changed by comparing
the master branch to which this patch is based on and the result with the
following git diff command:
 - git diff master-164 ftb-164

Some blocks might not be rendered quite correctly, either because the correct
rendering would require the use of tile entity data, which overviewer does not
currently support(?), or because of my laziness.
I'm also using cobwebs as a placeholder for unimplemented/missing texture
definitions, so if your renderings have cobwebs in places that shouldn't have
them, then it is most likely because that block has not been added yet.
This is mostly just with blocks that differentiate the type with the additional
4-bit metadata. This means that if there are supported block IDs, but with
unrecognized metadata values in the world data, then those will be
rendered as cobwebs. Blocks with unknown block IDs will be missing completely.

Installation
------------
Clone this repository, change to the ftb-164 branch, and then build overviewer:
 - git clone git@github.com:maruohon/Minecraft-Overviewer.git Minecraft-Overviewer.git
 - cd Minecraft-Overviewer.git
 - git checkout origin/ftb-164
 - python setup.py build

* You will also need to create the resource pack that contains all the textures.
* To create the resource pack, you need to create a zip file or a directory structure, that contains the following:
 - the assets directory from the 1.6.4 version of minecraft jar
   (this can be found inside the minecraft installation directory, in
   location versions/1.6.4/1.6.4.jar)
 - next, you need to copy the assets/<modname> directory from
   each of the mods' jars or zips supported by this version of overviewer
   into the assets/ directory that you copied from the vanilla jar.

* You should now have a directory structure like this inside your resource pack directory or zip file:
 - assets/minecraft/textures/blocks (vanilla stuff)
 - assets/appeng/textures/blocks
 - assets/biomesoplenty/textures/blocks
 - assets/buildcraft/textures/blocks
 - assets/dartcraft/textures/blocks
 - assets/extrabees/textures/blocks (from binniemods*.jar)
 - assets/extrabees/textures/tile   NOTE: this is an exception, other mods only need the blocks directory!
 - assets/extratrees/textures/blocks (from binniemods*.jar)
 - assets/extrautils/textures/blocks
 - assets/factorization/textures/blocks
 - assets/forestry/textures/blocks
 - assets/ic2/textures/blocks
 - assets/magicbees/textures/blocks
 - assets/minefactoryreloaded/textures/blocks
 - assets/mystcraft/textures/blocks
 - assets/natura/textures/blocks
 - assets/railcraft/textures/blocks
 - assets/thaumcraft/textures/blocks
 - assets/thermalexpansion/textures/blocks
 - assets/tinker/textures/blocks
* Optionally, you can delete all the other directories from
  assets/<modname>/ leaving just the textures directory, and also
  from assets/<modname>/textures/ leaving just the blocks directory (except BinnieMods - ExtraBees also needs the textures/tile/ directory!).
  In other words, you just need the blocks directories as listed above.
* Finally, you will need to create and modify the overviewer render config file as
  usual. Set the texturepath to point to your resource pack directory or zip
  file you just put together as explained above.

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

https://developers.google.com/maps/terms

Bugs
====

For a current list of issues, visit
https://github.com/overviewer/Minecraft-Overviewer/issues

Feel free to comment on issues, report new issues, and vote on issues that are
important to you.

.. |Build Status| image:: https://secure.travis-ci.org/overviewer/Minecraft-Overviewer.png?branch=master
