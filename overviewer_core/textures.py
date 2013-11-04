#    This file is part of the Minecraft Overviewer.
#
#    Minecraft Overviewer is free software: you can redistribute it and/or
#    modify it under the terms of the GNU General Public License as published
#    by the Free Software Foundation, either version 3 of the License, or (at
#    your option) any later version.
#
#    Minecraft Overviewer is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
#    Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with the Overviewer.  If not, see <http://www.gnu.org/licenses/>.

import sys
import imp
import os
import os.path
import zipfile
from cStringIO import StringIO
import math
from random import randint
import numpy
from PIL import Image, ImageEnhance, ImageOps, ImageDraw
import logging
import functools

import util
from c_overviewer import alpha_over

class TextureException(Exception):
    "To be thrown when a texture is not found."
    pass


##
## Textures object
##
class Textures(object):
    """An object that generates a set of block sprites to use while
    rendering. It accepts a background color, north direction, and
    local textures path.
    """
    def __init__(self, texturepath=None, bgcolor=(26, 26, 26, 0), northdirection=0):
        self.bgcolor = bgcolor
        self.rotation = northdirection
        self.find_file_local_path = texturepath
        
        # not yet configurable
        self.texture_size = 24
        self.texture_dimensions = (self.texture_size, self.texture_size)
        
        # this is set in in generate()
        self.generated = False

        # see load_image_texture()
        self.texture_cache = {}
    
    ##
    ## pickle support
    ##
    
    def __getstate__(self):
        # we must get rid of the huge image lists, and other images
        attributes = self.__dict__.copy()
        for attr in ['blockmap', 'biome_grass_texture', 'watertexture', 'lavatexture', 'firetexture', 'portaltexture', 'lightcolor', 'grasscolor', 'foliagecolor', 'watercolor', 'texture_cache']:
            try:
                del attributes[attr]
            except KeyError:
                pass
        return attributes
    def __setstate__(self, attrs):
        # regenerate textures, if needed
        for attr, val in attrs.iteritems():
            setattr(self, attr, val)
        self.texture_cache = {}
        if self.generated:
            self.generate()
    
    ##
    ## The big one: generate()
    ##
    
    def generate(self):
        
        # generate biome grass mask
        self.biome_grass_texture = self.build_block(self.load_image_texture("textures/blocks/grass_top.png"), self.load_image_texture("textures/blocks/grass_side_overlay.png"))
        
        # generate the blocks
        global blockmap_generators
        global known_blocks, used_datas
        self.blockmap = [None] * max_blockid * max_data
        
        for (blockid, data), texgen in blockmap_generators.iteritems():
            tex = texgen(self, blockid, data)
            self.blockmap[blockid * max_data + data] = self.generate_texture_tuple(tex)
        
        if self.texture_size != 24:
            # rescale biome grass
            self.biome_grass_texture = self.biome_grass_texture.resize(self.texture_dimensions, Image.ANTIALIAS)
            
            # rescale the rest
            for i, tex in enumerate(blockmap):
                if tex is None:
                    continue
                block = tex[0]
                scaled_block = block.resize(self.texture_dimensions, Image.ANTIALIAS)
                blockmap[i] = self.generate_texture_tuple(scaled_block)
        
        self.generated = True
    
    ##
    ## Helpers for opening textures
    ##
    
    def find_file(self, filename, mode="rb", verbose=False):
        """Searches for the given file and returns an open handle to it.
        This searches the following locations in this order:
        
        * the textures_path given in the initializer
        this can be either a directory or a zip file (texture pack)
        * The program dir (same dir as overviewer.py)
        * On Darwin, in /Applications/Minecraft
        * Inside minecraft.jar, which is looked for at these locations
        
            * On Windows, at %APPDATA%/.minecraft/bin/minecraft.jar
            * On Darwin, at
                $HOME/Library/Application Support/minecraft/bin/minecraft.jar
            * at $HOME/.minecraft/bin/minecraft.jar

        * The overviewer_core/data/textures dir
        
        In all of these, files are searched for in '.', 'anim', 'misc/', and
        'environment/'.
        
        """

        # a list of subdirectories to search for a given file,
        # after the obvious '.'
        search_dirs = ['anim', 'misc', 'environment', 'item']
        search_zip_paths = [filename,] + [d + '/' + filename for d in search_dirs]
        def search_dir(base):
            """Search the given base dir for filename, in search_dirs."""
            for path in [os.path.join(base, d, filename) for d in ['',] + search_dirs]:
                if os.path.isfile(path):
                    return path
            return None

        if self.find_file_local_path:
            if os.path.isdir(self.find_file_local_path):
                path = search_dir(self.find_file_local_path)
                if path:
                    if verbose: logging.info("Found %s in '%s'", filename, path)
                    return open(path, mode)
            elif os.path.isfile(self.find_file_local_path):
                try:
                    pack = zipfile.ZipFile(self.find_file_local_path)
                    for packfilename in search_zip_paths:
                        try:
                            pack.getinfo(packfilename)
                            if verbose: logging.info("Found %s in '%s'", packfilename, self.find_file_local_path)
                            return pack.open(packfilename)
                        except (KeyError, IOError):
                            pass
                except (zipfile.BadZipfile, IOError):
                    pass

        programdir = util.get_program_path()
        path = search_dir(programdir)
        if path:
            if verbose: logging.info("Found %s in '%s'", filename, path)
            return open(path, mode)

        if sys.platform == "darwin":
            path = search_dir("/Applications/Minecraft")
            if path:
                if verbose: logging.info("Found %s in '%s'", filename, path)
                return open(path, mode)

        # Find minecraft.jar.
        jarpaths = []
        if "APPDATA" in os.environ:
            jarpaths.append( os.path.join(os.environ['APPDATA'], ".minecraft",
                "bin", "minecraft.jar"))
        if "HOME" in os.environ:
            jarpaths.append(os.path.join(os.environ['HOME'], "Library",
                    "Application Support", "minecraft","bin","minecraft.jar"))
            jarpaths.append(os.path.join(os.environ['HOME'], ".minecraft", "bin",
                    "minecraft.jar"))
        jarpaths.append(os.path.join(programdir,"minecraft.jar"))
        jarpaths.append(os.path.join(os.getcwd(), "minecraft.jar"))
        if self.find_file_local_path:
            jarpaths.append(os.path.join(self.find_file_local_path, "minecraft.jar"))

        for jarpath in jarpaths:
            if os.path.isfile(jarpath):
                jar = zipfile.ZipFile(jarpath)
                for jarfilename in search_zip_paths:
                    try:
                        jar.getinfo(jarfilename)
                        if verbose: logging.info("Found %s in '%s'", jarfilename, jarpath)
                        return jar.open(jarfilename)
                    except (KeyError, IOError), e:
                        pass
            elif os.path.isdir(jarpath):
                path = search_dir(jarpath)
                if path:
                    if verbose: logging.info("Found %s in '%s'", filename, path)
                    return open(path, 'rb')
        
        path = search_dir(os.path.join(programdir, "overviewer_core", "data", "textures"))
        if path:
            if verbose: logging.info("Found %s in '%s'", filename, path)
            return open(path, mode)
        elif hasattr(sys, "frozen") or imp.is_frozen("__main__"):
            # windows special case, when the package dir doesn't exist
            path = search_dir(os.path.join(programdir, "textures"))
            if path:
                if verbose: logging.info("Found %s in '%s'", filename, path)
                return open(path, mode)

        raise TextureException("Could not find the file `{0}'. Try specifying the 'texturepath' option in your config file.\nSet it to the directory where I can find {0}.\nAlso see <http://docs.overviewer.org/en/latest/running/#installing-the-textures>".format(filename))

    def load_image_texture(self, filename):
        # Textures may be animated or in a different resolution than 16x16.  
        # This method will always return a 16x16 image
        if filename in self.texture_cache:
            return self.texture_cache[filename]

        img = self.load_image(filename)

        w,h = img.size
        if w != h:
            img = img.crop((0,0,w,w))
        if w != 16:
            img = img.resize((16, 16), Image.ANTIALIAS)

        self.texture_cache[filename] = img
        return img

    def load_image(self, filename):
        """Returns an image object"""
        

        fileobj = self.find_file(filename)
        buffer = StringIO(fileobj.read())
        img = Image.open(buffer).convert("RGBA")
        return img



    def load_water(self):
        """Special-case function for loading water, handles
        MCPatcher-compliant custom animated water."""
        watertexture = getattr(self, "watertexture", None)
        if watertexture:
            return watertexture
        try:
            # try the MCPatcher case first
            watertexture = self.load_image("custom_water_still.png")
            watertexture = watertexture.crop((0, 0, watertexture.size[0], watertexture.size[0]))
        except TextureException:
            watertexture = self.load_image_texture("textures/blocks/water.png")
        self.watertexture = watertexture
        return watertexture

    def load_lava(self):
        """Special-case function for loading lava, handles
        MCPatcher-compliant custom animated lava."""
        lavatexture = getattr(self, "lavatexture", None)
        if lavatexture:
            return lavatexture
        try:
            # try the MCPatcher lava first, in case it's present
            lavatexture = self.load_image("custom_lava_still.png")
            lavatexture = lavatexture.crop((0, 0, lavatexture.size[0], lavatexture.size[0]))
        except TextureException:
            lavatexture = self.load_image_texture("textures/blocks/lava.png")
        self.lavatexture = lavatexture
        return lavatexture
    
    def load_fire(self):
        """Special-case function for loading fire, handles
        MCPatcher-compliant custom animated fire."""
        firetexture = getattr(self, "firetexture", None)
        if firetexture:
            return firetexture
        try:
            # try the MCPatcher case first
            firetextureNS = self.load_image("custom_fire_n_s.png")
            firetextureNS = firetextureNS.crop((0, 0, firetextureNS.size[0], firetextureNS.size[0]))
            firetextureEW = self.load_image("custom_fire_e_w.png")
            firetextureEW = firetextureEW.crop((0, 0, firetextureEW.size[0], firetextureEW.size[0]))
            firetexture = (firetextureNS,firetextureEW)
        except TextureException:
            fireNS = self.load_image_texture("textures/blocks/fire_0.png")
            fireEW = self.load_image_texture("textures/blocks/fire_1.png")
            firetexture = (fireNS, fireEW)
        self.firetexture = firetexture
        return firetexture
    
    def load_portal(self):
        """Special-case function for loading portal, handles
        MCPatcher-compliant custom animated portal."""
        portaltexture = getattr(self, "portaltexture", None)
        if portaltexture:
            return portaltexture
        try:
            # try the MCPatcher case first
            portaltexture = self.load_image("custom_portal.png")
            portaltexture = portaltexture.crop((0, 0, portaltexture.size[0], portaltexture.size[1]))
        except TextureException:
            portaltexture = self.load_image_texture("textures/blocks/portal.png")
        self.portaltexture = portaltexture
        return portaltexture
    
    def load_light_color(self):
        """Helper function to load the light color texture."""
        if hasattr(self, "lightcolor"):
            return self.lightcolor
        try:
            lightcolor = list(self.load_image("light_normal.png").getdata())
        except Exception:
            logging.warning("Light color image could not be found.")
            lightcolor = None
        self.lightcolor = lightcolor
        return lightcolor
    
    def load_grass_color(self):
        """Helper function to load the grass color texture."""
        if not hasattr(self, "grasscolor"):
            self.grasscolor = list(self.load_image("grasscolor.png").getdata())
        return self.grasscolor

    def load_foliage_color(self):
        """Helper function to load the foliage color texture."""
        if not hasattr(self, "foliagecolor"):
            self.foliagecolor = list(self.load_image("foliagecolor.png").getdata())
        return self.foliagecolor

    def load_water_color(self):
        """Helper function to load the water color texture."""
        if not hasattr(self, "watercolor"):
            self.watercolor = list(self.load_image("watercolor.png").getdata())
        return self.watercolor

    def _split_terrain(self, terrain):
        """Builds and returns a length 256 array of each 16x16 chunk
        of texture.
        """
        textures = []
        (terrain_width, terrain_height) = terrain.size
        texture_resolution = terrain_width / 16
        for y in xrange(16):
            for x in xrange(16):
                left = x*texture_resolution
                upper = y*texture_resolution
                right = left+texture_resolution
                lower = upper+texture_resolution
                region = terrain.transform(
                          (16, 16),
                          Image.EXTENT,
                          (left,upper,right,lower),
                          Image.BICUBIC)
                textures.append(region)

        return textures

    ##
    ## Image Transformation Functions
    ##

    @staticmethod
    def transform_image_top(img):
        """Takes a PIL image and rotates it left 45 degrees and shrinks the y axis
        by a factor of 2. Returns the resulting image, which will be 24x12 pixels

        """

        # Resize to 17x17, since the diagonal is approximately 24 pixels, a nice
        # even number that can be split in half twice
        img = img.resize((17, 17), Image.ANTIALIAS)

        # Build the Affine transformation matrix for this perspective
        transform = numpy.matrix(numpy.identity(3))
        # Translate up and left, since rotations are about the origin
        transform *= numpy.matrix([[1,0,8.5],[0,1,8.5],[0,0,1]])
        # Rotate 45 degrees
        ratio = math.cos(math.pi/4)
        #transform *= numpy.matrix("[0.707,-0.707,0;0.707,0.707,0;0,0,1]")
        transform *= numpy.matrix([[ratio,-ratio,0],[ratio,ratio,0],[0,0,1]])
        # Translate back down and right
        transform *= numpy.matrix([[1,0,-12],[0,1,-12],[0,0,1]])
        # scale the image down by a factor of 2
        transform *= numpy.matrix("[1,0,0;0,2,0;0,0,1]")

        transform = numpy.array(transform)[:2,:].ravel().tolist()

        newimg = img.transform((24,12), Image.AFFINE, transform)
        return newimg

    @staticmethod
    def transform_image_side(img):
        """Takes an image and shears it for the left side of the cube (reflect for
        the right side)"""

        # Size of the cube side before shear
        img = img.resize((12,12), Image.ANTIALIAS)

        # Apply shear
        transform = numpy.matrix(numpy.identity(3))
        transform *= numpy.matrix("[1,0,0;-0.5,1,0;0,0,1]")

        transform = numpy.array(transform)[:2,:].ravel().tolist()

        newimg = img.transform((12,18), Image.AFFINE, transform)
        return newimg

    @staticmethod
    def transform_image_slope(img):
        """Takes an image and shears it in the shape of a slope going up
        in the -y direction (reflect for +x direction). Used for minetracks"""

        # Take the same size as trasform_image_side
        img = img.resize((12,12), Image.ANTIALIAS)

        # Apply shear
        transform = numpy.matrix(numpy.identity(3))
        transform *= numpy.matrix("[0.75,-0.5,3;0.25,0.5,-3;0,0,1]")
        transform = numpy.array(transform)[:2,:].ravel().tolist()

        newimg = img.transform((24,24), Image.AFFINE, transform)

        return newimg


    @staticmethod
    def transform_image_angle(img, angle):
        """Takes an image an shears it in arbitrary angle with the axis of
        rotation being vertical.

        WARNING! Don't use angle = pi/2 (or multiplies), it will return
        a blank image (or maybe garbage).

        NOTE: angle is in the image not in game, so for the left side of a
        block angle = 30 degree.
        """

        # Take the same size as trasform_image_side
        img = img.resize((12,12), Image.ANTIALIAS)

        # some values
        cos_angle = math.cos(angle)
        sin_angle = math.sin(angle)

        # function_x and function_y are used to keep the result image in the 
        # same position, and constant_x and constant_y are the coordinates
        # for the center for angle = 0.
        constant_x = 6.
        constant_y = 6.
        function_x = 6.*(1-cos_angle)
        function_y = -6*sin_angle
        big_term = ( (sin_angle * (function_x + constant_x)) - cos_angle* (function_y + constant_y))/cos_angle

        # The numpy array is not really used, but is helpful to 
        # see the matrix used for the transformation.
        transform = numpy.array([[1./cos_angle, 0, -(function_x + constant_x)/cos_angle],
                                 [-sin_angle/(cos_angle), 1., big_term ],
                                 [0, 0, 1.]])

        transform = tuple(transform[0]) + tuple(transform[1])

        newimg = img.transform((24,24), Image.AFFINE, transform)

        return newimg


    def build_block(self, top, side):
        """From a top texture and a side texture, build a block image.
        top and side should be 16x16 image objects. Returns a 24x24 image

        """
        img = Image.new("RGBA", (24,24), self.bgcolor)

        original_texture = top.copy()
        top = self.transform_image_top(top)

        if not side:
            alpha_over(img, top, (0,0), top)
            return img

        side = self.transform_image_side(side)
        otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

        # Darken the sides slightly. These methods also affect the alpha layer,
        # so save them first (we don't want to "darken" the alpha layer making
        # the block transparent)
        sidealpha = side.split()[3]
        side = ImageEnhance.Brightness(side).enhance(0.9)
        side.putalpha(sidealpha)
        othersidealpha = otherside.split()[3]
        otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
        otherside.putalpha(othersidealpha)

        alpha_over(img, top, (0,0), top)
        alpha_over(img, side, (0,6), side)
        alpha_over(img, otherside, (12,6), otherside)

        # Manually touch up 6 pixels that leave a gap because of how the
        # shearing works out. This makes the blocks perfectly tessellate-able
        for x,y in [(13,23), (17,21), (21,19)]:
            # Copy a pixel to x,y from x-1,y
            img.putpixel((x,y), img.getpixel((x-1,y)))
        for x,y in [(3,4), (7,2), (11,0)]:
            # Copy a pixel to x,y from x+1,y
            img.putpixel((x,y), img.getpixel((x+1,y)))

        return img

    def build_full_block(self, top, side1, side2, side3, side4, bottom=None):
        """From a top texture, a bottom texture and 4 different side textures,
        build a full block with four differnts faces. All images should be 16x16 
        image objects. Returns a 24x24 image. Can be used to render any block.

        side1 is in the -y face of the cube     (top left, east)
        side2 is in the +x                      (top right, south)
        side3 is in the -x                      (bottom left, north)
        side4 is in the +y                      (bottom right, west)

        A non transparent block uses top, side 3 and side 4.

        If top is a tuple then first item is the top image and the second
        item is an increment (integer) from 0 to 16 (pixels in the
        original minecraft texture). This increment will be used to crop the
        side images and to paste the top image increment pixels lower, so if
        you use an increment of 8, it will draw a half-block.

        NOTE: this method uses the bottom of the texture image (as done in 
        minecraft with beds and cackes)

        """

        increment = 0
        if isinstance(top, tuple):
            increment = int(round((top[1] / 16.)*12.)) # range increment in the block height in pixels (half texture size)
            crop_height = increment
            top = top[0]
            if side1 != None:
                side1 = side1.copy()
                ImageDraw.Draw(side1).rectangle((0, 0,16,crop_height),outline=(0,0,0,0),fill=(0,0,0,0))
            if side2 != None:
                side2 = side2.copy()
                ImageDraw.Draw(side2).rectangle((0, 0,16,crop_height),outline=(0,0,0,0),fill=(0,0,0,0))
            if side3 != None:
                side3 = side3.copy()
                ImageDraw.Draw(side3).rectangle((0, 0,16,crop_height),outline=(0,0,0,0),fill=(0,0,0,0))
            if side4 != None:
                side4 = side4.copy()
                ImageDraw.Draw(side4).rectangle((0, 0,16,crop_height),outline=(0,0,0,0),fill=(0,0,0,0))

        img = Image.new("RGBA", (24,24), self.bgcolor)

        # first back sides
        if side1 != None :
            side1 = self.transform_image_side(side1)
            side1 = side1.transpose(Image.FLIP_LEFT_RIGHT)

            # Darken this side.
            sidealpha = side1.split()[3]
            side1 = ImageEnhance.Brightness(side1).enhance(0.9)
            side1.putalpha(sidealpha)        

            alpha_over(img, side1, (0,0), side1)


        if side2 != None :
            side2 = self.transform_image_side(side2)

            # Darken this side.
            sidealpha2 = side2.split()[3]
            side2 = ImageEnhance.Brightness(side2).enhance(0.8)
            side2.putalpha(sidealpha2)

            alpha_over(img, side2, (12,0), side2)

        if bottom != None :
            bottom = self.transform_image_top(bottom)
            alpha_over(img, bottom, (0,12), bottom)

        # front sides
        if side3 != None :
            side3 = self.transform_image_side(side3)

            # Darken this side
            sidealpha = side3.split()[3]
            side3 = ImageEnhance.Brightness(side3).enhance(0.9)
            side3.putalpha(sidealpha)

            alpha_over(img, side3, (0,6), side3)

        if side4 != None :
            side4 = self.transform_image_side(side4)
            side4 = side4.transpose(Image.FLIP_LEFT_RIGHT)

            # Darken this side
            sidealpha = side4.split()[3]
            side4 = ImageEnhance.Brightness(side4).enhance(0.8)
            side4.putalpha(sidealpha)

            alpha_over(img, side4, (12,6), side4)

        if top != None :
            top = self.transform_image_top(top)
            alpha_over(img, top, (0, increment), top)

        return img

    def build_sprite(self, side):
        """From a side texture, create a sprite-like texture such as those used
        for spiderwebs or flowers."""
        img = Image.new("RGBA", (24,24), self.bgcolor)

        side = self.transform_image_side(side)
        otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

        alpha_over(img, side, (6,3), side)
        alpha_over(img, otherside, (6,3), otherside)
        return img

    def build_billboard(self, tex):
        """From a texture, create a billboard-like texture such as
        those used for tall grass or melon stems.
        """
        img = Image.new("RGBA", (24,24), self.bgcolor)

        front = tex.resize((14, 11), Image.ANTIALIAS)
        alpha_over(img, front, (5,9))
        return img

    def generate_opaque_mask(self, img):
        """ Takes the alpha channel of the image and generates a mask
        (used for lighting the block) that deprecates values of alpha
        smallers than 50, and sets every other value to 255. """

        alpha = img.split()[3]
        return alpha.point(lambda a: int(min(a, 25.5) * 10))

    def tint_texture(self, im, c):
        # apparently converting to grayscale drops the alpha channel?
        i = ImageOps.colorize(ImageOps.grayscale(im), (0,0,0), c)
        i.putalpha(im.split()[3]); # copy the alpha band back in. assuming RGBA
        return i

    def generate_texture_tuple(self, img):
        """ This takes an image and returns the needed tuple for the
        blockmap array."""
        if img is None:
            return None
        return (img, self.generate_opaque_mask(img))

##
## The other big one: @material and associated framework
##

# global variables to collate information in @material decorators
blockmap_generators = {}

known_blocks = set()
used_datas = set()
max_blockid = 0
max_data = 0

transparent_blocks = set()
solid_blocks = set()
fluid_blocks = set()
nospawn_blocks = set()
nodata_blocks = set()

# the material registration decorator
def material(blockid=[], data=[0], **kwargs):
    # mapping from property name to the set to store them in
    properties = {"transparent" : transparent_blocks, "solid" : solid_blocks, "fluid" : fluid_blocks, "nospawn" : nospawn_blocks, "nodata" : nodata_blocks}
    
    # make sure blockid and data are iterable
    try:
        iter(blockid)
    except:
        blockid = [blockid,]
    try:
        iter(data)
    except:
        data = [data,]
        
    def inner_material(func):
        global blockmap_generators
        global max_data, max_blockid

        # create a wrapper function with a known signature
        @functools.wraps(func)
        def func_wrapper(texobj, blockid, data):
            return func(texobj, blockid, data)
        
        used_datas.update(data)
        if max(data) >= max_data:
            max_data = max(data) + 1
        
        for block in blockid:
            # set the property sets appropriately
            known_blocks.update([block])
            if block >= max_blockid:
                max_blockid = block + 1
            for prop in properties:
                try:
                    if block in kwargs.get(prop, []):
                        properties[prop].update([block])
                except TypeError:
                    if kwargs.get(prop, False):
                        properties[prop].update([block])
            
            # populate blockmap_generators with our function
            for d in data:
                blockmap_generators[(block, d)] = func_wrapper
        
        return func_wrapper
    return inner_material

# shortcut function for pure blocks, default to solid, nodata
def block(blockid=[], top_image=None, side_image=None, **kwargs):
    new_kwargs = {'solid' : True, 'nodata' : True}
    new_kwargs.update(kwargs)
    
    if top_image is None:
        raise ValueError("top_image was not provided")
    
    if side_image is None:
        side_image = top_image
    
    @material(blockid=blockid, **new_kwargs)
    def inner_block(self, unused_id, unused_data):
        return self.build_block(self.load_image_texture(top_image), self.load_image_texture(side_image))
    return inner_block

# shortcut function for sprite blocks, defaults to transparent, nodata
def sprite(blockid=[], imagename=None, **kwargs):
    new_kwargs = {'transparent' : True, 'nodata' : True}
    new_kwargs.update(kwargs)
    
    if imagename is None:
        raise ValueError("imagename was not provided")
    
    @material(blockid=blockid, **new_kwargs)
    def inner_sprite(self, unused_id, unused_data):
        return self.build_sprite(self.load_image_texture(imagename))
    return inner_sprite

# shortcut function for billboard blocks, defaults to transparent, nodata
def billboard(blockid=[], imagename=None, **kwargs):
    new_kwargs = {'transparent' : True, 'nodata' : True}
    new_kwargs.update(kwargs)
    
    if imagename is None:
        raise ValueError("imagename was not provided")
    
    @material(blockid=blockid, **new_kwargs)
    def inner_billboard(self, unused_id, unused_data):
        return self.build_billboard(self.load_image_texture(imagename))
    return inner_billboard

##
## and finally: actual texture definitions
##

# stone
block(blockid=1, top_image="textures/blocks/stone.png")

@material(blockid=2, data=range(11)+[0x10,], solid=True)
def grass(self, blockid, data):
    # 0x10 bit means SNOW
    side_img = self.load_image_texture("textures/blocks/grass_side.png")
    if data & 0x10:
        side_img = self.load_image_texture("textures/blocks/snow_side.png")
    img = self.build_block(self.load_image_texture("textures/blocks/grass_top.png"), side_img)
    if not data & 0x10:
        alpha_over(img, self.biome_grass_texture, (0, 0), self.biome_grass_texture)
    return img

# dirt
block(blockid=3, top_image="textures/blocks/dirt.png")
# cobblestone
block(blockid=4, top_image="textures/blocks/stonebrick.png")

# wooden planks
@material(blockid=5, data=range(4), solid=True)
def wooden_planks(self, blockid, data):
    if data == 0: # normal
        return self.build_block(self.load_image_texture("textures/blocks/wood.png"), self.load_image_texture("textures/blocks/wood.png"))
    if data == 1: # pine
        return self.build_block(self.load_image_texture("textures/blocks/wood_spruce.png"),self.load_image_texture("textures/blocks/wood_spruce.png"))
    if data == 2: # birch
        return self.build_block(self.load_image_texture("textures/blocks/wood_birch.png"),self.load_image_texture("textures/blocks/wood_birch.png"))
    if data == 3: # jungle wood
        return self.build_block(self.load_image_texture("textures/blocks/wood_jungle.png"),self.load_image_texture("textures/blocks/wood_jungle.png"))

@material(blockid=6, data=range(16), transparent=True)
def saplings(self, blockid, data):
    # usual saplings
    tex = self.load_image_texture("textures/blocks/sapling.png")
    
    if data & 0x3 == 1: # spruce sapling
        tex = self.load_image_texture("textures/blocks/sapling_spruce.png")
    elif data & 0x3 == 2: # birch sapling
        tex = self.load_image_texture("textures/blocks/sapling_birch.png")
    elif data & 0x3 == 3: # jungle sapling
        tex = self.load_image_texture("textures/blocks/sapling_jungle.png")
    return self.build_sprite(tex)

# bedrock
block(blockid=7, top_image="textures/blocks/bedrock.png")

@material(blockid=8, data=range(16), fluid=True, transparent=True, nospawn=True)
def water(self, blockid, data):
    watertex = self.load_water()
    return self.build_block(watertex, watertex)

# other water, glass, and ice (no inner surfaces)
# uses pseudo-ancildata found in iterate.c
@material(blockid=[9, 20, 79], data=range(32), fluid=(9,), transparent=True, nospawn=True, solid=(79, 20))
def no_inner_surfaces(self, blockid, data):
    if blockid == 9:
        texture = self.load_water()
    elif blockid == 20:
        texture = self.load_image_texture("textures/blocks/glass.png")
    else:
        texture = self.load_image_texture("textures/blocks/ice.png")
        
    if (data & 0b10000) == 16:
        top = texture
    else:
        top = None
        
    if (data & 0b0001) == 1:
        side1 = texture    # top left
    else:
        side1 = None
    
    if (data & 0b1000) == 8:
        side2 = texture    # top right           
    else:
        side2 = None
    
    if (data & 0b0010) == 2:
        side3 = texture    # bottom left    
    else:
        side3 = None
    
    if (data & 0b0100) == 4:
        side4 = texture    # bottom right
    else:
        side4 = None
    
    # if nothing shown do not draw at all
    if top is None and side3 is None and side4 is None:
        return None
    
    img = self.build_full_block(top,None,None,side3,side4)
    return img

@material(blockid=[10, 11], data=range(16), fluid=True, transparent=False, nospawn=True)
def lava(self, blockid, data):
    lavatex = self.load_lava()
    return self.build_block(lavatex, lavatex)

# sand
block(blockid=12, top_image="textures/blocks/sand.png")
# gravel
block(blockid=13, top_image="textures/blocks/gravel.png")
# gold ore
block(blockid=14, top_image="textures/blocks/oreGold.png")
# iron ore
block(blockid=15, top_image="textures/blocks/oreIron.png")
# coal ore
block(blockid=16, top_image="textures/blocks/oreCoal.png")

@material(blockid=17, data=range(12), solid=True)
def wood(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose textures
    top = self.load_image_texture("textures/blocks/tree_top.png")
    if wood_type == 0: # normal
        side = self.load_image_texture("textures/blocks/tree_side.png")
    if wood_type == 1: # spruce
        side = self.load_image_texture("textures/blocks/tree_spruce.png")
    if wood_type == 2: # birch
        side = self.load_image_texture("textures/blocks/tree_birch.png")
    if wood_type == 3: # jungle wood
        side = self.load_image_texture("textures/blocks/tree_jungle.png")

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

@material(blockid=18, data=range(16), transparent=True, solid=True)
def leaves(self, blockid, data):
    # mask out the bits 4 and 8
    # they are used for player placed and check-for-decay blocks
    data = data & 0x3
    t = self.load_image_texture("textures/blocks/leaves.png")
    if data == 1:
        # pine!
        t = self.load_image_texture("textures/blocks/leaves_spruce.png")
    elif data == 3:
        # jungle tree
        t = self.load_image_texture("textures/blocks/leaves_jungle.png")
    return self.build_block(t, t)

# sponge
block(blockid=19, top_image="textures/blocks/sponge.png")
# lapis lazuli ore
block(blockid=21, top_image="textures/blocks/oreLapis.png")
# lapis lazuli block
block(blockid=22, top_image="textures/blocks/blockLapis.png")

# dispensers, dropper, furnaces, and burning furnaces
@material(blockid=[23, 61, 62, 158], data=range(6), solid=True)
def furnaces(self, blockid, data):
    # first, do the rotation if needed
    if self.rotation == 1:
        if data == 2: data = 5
        elif data == 3: data = 4
        elif data == 4: data = 2
        elif data == 5: data = 3
    elif self.rotation == 2:
        if data == 2: data = 3
        elif data == 3: data = 2
        elif data == 4: data = 5
        elif data == 5: data = 4
    elif self.rotation == 3:
        if data == 2: data = 4
        elif data == 3: data = 5
        elif data == 4: data = 3
        elif data == 5: data = 2
    
    top = self.load_image_texture("textures/blocks/furnace_top.png")
    side = self.load_image_texture("textures/blocks/furnace_side.png")
    
    if blockid == 61:
        front = self.load_image_texture("textures/blocks/furnace_front.png")
    elif blockid == 62:
        front = self.load_image_texture("textures/blocks/furnace_front_lit.png")
    elif blockid == 23:
        front = self.load_image_texture("textures/blocks/dispenser_front.png")
        if data == 0: # dispenser pointing down
            return self.build_block(top, top)
        elif data == 1: # dispenser pointing up
            dispenser_top = self.load_image_texture("textures/blocks/dispenser_front_vertical.png")
            return self.build_block(dispenser_top, top)
    elif blockid == 158:
        front = self.load_image_texture("textures/blocks/dropper_front.png")
        if data == 0: # dropper pointing down
            return self.build_block(top, top)
        elif data == 1: # dispenser pointing up
            dropper_top = self.load_image_texture("textures/blocks/dropper_front_vertical.png")
            return self.build_block(dropper_top, top)
    
    if data == 3: # pointing west
        return self.build_full_block(top, None, None, side, front)
    elif data == 4: # pointing north
        return self.build_full_block(top, None, None, front, side)
    else: # in any other direction the front can't be seen
        return self.build_full_block(top, None, None, side, side)

# sandstone
@material(blockid=24, data=range(3), solid=True)
def sandstone(self, blockid, data):
    top = self.load_image_texture("textures/blocks/sandstone_top.png")
    if data == 0: # normal
        return self.build_block(top, self.load_image_texture("textures/blocks/sandstone_side.png"))
    if data == 1: # hieroglyphic
        return self.build_block(top, self.load_image_texture("textures/blocks/sandstone_carved.png"))
    if data == 2: # soft
        return self.build_block(top, self.load_image_texture("textures/blocks/sandstone_smooth.png"))

# note block
block(blockid=25, top_image="textures/blocks/musicBlock.png")

@material(blockid=26, data=range(12), transparent=True, nospawn=True)
def bed(self, blockid, data):
    # first get rotation done
    # Masked to not clobber block head/foot info
    if self.rotation == 1:
        if (data & 0b0011) == 0: data = data & 0b1100 | 1
        elif (data & 0b0011) == 1: data = data & 0b1100 | 2
        elif (data & 0b0011) == 2: data = data & 0b1100 | 3
        elif (data & 0b0011) == 3: data = data & 0b1100 | 0
    elif self.rotation == 2:
        if (data & 0b0011) == 0: data = data & 0b1100 | 2
        elif (data & 0b0011) == 1: data = data & 0b1100 | 3
        elif (data & 0b0011) == 2: data = data & 0b1100 | 0
        elif (data & 0b0011) == 3: data = data & 0b1100 | 1
    elif self.rotation == 3:
        if (data & 0b0011) == 0: data = data & 0b1100 | 3
        elif (data & 0b0011) == 1: data = data & 0b1100 | 0
        elif (data & 0b0011) == 2: data = data & 0b1100 | 1
        elif (data & 0b0011) == 3: data = data & 0b1100 | 2
    
    increment = 8
    left_face = None
    right_face = None
    if data & 0x8 == 0x8: # head of the bed
        top = self.load_image_texture("textures/blocks/bed_head_top.png")
        if data & 0x00 == 0x00: # head pointing to West
            top = top.copy().rotate(270)
            left_face = self.load_image_texture("textures/blocks/bed_head_side.png")
            right_face = self.load_image_texture("textures/blocks/bed_head_end.png")
        if data & 0x01 == 0x01: # ... North
            top = top.rotate(270)
            left_face = self.load_image_texture("textures/blocks/bed_head_end.png")
            right_face = self.load_image_texture("textures/blocks/bed_head_side.png")
        if data & 0x02 == 0x02: # East
            top = top.rotate(180)
            left_face = self.load_image_texture("textures/blocks/bed_head_side.png").transpose(Image.FLIP_LEFT_RIGHT)
            right_face = None
        if data & 0x03 == 0x03: # South
            right_face = None
            right_face = self.load_image_texture("textures/blocks/bed_head_side.png").transpose(Image.FLIP_LEFT_RIGHT)
    
    else: # foot of the bed
        top = self.load_image_texture("textures/blocks/bed_feet_top.png")
        if data & 0x00 == 0x00: # head pointing to West
            top = top.rotate(270)
            left_face = self.load_image_texture("textures/blocks/bed_feet_side.png")
            right_face = None
        if data & 0x01 == 0x01: # ... North
            top = top.rotate(270)
            left_face = None
            right_face = self.load_image_texture("textures/blocks/bed_feet_side.png")
        if data & 0x02 == 0x02: # East
            top = top.rotate(180)
            left_face = self.load_image_texture("textures/blocks/bed_feet_side.png").transpose(Image.FLIP_LEFT_RIGHT)
            right_face = self.load_image_texture("textures/blocks/bed_feet_end.png").transpose(Image.FLIP_LEFT_RIGHT)
        if data & 0x03 == 0x03: # South
            left_face = self.load_image_texture("textures/blocks/bed_feet_end.png")
            right_face = self.load_image_texture("textures/blocks/bed_feet_side.png").transpose(Image.FLIP_LEFT_RIGHT)
    
    top = (top, increment)
    return self.build_full_block(top, None, None, left_face, right_face)

# powered, detector, activator and normal rails
@material(blockid=[27, 28, 66, 157], data=range(14), transparent=True)
def rails(self, blockid, data):
    # first, do rotation
    # Masked to not clobber powered rail on/off info
    # Ascending and flat straight
    if self.rotation == 1:
        if (data & 0b0111) == 0: data = data & 0b1000 | 1
        elif (data & 0b0111) == 1: data = data & 0b1000 | 0
        elif (data & 0b0111) == 2: data = data & 0b1000 | 5
        elif (data & 0b0111) == 3: data = data & 0b1000 | 4
        elif (data & 0b0111) == 4: data = data & 0b1000 | 2
        elif (data & 0b0111) == 5: data = data & 0b1000 | 3
    elif self.rotation == 2:
        if (data & 0b0111) == 2: data = data & 0b1000 | 3
        elif (data & 0b0111) == 3: data = data & 0b1000 | 2
        elif (data & 0b0111) == 4: data = data & 0b1000 | 5
        elif (data & 0b0111) == 5: data = data & 0b1000 | 4
    elif self.rotation == 3:
        if (data & 0b0111) == 0: data = data & 0b1000 | 1
        elif (data & 0b0111) == 1: data = data & 0b1000 | 0
        elif (data & 0b0111) == 2: data = data & 0b1000 | 4
        elif (data & 0b0111) == 3: data = data & 0b1000 | 5
        elif (data & 0b0111) == 4: data = data & 0b1000 | 3
        elif (data & 0b0111) == 5: data = data & 0b1000 | 2
    if blockid == 66: # normal minetrack only
        #Corners
        if self.rotation == 1:
            if data == 6: data = 7
            elif data == 7: data = 8
            elif data == 8: data = 6
            elif data == 9: data = 9
        elif self.rotation == 2:
            if data == 6: data = 8
            elif data == 7: data = 9
            elif data == 8: data = 6
            elif data == 9: data = 7
        elif self.rotation == 3:
            if data == 6: data = 9
            elif data == 7: data = 6
            elif data == 8: data = 8
            elif data == 9: data = 7
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    if blockid == 27: # powered rail
        if data & 0x8 == 0: # unpowered
            raw_straight = self.load_image_texture("textures/blocks/goldenRail.png")
            raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")    # they don't exist but make the code
                                                # much simplier
        elif data & 0x8 == 0x8: # powered
            raw_straight = self.load_image_texture("textures/blocks/goldenRail_powered.png")
            raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")    # leave corners for code simplicity
        # filter the 'powered' bit
        data = data & 0x7
            
    elif blockid == 28: # detector rail
        raw_straight = self.load_image_texture("textures/blocks/detectorRail.png")
        raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")    # leave corners for code simplicity
        
    elif blockid == 66: # normal rail
        raw_straight = self.load_image_texture("textures/blocks/rail.png")
        raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")

    elif blockid == 157: # activator rail
        if data & 0x8 == 0: # unpowered
            raw_straight = self.load_image_texture("textures/blocks/activatorRail.png")
            raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")    # they don't exist but make the code
                                                # much simplier
        elif data & 0x8 == 0x8: # powered
            raw_straight = self.load_image_texture("textures/blocks/activatorRail_powered.png")
            raw_corner = self.load_image_texture("textures/blocks/rail_turn.png")    # leave corners for code simplicity
        # filter the 'powered' bit
        data = data & 0x7
        
    ## use transform_image to scale and shear
    if data == 0:
        track = self.transform_image_top(raw_straight)
        alpha_over(img, track, (0,12), track)
    elif data == 6:
        track = self.transform_image_top(raw_corner)
        alpha_over(img, track, (0,12), track)
    elif data == 7:
        track = self.transform_image_top(raw_corner.rotate(270))
        alpha_over(img, track, (0,12), track)
    elif data == 8:
        # flip
        track = self.transform_image_top(raw_corner.transpose(Image.FLIP_TOP_BOTTOM).rotate(90))
        alpha_over(img, track, (0,12), track)
    elif data == 9:
        track = self.transform_image_top(raw_corner.transpose(Image.FLIP_TOP_BOTTOM))
        alpha_over(img, track, (0,12), track)
    elif data == 1:
        track = self.transform_image_top(raw_straight.rotate(90))
        alpha_over(img, track, (0,12), track)
        
    #slopes
    elif data == 2: # slope going up in +x direction
        track = self.transform_image_slope(raw_straight)
        track = track.transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, track, (2,0), track)
        # the 2 pixels move is needed to fit with the adjacent tracks
        
    elif data == 3: # slope going up in -x direction
        # tracks are sprites, in this case we are seeing the "side" of 
        # the sprite, so draw a line to make it beautiful.
        ImageDraw.Draw(img).line([(11,11),(23,17)],fill=(164,164,164))
        # grey from track texture (exterior grey).
        # the track doesn't start from image corners, be carefull drawing the line!
    elif data == 4: # slope going up in -y direction
        track = self.transform_image_slope(raw_straight)
        alpha_over(img, track, (0,0), track)
        
    elif data == 5: # slope going up in +y direction
        # same as "data == 3"
        ImageDraw.Draw(img).line([(1,17),(12,11)],fill=(164,164,164))
        
    return img

# sticky and normal piston body
@material(blockid=[29, 33], data=[0,1,2,3,4,5,8,9,10,11,12,13], transparent=True, solid=True, nospawn=True)
def piston(self, blockid, data):
    # first, rotation
    # Masked to not clobber block head/foot info
    if self.rotation == 1:
        if (data & 0b0111) == 2: data = data & 0b1000 | 5
        elif (data & 0b0111) == 3: data = data & 0b1000 | 4
        elif (data & 0b0111) == 4: data = data & 0b1000 | 2
        elif (data & 0b0111) == 5: data = data & 0b1000 | 3
    elif self.rotation == 2:
        if (data & 0b0111) == 2: data = data & 0b1000 | 3
        elif (data & 0b0111) == 3: data = data & 0b1000 | 2
        elif (data & 0b0111) == 4: data = data & 0b1000 | 5
        elif (data & 0b0111) == 5: data = data & 0b1000 | 4
    elif self.rotation == 3:
        if (data & 0b0111) == 2: data = data & 0b1000 | 4
        elif (data & 0b0111) == 3: data = data & 0b1000 | 5
        elif (data & 0b0111) == 4: data = data & 0b1000 | 3
        elif (data & 0b0111) == 5: data = data & 0b1000 | 2
    
    if blockid == 29: # sticky
        piston_t = self.load_image_texture("textures/blocks/piston_top_sticky.png").copy()
    else: # normal
        piston_t = self.load_image_texture("textures/blocks/piston_top.png").copy()
        
    # other textures
    side_t = self.load_image_texture("textures/blocks/piston_side.png").copy()
    back_t = self.load_image_texture("textures/blocks/piston_bottom.png").copy()
    interior_t = self.load_image_texture("textures/blocks/piston_inner_top.png").copy()
    
    if data & 0x08 == 0x08: # pushed out, non full blocks, tricky stuff
        # remove piston texture from piston body
        ImageDraw.Draw(side_t).rectangle((0, 0,16,3),outline=(0,0,0,0),fill=(0,0,0,0))
        
        if data & 0x07 == 0x0: # down
            side_t = side_t.rotate(180)
            img = self.build_full_block(back_t ,None ,None ,side_t, side_t)
            
        elif data & 0x07 == 0x1: # up
            img = self.build_full_block((interior_t, 4) ,None ,None ,side_t, side_t)
            
        elif data & 0x07 == 0x2: # east
            img = self.build_full_block(side_t , None, None ,side_t.rotate(90), back_t)
            
        elif data & 0x07 == 0x3: # west
            img = self.build_full_block(side_t.rotate(180) ,None ,None ,side_t.rotate(270), None)
            temp = self.transform_image_side(interior_t)
            temp = temp.transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, temp, (9,5), temp)
            
        elif data & 0x07 == 0x4: # north
            img = self.build_full_block(side_t.rotate(90) ,None ,None , None, side_t.rotate(270))
            temp = self.transform_image_side(interior_t)
            alpha_over(img, temp, (3,5), temp)
            
        elif data & 0x07 == 0x5: # south
            img = self.build_full_block(side_t.rotate(270) ,None , None ,back_t, side_t.rotate(90))

    else: # pushed in, normal full blocks, easy stuff
        if data & 0x07 == 0x0: # down
            side_t = side_t.rotate(180)
            img = self.build_full_block(back_t ,None ,None ,side_t, side_t)
        elif data & 0x07 == 0x1: # up
            img = self.build_full_block(piston_t ,None ,None ,side_t, side_t)
        elif data & 0x07 == 0x2: # east 
            img = self.build_full_block(side_t ,None ,None ,side_t.rotate(90), back_t)
        elif data & 0x07 == 0x3: # west
            img = self.build_full_block(side_t.rotate(180) ,None ,None ,side_t.rotate(270), piston_t)
        elif data & 0x07 == 0x4: # north
            img = self.build_full_block(side_t.rotate(90) ,None ,None ,piston_t, side_t.rotate(270))
        elif data & 0x07 == 0x5: # south
            img = self.build_full_block(side_t.rotate(270) ,None ,None ,back_t, side_t.rotate(90))
            
    return img

# sticky and normal piston shaft
@material(blockid=34, data=[0,1,2,3,4,5,8,9,10,11,12,13], transparent=True, nospawn=True)
def piston_extension(self, blockid, data):
    # first, rotation
    # Masked to not clobber block head/foot info
    if self.rotation == 1:
        if (data & 0b0111) == 2: data = data & 0b1000 | 5
        elif (data & 0b0111) == 3: data = data & 0b1000 | 4
        elif (data & 0b0111) == 4: data = data & 0b1000 | 2
        elif (data & 0b0111) == 5: data = data & 0b1000 | 3
    elif self.rotation == 2:
        if (data & 0b0111) == 2: data = data & 0b1000 | 3
        elif (data & 0b0111) == 3: data = data & 0b1000 | 2
        elif (data & 0b0111) == 4: data = data & 0b1000 | 5
        elif (data & 0b0111) == 5: data = data & 0b1000 | 4
    elif self.rotation == 3:
        if (data & 0b0111) == 2: data = data & 0b1000 | 4
        elif (data & 0b0111) == 3: data = data & 0b1000 | 5
        elif (data & 0b0111) == 4: data = data & 0b1000 | 3
        elif (data & 0b0111) == 5: data = data & 0b1000 | 2
    
    if (data & 0x8) == 0x8: # sticky
        piston_t = self.load_image_texture("textures/blocks/piston_top_sticky.png").copy()
    else: # normal
        piston_t = self.load_image_texture("textures/blocks/piston_top.png").copy()
    
    # other textures
    side_t = self.load_image_texture("textures/blocks/piston_side.png").copy()
    back_t = self.load_image_texture("textures/blocks/piston_top.png").copy()
    # crop piston body
    ImageDraw.Draw(side_t).rectangle((0, 4,16,16),outline=(0,0,0,0),fill=(0,0,0,0))
    
    # generate the horizontal piston extension stick
    h_stick = Image.new("RGBA", (24,24), self.bgcolor)
    temp = self.transform_image_side(side_t)
    alpha_over(h_stick, temp, (1,7), temp)
    temp = self.transform_image_top(side_t.rotate(90))
    alpha_over(h_stick, temp, (1,1), temp)
    # Darken it
    sidealpha = h_stick.split()[3]
    h_stick = ImageEnhance.Brightness(h_stick).enhance(0.85)
    h_stick.putalpha(sidealpha)
    
    # generate the vertical piston extension stick
    v_stick = Image.new("RGBA", (24,24), self.bgcolor)
    temp = self.transform_image_side(side_t.rotate(90))
    alpha_over(v_stick, temp, (12,6), temp)
    temp = temp.transpose(Image.FLIP_LEFT_RIGHT)
    alpha_over(v_stick, temp, (1,6), temp)
    # Darken it
    sidealpha = v_stick.split()[3]
    v_stick = ImageEnhance.Brightness(v_stick).enhance(0.85)
    v_stick.putalpha(sidealpha)
    
    # Piston orientation is stored in the 3 first bits
    if data & 0x07 == 0x0: # down
        side_t = side_t.rotate(180)
        img = self.build_full_block((back_t, 12) ,None ,None ,side_t, side_t)
        alpha_over(img, v_stick, (0,-3), v_stick)
    elif data & 0x07 == 0x1: # up
        img = Image.new("RGBA", (24,24), self.bgcolor)
        img2 = self.build_full_block(piston_t ,None ,None ,side_t, side_t)
        alpha_over(img, v_stick, (0,4), v_stick)
        alpha_over(img, img2, (0,0), img2)
    elif data & 0x07 == 0x2: # east 
        img = self.build_full_block(side_t ,None ,None ,side_t.rotate(90), None)
        temp = self.transform_image_side(back_t).transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, temp, (2,2), temp)
        alpha_over(img, h_stick, (6,3), h_stick)
    elif data & 0x07 == 0x3: # west
        img = Image.new("RGBA", (24,24), self.bgcolor)
        img2 = self.build_full_block(side_t.rotate(180) ,None ,None ,side_t.rotate(270), piston_t)
        alpha_over(img, h_stick, (0,0), h_stick)
        alpha_over(img, img2, (0,0), img2)            
    elif data & 0x07 == 0x4: # north
        img = self.build_full_block(side_t.rotate(90) ,None ,None , piston_t, side_t.rotate(270))
        alpha_over(img, h_stick.transpose(Image.FLIP_LEFT_RIGHT), (0,0), h_stick.transpose(Image.FLIP_LEFT_RIGHT))
    elif data & 0x07 == 0x5: # south
        img = Image.new("RGBA", (24,24), self.bgcolor)
        img2 = self.build_full_block(side_t.rotate(270) ,None ,None ,None, side_t.rotate(90))
        temp = self.transform_image_side(back_t)
        alpha_over(img2, temp, (10,2), temp)
        alpha_over(img, img2, (0,0), img2)
        alpha_over(img, h_stick.transpose(Image.FLIP_LEFT_RIGHT), (-3,2), h_stick.transpose(Image.FLIP_LEFT_RIGHT))
        
    return img

# cobweb
sprite(blockid=30, imagename="textures/blocks/web.png", nospawn=True)

@material(blockid=31, data=range(3), transparent=True)
def tall_grass(self, blockid, data):
    if data == 0: # dead shrub
        texture = self.load_image_texture("textures/blocks/deadbush.png")
    elif data == 1: # tall grass
        texture = self.load_image_texture("textures/blocks/tallgrass.png")
    elif data == 2: # fern
        texture = self.load_image_texture("textures/blocks/fern.png")
    
    return self.build_billboard(texture)

# dead bush
billboard(blockid=32, imagename="textures/blocks/deadbush.png")

@material(blockid=35, data=range(16), solid=True)
def wool(self, blockid, data):
    texture = self.load_image_texture("textures/blocks/cloth_%d.png" % data)
    
    return self.build_block(texture, texture)

# dandelion
sprite(blockid=37, imagename="textures/blocks/flower.png")
# rose
sprite(blockid=38, imagename="textures/blocks/rose.png")
# brown mushroom
sprite(blockid=39, imagename="textures/blocks/mushroom_brown.png")
# red mushroom
sprite(blockid=40, imagename="textures/blocks/mushroom_red.png")
# block of gold
block(blockid=41, top_image="textures/blocks/blockGold.png")
# block of iron
block(blockid=42, top_image="textures/blocks/blockIron.png")

# double slabs and slabs
# these wooden slabs are unobtainable without cheating, they are still
# here because lots of pre-1.3 worlds use this blocks
@material(blockid=[43, 44], data=range(16), transparent=(44,), solid=True)
def slabs(self, blockid, data):
    if blockid == 44: 
        texture = data & 7
    else: # data > 8 are special double slabs
        texture = data
    if texture== 0: # stone slab
        top = self.load_image_texture("textures/blocks/stoneslab_top.png")
        side = self.load_image_texture("textures/blocks/stoneslab_side.png")
    elif texture== 1: # smooth stone
        top = self.load_image_texture("textures/blocks/sandstone_top.png")
        side = self.load_image_texture("textures/blocks/sandstone_side.png")
    elif texture== 2: # wooden slab
        top = side = self.load_image_texture("textures/blocks/wood.png")
    elif texture== 3: # c43obblestone slab
        top = side = self.load_image_texture("textures/blocks/stonebrick.png")
    elif texture== 4: # brick
        top = side = self.load_image_texture("textures/blocks/brick.png")
    elif texture== 5: # stone brick
        top = side = self.load_image_texture("textures/blocks/stonebricksmooth.png")
    elif texture== 6: # nether brick slab
        top = side = self.load_image_texture("textures/blocks/netherBrick.png")
    elif texture== 7: #quartz        
        top = side = self.load_image_texture("textures/blocks/quartzblock_side.png")
    elif texture== 8: # special stone double slab with top texture only
        top = side = self.load_image_texture("textures/blocks/stoneslab_top.png")
    elif texture== 9: # special sandstone double slab with top texture only
        top = side = self.load_image_texture("textures/blocks/sandstone_top.png")
    else:
        return None
    
    if blockid == 43: # double slab
        return self.build_block(top, side)
    
    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask,(0,0,16,8), mask)
    
    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)
    
    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)
    
    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)
    
    return img

# brick block
block(blockid=45, top_image="textures/blocks/brick.png")
# TNT
block(blockid=46, top_image="textures/blocks/tnt_top.png", side_image="textures/blocks/tnt_side.png", nospawn=True)
# bookshelf
block(blockid=47, top_image="textures/blocks/wood.png", side_image="textures/blocks/bookshelf.png")
# moss stone
block(blockid=48, top_image="textures/blocks/stoneMoss.png")
# obsidian
block(blockid=49, top_image="textures/blocks/obsidian.png")

# torch, redstone torch (off), redstone torch(on)
@material(blockid=[50, 75, 76], data=[1, 2, 3, 4, 5], transparent=True)
def torches(self, blockid, data):
    # first, rotations
    if self.rotation == 1:
        if data == 1: data = 3
        elif data == 2: data = 4
        elif data == 3: data = 2
        elif data == 4: data = 1
    elif self.rotation == 2:
        if data == 1: data = 2
        elif data == 2: data = 1
        elif data == 3: data = 4
        elif data == 4: data = 3
    elif self.rotation == 3:
        if data == 1: data = 4
        elif data == 2: data = 3
        elif data == 3: data = 1
        elif data == 4: data = 2
    
    # choose the proper texture
    if blockid == 50: # torch
        small = self.load_image_texture("textures/blocks/torch.png")
    elif blockid == 75: # off redstone torch
        small = self.load_image_texture("textures/blocks/redtorch.png")
    else: # on redstone torch
        small = self.load_image_texture("textures/blocks/redtorch_lit.png")
        
    # compose a torch bigger than the normal
    # (better for doing transformations)
    torch = Image.new("RGBA", (16,16), self.bgcolor)
    alpha_over(torch,small,(-4,-3))
    alpha_over(torch,small,(-5,-2))
    alpha_over(torch,small,(-3,-2))
    
    # angle of inclination of the texture
    rotation = 15
    
    if data == 1: # pointing south
        torch = torch.rotate(-rotation, Image.NEAREST) # nearest filter is more nitid.
        img = self.build_full_block(None, None, None, torch, None, None)
        
    elif data == 2: # pointing north
        torch = torch.rotate(rotation, Image.NEAREST)
        img = self.build_full_block(None, None, torch, None, None, None)
        
    elif data == 3: # pointing west
        torch = torch.rotate(rotation, Image.NEAREST)
        img = self.build_full_block(None, torch, None, None, None, None)
        
    elif data == 4: # pointing east
        torch = torch.rotate(-rotation, Image.NEAREST)
        img = self.build_full_block(None, None, None, None, torch, None)
        
    elif data == 5: # standing on the floor
        # compose a "3d torch".
        img = Image.new("RGBA", (24,24), self.bgcolor)
        
        small_crop = small.crop((2,2,14,14))
        slice = small_crop.copy()
        ImageDraw.Draw(slice).rectangle((6,0,12,12),outline=(0,0,0,0),fill=(0,0,0,0))
        ImageDraw.Draw(slice).rectangle((0,0,4,12),outline=(0,0,0,0),fill=(0,0,0,0))
        
        alpha_over(img, slice, (7,5))
        alpha_over(img, small_crop, (6,6))
        alpha_over(img, small_crop, (7,6))
        alpha_over(img, slice, (7,7))
        
    return img

# fire
@material(blockid=51, data=range(16), transparent=True)
def fire(self, blockid, data):
    firetextures = self.load_fire()
    side1 = self.transform_image_side(firetextures[0])
    side2 = self.transform_image_side(firetextures[1]).transpose(Image.FLIP_LEFT_RIGHT)
    
    img = Image.new("RGBA", (24,24), self.bgcolor)

    alpha_over(img, side1, (12,0), side1)
    alpha_over(img, side2, (0,0), side2)

    alpha_over(img, side1, (0,6), side1)
    alpha_over(img, side2, (12,6), side2)
    
    return img

# monster spawner
block(blockid=52, top_image="textures/blocks/mobSpawner.png", transparent=True)

# wooden, cobblestone, red brick, stone brick, netherbrick, sandstone, spruce, birch, jungle and quartz stairs.
@material(blockid=[53,67,108,109,114,128,134,135,136,156], data=range(8), transparent=True, solid=True, nospawn=True)
def stairs(self, blockid, data):

    # first, rotations
    # preserve the upside-down bit
    upside_down = data & 0x4
    data = data & 0x3
    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1
    data = data | upside_down

    if blockid == 53: # wooden
        texture = self.load_image_texture("textures/blocks/wood.png")
    elif blockid == 67: # cobblestone
        texture = self.load_image_texture("textures/blocks/stonebrick.png")
    elif blockid == 108: # red brick stairs
        texture = self.load_image_texture("textures/blocks/brick.png")
    elif blockid == 109: # stone brick stairs
        texture = self.load_image_texture("textures/blocks/stonebricksmooth.png")
    elif blockid == 114: # netherbrick stairs
        texture = self.load_image_texture("textures/blocks/netherBrick.png")
    elif blockid == 128: # sandstone stairs
        texture = self.load_image_texture("textures/blocks/sandstone_side.png")
    elif blockid == 134: # spruce wood stairs
        texture = self.load_image_texture("textures/blocks/wood_spruce.png")
    elif blockid == 135: # birch wood  stairs
        texture = self.load_image_texture("textures/blocks/wood_birch.png")
    elif blockid == 136: # jungle good stairs
        texture = self.load_image_texture("textures/blocks/wood_jungle.png")
    elif blockid == 156: # quartz block stairs
        texture = self.load_image_texture("textures/blocks/quartzblock_side.png")


    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # sandstone stairs have spcial top texture
    if blockid == 128:
        half_block_u = self.load_image_texture("textures/blocks/sandstone_top.png").copy()
        half_block_d = self.load_image_texture("textures/blocks/sandstone_top.png").copy()
        texture = self.load_image_texture("textures/blocks/sandstone_top.png").copy()
    elif blockid == 156: # also quartz stairs
        half_block_u = self.load_image_texture("textures/blocks/quartzblock_top.png").copy()
        half_block_d = self.load_image_texture("textures/blocks/quartzblock_top.png").copy()
        texture = self.load_image_texture("textures/blocks/quartzblock_top.png").copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))
    
    if data & 0x4 == 0x4: # upside doen stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))

        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)
        
        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)
            
        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))
        
    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)
            
            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)
            
            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))
            
        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)
        
        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)
            
        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)
            
            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)
            
            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))
        
        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))
        
    return img

# normal, locked (used in april's fool day), ender and trapped chest
@material(blockid=[54,95,130,146], data=range(30), transparent = True)
def chests(self, blockid, data):
    # the first 3 bits are the orientation as stored in minecraft, 
    # bits 0x8 and 0x10 indicate which half of the double chest is it.
    
    # first, do the rotation if needed
    orientation_data = data & 7
    if self.rotation == 1:
        if orientation_data == 2: data = 5 | (data & 24)
        elif orientation_data == 3: data = 4 | (data & 24)
        elif orientation_data == 4: data = 2 | (data & 24)
        elif orientation_data == 5: data = 3 | (data & 24)
    elif self.rotation == 2:
        if orientation_data == 2: data = 3 | (data & 24)
        elif orientation_data == 3: data = 2 | (data & 24)
        elif orientation_data == 4: data = 5 | (data & 24)
        elif orientation_data == 5: data = 4 | (data & 24)
    elif self.rotation == 3:
        if orientation_data == 2: data = 4 | (data & 24)
        elif orientation_data == 3: data = 5 | (data & 24)
        elif orientation_data == 4: data = 3 | (data & 24)
        elif orientation_data == 5: data = 2 | (data & 24)
    
    if blockid in (95,130) and not data in [2,3,4,5]: return None
        # iterate.c will only return the ancil data (without pseudo 
        # ancil data) for locked and ender chests, so only 
        # ancilData = 2,3,4,5 are used for this blockids
    
    if data & 24 == 0:
        if blockid == 130: t = self.load_image("enderchest.png")
        else: t = self.load_image("chest.png")

        # the textures is no longer in terrain.png, get it from 
        # item/chest.png and get by cropping all the needed stuff
        if t.size != (64,64): t = t.resize((64,64), Image.ANTIALIAS)
        # top
        top = t.crop((14,0,28,14))
        top.load() # every crop need a load, crop is a lazy operation
                   # see PIL manual
        img = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(img,top,(1,1))
        top = img
        # front
        front_top = t.crop((14,14,28,19))
        front_top.load()
        front_bottom = t.crop((14,34,28,43))
        front_bottom.load()
        front_lock = t.crop((1,0,3,4))
        front_lock.load()
        front = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(front,front_top, (1,1))
        alpha_over(front,front_bottom, (1,6))
        alpha_over(front,front_lock, (7,3))
        # left side
        # left side, right side, and back are esentially the same for
        # the default texture, we take it anyway just in case other
        # textures make use of it.
        side_l_top = t.crop((0,14,14,19))
        side_l_top.load()
        side_l_bottom = t.crop((0,34,14,43))
        side_l_bottom.load()
        side_l = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(side_l,side_l_top, (1,1))
        alpha_over(side_l,side_l_bottom, (1,6))
        # right side
        side_r_top = t.crop((28,14,43,20))
        side_r_top.load()
        side_r_bottom = t.crop((28,33,42,43))
        side_r_bottom.load()
        side_r = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(side_r,side_l_top, (1,1))
        alpha_over(side_r,side_l_bottom, (1,6))
        # back
        back_top = t.crop((42,14,56,18))
        back_top.load()
        back_bottom = t.crop((42,33,56,43))
        back_bottom.load()
        back = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(back,side_l_top, (1,1))
        alpha_over(back,side_l_bottom, (1,6))

    else:
        # large chest
        # the textures is no longer in terrain.png, get it from 
        # item/chest.png and get all the needed stuff
        t = self.load_image("largechest.png")
        if t.size != (128,64): t = t.resize((128,64), Image.ANTIALIAS)
        # top
        top = t.crop((14,0,44,14))
        top.load()
        img = Image.new("RGBA", (32,16), self.bgcolor)
        alpha_over(img,top,(1,1))
        top = img
        # front
        front_top = t.crop((14,14,44,18))
        front_top.load()
        front_bottom = t.crop((14,33,44,43))
        front_bottom.load()
        front_lock = t.crop((1,0,3,5))
        front_lock.load()
        front = Image.new("RGBA", (32,16), self.bgcolor)
        alpha_over(front,front_top,(1,1))
        alpha_over(front,front_bottom,(1,5))
        alpha_over(front,front_lock,(15,3))
        # left side
        side_l_top = t.crop((0,14,14,18))
        side_l_top.load()
        side_l_bottom = t.crop((0,33,14,43))
        side_l_bottom.load()
        side_l = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(side_l,side_l_top, (1,1))
        alpha_over(side_l,side_l_bottom,(1,5))
        # right side
        side_r_top = t.crop((44,14,58,18))
        side_r_top.load()
        side_r_bottom = t.crop((44,33,58,43))
        side_r_bottom.load()
        side_r = Image.new("RGBA", (16,16), self.bgcolor)
        alpha_over(side_r,side_r_top, (1,1))
        alpha_over(side_r,side_r_bottom,(1,5))
        # back
        back_top = t.crop((58,14,88,18))
        back_top.load()
        back_bottom = t.crop((58,33,88,43))
        back_bottom.load()
        back = Image.new("RGBA", (32,16), self.bgcolor)
        alpha_over(back,back_top,(1,1))
        alpha_over(back,back_bottom,(1,5))
        

        if data & 24 == 8: # double chest, first half
            top = top.crop((0,0,16,16))
            top.load()
            front = front.crop((0,0,16,16))
            front.load()
            back = back.crop((0,0,16,16))
            back.load()
            #~ side = side_l

        elif data & 24 == 16: # double, second half
            top = top.crop((16,0,32,16))
            top.load()
            front = front.crop((16,0,32,16))
            front.load()
            back = back.crop((16,0,32,16))
            back.load()
            #~ side = side_r

        else: # just in case
            return None

    # compose the final block
    img = Image.new("RGBA", (24,24), self.bgcolor)
    if data & 7 == 2: # north
        side = self.transform_image_side(side_r)
        alpha_over(img, side, (1,7))
        back = self.transform_image_side(back)
        alpha_over(img, back.transpose(Image.FLIP_LEFT_RIGHT), (11,7))
        front = self.transform_image_side(front)
        top = self.transform_image_top(top.rotate(180))
        alpha_over(img, top, (0,2))

    elif data & 7 == 3: # south
        side = self.transform_image_side(side_l)
        alpha_over(img, side, (1,7))
        front = self.transform_image_side(front).transpose(Image.FLIP_LEFT_RIGHT)
        top = self.transform_image_top(top.rotate(180))
        alpha_over(img, top, (0,2))
        alpha_over(img, front,(11,7))

    elif data & 7 == 4: # west
        side = self.transform_image_side(side_r)
        alpha_over(img, side.transpose(Image.FLIP_LEFT_RIGHT), (11,7))
        front = self.transform_image_side(front)
        alpha_over(img, front,(1,7))
        top = self.transform_image_top(top.rotate(270))
        alpha_over(img, top, (0,2))

    elif data & 7 == 5: # east
        back = self.transform_image_side(back)
        side = self.transform_image_side(side_l).transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, side, (11,7))
        alpha_over(img, back, (1,7))
        top = self.transform_image_top(top.rotate(270))
        alpha_over(img, top, (0,2))
        
    else: # just in case
        img = None

    return img

# redstone wire
# uses pseudo-ancildata found in iterate.c
@material(blockid=55, data=range(128), transparent=True)
def wire(self, blockid, data):

    if data & 0b1000000 == 64: # powered redstone wire
        redstone_wire_t = self.load_image_texture("textures/blocks/redstoneDust_line.png")
        redstone_wire_t = self.tint_texture(redstone_wire_t,(255,0,0))

        redstone_cross_t = self.load_image_texture("textures/blocks/redstoneDust_cross.png")
        redstone_cross_t = self.tint_texture(redstone_cross_t,(255,0,0))

        
    else: # unpowered redstone wire
        redstone_wire_t = self.load_image_texture("textures/blocks/redstoneDust_line.png")
        redstone_wire_t = self.tint_texture(redstone_wire_t,(48,0,0))
        
        redstone_cross_t = self.load_image_texture("textures/blocks/redstoneDust_cross.png")
        redstone_cross_t = self.tint_texture(redstone_cross_t,(48,0,0))

    # generate an image per redstone direction
    branch_top_left = redstone_cross_t.copy()
    ImageDraw.Draw(branch_top_left).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_top_left).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_top_left).rectangle((0,11,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    
    branch_top_right = redstone_cross_t.copy()
    ImageDraw.Draw(branch_top_right).rectangle((0,0,15,4),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_top_right).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_top_right).rectangle((0,11,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    
    branch_bottom_right = redstone_cross_t.copy()
    ImageDraw.Draw(branch_bottom_right).rectangle((0,0,15,4),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_bottom_right).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_bottom_right).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    branch_bottom_left = redstone_cross_t.copy()
    ImageDraw.Draw(branch_bottom_left).rectangle((0,0,15,4),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_bottom_left).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(branch_bottom_left).rectangle((0,11,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
            
    # generate the bottom texture
    if data & 0b111111 == 0:
        bottom = redstone_cross_t.copy()
    
    elif data & 0b1111 == 10: #= 0b1010 redstone wire in the x direction
        bottom = redstone_wire_t.copy()
        
    elif data & 0b1111 == 5: #= 0b0101 redstone wire in the y direction
        bottom = redstone_wire_t.copy().rotate(90)
    
    else:
        bottom = Image.new("RGBA", (16,16), self.bgcolor)
        if (data & 0b0001) == 1:
            alpha_over(bottom,branch_top_left)
            
        if (data & 0b1000) == 8:
            alpha_over(bottom,branch_top_right)
            
        if (data & 0b0010) == 2:
            alpha_over(bottom,branch_bottom_left)
            
        if (data & 0b0100) == 4:
            alpha_over(bottom,branch_bottom_right)

    # check for going up redstone wire
    if data & 0b100000 == 32:
        side1 = redstone_wire_t.rotate(90)
    else:
        side1 = None
        
    if data & 0b010000 == 16:
        side2 = redstone_wire_t.rotate(90)
    else:
        side2 = None
        
    img = self.build_full_block(None,side1,side2,None,None,bottom)

    return img

# diamond ore
block(blockid=56, top_image="textures/blocks/oreDiamond.png")
# diamond block
block(blockid=57, top_image="textures/blocks/blockDiamond.png")

# crafting table
# needs two different sides
@material(blockid=58, solid=True, nodata=True)
def crafting_table(self, blockid, data):
    top = self.load_image_texture("textures/blocks/workbench_top.png")
    side3 = self.load_image_texture("textures/blocks/workbench_side.png")
    side4 = self.load_image_texture("textures/blocks/workbench_front.png")
    
    img = self.build_full_block(top, None, None, side3, side4, None)
    return img

# crops
@material(blockid=59, data=range(8), transparent=True, nospawn=True)
def crops(self, blockid, data):
    raw_crop = self.load_image_texture("textures/blocks/crops_%d.png" % data)
    crop1 = self.transform_image_top(raw_crop)
    crop2 = self.transform_image_side(raw_crop)
    crop3 = crop2.transpose(Image.FLIP_LEFT_RIGHT)

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, crop1, (0,12), crop1)
    alpha_over(img, crop2, (6,3), crop2)
    alpha_over(img, crop3, (6,3), crop3)
    return img

# farmland
@material(blockid=60, data=range(9), solid=True)
def farmland(self, blockid, data):
    top = self.load_image_texture("textures/blocks/farmland_wet.png")
    if data == 0:
        top = self.load_image_texture("textures/blocks/farmland_dry.png")
    return self.build_block(top, self.load_image_texture("textures/blocks/dirt.png"))

# signposts
@material(blockid=63, data=range(16), transparent=True)
def signpost(self, blockid, data):

    # first rotations
    if self.rotation == 1:
        data = (data + 4) % 16
    elif self.rotation == 2:
        data = (data + 8) % 16
    elif self.rotation == 3:
        data = (data + 12) % 16

    texture = self.load_image_texture("textures/blocks/wood.png").copy()
    # cut the planks to the size of a signpost
    ImageDraw.Draw(texture).rectangle((0,12,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # If the signpost is looking directly to the image, draw some 
    # random dots, they will look as text.
    if data in (0,1,2,3,4,5,15):
        for i in range(15):
            x = randint(4,11)
            y = randint(3,7)
            texture.putpixel((x,y),(0,0,0,255))

    # Minecraft uses wood texture for the signpost stick
    texture_stick = self.load_image_texture("textures/blocks/tree_side.png")
    texture_stick = texture_stick.resize((12,12), Image.ANTIALIAS)
    ImageDraw.Draw(texture_stick).rectangle((2,0,12,12),outline=(0,0,0,0),fill=(0,0,0,0))

    img = Image.new("RGBA", (24,24), self.bgcolor)

    #         W                N      ~90       E                   S        ~270
    angles = (330.,345.,0.,15.,30.,55.,95.,120.,150.,165.,180.,195.,210.,230.,265.,310.)
    angle = math.radians(angles[data])
    post = self.transform_image_angle(texture, angle)

    # choose the position of the "3D effect"
    incrementx = 0
    if data in (1,6,7,8,9,14):
        incrementx = -1
    elif data in (3,4,5,11,12,13):
        incrementx = +1

    alpha_over(img, texture_stick,(11, 8),texture_stick)
    # post2 is a brighter signpost pasted with a small shift,
    # gives to the signpost some 3D effect.
    post2 = ImageEnhance.Brightness(post).enhance(1.2)
    alpha_over(img, post2,(incrementx, -3),post2)
    alpha_over(img, post, (0,-2), post)

    return img


# wooden and iron door
# uses pseudo-ancildata found in iterate.c
@material(blockid=[64,71], data=range(32), transparent=True)
def door(self, blockid, data):
    #Masked to not clobber block top/bottom & swung info
    if self.rotation == 1:
        if (data & 0b00011) == 0: data = data & 0b11100 | 1
        elif (data & 0b00011) == 1: data = data & 0b11100 | 2
        elif (data & 0b00011) == 2: data = data & 0b11100 | 3
        elif (data & 0b00011) == 3: data = data & 0b11100 | 0
    elif self.rotation == 2:
        if (data & 0b00011) == 0: data = data & 0b11100 | 2
        elif (data & 0b00011) == 1: data = data & 0b11100 | 3
        elif (data & 0b00011) == 2: data = data & 0b11100 | 0
        elif (data & 0b00011) == 3: data = data & 0b11100 | 1
    elif self.rotation == 3:
        if (data & 0b00011) == 0: data = data & 0b11100 | 3
        elif (data & 0b00011) == 1: data = data & 0b11100 | 0
        elif (data & 0b00011) == 2: data = data & 0b11100 | 1
        elif (data & 0b00011) == 3: data = data & 0b11100 | 2

    if data & 0x8 == 0x8: # top of the door
        raw_door = self.load_image_texture("textures/blocks/%s.png" % ("doorWood_upper" if blockid == 64 else "doorIron_upper"))
    else: # bottom of the door
        raw_door = self.load_image_texture("textures/blocks/%s.png" % ("doorWood_lower" if blockid == 64 else "doorIron_lower"))
    
    # if you want to render all doors as closed, then force
    # force closed to be True
    if data & 0x4 == 0x4:
        closed = False
    else:
        closed = True
    
    if data & 0x10 == 0x10:
        # hinge on the left (facing same door direction)
        hinge_on_left = True
    else:
        # hinge on the right (default single door)
        hinge_on_left = False

    # mask out the high bits to figure out the orientation 
    img = Image.new("RGBA", (24,24), self.bgcolor)
    if (data & 0x03) == 0: # facing west when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (0,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door)    
                alpha_over(img, tex, (0,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
    
    if (data & 0x03) == 1: # facing north when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (0,6), tex)

        else:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (12,0), tex)

                
    if (data & 0x03) == 2: # facing east when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (12,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (12,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)

    if (data & 0x03) == 3: # facing south when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (12,0), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (0,6), tex)

    return img

# ladder
@material(blockid=65, data=[2, 3, 4, 5], transparent=True)
def ladder(self, blockid, data):

    # first rotations
    if self.rotation == 1:
        if data == 2: data = 5
        elif data == 3: data = 4
        elif data == 4: data = 2
        elif data == 5: data = 3
    elif self.rotation == 2:
        if data == 2: data = 3
        elif data == 3: data = 2
        elif data == 4: data = 5
        elif data == 5: data = 4
    elif self.rotation == 3:
        if data == 2: data = 4
        elif data == 3: data = 5
        elif data == 4: data = 3
        elif data == 5: data = 2

    img = Image.new("RGBA", (24,24), self.bgcolor)
    raw_texture = self.load_image_texture("textures/blocks/ladder.png")

    if data == 5:
        # normally this ladder would be obsured by the block it's attached to
        # but since ladders can apparently be placed on transparent blocks, we 
        # have to render this thing anyway.  same for data == 2
        tex = self.transform_image_side(raw_texture)
        alpha_over(img, tex, (0,6), tex)
        return img
    if data == 2:
        tex = self.transform_image_side(raw_texture).transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, tex, (12,6), tex)
        return img
    if data == 3:
        tex = self.transform_image_side(raw_texture).transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, tex, (0,0), tex)
        return img
    if data == 4:
        tex = self.transform_image_side(raw_texture)
        alpha_over(img, tex, (12,0), tex)
        return img


# wall signs
@material(blockid=68, data=[2, 3, 4, 5], transparent=True)
def wall_sign(self, blockid, data): # wall sign

    # first rotations
    if self.rotation == 1:
        if data == 2: data = 5
        elif data == 3: data = 4
        elif data == 4: data = 2
        elif data == 5: data = 3
    elif self.rotation == 2:
        if data == 2: data = 3
        elif data == 3: data = 2
        elif data == 4: data = 5
        elif data == 5: data = 4
    elif self.rotation == 3:
        if data == 2: data = 4
        elif data == 3: data = 5
        elif data == 4: data = 3
        elif data == 5: data = 2

    texture = self.load_image_texture("textures/blocks/wood.png").copy()
    # cut the planks to the size of a signpost
    ImageDraw.Draw(texture).rectangle((0,12,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # draw some random black dots, they will look as text
    """ don't draw text at the moment, they are used in blank for decoration
    
    if data in (3,4):
        for i in range(15):
            x = randint(4,11)
            y = randint(3,7)
            texture.putpixel((x,y),(0,0,0,255))
    """
    
    img = Image.new("RGBA", (24,24), self.bgcolor)

    incrementx = 0
    if data == 2:  # east
        incrementx = +1
        sign = self.build_full_block(None, None, None, None, texture)
    elif data == 3:  # west
        incrementx = -1
        sign = self.build_full_block(None, texture, None, None, None)
    elif data == 4:  # north
        incrementx = +1
        sign = self.build_full_block(None, None, texture, None, None)
    elif data == 5:  # south
        incrementx = -1
        sign = self.build_full_block(None, None, None, texture, None)

    sign2 = ImageEnhance.Brightness(sign).enhance(1.2)
    alpha_over(img, sign2,(incrementx, 2),sign2)
    alpha_over(img, sign, (0,3), sign)

    return img

# levers
@material(blockid=69, data=range(16), transparent=True)
def levers(self, blockid, data):
    if data & 8 == 8: powered = True
    else: powered = False

    data = data & 7

    # first rotations
    if self.rotation == 1:
        # on wall levers
        if data == 1: data = 3
        elif data == 2: data = 4
        elif data == 3: data = 2
        elif data == 4: data = 1
        # on floor levers
        elif data == 5: data = 6
        elif data == 6: data = 5
    elif self.rotation == 2:
        if data == 1: data = 2
        elif data == 2: data = 1
        elif data == 3: data = 4
        elif data == 4: data = 3
        elif data == 5: data = 5
        elif data == 6: data = 6
    elif self.rotation == 3:
        if data == 1: data = 4
        elif data == 2: data = 3
        elif data == 3: data = 1
        elif data == 4: data = 2
        elif data == 5: data = 6
        elif data == 6: data = 5

    # generate the texture for the base of the lever
    t_base = self.load_image_texture("textures/blocks/stonebrick.png").copy()

    ImageDraw.Draw(t_base).rectangle((0,0,15,3),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t_base).rectangle((0,12,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t_base).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t_base).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # generate the texture for the stick
    stick = self.load_image_texture("textures/blocks/lever.png").copy()
    c_stick = Image.new("RGBA", (16,16), self.bgcolor)
    
    tmp = ImageEnhance.Brightness(stick).enhance(0.8)
    alpha_over(c_stick, tmp, (1,0), tmp)
    alpha_over(c_stick, stick, (0,0), stick)
    t_stick = self.transform_image_side(c_stick.rotate(45, Image.NEAREST))

    # where the lever will be composed
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    # wall levers
    if data == 1: # facing SOUTH
        # levers can't be placed in transparent blocks, so this
        # direction is almost invisible
        return None

    elif data == 2: # facing NORTH
        base = self.transform_image_side(t_base)
        
        # paste it twice with different brightness to make a fake 3D effect
        alpha_over(img, base, (12,-1), base)

        alpha = base.split()[3]
        base = ImageEnhance.Brightness(base).enhance(0.9)
        base.putalpha(alpha)
        
        alpha_over(img, base, (11,0), base)

        # paste the lever stick
        pos = (7,-7)
        if powered:
            t_stick = t_stick.transpose(Image.FLIP_TOP_BOTTOM)
            pos = (7,6)
        alpha_over(img, t_stick, pos, t_stick)

    elif data == 3: # facing WEST
        base = self.transform_image_side(t_base)
        
        # paste it twice with different brightness to make a fake 3D effect
        base = base.transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, base, (0,-1), base)

        alpha = base.split()[3]
        base = ImageEnhance.Brightness(base).enhance(0.9)
        base.putalpha(alpha)
        
        alpha_over(img, base, (1,0), base)
        
        # paste the lever stick
        t_stick = t_stick.transpose(Image.FLIP_LEFT_RIGHT)
        pos = (5,-7)
        if powered:
            t_stick = t_stick.transpose(Image.FLIP_TOP_BOTTOM)
            pos = (6,6)
        alpha_over(img, t_stick, pos, t_stick)

    elif data == 4: # facing EAST
        # levers can't be placed in transparent blocks, so this
        # direction is almost invisible
        return None

    # floor levers
    elif data == 5: # pointing south when off
        # lever base, fake 3d again
        base = self.transform_image_top(t_base)

        alpha = base.split()[3]
        tmp = ImageEnhance.Brightness(base).enhance(0.8)
        tmp.putalpha(alpha)
        
        alpha_over(img, tmp, (0,12), tmp)
        alpha_over(img, base, (0,11), base)

        # lever stick
        pos = (3,2)
        if not powered:
            t_stick = t_stick.transpose(Image.FLIP_LEFT_RIGHT)
            pos = (11,2)
        alpha_over(img, t_stick, pos, t_stick)

    elif data == 6: # pointing east when off
        # lever base, fake 3d again
        base = self.transform_image_top(t_base.rotate(90))

        alpha = base.split()[3]
        tmp = ImageEnhance.Brightness(base).enhance(0.8)
        tmp.putalpha(alpha)
        
        alpha_over(img, tmp, (0,12), tmp)
        alpha_over(img, base, (0,11), base)

        # lever stick
        pos = (2,3)
        if not powered:
            t_stick = t_stick.transpose(Image.FLIP_LEFT_RIGHT)
            pos = (10,2)
        alpha_over(img, t_stick, pos, t_stick)

    return img

# wooden and stone pressure plates, and weighted pressure plates
@material(blockid=[70, 72,147,148], data=[0,1], transparent=True)
def pressure_plate(self, blockid, data):
    if blockid == 70: # stone
        t = self.load_image_texture("textures/blocks/stone.png").copy()
    elif blockid == 72: # wooden
        t = self.load_image_texture("textures/blocks/wood.png").copy()
    elif blockid == 147: # light golden
        t = self.load_image_texture("textures/blocks/blockGold.png").copy()
    else: # blockid == 148: # heavy iron
        t = self.load_image_texture("textures/blocks/blockIron.png").copy()
    
    # cut out the outside border, pressure plates are smaller
    # than a normal block
    ImageDraw.Draw(t).rectangle((0,0,15,15),outline=(0,0,0,0))
    
    # create the textures and a darker version to make a 3d by 
    # pasting them with an offstet of 1 pixel
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    top = self.transform_image_top(t)
    
    alpha = top.split()[3]
    topd = ImageEnhance.Brightness(top).enhance(0.8)
    topd.putalpha(alpha)
    
    #show it 3d or 2d if unpressed or pressed
    if data == 0:
        alpha_over(img,topd, (0,12),topd)
        alpha_over(img,top, (0,11),top)
    elif data == 1:
        alpha_over(img,top, (0,12),top)
    
    return img

# normal and glowing redstone ore
block(blockid=[73, 74], top_image="textures/blocks/oreRedstone.png")

# stone a wood buttons
@material(blockid=(77,143), data=range(16), transparent=True)
def buttons(self, blockid, data):

    # 0x8 is set if the button is pressed mask this info and render
    # it as unpressed
    data = data & 0x7

    if self.rotation == 1:
        if data == 1: data = 3
        elif data == 2: data = 4
        elif data == 3: data = 2
        elif data == 4: data = 1
    elif self.rotation == 2:
        if data == 1: data = 2
        elif data == 2: data = 1
        elif data == 3: data = 4
        elif data == 4: data = 3
    elif self.rotation == 3:
        if data == 1: data = 4
        elif data == 2: data = 3
        elif data == 3: data = 1
        elif data == 4: data = 2

    if blockid == 77:
        t = self.load_image_texture("textures/blocks/stone.png").copy()
    else:
        t = self.load_image_texture("textures/blocks/wood.png").copy()

    # generate the texture for the button
    ImageDraw.Draw(t).rectangle((0,0,15,5),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((0,10,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    img = Image.new("RGBA", (24,24), self.bgcolor)

    button = self.transform_image_side(t)
    
    if data == 1: # facing SOUTH
        # buttons can't be placed in transparent blocks, so this
        # direction can't be seen
        return None

    elif data == 2: # facing NORTH
        # paste it twice with different brightness to make a 3D effect
        alpha_over(img, button, (12,-1), button)

        alpha = button.split()[3]
        button = ImageEnhance.Brightness(button).enhance(0.9)
        button.putalpha(alpha)
        
        alpha_over(img, button, (11,0), button)

    elif data == 3: # facing WEST
        # paste it twice with different brightness to make a 3D effect
        button = button.transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, button, (0,-1), button)

        alpha = button.split()[3]
        button = ImageEnhance.Brightness(button).enhance(0.9)
        button.putalpha(alpha)
        
        alpha_over(img, button, (1,0), button)

    elif data == 4: # facing EAST
        # buttons can't be placed in transparent blocks, so this
        # direction can't be seen
        return None

    return img

# snow
@material(blockid=78, data=range(16), transparent=True, solid=True)
def snow(self, blockid, data):
    # still not rendered correctly: data other than 0
    
    tex = self.load_image_texture("textures/blocks/snow.png")
    
    # make the side image, top 3/4 transparent
    mask = tex.crop((0,12,16,16))
    sidetex = Image.new(tex.mode, tex.size, self.bgcolor)
    alpha_over(sidetex, mask, (0,12,16,16), mask)
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    top = self.transform_image_top(tex)
    side = self.transform_image_side(sidetex)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)
    
    alpha_over(img, side, (0,6), side)
    alpha_over(img, otherside, (12,6), otherside)
    alpha_over(img, top, (0,9), top)
    
    return img

# snow block
block(blockid=80, top_image="textures/blocks/snow.png")

# cactus
@material(blockid=81, data=range(15), transparent=True, solid=True, nospawn=True)
def cactus(self, blockid, data):
    top = self.load_image_texture("textures/blocks/cactus_top.png")
    side = self.load_image_texture("textures/blocks/cactus_side.png")

    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    alpha_over(img, side, (1,6), side)
    alpha_over(img, otherside, (11,6), otherside)
    alpha_over(img, top, (0,0), top)
    
    return img

# clay block
block(blockid=82, top_image="textures/blocks/clay.png")

# sugar cane
@material(blockid=83, data=range(16), transparent=True)
def sugar_cane(self, blockid, data):
    tex = self.load_image_texture("textures/blocks/reeds.png")
    return self.build_sprite(tex)

# jukebox
@material(blockid=84, data=range(16), solid=True)
def jukebox(self, blockid, data):
    return self.build_block(self.load_image_texture("textures/blocks/jukebox_top.png"), self.load_image_texture("textures/blocks/musicBlock.png"))

# nether and normal fences
# uses pseudo-ancildata found in iterate.c
@material(blockid=[85, 113], data=range(16), transparent=True, nospawn=True)
def fence(self, blockid, data):
    # no need for rotations, it uses pseudo data.
    # create needed images for Big stick fence
    if blockid == 85: # normal fence
        fence_top = self.load_image_texture("textures/blocks/wood.png").copy()
        fence_side = self.load_image_texture("textures/blocks/wood.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/wood.png").copy()
    else: # netherbrick fence
        fence_top = self.load_image_texture("textures/blocks/netherBrick.png").copy()
        fence_side = self.load_image_texture("textures/blocks/netherBrick.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/netherBrick.png").copy()

    # generate the textures of the fence
    ImageDraw.Draw(fence_top).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,0,15,5),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,10,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    ImageDraw.Draw(fence_side).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_side).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the big stick
    fence_side = self.transform_image_side(fence_side)
    fence_other_side = fence_side.transpose(Image.FLIP_LEFT_RIGHT)
    fence_top = self.transform_image_top(fence_top)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_side.split()[3]
    fence_side = ImageEnhance.Brightness(fence_side).enhance(0.9)
    fence_side.putalpha(sidealpha)
    othersidealpha = fence_other_side.split()[3]
    fence_other_side = ImageEnhance.Brightness(fence_other_side).enhance(0.8)
    fence_other_side.putalpha(othersidealpha)

    # Compose the fence big stick
    fence_big = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(fence_big,fence_side, (5,4),fence_side)
    alpha_over(fence_big,fence_other_side, (7,4),fence_other_side)
    alpha_over(fence_big,fence_top, (0,0),fence_top)
    
    # Now render the small sticks.
    # Create needed images
    ImageDraw.Draw(fence_small_side).rectangle((0,0,15,0),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,4,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,10,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the small sticks
    fence_small_side = self.transform_image_side(fence_small_side)
    fence_small_other_side = fence_small_side.transpose(Image.FLIP_LEFT_RIGHT)
    
    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_small_other_side.split()[3]
    fence_small_other_side = ImageEnhance.Brightness(fence_small_other_side).enhance(0.9)
    fence_small_other_side.putalpha(sidealpha)
    sidealpha = fence_small_side.split()[3]
    fence_small_side = ImageEnhance.Brightness(fence_small_side).enhance(0.9)
    fence_small_side.putalpha(sidealpha)

    # Create img to compose the fence
    img = Image.new("RGBA", (24,24), self.bgcolor)

    # Position of fence small sticks in img.
    # These postitions are strange because the small sticks of the 
    # fence are at the very left and at the very right of the 16x16 images
    pos_top_left = (2,3)
    pos_top_right = (10,3)
    pos_bottom_right = (10,7)
    pos_bottom_left = (2,7)
    
    # +x axis points top right direction
    # +y axis points bottom right direction
    # First compose small sticks in the back of the image, 
    # then big stick and thecn small sticks in the front.

    if (data & 0b0001) == 1:
        alpha_over(img,fence_small_side, pos_top_left,fence_small_side)                # top left
    if (data & 0b1000) == 8:
        alpha_over(img,fence_small_other_side, pos_top_right,fence_small_other_side)    # top right
        
    alpha_over(img,fence_big,(0,0),fence_big)
        
    if (data & 0b0010) == 2:
        alpha_over(img,fence_small_other_side, pos_bottom_left,fence_small_other_side)      # bottom left    
    if (data & 0b0100) == 4:
        alpha_over(img,fence_small_side, pos_bottom_right,fence_small_side)                  # bottom right
    
    return img

# pumpkin
@material(blockid=[86, 91], data=range(4), solid=True)
def pumpkin(self, blockid, data): # pumpkins, jack-o-lantern
    # rotation
    if self.rotation == 1:
        if data == 0: data = 1
        elif data == 1: data = 2
        elif data == 2: data = 3
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 0
        elif data == 3: data = 1
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 0
        elif data == 2: data = 1
        elif data == 3: data = 2
    
    # texture generation
    top = self.load_image_texture("textures/blocks/pumpkin_top.png")
    frontName = "textures/blocks/pumpkin_face.png" if blockid == 86 else "textures/blocks/pumpkin_jack.png"
    front = self.load_image_texture(frontName)
    side = self.load_image_texture("textures/blocks/pumpkin_side.png")

    if data == 0: # pointing west
        img = self.build_full_block(top, None, None, side, front)

    elif data == 1: # pointing north
        img = self.build_full_block(top, None, None, front, side)

    else: # in any other direction the front can't be seen
        img = self.build_full_block(top, None, None, side, side)

    return img

# netherrack
block(blockid=87, top_image="textures/blocks/hellrock.png")

# soul sand
block(blockid=88, top_image="textures/blocks/hellsand.png")

# glowstone
block(blockid=89, top_image="textures/blocks/lightgem.png")

# portal
@material(blockid=90, data=[1, 2, 4, 8], transparent=True)
def portal(self, blockid, data):
    # no rotations, uses pseudo data
    portaltexture = self.load_portal()
    img = Image.new("RGBA", (24,24), self.bgcolor)

    side = self.transform_image_side(portaltexture)
    otherside = side.transpose(Image.FLIP_TOP_BOTTOM)

    if data in (1,4):
        alpha_over(img, side, (5,4), side)

    if data in (2,8):
        alpha_over(img, otherside, (5,4), otherside)

    return img

# cake!
@material(blockid=92, data=range(6), transparent=True, nospawn=True)
def cake(self, blockid, data):
    
    # cake textures
    top = self.load_image_texture("textures/blocks/cake_top.png").copy()
    side = self.load_image_texture("textures/blocks/cake_side.png").copy()
    fullside = side.copy()
    inside = self.load_image_texture("textures/blocks/cake_inner.png")
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    if data == 0: # unbitten cake
        top = self.transform_image_top(top)
        side = self.transform_image_side(side)
        otherside = side.transpose(Image.FLIP_LEFT_RIGHT)
        
        # darken sides slightly
        sidealpha = side.split()[3]
        side = ImageEnhance.Brightness(side).enhance(0.9)
        side.putalpha(sidealpha)
        othersidealpha = otherside.split()[3]
        otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
        otherside.putalpha(othersidealpha)
        
        # composite the cake
        alpha_over(img, side, (1,6), side)
        alpha_over(img, otherside, (11,7), otherside) # workaround, fixes a hole
        alpha_over(img, otherside, (12,6), otherside)
        alpha_over(img, top, (0,6), top)
    
    else:
        # cut the textures for a bitten cake
        coord = int(16./6.*data)
        ImageDraw.Draw(side).rectangle((16 - coord,0,16,16),outline=(0,0,0,0),fill=(0,0,0,0))
        ImageDraw.Draw(top).rectangle((0,0,coord,16),outline=(0,0,0,0),fill=(0,0,0,0))

        # the bitten part of the cake always points to the west
        # composite the cake for every north orientation
        if self.rotation == 0: # north top-left
            # create right side
            rs = self.transform_image_side(side).transpose(Image.FLIP_LEFT_RIGHT)
            # create bitten side and its coords
            deltax = 2*data
            deltay = -1*data
            if data == 3: deltax += 1 # special case fixing pixel holes
            ls = self.transform_image_side(inside)
            # create top side
            t = self.transform_image_top(top)
            # darken sides slightly
            sidealpha = ls.split()[3]
            ls = ImageEnhance.Brightness(ls).enhance(0.9)
            ls.putalpha(sidealpha)
            othersidealpha = rs.split()[3]
            rs = ImageEnhance.Brightness(rs).enhance(0.8)
            rs.putalpha(othersidealpha)
            # compose the cake
            alpha_over(img, rs, (12,6), rs)
            alpha_over(img, ls, (1 + deltax,6 + deltay), ls)
            alpha_over(img, t, (0,6), t)

        elif self.rotation == 1: # north top-right
            # bitten side not shown
            # create left side
            ls = self.transform_image_side(side.transpose(Image.FLIP_LEFT_RIGHT))
            # create top
            t = self.transform_image_top(top.rotate(-90))
            # create right side
            rs = self.transform_image_side(fullside).transpose(Image.FLIP_LEFT_RIGHT)
            # darken sides slightly
            sidealpha = ls.split()[3]
            ls = ImageEnhance.Brightness(ls).enhance(0.9)
            ls.putalpha(sidealpha)
            othersidealpha = rs.split()[3]
            rs = ImageEnhance.Brightness(rs).enhance(0.8)
            rs.putalpha(othersidealpha)
            # compose the cake
            alpha_over(img, ls, (2,6), ls)
            alpha_over(img, t, (0,6), t)
            alpha_over(img, rs, (12,6), rs)

        elif self.rotation == 2: # north bottom-right
            # bitten side not shown
            # left side
            ls = self.transform_image_side(fullside)
            # top
            t = self.transform_image_top(top.rotate(180))
            # right side
            rs = self.transform_image_side(side.transpose(Image.FLIP_LEFT_RIGHT)).transpose(Image.FLIP_LEFT_RIGHT)
            # darken sides slightly
            sidealpha = ls.split()[3]
            ls = ImageEnhance.Brightness(ls).enhance(0.9)
            ls.putalpha(sidealpha)
            othersidealpha = rs.split()[3]
            rs = ImageEnhance.Brightness(rs).enhance(0.8)
            rs.putalpha(othersidealpha)
            # compose the cake
            alpha_over(img, ls, (2,6), ls)
            alpha_over(img, t, (1,6), t)
            alpha_over(img, rs, (12,6), rs)

        elif self.rotation == 3: # north bottom-left
            # create left side
            ls = self.transform_image_side(side)
            # create top
            t = self.transform_image_top(top.rotate(90))
            # create right side and its coords
            deltax = 12-2*data
            deltay = -1*data
            if data == 3: deltax += -1 # special case fixing pixel holes
            rs = self.transform_image_side(inside).transpose(Image.FLIP_LEFT_RIGHT)
            # darken sides slightly
            sidealpha = ls.split()[3]
            ls = ImageEnhance.Brightness(ls).enhance(0.9)
            ls.putalpha(sidealpha)
            othersidealpha = rs.split()[3]
            rs = ImageEnhance.Brightness(rs).enhance(0.8)
            rs.putalpha(othersidealpha)
            # compose the cake
            alpha_over(img, ls, (2,6), ls)
            alpha_over(img, t, (1,6), t)
            alpha_over(img, rs, (1 + deltax,6 + deltay), rs)

    return img

# redstone repeaters ON and OFF
@material(blockid=[93,94], data=range(16), transparent=True, nospawn=True)
def repeater(self, blockid, data):
    # rotation
    # Masked to not clobber delay info
    if self.rotation == 1:
        if (data & 0b0011) == 0: data = data & 0b1100 | 1
        elif (data & 0b0011) == 1: data = data & 0b1100 | 2
        elif (data & 0b0011) == 2: data = data & 0b1100 | 3
        elif (data & 0b0011) == 3: data = data & 0b1100 | 0
    elif self.rotation == 2:
        if (data & 0b0011) == 0: data = data & 0b1100 | 2
        elif (data & 0b0011) == 1: data = data & 0b1100 | 3
        elif (data & 0b0011) == 2: data = data & 0b1100 | 0
        elif (data & 0b0011) == 3: data = data & 0b1100 | 1
    elif self.rotation == 3:
        if (data & 0b0011) == 0: data = data & 0b1100 | 3
        elif (data & 0b0011) == 1: data = data & 0b1100 | 0
        elif (data & 0b0011) == 2: data = data & 0b1100 | 1
        elif (data & 0b0011) == 3: data = data & 0b1100 | 2
    
    # generate the diode
    top = self.load_image_texture("textures/blocks/repeater.png") if blockid == 93 else self.load_image_texture("textures/blocks/repeater_lit.png")
    side = self.load_image_texture("textures/blocks/stoneslab_side.png")
    increment = 13
    
    if (data & 0x3) == 0: # pointing east
        pass
    
    if (data & 0x3) == 1: # pointing south
        top = top.rotate(270)

    if (data & 0x3) == 2: # pointing west
        top = top.rotate(180)

    if (data & 0x3) == 3: # pointing north
        top = top.rotate(90)

    img = self.build_full_block( (top, increment), None, None, side, side)

    # compose a "3d" redstone torch
    t = self.load_image_texture("textures/blocks/redtorch.png").copy() if blockid == 93 else self.load_image_texture("textures/blocks/redtorch_lit.png").copy()
    torch = Image.new("RGBA", (24,24), self.bgcolor)
    
    t_crop = t.crop((2,2,14,14))
    slice = t_crop.copy()
    ImageDraw.Draw(slice).rectangle((6,0,12,12),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(slice).rectangle((0,0,4,12),outline=(0,0,0,0),fill=(0,0,0,0))
    
    alpha_over(torch, slice, (6,4))
    alpha_over(torch, t_crop, (5,5))
    alpha_over(torch, t_crop, (6,5))
    alpha_over(torch, slice, (6,6))
    
    # paste redstone torches everywhere!
    # the torch is too tall for the repeater, crop the bottom.
    ImageDraw.Draw(torch).rectangle((0,16,24,24),outline=(0,0,0,0),fill=(0,0,0,0))
    
    # touch up the 3d effect with big rectangles, just in case, for other texture packs
    ImageDraw.Draw(torch).rectangle((0,24,10,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(torch).rectangle((12,15,24,24),outline=(0,0,0,0),fill=(0,0,0,0))
    
    # torch positions for every redstone torch orientation.
    #
    # This is a horrible list of torch orientations. I tried to 
    # obtain these orientations by rotating the positions for one
    # orientation, but pixel rounding is horrible and messes the
    # torches.

    if (data & 0x3) == 0: # pointing east
        if (data & 0xC) == 0: # one tick delay
            moving_torch = (1,1)
            static_torch = (-3,-1)
            
        elif (data & 0xC) == 4: # two ticks delay
            moving_torch = (2,2)
            static_torch = (-3,-1)
            
        elif (data & 0xC) == 8: # three ticks delay
            moving_torch = (3,2)
            static_torch = (-3,-1)
            
        elif (data & 0xC) == 12: # four ticks delay
            moving_torch = (4,3)
            static_torch = (-3,-1)
    
    elif (data & 0x3) == 1: # pointing south
        if (data & 0xC) == 0: # one tick delay
            moving_torch = (1,1)
            static_torch = (5,-1)
            
        elif (data & 0xC) == 4: # two ticks delay
            moving_torch = (0,2)
            static_torch = (5,-1)
            
        elif (data & 0xC) == 8: # three ticks delay
            moving_torch = (-1,2)
            static_torch = (5,-1)
            
        elif (data & 0xC) == 12: # four ticks delay
            moving_torch = (-2,3)
            static_torch = (5,-1)

    elif (data & 0x3) == 2: # pointing west
        if (data & 0xC) == 0: # one tick delay
            moving_torch = (1,1)
            static_torch = (5,3)
            
        elif (data & 0xC) == 4: # two ticks delay
            moving_torch = (0,0)
            static_torch = (5,3)
            
        elif (data & 0xC) == 8: # three ticks delay
            moving_torch = (-1,0)
            static_torch = (5,3)
            
        elif (data & 0xC) == 12: # four ticks delay
            moving_torch = (-2,-1)
            static_torch = (5,3)

    elif (data & 0x3) == 3: # pointing north
        if (data & 0xC) == 0: # one tick delay
            moving_torch = (1,1)
            static_torch = (-3,3)
            
        elif (data & 0xC) == 4: # two ticks delay
            moving_torch = (2,0)
            static_torch = (-3,3)
            
        elif (data & 0xC) == 8: # three ticks delay
            moving_torch = (3,0)
            static_torch = (-3,3)
            
        elif (data & 0xC) == 12: # four ticks delay
            moving_torch = (4,-1)
            static_torch = (-3,3)
    
    # this paste order it's ok for east and south orientation
    # but it's wrong for north and west orientations. But using the
    # default texture pack the torches are small enough to no overlap.
    alpha_over(img, torch, static_torch, torch) 
    alpha_over(img, torch, moving_torch, torch)

    return img

# redstone comparator (149 is inactive, 150 is active)
@material(blockid=[149,150], data=range(16), transparent=True, nospawn=True)
def comparator(self, blockid, data):

    # rotation
    # add self.rotation to the lower 2 bits,  mod 4
    data = data & 0b1100 | (((data & 0b11) + self.rotation) % 4)


    top = self.load_image_texture("textures/blocks/comparator.png") if blockid == 149 else self.load_image_texture("textures/blocks/comparator_lit.png")
    side = self.load_image_texture("textures/blocks/stoneslab_side.png")
    increment = 13

    if (data & 0x3) == 0: # pointing north
        pass
        static_torch = (-3,-1)
        torch = ((0,2),(6,-1))
    
    if (data & 0x3) == 1: # pointing east
        top = top.rotate(270)
        static_torch = (5,-1)
        torch = ((-4,-1),(0,2))

    if (data & 0x3) == 2: # pointing south
        top = top.rotate(180)
        static_torch = (5,3)
        torch = ((0,-4),(-4,-1))

    if (data & 0x3) == 3: # pointing west
        top = top.rotate(90)
        static_torch = (-3,3)
        torch = ((1,-4),(6,-1))


    def build_torch(active):
        # compose a "3d" redstone torch
        t = self.load_image_texture("textures/blocks/redtorch.png").copy() if not active else self.load_image_texture("textures/blocks/redtorch_lit.png").copy()
        torch = Image.new("RGBA", (24,24), self.bgcolor)
        
        t_crop = t.crop((2,2,14,14))
        slice = t_crop.copy()
        ImageDraw.Draw(slice).rectangle((6,0,12,12),outline=(0,0,0,0),fill=(0,0,0,0))
        ImageDraw.Draw(slice).rectangle((0,0,4,12),outline=(0,0,0,0),fill=(0,0,0,0))
        
        alpha_over(torch, slice, (6,4))
        alpha_over(torch, t_crop, (5,5))
        alpha_over(torch, t_crop, (6,5))
        alpha_over(torch, slice, (6,6))

        return torch
    
    active_torch = build_torch(True)
    inactive_torch = build_torch(False)
    back_torch = active_torch if (blockid == 150 or data & 0b1000 == 0b1000) else inactive_torch
    static_torch_img = active_torch if (data & 0b100 == 0b100) else inactive_torch 

    img = self.build_full_block( (top, increment), None, None, side, side)

    alpha_over(img, static_torch_img, static_torch, static_torch_img) 
    alpha_over(img, back_torch, torch[0], back_torch) 
    alpha_over(img, back_torch, torch[1], back_torch) 
    return img
    
    
# trapdoor
# TODO the trapdoor is looks like a sprite when opened, that's not good
@material(blockid=96, data=range(16), transparent=True, nospawn=True)
def trapdoor(self, blockid, data):

    # rotation
    # Masked to not clobber opened/closed info
    if self.rotation == 1:
        if (data & 0b0011) == 0: data = data & 0b1100 | 3
        elif (data & 0b0011) == 1: data = data & 0b1100 | 2
        elif (data & 0b0011) == 2: data = data & 0b1100 | 0
        elif (data & 0b0011) == 3: data = data & 0b1100 | 1
    elif self.rotation == 2:
        if (data & 0b0011) == 0: data = data & 0b1100 | 1
        elif (data & 0b0011) == 1: data = data & 0b1100 | 0
        elif (data & 0b0011) == 2: data = data & 0b1100 | 3
        elif (data & 0b0011) == 3: data = data & 0b1100 | 2
    elif self.rotation == 3:
        if (data & 0b0011) == 0: data = data & 0b1100 | 2
        elif (data & 0b0011) == 1: data = data & 0b1100 | 3
        elif (data & 0b0011) == 2: data = data & 0b1100 | 1
        elif (data & 0b0011) == 3: data = data & 0b1100 | 0

    # texture generation
    texture = self.load_image_texture("textures/blocks/trapdoor.png")
    if data & 0x4 == 0x4: # opened trapdoor
        if data & 0x3 == 0: # west
            img = self.build_full_block(None, None, None, None, texture)
        if data & 0x3 == 1: # east
            img = self.build_full_block(None, texture, None, None, None)
        if data & 0x3 == 2: # south
            img = self.build_full_block(None, None, texture, None, None)
        if data & 0x3 == 3: # north
            img = self.build_full_block(None, None, None, texture, None)
        
    elif data & 0x4 == 0: # closed trapdoor
        if data & 0x8 == 0x8: # is a top trapdoor
            img = Image.new("RGBA", (24,24), self.bgcolor)
            t = self.build_full_block((texture, 12), None, None, texture, texture)
            alpha_over(img, t, (0,-9),t)
        else: # is a bottom trapdoor
            img = self.build_full_block((texture, 12), None, None, texture, texture)
    
    return img

# block with hidden silverfish (stone, cobblestone and stone brick)
@material(blockid=97, data=range(3), solid=True)
def hidden_silverfish(self, blockid, data):
    if data == 0: # stone
        t = self.load_image_texture("textures/blocks/stone.png")
    elif data == 1: # cobblestone
        t = self.load_image_texture("textures/blocks/stonebrick.png")
    elif data == 2: # stone brick
        t = self.load_image_texture("textures/blocks/stonebricksmooth.png")
    
    img = self.build_block(t, t)
    
    return img

# stone brick
@material(blockid=98, data=range(4), solid=True)
def stone_brick(self, blockid, data):
    if data == 0: # normal
        t = self.load_image_texture("textures/blocks/stonebricksmooth.png")
    elif data == 1: # mossy
        t = self.load_image_texture("textures/blocks/stonebricksmooth_mossy.png")
    elif data == 2: # cracked
        t = self.load_image_texture("textures/blocks/stonebricksmooth_cracked.png")
    elif data == 3: # "circle" stone brick
        t = self.load_image_texture("textures/blocks/stonebricksmooth_carved.png")

    img = self.build_full_block(t, None, None, t, t)

    return img

# huge brown and red mushroom
@material(blockid=[99,100], data= range(11) + [14,15], solid=True)
def huge_mushroom(self, blockid, data):
    # rotation
    if self.rotation == 1:
        if data == 1: data = 3
        elif data == 2: data = 6
        elif data == 3: data = 9
        elif data == 4: data = 2
        elif data == 6: data = 8
        elif data == 7: data = 1
        elif data == 8: data = 4
        elif data == 9: data = 7
    elif self.rotation == 2:
        if data == 1: data = 9
        elif data == 2: data = 8
        elif data == 3: data = 7
        elif data == 4: data = 6
        elif data == 6: data = 4
        elif data == 7: data = 3
        elif data == 8: data = 2
        elif data == 9: data = 1
    elif self.rotation == 3:
        if data == 1: data = 7
        elif data == 2: data = 4
        elif data == 3: data = 1
        elif data == 4: data = 2
        elif data == 6: data = 8
        elif data == 7: data = 9
        elif data == 8: data = 6
        elif data == 9: data = 3

    # texture generation
    if blockid == 99: # brown
        cap = self.load_image_texture("textures/blocks/mushroom_skin_brown.png")
    else: # red
        cap = self.load_image_texture("textures/blocks/mushroom_skin_red.png")

    stem = self.load_image_texture("textures/blocks/mushroom_skin_stem.png")
    porous = self.load_image_texture("textures/blocks/mushroom_inside.png")
    
    if data == 0: # fleshy piece
        img = self.build_full_block(porous, None, None, porous, porous)

    if data == 1: # north-east corner
        img = self.build_full_block(cap, None, None, cap, porous)

    if data == 2: # east side
        img = self.build_full_block(cap, None, None, porous, porous)

    if data == 3: # south-east corner
        img = self.build_full_block(cap, None, None, porous, cap)

    if data == 4: # north side
        img = self.build_full_block(cap, None, None, cap, porous)

    if data == 5: # top piece
        img = self.build_full_block(cap, None, None, porous, porous)

    if data == 6: # south side
        img = self.build_full_block(cap, None, None, cap, porous)

    if data == 7: # north-west corner
        img = self.build_full_block(cap, None, None, cap, cap)

    if data == 8: # west side
        img = self.build_full_block(cap, None, None, porous, cap)

    if data == 9: # south-west corner
        img = self.build_full_block(cap, None, None, porous, cap)

    if data == 10: # stem
        img = self.build_full_block(porous, None, None, stem, stem)

    if data == 14: # all cap
        img = self.build_block(cap,cap)

    if data == 15: # all stem
        img = self.build_block(stem,stem)

    return img

# iron bars and glass pane
# TODO glass pane is not a sprite, it has a texture for the side,
# at the moment is not used
@material(blockid=[101,102], data=range(16), transparent=True, nospawn=True)
def panes(self, blockid, data):
    # no rotation, uses pseudo data
    if blockid == 101:
        # iron bars
        t = self.load_image_texture("textures/blocks/fenceIron.png")
    else:
        # glass panes
        t = self.load_image_texture("textures/blocks/glass.png")
    left = t.copy()
    right = t.copy()

    # generate the four small pieces of the glass pane
    ImageDraw.Draw(right).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(left).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    
    up_left = self.transform_image_side(left)
    up_right = self.transform_image_side(right).transpose(Image.FLIP_TOP_BOTTOM)
    dw_right = self.transform_image_side(right)
    dw_left = self.transform_image_side(left).transpose(Image.FLIP_TOP_BOTTOM)

    # Create img to compose the texture
    img = Image.new("RGBA", (24,24), self.bgcolor)

    # +x axis points top right direction
    # +y axis points bottom right direction
    # First compose things in the back of the image, 
    # then things in the front.

    if (data & 0b0001) == 1 or data == 0:
        alpha_over(img,up_left, (6,3),up_left)    # top left
    if (data & 0b1000) == 8 or data == 0:
        alpha_over(img,up_right, (6,3),up_right)  # top right
    if (data & 0b0010) == 2 or data == 0:
        alpha_over(img,dw_left, (6,3),dw_left)    # bottom left    
    if (data & 0b0100) == 4 or data == 0:
        alpha_over(img,dw_right, (6,3),dw_right)  # bottom right

    return img

# melon
block(blockid=103, top_image="textures/blocks/melon_top.png", side_image="textures/blocks/melon_side.png", solid=True)

# pumpkin and melon stem
# TODO To render it as in game needs from pseudo data and ancil data:
# once fully grown the stem bends to the melon/pumpkin block,
# at the moment only render the growing stem
@material(blockid=[104,105], data=range(8), transparent=True)
def stem(self, blockid, data):
    # the ancildata value indicates how much of the texture
    # is shown.

    # not fully grown stem or no pumpkin/melon touching it,
    # straight up stem
    t = self.load_image_texture("textures/blocks/stem_straight.png").copy()
    img = Image.new("RGBA", (16,16), self.bgcolor)
    alpha_over(img, t, (0, int(16 - 16*((data + 1)/8.))), t)
    img = self.build_sprite(t)
    if data & 7 == 7:
        # fully grown stem gets brown color!
        # there is a conditional in rendermode-normal.c to not
        # tint the data value 7
        img = self.tint_texture(img, (211,169,116))
    return img
    

# vines
@material(blockid=106, data=range(16), transparent=True)
def vines(self, blockid, data):
    # rotation
    # vines data is bit coded. decode it first.
    # NOTE: the directions used in this function are the new ones used
    # in minecraft 1.0.0, no the ones used by overviewer 
    # (i.e. north is top-left by defalut)

    # rotate the data by bitwise shift
    shifts = 0
    if self.rotation == 1:
        shifts = 1
    elif self.rotation == 2:
        shifts = 2
    elif self.rotation == 3:
        shifts = 3
    
    for i in range(shifts):
        data = data * 2
        if data & 16:
            data = (data - 16) | 1

    # decode data and prepare textures
    raw_texture = self.load_image_texture("textures/blocks/vine.png")
    s = w = n = e = None

    if data & 1: # south
        s = raw_texture
    if data & 2: # west
        w = raw_texture
    if data & 4: # north
        n = raw_texture
    if data & 8: # east
        e = raw_texture

    # texture generation
    img = self.build_full_block(None, n, e, w, s)

    return img

# fence gates
@material(blockid=107, data=range(8), transparent=True, nospawn=True)
def fence_gate(self, blockid, data):

    # rotation
    opened = False
    if data & 0x4:
        data = data & 0x3
        opened = True
    if self.rotation == 1:
        if data == 0: data = 1
        elif data == 1: data = 2
        elif data == 2: data = 3
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 0
        elif data == 3: data = 1
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 0
        elif data == 2: data = 1
        elif data == 3: data = 2
    if opened:
        data = data | 0x4

    # create the closed gate side
    gate_side = self.load_image_texture("textures/blocks/wood.png").copy()
    gate_side_draw = ImageDraw.Draw(gate_side)
    gate_side_draw.rectangle((7,0,15,0),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((7,4,9,6),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((7,10,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((0,12,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((14,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    
    # darken the sides slightly, as with the fences
    sidealpha = gate_side.split()[3]
    gate_side = ImageEnhance.Brightness(gate_side).enhance(0.9)
    gate_side.putalpha(sidealpha)
    
    # create the other sides
    mirror_gate_side = self.transform_image_side(gate_side.transpose(Image.FLIP_LEFT_RIGHT))
    gate_side = self.transform_image_side(gate_side)
    gate_other_side = gate_side.transpose(Image.FLIP_LEFT_RIGHT)
    mirror_gate_other_side = mirror_gate_side.transpose(Image.FLIP_LEFT_RIGHT)
    
    # Create img to compose the fence gate
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    if data & 0x4:
        # opened
        data = data & 0x3
        if data == 0:
            alpha_over(img, gate_side, (2,8), gate_side)
            alpha_over(img, gate_side, (13,3), gate_side)
        elif data == 1:
            alpha_over(img, gate_other_side, (-1,3), gate_other_side)
            alpha_over(img, gate_other_side, (10,8), gate_other_side)
        elif data == 2:
            alpha_over(img, mirror_gate_side, (-1,7), mirror_gate_side)
            alpha_over(img, mirror_gate_side, (10,2), mirror_gate_side)
        elif data == 3:
            alpha_over(img, mirror_gate_other_side, (2,1), mirror_gate_other_side)
            alpha_over(img, mirror_gate_other_side, (13,7), mirror_gate_other_side)
    else:
        # closed
        
        # positions for pasting the fence sides, as with fences
        pos_top_left = (2,3)
        pos_top_right = (10,3)
        pos_bottom_right = (10,7)
        pos_bottom_left = (2,7)
        
        if data == 0 or data == 2:
            alpha_over(img, gate_other_side, pos_top_right, gate_other_side)
            alpha_over(img, mirror_gate_other_side, pos_bottom_left, mirror_gate_other_side)
        elif data == 1 or data == 3:
            alpha_over(img, gate_side, pos_top_left, gate_side)
            alpha_over(img, mirror_gate_side, pos_bottom_right, mirror_gate_side)
    
    return img

# mycelium
block(blockid=110, top_image="textures/blocks/mycel_top.png", side_image="textures/blocks/mycel_side.png")

# lilypad
# At the moment of writing this lilypads has no ancil data and their
# orientation depends on their position on the map. So it uses pseudo
# ancildata.
@material(blockid=111, data=range(4), transparent=True)
def lilypad(self, blockid, data):
    t = self.load_image_texture("textures/blocks/waterlily.png").copy()
    if data == 0:
        t = t.rotate(180)
    elif data == 1:
        t = t.rotate(270)
    elif data == 2:
        t = t
    elif data == 3:
        t = t.rotate(90)

    return self.build_full_block(None, None, None, None, None, t)

# nether brick
block(blockid=112, top_image="textures/blocks/netherBrick.png")

# nether wart
@material(blockid=115, data=range(4), transparent=True)
def nether_wart(self, blockid, data):
    if data == 0: # just come up
        t = self.load_image_texture("textures/blocks/netherStalk_0.png")
    elif data in (1, 2):
        t = self.load_image_texture("textures/blocks/netherStalk_1.png")
    else: # fully grown
        t = self.load_image_texture("textures/blocks/netherStalk_2.png")
    
    # use the same technic as tall grass
    img = self.build_billboard(t)

    return img

# enchantment table
# TODO there's no book at the moment
@material(blockid=116, transparent=True, nodata=True)
def enchantment_table(self, blockid, data):
    # no book at the moment
    top = self.load_image_texture("textures/blocks/enchantment_top.png")
    side = self.load_image_texture("textures/blocks/enchantment_side.png")
    img = self.build_full_block((top, 4), None, None, side, side)

    return img

# brewing stand
# TODO this is a place holder, is a 2d image pasted
@material(blockid=117, data=range(5), transparent=True)
def brewing_stand(self, blockid, data):
    base = self.load_image_texture("textures/blocks/brewingStand_base.png")
    img = self.build_full_block(None, None, None, None, None, base)
    t = self.load_image_texture("textures/blocks/brewingStand.png")
    stand = self.build_billboard(t)
    alpha_over(img,stand,(0,-2))
    return img

# cauldron
@material(blockid=118, data=range(4), transparent=True)
def cauldron(self, blockid, data):
    side = self.load_image_texture("textures/blocks/cauldron_side.png")
    top = self.load_image_texture("textures/blocks/cauldron_top.png")
    bottom = self.load_image_texture("textures/blocks/cauldron_inner.png")
    water = self.transform_image_top(self.load_water())
    if data == 0: # empty
        img = self.build_full_block(top, side, side, side, side)
    if data == 1: # 1/3 filled
        img = self.build_full_block(None , side, side, None, None)
        alpha_over(img, water, (0,8), water)
        img2 = self.build_full_block(top , None, None, side, side)
        alpha_over(img, img2, (0,0), img2)
    if data == 2: # 2/3 filled
        img = self.build_full_block(None , side, side, None, None)
        alpha_over(img, water, (0,4), water)
        img2 = self.build_full_block(top , None, None, side, side)
        alpha_over(img, img2, (0,0), img2)
    if data == 3: # 3/3 filled
        img = self.build_full_block(None , side, side, None, None)
        alpha_over(img, water, (0,0), water)
        img2 = self.build_full_block(top , None, None, side, side)
        alpha_over(img, img2, (0,0), img2)

    return img

# end portal
@material(blockid=119, transparent=True, nodata=True)
def end_portal(self, blockid, data):
    img = Image.new("RGBA", (24,24), self.bgcolor)
    # generate a black texure with white, blue and grey dots resembling stars
    t = Image.new("RGBA", (16,16), (0,0,0,255))
    for color in [(155,155,155,255), (100,255,100,255), (255,255,255,255)]:
        for i in range(6):
            x = randint(0,15)
            y = randint(0,15)
            t.putpixel((x,y),color)

    t = self.transform_image_top(t)
    alpha_over(img, t, (0,0), t)

    return img

# end portal frame (data range 8 to get all orientations of filled)
@material(blockid=120, data=range(8), transparent=True)
def end_portal_frame(self, blockid, data):
    # The bottom 2 bits are oritation info but seems there is no
    # graphical difference between orientations
    top = self.load_image_texture("textures/blocks/endframe_top.png")
    eye_t = self.load_image_texture("textures/blocks/endframe_eye.png")
    side = self.load_image_texture("textures/blocks/endframe_side.png")
    img = self.build_full_block((top, 4), None, None, side, side)
    if data & 0x4 == 0x4: # ender eye on it
        # generate the eye
        eye_t = self.load_image_texture("textures/blocks/endframe_eye.png").copy()
        eye_t_s = self.load_image_texture("textures/blocks/endframe_eye.png").copy()
        # cut out from the texture the side and the top of the eye
        ImageDraw.Draw(eye_t).rectangle((0,0,15,4),outline=(0,0,0,0),fill=(0,0,0,0))
        ImageDraw.Draw(eye_t_s).rectangle((0,4,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
        # trnasform images and paste
        eye = self.transform_image_top(eye_t)
        eye_s = self.transform_image_side(eye_t_s)
        eye_os = eye_s.transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, eye_s, (5,5), eye_s)
        alpha_over(img, eye_os, (9,5), eye_os)
        alpha_over(img, eye, (0,0), eye)

    return img

# end stone
block(blockid=121, top_image="textures/blocks/whiteStone.png")

# dragon egg
# NOTE: this isn't a block, but I think it's better than nothing
block(blockid=122, top_image="textures/blocks/dragonEgg.png")

# inactive redstone lamp
block(blockid=123, top_image="textures/blocks/redstoneLight.png")

# active redstone lamp
block(blockid=124, top_image="textures/blocks/redstoneLight_lit.png")

# daylight sensor.  
@material(blockid=151, transparent=True)
def daylight_sensor(self, blockid, data):
    top = self.load_image_texture("textures/blocks/daylightDetector_top.png")
    side = self.load_image_texture("textures/blocks/daylightDetector_side.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask,(0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)
    
    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12), side)
    alpha_over(img, otherside, (12,12), otherside)
    alpha_over(img, top, (0,6), top)
    
    return img


# wooden double and normal slabs
# these are the new wooden slabs, blockids 43 44 still have wooden
# slabs, but those are unobtainable without cheating
@material(blockid=[125, 126], data=range(16), transparent=(44,), solid=True)
def wooden_slabs(self, blockid, data):
    texture = data & 7
    if texture== 0: # oak 
        top = side = self.load_image_texture("textures/blocks/wood.png")
    elif texture== 1: # spruce
        top = side = self.load_image_texture("textures/blocks/wood_spruce.png")
    elif texture== 2: # birch
        top = side = self.load_image_texture("textures/blocks/wood_birch.png")
    elif texture== 3: # jungle
        top = side = self.load_image_texture("textures/blocks/wood_jungle.png")
    else:
        return None
    
    if blockid == 125: # double slab
        return self.build_block(top, side)
    
    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask,(0,0,16,8), mask)
    
    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)
    
    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)
    
    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)
    
    return img

# emerald ore
block(blockid=129, top_image="textures/blocks/oreEmerald.png")

# emerald block
block(blockid=133, top_image="textures/blocks/blockEmerald.png")

# cocoa plant
@material(blockid=127, data=range(12), transparent=True)
def cocoa_plant(self, blockid, data):
    orientation = data & 3
    # rotation
    if self.rotation == 1:
        if orientation == 0: orientation = 1
        elif orientation == 1: orientation = 2
        elif orientation == 2: orientation = 3
        elif orientation == 3: orientation = 0
    elif self.rotation == 2:
        if orientation == 0: orientation = 2
        elif orientation == 1: orientation = 3
        elif orientation == 2: orientation = 0
        elif orientation == 3: orientation = 1
    elif self.rotation == 3:
        if orientation == 0: orientation = 3
        elif orientation == 1: orientation = 0
        elif orientation == 2: orientation = 1
        elif orientation == 3: orientation = 2

    size = data & 12
    if size == 8: # big
        t = self.load_image_texture("textures/blocks/cocoa_2.png")
        c_left = (0,3)
        c_right = (8,3)
        c_top = (5,2)
    elif size == 4: # normal
        t = self.load_image_texture("textures/blocks/cocoa_1.png")
        c_left = (-2,2)
        c_right = (8,2)
        c_top = (5,2)
    elif size == 0: # small
        t = self.load_image_texture("textures/blocks/cocoa_0.png")
        c_left = (-3,2)
        c_right = (6,2)
        c_top = (5,2)

    # let's get every texture piece necessary to do this
    stalk = t.copy()
    ImageDraw.Draw(stalk).rectangle((0,0,11,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(stalk).rectangle((12,4,16,16),outline=(0,0,0,0),fill=(0,0,0,0))
    
    top = t.copy() # warning! changes with plant size
    ImageDraw.Draw(top).rectangle((0,7,16,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(top).rectangle((7,0,16,6),outline=(0,0,0,0),fill=(0,0,0,0))

    side = t.copy() # warning! changes with plant size
    ImageDraw.Draw(side).rectangle((0,0,6,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(side).rectangle((0,0,16,3),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(side).rectangle((0,14,16,16),outline=(0,0,0,0),fill=(0,0,0,0))
    
    # first compose the block of the cocoa plant
    block = Image.new("RGBA", (24,24), self.bgcolor)
    tmp = self.transform_image_side(side).transpose(Image.FLIP_LEFT_RIGHT)
    alpha_over (block, tmp, c_right,tmp) # right side
    tmp = tmp.transpose(Image.FLIP_LEFT_RIGHT)
    alpha_over (block, tmp, c_left,tmp) # left side
    tmp = self.transform_image_top(top)
    alpha_over(block, tmp, c_top,tmp)
    if size == 0:
        # fix a pixel hole
        block.putpixel((6,9), block.getpixel((6,10)))

    # compose the cocoa plant
    img = Image.new("RGBA", (24,24), self.bgcolor)
    if orientation in (2,3): # south and west
        tmp = self.transform_image_side(stalk).transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, block,(-1,-2), block)
        alpha_over(img, tmp, (4,-2), tmp)
        if orientation == 3:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
    elif orientation in (0,1): # north and east
        tmp = self.transform_image_side(stalk.transpose(Image.FLIP_LEFT_RIGHT))
        alpha_over(img, block,(-1,5), block)
        alpha_over(img, tmp, (2,12), tmp)
        if orientation == 0:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)

    return img

# command block
block(blockid=137, top_image="textures/blocks/commandBlock.png")

# beacon block
# at the moment of writing this, it seems the beacon block doens't use
# the data values
@material(blockid=138, transparent=True, nodata = True)
def beacon(self, blockid, data):
    # generate the three pieces of the block
    t = self.load_image_texture("textures/blocks/glass.png")
    glass = self.build_block(t,t)
    t = self.load_image_texture("textures/blocks/obsidian.png")
    obsidian = self.build_full_block((t,12),None, None, t, t)
    obsidian = obsidian.resize((20,20), Image.ANTIALIAS)
    t = self.load_image_texture("textures/blocks/beacon.png")
    crystal = self.build_block(t,t)
    crystal = crystal.resize((16,16),Image.ANTIALIAS)
    
    # compose the block
    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, obsidian, (2, 4), obsidian)
    alpha_over(img, crystal, (4,3), crystal)
    alpha_over(img, glass, (0,0), glass)
    
    return img

# cobbleston and mossy cobblestone walls
# one additional bit of data value added for mossy and cobblestone
@material(blockid=139, data=range(32), transparent=True, nospawn=True)
def cobblestone_wall(self, blockid, data):
    # no rotation, uses pseudo data
    if data & 0b10000 == 0:
        # cobblestone
        t = self.load_image_texture("textures/blocks/stonebrick.png").copy()
    else:
        # mossy cobblestone
        t = self.load_image_texture("textures/blocks/stoneMoss.png").copy()

    wall_pole_top = t.copy()
    wall_pole_side = t.copy()
    wall_side_top = t.copy()
    wall_side = t.copy()
    # _full is used for walls without pole
    wall_side_top_full = t.copy()
    wall_side_full = t.copy()

    # generate the textures of the wall
    ImageDraw.Draw(wall_pole_top).rectangle((0,0,3,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_pole_top).rectangle((12,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_pole_top).rectangle((0,0,15,3),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_pole_top).rectangle((0,12,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    ImageDraw.Draw(wall_pole_side).rectangle((0,0,3,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_pole_side).rectangle((12,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the pole
    wall_pole_side = self.transform_image_side(wall_pole_side)
    wall_pole_other_side = wall_pole_side.transpose(Image.FLIP_LEFT_RIGHT)
    wall_pole_top = self.transform_image_top(wall_pole_top)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = wall_pole_side.split()[3]
    wall_pole_side = ImageEnhance.Brightness(wall_pole_side).enhance(0.8)
    wall_pole_side.putalpha(sidealpha)
    othersidealpha = wall_pole_other_side.split()[3]
    wall_pole_other_side = ImageEnhance.Brightness(wall_pole_other_side).enhance(0.7)
    wall_pole_other_side.putalpha(othersidealpha)

    # Compose the wall pole
    wall_pole = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(wall_pole,wall_pole_side, (3,4),wall_pole_side)
    alpha_over(wall_pole,wall_pole_other_side, (9,4),wall_pole_other_side)
    alpha_over(wall_pole,wall_pole_top, (0,0),wall_pole_top)
    
    # create the sides and the top of a wall attached to a pole
    ImageDraw.Draw(wall_side).rectangle((0,0,15,2),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side).rectangle((0,0,11,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side_top).rectangle((0,0,11,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side_top).rectangle((0,0,15,4),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side_top).rectangle((0,11,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    # full version, without pole
    ImageDraw.Draw(wall_side_full).rectangle((0,0,15,2),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side_top_full).rectangle((0,4,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(wall_side_top_full).rectangle((0,4,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # compose the sides of a wall atached to a pole
    tmp = Image.new("RGBA", (24,24), self.bgcolor)
    wall_side = self.transform_image_side(wall_side)
    wall_side_top = self.transform_image_top(wall_side_top)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = wall_side.split()[3]
    wall_side = ImageEnhance.Brightness(wall_side).enhance(0.7)
    wall_side.putalpha(sidealpha)

    alpha_over(tmp,wall_side, (0,0),wall_side)
    alpha_over(tmp,wall_side_top, (-5,3),wall_side_top)
    wall_side = tmp
    wall_other_side = wall_side.transpose(Image.FLIP_LEFT_RIGHT)

    # compose the sides of the full wall
    tmp = Image.new("RGBA", (24,24), self.bgcolor)
    wall_side_full = self.transform_image_side(wall_side_full)
    wall_side_top_full = self.transform_image_top(wall_side_top_full.rotate(90))

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = wall_side_full.split()[3]
    wall_side_full = ImageEnhance.Brightness(wall_side_full).enhance(0.7)
    wall_side_full.putalpha(sidealpha)

    alpha_over(tmp,wall_side_full, (4,0),wall_side_full)
    alpha_over(tmp,wall_side_top_full, (3,-4),wall_side_top_full)
    wall_side_full = tmp
    wall_other_side_full = wall_side_full.transpose(Image.FLIP_LEFT_RIGHT)

    # Create img to compose the wall
    img = Image.new("RGBA", (24,24), self.bgcolor)

    # Position wall imgs around the wall bit stick
    pos_top_left = (-5,-2)
    pos_bottom_left = (-8,4)
    pos_top_right = (5,-3)
    pos_bottom_right = (7,4)
    
    # +x axis points top right direction
    # +y axis points bottom right direction
    # There are two special cases for wall without pole.
    # Normal case: 
    # First compose the walls in the back of the image, 
    # then the pole and then the walls in the front.
    if (data == 0b1010) or (data == 0b11010):
        alpha_over(img, wall_other_side_full,(0,2), wall_other_side_full)
    elif (data == 0b0101) or (data == 0b10101):
        alpha_over(img, wall_side_full,(0,2), wall_side_full)
    else:
        if (data & 0b0001) == 1:
            alpha_over(img,wall_side, pos_top_left,wall_side)                # top left
        if (data & 0b1000) == 8:
            alpha_over(img,wall_other_side, pos_top_right,wall_other_side)    # top right

        alpha_over(img,wall_pole,(0,0),wall_pole)
            
        if (data & 0b0010) == 2:
            alpha_over(img,wall_other_side, pos_bottom_left,wall_other_side)      # bottom left    
        if (data & 0b0100) == 4:
            alpha_over(img,wall_side, pos_bottom_right,wall_side)                  # bottom right
    
    return img

# carrots and potatoes
@material(blockid=[141,142], data=range(8), transparent=True, nospawn=True)
def crops(self, blockid, data):
    if data != 7: # when growing they look the same
        # data = 7 -> fully grown, everything else is growing
        # this seems to work, but still not sure
        raw_crop = self.load_image_texture("textures/blocks/potatoes_%d.png" % (data % 3))
    elif blockid == 141: # carrots
        raw_crop = self.load_image_texture("textures/blocks/carrots_3.png")
    else: # potatoes
        raw_crop = self.load_image_texture("textures/blocks/potatoes_3.png")
    crop1 = self.transform_image_top(raw_crop)
    crop2 = self.transform_image_side(raw_crop)
    crop3 = crop2.transpose(Image.FLIP_LEFT_RIGHT)

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, crop1, (0,12), crop1)
    alpha_over(img, crop2, (6,3), crop2)
    alpha_over(img, crop3, (6,3), crop3)
    return img

# anvils
@material(blockid=145, data=range(12), transparent=True)
def anvil(self, blockid, data):
    
    # anvils only have two orientations, invert it for rotations 1 and 3
    orientation = data & 0x1
    if self.rotation in (1,3):
        if orientation == 1:
            orientation = 0
        else:
            orientation = 1

    # get the correct textures
    # the bits 0x4 and 0x8 determine how damaged is the anvil
    if (data & 0xc) == 0: # non damaged anvil
        top = self.load_image_texture("textures/blocks/anvil_top.png")
    elif (data & 0xc) == 0x4: # slightly damaged
        top = self.load_image_texture("textures/blocks/anvil_top_damaged_1.png")
    elif (data & 0xc) == 0x8: # very damaged
        top = self.load_image_texture("textures/blocks/anvil_top_damaged_2.png")
    # everything else use this texture
    big_side = self.load_image_texture("textures/blocks/anvil_base.png").copy()
    small_side = self.load_image_texture("textures/blocks/anvil_base.png").copy()
    base = self.load_image_texture("textures/blocks/anvil_base.png").copy()
    small_base = self.load_image_texture("textures/blocks/anvil_base.png").copy()
    
    # cut needed patterns
    ImageDraw.Draw(big_side).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(small_side).rectangle((0,0,2,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(small_side).rectangle((13,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(small_side).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(base).rectangle((0,0,15,15),outline=(0,0,0,0))
    ImageDraw.Draw(base).rectangle((1,1,14,14),outline=(0,0,0,0))
    ImageDraw.Draw(small_base).rectangle((0,0,15,15),outline=(0,0,0,0))
    ImageDraw.Draw(small_base).rectangle((1,1,14,14),outline=(0,0,0,0))
    ImageDraw.Draw(small_base).rectangle((2,2,13,13),outline=(0,0,0,0))
    ImageDraw.Draw(small_base).rectangle((3,3,12,12),outline=(0,0,0,0))
    
    # check orientation and compose the anvil
    if orientation == 1: # bottom-left top-right
        top = top.rotate(90)
        left_side = small_side
        left_pos = (1,7)
        right_side = big_side
        right_pos = (10,5)
    else: # top-left bottom-right
        right_side = small_side
        right_pos = (12,7)
        left_side = big_side
        left_pos = (3,5)
    
    img = Image.new("RGBA", (24,24), self.bgcolor)
    
    # darken sides
    alpha = big_side.split()[3]
    big_side = ImageEnhance.Brightness(big_side).enhance(0.8)
    big_side.putalpha(alpha)
    alpha = small_side.split()[3]
    small_side = ImageEnhance.Brightness(small_side).enhance(0.9)
    small_side.putalpha(alpha)
    alpha = base.split()[3]
    base_d = ImageEnhance.Brightness(base).enhance(0.8)
    base_d.putalpha(alpha)
    
    # compose
    base = self.transform_image_top(base)
    base_d = self.transform_image_top(base_d)
    small_base = self.transform_image_top(small_base)
    top = self.transform_image_top(top)
    
    alpha_over(img, base_d, (0,12), base_d)
    alpha_over(img, base_d, (0,11), base_d)
    alpha_over(img, base_d, (0,10), base_d)
    alpha_over(img, small_base, (0,10), small_base)
    
    alpha_over(img, top, (0,0), top)
    
    left_side = self.transform_image_side(left_side)
    right_side = self.transform_image_side(right_side).transpose(Image.FLIP_LEFT_RIGHT)
    
    alpha_over(img, left_side, left_pos, left_side)
    alpha_over(img, right_side, right_pos, right_side)
    
    return img


# block of redstone
block(blockid=152, top_image="textures/blocks/blockRedstone.png")

# nether quartz ore
block(blockid=153, top_image="textures/blocks/netherquartz.png")

# block of quartz
@material(blockid=155, data=range(5), solid=True)
def quartz_block(self, blockid, data):
    
    if data in (0,1): # normal and chiseled quartz block
        if data == 0:
            top = self.load_image_texture("textures/blocks/quartzblock_top.png")
            side = self.load_image_texture("textures/blocks/quartzblock_side.png")
        else:
            top = self.load_image_texture("textures/blocks/quartzblock_chiseled_top.png")
            side = self.load_image_texture("textures/blocks/quartzblock_chiseled.png")    
        return self.build_block(top, side)
    
    # pillar quartz block with orientation
    top = self.load_image_texture("textures/blocks/quartzblock_lines_top.png")
    side = self.load_image_texture("textures/blocks/quartzblock_lines.png").copy()
    if data == 2: # vertical
        return self.build_block(top, side)
    elif data == 3: # north-south oriented
        if self.rotation in (0,2):
            return self.build_full_block(side, None, None, top, side.rotate(90))
        return self.build_full_block(side.rotate(90), None, None, side.rotate(90), top)
        
    elif data == 4: # east-west oriented
        if self.rotation in (0,2):
            return self.build_full_block(side.rotate(90), None, None, side.rotate(90), top)
        return self.build_full_block(side, None, None, top, side.rotate(90))
    
# hopper
@material(blockid=154, data=range(4), transparent=True)
def hopper(self, blockid, data):
    #build the top
    side = self.load_image_texture("textures/blocks/hopper.png")
    top = self.load_image_texture("textures/blocks/hopper_top.png")
    bottom = self.load_image_texture("textures/blocks/hopper_inside.png")
    hop_top = self.build_full_block((top,10), side, side, side, side, side)

    #build a solid block for mid/top
    hop_mid = self.build_full_block((top,5), side, side, side, side, side)
    hop_bot = self.build_block(side,side)

    hop_mid = hop_mid.resize((17,17),Image.ANTIALIAS)
    hop_bot = hop_bot.resize((10,10),Image.ANTIALIAS)
    
    #compose the final block
    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, hop_bot, (7,14), hop_bot)
    alpha_over(img, hop_mid, (3,3), hop_mid)
    alpha_over(img, hop_top, (0,-6), hop_top)

    return img


#########################################
#	Start mod blocks					#
#	Taken from FTB Unleashed configs	#
#########################################

#################################
#	 	Applied Energistics		#
#################################

# Applied Energistics: Machinery and cables (I:appeng.blockMulti=900)
@material(blockid=900, data=range(16), solid=True, transparent=True)
def ae_multi1(self, blockid, data):
    # FIXME All of the blocks are rendered either with no face, or the face on every side,
    # because the orientation and other spesific information is stored in the tile entity data
    if data == 0: # ME Cable - Blue FIXME totally wrong, maybe we shouldn't render anything?
        side = self.load_image_texture("textures/blocks/ae/MECable_Blue.png")
        return self.build_block(side, side)
    elif data == 1: # ME Pattern Provider
        side = self.load_image_texture("textures/blocks/ae/BlockAssembler.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 2: # ME Controller
        side = self.load_image_texture("textures/blocks/ae/ControllerPanel.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 3: # ME Drive
        side = self.load_image_texture("textures/blocks/ae/BlockDriveFace.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 4: # ME Pattern Encoder
        side = self.load_image_texture("textures/blocks/ae/BlockPatternEncoderSide.png")
        top = self.load_image_texture("textures/blocks/ae/BlockPatternEncoder.png")
    elif data == 5: # ME Wireless Access Point
        side = self.load_image_texture("textures/blocks/ae/BlockWireless.png")
        return self.build_block(side, side)
    elif data == 6: # ME Access Terminal
        side = self.load_image_texture("textures/blocks/ae/METerm_Blue.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 7: # ME Chest
        side = self.load_image_texture("textures/blocks/ae/BlockChestSide.png")
        top = self.load_image_texture("textures/blocks/ae/BlockChestTopGreen.png")
    elif data == 8: # ME Interface
        side = self.load_image_texture("textures/blocks/ae/BlockInterface.png")
        top = self.load_image_texture("textures/blocks/ae/BlockInterface.png")
    elif data == 9: # ME Partition Editor
        side = self.load_image_texture("textures/blocks/ae/BlockPreformatterSide.png")
        top = self.load_image_texture("textures/blocks/ae/BlockPreformatter.png")

    # FIXME the cables are totally wrong, maybe we shouldn't render anything?
    elif data == 10: # ME Cable - Black
        side = self.load_image_texture("textures/blocks/ae/MECable_Black.png")
        return self.build_block(side, side)
    elif data == 11: # ME Cable - White
        side = self.load_image_texture("textures/blocks/ae/MECable_White.png")
        return self.build_block(side, side)
    elif data == 12: # ME Cable - Brown
        side = self.load_image_texture("textures/blocks/ae/MECable_Brown.png")
        return self.build_block(side, side)
    elif data == 13: # ME Cable - Red
        side = self.load_image_texture("textures/blocks/ae/MECable_Red.png")
        return self.build_block(side, side)
    elif data == 14: # ME Cable - Yellow
        side = self.load_image_texture("textures/blocks/ae/MECable_Yellow.png")
        return self.build_block(side, side)
    elif data == 15: # ME Cable - Green
        side = self.load_image_texture("textures/blocks/ae/MECable_Green.png")
        return self.build_block(side, side)

    return self.build_block(top, side)

# Applied Energistics: More machines etc. (I:appeng.blockMulti2=901)
@material(blockid=901, data=range(16), solid=True, transparent=True)
def ae_multi1(self, blockid, data):
    # FIXME All of the blocks are rendered either with no face, or the face on every side,
    # because the orientation and other spesific information is stored in the tile entity data
    if data == 3: # ME Crafting Terminal
        side = self.load_image_texture("textures/blocks/ae/MECTerm_Blue.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 5: # ME Crafting CPU
        side = self.load_image_texture("textures/blocks/ae/BlockCraftingCpu.png")
        return self.build_block(side, side)
    elif data == 6: # ME Heat Vent
        side = self.load_image_texture("textures/blocks/ae/BlockHeatVent.png")
        return self.build_block(side, side)
    elif data == 7: # ME Assembler Containment Wall
        side = self.load_image_texture("textures/blocks/ae/BlockContainmentWall.png")
        return self.build_block(side, side)
    elif data == 10: # ME IO Port
        side = self.load_image_texture("textures/blocks/ae/BlockIOPortSide.png")
        top = self.load_image_texture("textures/blocks/ae/BlockIOPortTop.png")
    elif data == 11: # ME Crafting Monitor
        side = self.load_image_texture("textures/blocks/ae/MECraftingMon_Blue.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    elif data == 12: # ME Storage Monitor
        side = self.load_image_texture("textures/blocks/ae/MEStorageMonitor_Blue.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
    else: # Cables, import/export/storage buses etc. that we don't support atm
        return None

    return self.build_block(top, side)

# Applied Energistics: Ore, Glass, etc. (I:appeng.blockWorld=902)
@material(blockid=902, data=range(5), solid=True, transparent=True)
def ae_world(self, blockid, data):
    if data == 0: # Certus Quartz Ore
        side = self.load_image_texture("textures/blocks/ae/BlockQuartz.png")
    elif data == 1: # Grind Stone NOTE: we render every side the same (no front face, orientation is in te data)
        side = self.load_image_texture("textures/blocks/ae/BlockGrinderSide.png")
        top = self.load_image_texture("textures/blocks/ae/BlockGrinderTop.png")
        return self.build_block(top, side)
    elif data == 2: # Certus Quartz Block
        side = self.load_image_texture("textures/blocks/ae/BlockQuartzBlk.png")
    elif data == 3: # Quartz Glass (NOTE: We don't do connected textures...)
        side = self.load_image_texture("textures/blocks/ae/BlockQuartzGlass.png")
    elif data == 4: # Vibrant Quartz Glass (NOTE: We don't do connected textures...)
        side = self.load_image_texture("textures/blocks/ae/BlockQuartzGlass.png")
    return self.build_block(side, side)

# Applied Energistics: More machines etc. (I:appeng.blockMulti3=903)
@material(blockid=903, data=range(16), solid=True, transparent=True)
def ae_multi1(self, blockid, data):
    # FIXME All of the blocks are rendered either with no face, or the face on every side,
    # because the orientation and other spesific information is stored in the tile entity data
    if data == 4: # ME Transition Plane
        side = self.load_image_texture("textures/blocks/ae/block_side.png")
        top = self.load_image_texture("textures/blocks/ae/block_top.png")
        return self.build_block(top, side)
    elif data == 5: # Energy Cell
        side = self.load_image_texture("textures/blocks/ae/BlockEnergyCell.png")
    elif data == 6: # ME Power Relay
        side = self.load_image_texture("textures/blocks/ae/BlockPowerRelay.png")
    elif data == 7: # ME Condenser
        side = self.load_image_texture("textures/blocks/ae/BlockCondendser.png")
    else: # Other stuff that we don't support atm
        return None

    return self.build_block(side, side)


#################################
#	 	Factorization			#
#################################

# Factorization: Barrels (I:factoryBlockId=1000)
@material(blockid=1000, data=range(16), solid=True)
def fact_machine(self, blockid, data):
    # FIXME A lot of these things are approximations, because a lot of the data is in the tile entity data
    if data == 1: # Router
        side = self.load_image_texture("textures/blocks/factorization/router/south_off.png")
        top = self.load_image_texture("textures/blocks/factorization/router/top.png")
    elif data == 2: # Barrel (both regular and upgraded...)
        side = self.load_image_texture("textures/blocks/factorization/storage/barrel_side.png")
        top = self.load_image_texture("textures/blocks/factorization/storage/barrel_top.png")
    elif data == 7: # Craftpacket Maker AND Craftpacket Stamper AND Packager... (FFS)
        side = self.load_image_texture("textures/blocks/factorization/craft/maker_side.png")
        top = self.load_image_texture("textures/blocks/factorization/craft/maker_top.png")
    elif data == 8: # Slag Furnace
        side = self.load_image_texture("textures/blocks/factorization/machine/slag_furnace_face.png")
        top = self.load_image_texture("textures/blocks/factorization/machine/slag_furnace_top.png")
    else: # Unsupported blocks
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(side)

    return self.build_block(top, side)

# Factorization: Resource Blocks (I:resourceBlockId=1002)
@material(blockid=1002, data=range(16), solid=True)
def fact_machine(self, blockid, data):
    if data == 3: # Block of Dark Iron
        side = self.load_image_texture("textures/blocks/factorization/resource/dark_iron_block.png")
    else: # Unsupported blocks
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(side)

    return self.build_block(side, side)

#################################
#	 	Dartcraft				#
#################################

# Dartcraft: Power Ore (I:"Power Ore"=1900)
@material(blockid=1900, data=range(2), solid=True)
def dartcraft_ore(self, blockid, data):
    if data == 0: # Power Ore
        side = self.load_image_texture("textures/blocks/dartcraft/oreTop.png")
    elif data == 1: # Nether Ore
        side = self.load_image_texture("textures/blocks/dartcraft/nether.png")
    return self.build_block(side, side)

# Dartcraft: Force Stairs (I:"Force Stairs"=1901)
@material(blockid=1901, data=range(16), transparent=True, solid=True, nospawn=True)
def dartcraft_stairs(self, blockid, data):
    # first, rotations
    # preserve the upside-down bit
    upside_down = data & 0x4
    data = data & 0x3
    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1
    data = data | upside_down

    # FIXME/NOTE: The stair type is stored in tile entity data, we render them all as Black Force Stairs
    texture = self.load_image_texture("textures/blocks/dartcraft/brick0.png")

    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))

    if data & 0x4 == 0x4: # upside down stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))

        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)

        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)

        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))

    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))

        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)

        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)

        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) # workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))

        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))

    return img

# Dartcraft: Force Bricks (I:"Force Brick"=1903)
@material(blockid=1903, data=range(16), solid=True)
def dartcraft_forcebricks(self, blockid, data):
    side = self.load_image_texture("textures/blocks/dartcraft/brick%d.png" % data)
    return self.build_block(side, side)

# Dartcraft: Force Log & Planks (I:"Force Wood"=1904)
@material(blockid=1904, data=range(16), solid=True)
def dartcraft_forcewood(self, blockid, data):
    if data == 1: # Force Planks
        side = self.load_image_texture("textures/blocks/dartcraft/logSide.png")
        return self.build_block(side, side)

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    side = self.load_image_texture("textures/blocks/dartcraft/logSide.png")
    top = self.load_image_texture("textures/blocks/dartcraft/logTop.png")

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Dartcraft: Force Leaves (I:"Force Leaves"=1905)
block(blockid=1905, top_image="textures/blocks/dartcraft/leaves.png", transparent=True, solid=True)

# Dartcraft: Force Sapling (I:Plants=1906)
sprite(blockid=1906, imagename="textures/blocks/dartcraft/sapling.png")

# Dartcraft: Force Slabs (I:"Force Slab"=1908)
@material(blockid=1908, data=range(16), solid=True)
def dartcraft_forceslabs(self, blockid, data):
    # FIXME We use the same texture for all the slabs, since the slab type is stored in the tile entity data
    top = side = self.load_image_texture("textures/blocks/dartcraft/brick0.png")
    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

#################################
#	 Extra Utilities			#
#################################

# Extra Utilities: Angel Block (I:angelBlock=2500)
block(blockid=2500, top_image="textures/blocks/extrautilities/angelBlock.png")

# Extra Utilities: Block Update Detector (I:BUDBlockId=2501)
# NOTE: we don't care about the metadata, the block is usually ON for so short
# times that we render it always in the OFF state
block(blockid=2501, top_image="textures/blocks/extrautilities/budoff.png")

# Extra Utilities: Colored Bricks (I:colorBlockBrickId=2504)
@material(blockid=2504, data=range(16), solid=True)
def extrautilities_coloredbricks(self, blockid, data):
    texture = self.load_image_texture("textures/blocks/extrautilities/colorStoneBrick.png")

    # FIXME: The colors may not be entirely accurate, they are estimates from a screenshot...
    if data == 0: # White: Do nothing
        return self.build_block(texture, texture)
    elif data == 1: # Orange
        side = self.tint_texture(texture, (0xc8, 0x84, 0x35))
    elif data == 2: # Magenta
        side = self.tint_texture(texture, (0xcc, 0x57, 0xdd))
    elif data == 3: # Light Blue
        side = self.tint_texture(texture, (0x6e, 0xa5, 0xd1))
    elif data == 4: # Yellow
        side = self.tint_texture(texture, (0xdd, 0xdd, 0x3a))
    elif data == 5: # Lime
        side = self.tint_texture(texture, (0x8a, 0xd1, 0x1c))
    elif data == 6: # Pink
        side = self.tint_texture(texture, (0xdd, 0x92, 0xbe))
    elif data == 7: # Gray
        side = self.tint_texture(texture, (0x57, 0x57, 0x57))
    elif data == 8: # Light Gray
        side = self.tint_texture(texture, (0x9e, 0x9e, 0x9e))
    elif data == 9: # Cyan
        side = self.tint_texture(texture, (0x57, 0x92, 0xaf))
    elif data == 10: # Purple
        side = self.tint_texture(texture, (0x84, 0x42, 0xb9))
    elif data == 11: # Blue
        side = self.tint_texture(texture, (0x3a, 0x57, 0xcc))
    elif data == 12: # Brown
        side = self.tint_texture(texture, (0x6a, 0x4f, 0x35))
    elif data == 13: # Green
        side = self.tint_texture(texture, (0x75, 0x92, 0x3a))
    elif data == 14: # Red
        side = self.tint_texture(texture, (0x9e, 0x35, 0x35))
    elif data == 15: # Black
        side = self.tint_texture(texture, (0x18, 0x18, 0x18))

    return self.build_block(side, side)

# Extra Utilities: Compressed Cobblestone (I:cobblestoneComprId=2506)
@material(blockid=2506, data=range(8), solid=True)
def extrautilities_compressedcobble(self, blockid, data):
    side = self.load_image_texture("textures/blocks/extrautilities/cobblestone_compressed_%d.png" % (data + 1))
    return self.build_block(side, side)

# Extra Utilities: Sound Muffler & Rain Muffler (I:soundMufflerId=2510)
@material(blockid=2510, data=range(2), solid=True)
def extrautilities_muffler(self, blockid, data):
    if data == 0: # Sound Muffler
        side = self.load_image_texture("textures/blocks/extrautilities/sound_muffler.png")
    elif data == 1: # Rain Muffler
        side = self.load_image_texture("textures/blocks/extrautilities/rain_muffler.png")

    return self.build_block(side, side)

# Extra Utilities: Trading Post (I:tradingPost=2511)
@material(blockid=2511, nodata=True, solid=True)
def extrautilities_muffler(self, blockid, data):
    side = self.load_image_texture("textures/blocks/extrautilities/trading_post_side.png")
    top = self.load_image_texture("textures/blocks/extrautilities/trading_post_top.png")
    return self.build_block(top, side)

# Extra Utilities: Cursed Earth (I:cursedEarth=2515)
@material(blockid=2515, nodata=True, solid=True)
def extrautilities_muffler(self, blockid, data):
    side = self.load_image_texture("textures/blocks/extrautilities/cursedearthside.png")
    top = self.load_image_texture("textures/blocks/extrautilities/cursedearthtop.png")
    return self.build_block(top, side)

# Extra Utilities: Ethereal Glass (I:etherealBlockId=2518)
block(blockid=2518, top_image="textures/blocks/extrautilities/etherealglass.png", transparent=True, nospawn=True)

# Extra Utilities: Colored Planks (I:coloredWoodId=2519)
@material(blockid=2519, data=range(16), solid=True)
def extrautilities_coloredplanks(self, blockid, data):
    texture = self.load_image_texture("textures/blocks/extrautilities/colorWoodPlanks.png")

    # FIXME: The colors may not be entirely accurate, they are estimates from a screenshot...
    if data == 0: # White: Do nothing
        return self.build_block(texture, texture)
    elif data == 1: # Orange
        side = self.tint_texture(texture, (0xff, 0x9c, 0x32))
    elif data == 2: # Magenta
        side = self.tint_texture(texture, (0xd8, 0x54, 0x9e))
    elif data == 3: # Light Blue
        side = self.tint_texture(texture, (0x86, 0xb4, 0xb4))
    elif data == 4: # Yellow
        side = self.tint_texture(texture, (0xea, 0xd5, 0x2a))
    elif data == 5: # Lime
        side = self.tint_texture(texture, (0x9a, 0xd5, 0x15))
    elif data == 6: # Pink
        side = self.tint_texture(texture, (0xff, 0x96, 0x9a))
    elif data == 7: # Gray
        side = self.tint_texture(texture, (0x65, 0x5a, 0x47))
    elif data == 8: # Light Gray
        side = self.tint_texture(texture, (0xca, 0xbc, 0x96))
    elif data == 9: # Cyan
        side = self.tint_texture(texture, (0x5d, 0x8c, 0x7d))
    elif data == 10: # Purple
        side = self.tint_texture(texture, (0x9a, 0x46, 0x92))
    elif data == 11: # Blue
        side = self.tint_texture(texture, (0x43, 0x5e, 0xaf))
    elif data == 12: # Brown
        side = self.tint_texture(texture, (0x86, 0x5e, 0x32))
    elif data == 13: # Green
        side = self.tint_texture(texture, (0x86, 0x96, 0x30))
    elif data == 14: # Red
        side = self.tint_texture(texture, (0xca, 0x3f, 0x32))
    elif data == 15: # Black
        side = self.tint_texture(texture, (0x1f, 0x1c, 0x15))

    return self.build_block(side, side)

# Extra Utilities: Ender-Thermic Pump (I:enderThermicPumpId=2520)
@material(blockid=2520, nodata=True, solid=True)
def extrautilities_enderthermicpump(self, blockid, data):
    side = self.load_image_texture("textures/blocks/extrautilities/enderThermicPump_side.png")
    top = self.load_image_texture("textures/blocks/extrautilities/enderThermicPump_top.png")
    return self.build_block(top, side)

# Extra Utilities: Redstone Clock (I:timerBlockId=2521)
block(blockid=2521, top_image="textures/blocks/extrautilities/timer.png")

#################################
#	 	Binnie Mods				#
#################################

# Binnie Mods (Extra Trees) Planks (I:planks=3700)
# FIXME We use the same texture for all the planks, since the wood type is stored in the tile entity data
block(blockid=3700, top_image="textures/blocks/extratrees/planks/Fir.png")

# Binnie Mods (Extra Trees) Stairs (I:stairs=3702)
@material(blockid=3702, data=range(16), transparent=True, solid=True, nospawn=True)
def binnie_stairs(self, blockid, data):
    # first, rotations
    # preserve the upside-down bit
    upside_down = data & 0x4
    data = data & 0x3
    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1
    data = data | upside_down

    # FIXME/NOTE: The wood type is stored in tile entity data, we render them all as Fir stairs
    texture = self.load_image_texture("textures/blocks/extratrees/planks/Fir.png")

    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))

    if data & 0x4 == 0x4: # upside down stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))

        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)

        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)

        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))

    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))

        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)

        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)

        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) # workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))

        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))

    return img

# Binnie Mods (Extra Trees) Logs (I:log=3704)
@material(blockid=3704, data=range(16), solid=True)
def binnie_logs(self, blockid, data):
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # FIXME We use the same texture for all the logs, since the wood type is stored in the tile entity data
    side = self.load_image_texture("textures/blocks/extratrees/logs/firBark.png")
    top = self.load_image_texture("textures/blocks/extratrees/logs/firTrunk.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Binnie Mods (Extra Trees) Slabs (I:slab=3707)
@material(blockid=3707, data=range(16), solid=True)
def binnie_slabs(self, blockid, data):
    # FIXME We use the same texture for all the slabs, since the wood type is stored in the tile entity data
    top = side = self.load_image_texture("textures/blocks/extratrees/planks/Fir.png")
    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Binnie Mods (Extra Trees) Double Slabs (I:doubleSlab=3708)
# FIXME We use the same texture for all the blocks, since the wood type is stored in the tile entity data
block(blockid=3708, top_image="textures/blocks/extratrees/planks/Fir.png")

# Binnie Mods (Extra Bees) Hives (I:hive=4000)
@material(blockid=4000, data=range(4), solid=True)
def binnie_hive(self, blockid, data):
    if data == 0: # Water Hive
        side = self.load_image_texture("textures/blocks/extrabees/hive/water.0.png")
        top = self.load_image_texture("textures/blocks/extrabees/hive/water.1.png")
    elif data == 1: # Rock Hive
        side = self.load_image_texture("textures/blocks/extrabees/hive/rock.0.png")
        top = self.load_image_texture("textures/blocks/extrabees/hive/rock.1.png")
    elif data == 2: # Nether Hive
        side = self.load_image_texture("textures/blocks/extrabees/hive/rock.0.png")
        top = self.load_image_texture("textures/blocks/extrabees/hive/rock.1.png")
    elif data == 3: # Marble Hive
        side = self.load_image_texture("textures/blocks/extrabees/hive/rock.0.png")
        top = self.load_image_texture("textures/blocks/extrabees/hive/rock.1.png")
    return self.build_block(top, side)


#################################
#	 		Natura				#
#################################

# Natura: Tainted Soil (I:"Tainted Soil"=169)
block(blockid=169, top_image="textures/blocks/natura/tainted_soil.png")

# Natura: Heat Sand (I:"Heat Sand"=170)
block(blockid=170, top_image="textures/blocks/natura/heatsand.png")

# Natura: Wood logs (I:"Wood Block"=3251)
@material(blockid=3251, data=range(16), solid=True)
def natura_wood(self, blockid, data):
    bdata = data & 3
    if bdata == 0: # Eucalyptus Wood
        side = self.load_image_texture("textures/blocks/natura/eucalyptus_bark.png")
        top = self.load_image_texture("textures/blocks/natura/eucalyptus_heart.png")
    elif bdata == 1: # Sakura Wood
        side = self.load_image_texture("textures/blocks/natura/sakura_bark.png")
        top = self.load_image_texture("textures/blocks/natura/sakura_heart.png")
    elif bdata == 2: # Ghostwood Wood
        side = self.load_image_texture("textures/blocks/natura/ghostwood_bark.png")
        top = self.load_image_texture("textures/blocks/natura/ghostwood_heart.png")
    elif bdata == 3: # Hopseed Wood
        side = self.load_image_texture("textures/blocks/natura/hopseed_bark.png")
        top = self.load_image_texture("textures/blocks/natura/hopseed_heart.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Natura: Clouds (I:"Cloud Block"=3253)
@material(blockid=3253, data=range(4), solid=True, transparent=True)
def natura_clouds(self, blockid, data):
    if data == 0: # Cloud
        side = self.load_image_texture("textures/blocks/natura/cloud_white.png")
    elif data == 1: # Dark Cloud
        side = self.load_image_texture("textures/blocks/natura/cloud_gray.png")
    elif data == 2: # Ash Cloud
        side = self.load_image_texture("textures/blocks/natura/cloud_dark.png")
    elif data == 3: # Sulfur Cloud
        side = self.load_image_texture("textures/blocks/natura/cloud_sulfur.png")
    return self.build_block(side, side)

# Natura: Saguaro Cactus (I:"Saguaro Cactus"=3254)
@material(blockid=3254, data=range(16), solid=True)
def natura_saguarocactus(self, blockid, data):
    # FIXME: data values unchecked, rendering not accurate, missing fruits, etc.
    side = self.load_image_texture("textures/blocks/natura/saguaro_side.png")
    top = self.load_image_texture("textures/blocks/natura/saguaro_top.png")
    return self.build_block(top, side)

# Natura: Nether Berry Bushes (I:"Nether Berry Bush"=3255)
@material(blockid=3255, data=range(16), transparent=True, solid=True)
def natura_netherberrybushes(self, blockid, data):
    # FIXME Stage 1 and 2 should be scaled down in size
    if data == 0: # Blightberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/blightberry_fancy.png")
    elif data == 1: # Duskberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/duskberry_fancy.png")
    elif data == 2: # Skyberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/skyberry_fancy.png")
    elif data == 3: # Stingberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/stingberry_fancy.png")
    elif data == 4: # Blightberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/blightberry_fancy.png")
    elif data == 5: # Duskberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/duskberry_fancy.png")
    elif data == 6: # Skyberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/skyberry_fancy.png")
    elif data == 7: # Stingberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/stingberry_fancy.png")
    elif data == 8: # Blightberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/blightberry_fancy.png")
    elif data == 9: # Duskberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/duskberry_fancy.png")
    elif data == 10: # Skyberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/skyberry_fancy.png")
    elif data == 11: # Stingberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/stingberry_fancy.png")
    elif data == 12: # Blightberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/blightberry_ripe_fancy.png")
    elif data == 13: # Duskberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/duskberry_ripe_fancy.png")
    elif data == 14: # Skyberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/skyberry_ripe_fancy.png")
    elif data == 15: # Stingberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/stingberry_ripe_fancy.png")
    return self.build_block(t, t)

# Natura: Saplings (I:Sapling=3256)
@material(blockid=3256, data=range(8), transparent=True)
def natura_saplings(self, blockid, data):
    if data == 0: # Redwood Sapling
        t = self.load_image_texture("textures/blocks/natura/redwood_sapling.png")
    elif data == 1: # Eucalyptus Sapling
        t = self.load_image_texture("textures/blocks/natura/eucalyptus_sapling.png")
    elif data == 2: # Hopseed Sapling
        t = self.load_image_texture("textures/blocks/natura/hopseed_sapling.png")
    elif data == 3: # Sakura Sapling
        t = self.load_image_texture("textures/blocks/natura/sakura_sapling.png")
    elif data == 4: # Ghostwood Sapling
        t = self.load_image_texture("textures/blocks/natura/ghostwood_sapling.png")
    elif data == 5: # Blood Sapling
        t = self.load_image_texture("textures/blocks/natura/bloodwood_sapling.png")
    elif data == 6: # Darkwood Sapling
        t = self.load_image_texture("textures/blocks/natura/darkwood_sapling.png")
    elif data == 7: # Fusewood Sapling
        t = self.load_image_texture("textures/blocks/natura/fusewood_sapling.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_sprite(t)

# Natura: Berry Bushes (I:Berry_Bush=3257)
@material(blockid=3257, data=range(16), transparent=True, solid=True)
def natura_berrybushes(self, blockid, data):
    # FIXME Stage 1 and 2 should be scaled down in size
    if data == 0: # Raspberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/raspberry_fancy.png")
    elif data == 1: # Blueberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/blueberry_fancy.png")
    elif data == 2: # Blackberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/blackberry_fancy.png")
    elif data == 3: # Maloberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/natura/geoberry_fancy.png")
    elif data == 4: # Raspberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/raspberry_fancy.png")
    elif data == 5: # Blueberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/blueberry_fancy.png")
    elif data == 6: # Blackberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/blackberry_fancy.png")
    elif data == 7: # Maloberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/natura/geoberry_fancy.png")
    elif data == 8: # Raspberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/raspberry_fancy.png")
    elif data == 9: # Blueberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/blueberry_fancy.png")
    elif data == 10: # Blackberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/blackberry_fancy.png")
    elif data == 11: # Maloberry Bush (stage 3)
        t = self.load_image_texture("textures/blocks/natura/geoberry_fancy.png")
    elif data == 12: # Raspberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/raspberry_ripe_fancy.png")
    elif data == 13: # Blueberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/blueberry_ripe_fancy.png")
    elif data == 14: # Blackberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/blackberry_ripe_fancy.png")
    elif data == 15: # Maloberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/natura/geoberry_ripe_fancy.png")
    return self.build_block(t, t)

# Natura: Leaves (I:"Sakura Leaves"=3258)
@material(blockid=3258, data=range(16), transparent=True, solid=True)
def natura_sakuraleaves(self, blockid, data):
    # The highest bit indicates non-decaying leaves(?)
    data = data & 7
    if data == 0: # Sakura Leaves
        t = self.load_image_texture("textures/blocks/natura/sakura_leaves_fancy.png")
    elif data == 1: # Ghostwood Leaves
        t = self.load_image_texture("textures/blocks/natura/ghostwood_leaves_fancy.png")
    elif data == 2: # Bloodleaves
        t = self.load_image_texture("textures/blocks/natura/bloodwood_leaves_fancy.png")
    elif data == 3: # Willow leaves
        t = self.load_image_texture("textures/blocks/natura/willow_leaves_fancy.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura: Leaves (I:"Flora Leaves"=3259)
@material(blockid=3259, data=range(16), transparent=True, solid=True)
def natura_floraleaves(self, blockid, data):
    # The highest bit indicates non-decaying leaves(?)
    data = data & 7
    if data == 0: # Redwood Leaves NOTE: needs biome coloring
        t = self.load_image_texture("textures/blocks/natura/redwood_leaves_fancy.png")
    elif data == 1: # Eucalyptus Leaves NOTE: needs biome coloring
        t = self.load_image_texture("textures/blocks/natura/eucalyptus_leaves_fancy.png")
    elif data == 2: # Hopseed Leaves TODO does this need biome coloring?
        t = self.load_image_texture("textures/blocks/natura/hopseed_leaves_fancy.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura: Crops (Barley and Cotton) (I:Crops=3260)
@material(blockid=3260, data=range(16), transparent=True)
def natura_crops(self, blockid, data):
    if data <= 3: # 0..3 Barley, 4 different growth stages
        raw_crop = self.load_image_texture("textures/blocks/natura/barley_%d.png" % (data + 1))
    elif data <= 8: # 4..8 Cotton, 3 different growth stages and 2 different maturity stages
        t = self.load_image_texture("textures/blocks/natura/cotton_%d.png" % (data - 3))
        return self.build_sprite(t)
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # Barley rendering is the same as vanilla crops
    crop1 = self.transform_image_top(raw_crop)
    crop2 = self.transform_image_side(raw_crop)
    crop3 = crop2.transpose(Image.FLIP_LEFT_RIGHT)

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, crop1, (0,12), crop1)
    alpha_over(img, crop2, (6,3), crop2)
    alpha_over(img, crop3, (6,3), crop3)
    return img

# Natura: Redwood logs (I:"Redwood Block"=3261)
@material(blockid=3261, data=range(16), solid=True)
def natura_redwood(self, blockid, data):
    if data == 0: # Redwood Bark
        t = self.load_image_texture("textures/blocks/natura/redwood_bark.png")
    elif data == 1: # Redwood
        t = self.load_image_texture("textures/blocks/natura/redwood_heart.png")
    elif data == 2: # Redwood Root
        t = self.load_image_texture("textures/blocks/natura/redwood_root.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura: Wood planks (I:"Planks Block"=3262)
@material(blockid=3262, data=range(13), solid=True)
def natura_woodplanks(self, blockid, data):
    if data == 0: # Eucalyptus Planks
        t = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png")
    elif data == 1: # Sakura Planks
        t = self.load_image_texture("textures/blocks/natura/sakura_planks.png")
    elif data == 2: # Ghostwood Planks
        t = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png")
    elif data == 3: # Redwood Planks
        t = self.load_image_texture("textures/blocks/natura/redwood_planks.png")
    elif data == 4: # Bloodwood Planks
        t = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png")
    elif data == 5: # Hopseed Planks
        t = self.load_image_texture("textures/blocks/natura/hopseed_planks.png")
    elif data == 6: # Maple Planks
        t = self.load_image_texture("textures/blocks/natura/maple_planks.png")
    elif data == 7: # Silverbell Planks
        t = self.load_image_texture("textures/blocks/natura/silverbell_planks.png")
    elif data == 8: # Amaranth Planks
        t = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png")
    elif data == 9: # Tigerwood Planks
        t = self.load_image_texture("textures/blocks/natura/tiger_planks.png")
    elif data == 10: # Willow Planks
        t = self.load_image_texture("textures/blocks/natura/willow_planks.png")
    elif data == 11: # Darkwood Planks
        t = self.load_image_texture("textures/blocks/natura/darkwood_planks.png")
    elif data == 12: # Fusewood Planks
        t = self.load_image_texture("textures/blocks/natura/fusewood_planks.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura: Bloodwood (I:"Bloodwood Block"=3263)
@material(blockid=3263, data=range(16), solid=True)
def natura_bloodwood(self, blockid, data):
    bdata = data & 3
    if bdata == 0: # Bloodwood
        side = self.load_image_texture("textures/blocks/natura/bloodwood_bark.png")
        top = self.load_image_texture("textures/blocks/natura/bloodwood_heart_small.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/natura/mushroom_purple.png")
        return self.build_sprite(t)

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Natura: Doors
#   I:"Bloodwood Door"=3268
#   I:"Eucalyptus Door"=3264
#   I:"Ghostwood Door"=3267
#   I:"Hopseed Door"=3265
#   I:"Redwood Bark Door"=3269
#   I:"Redwood Door"=3252
#   I:"Sakura Door"=3266
@material(blockid=[3252,3264,3265,3266,3267,3268,3269], data=range(32), transparent=True)
def natura_doors(self, blockid, data):
    # Masked to not clobber block top/bottom & swung info
    if self.rotation == 1:
        if (data & 0b00011) == 0: data = data & 0b11100 | 1
        elif (data & 0b00011) == 1: data = data & 0b11100 | 2
        elif (data & 0b00011) == 2: data = data & 0b11100 | 3
        elif (data & 0b00011) == 3: data = data & 0b11100 | 0
    elif self.rotation == 2:
        if (data & 0b00011) == 0: data = data & 0b11100 | 2
        elif (data & 0b00011) == 1: data = data & 0b11100 | 3
        elif (data & 0b00011) == 2: data = data & 0b11100 | 0
        elif (data & 0b00011) == 3: data = data & 0b11100 | 1
    elif self.rotation == 3:
        if (data & 0b00011) == 0: data = data & 0b11100 | 3
        elif (data & 0b00011) == 1: data = data & 0b11100 | 0
        elif (data & 0b00011) == 2: data = data & 0b11100 | 1
        elif (data & 0b00011) == 3: data = data & 0b11100 | 2

    if data & 0x8 == 0x8: # top of the door
        doorpart = "top"
    else: # bottom of the door
        doorpart = "bottom"

    if blockid == 3252: # Redwood Door
        raw_door = self.load_image_texture("textures/blocks/natura/redwood_door_%s.png" % doorpart)
    elif blockid == 3264: # Eucalyptus Door
        raw_door = self.load_image_texture("textures/blocks/natura/eucalyptus_door_%s.png" % doorpart)
    elif blockid == 3265: # Hopseed Door
        raw_door = self.load_image_texture("textures/blocks/natura/hopseed_door_%s.png" % doorpart)
    elif blockid == 3266: # Sakura Door
        raw_door = self.load_image_texture("textures/blocks/natura/sakura_door_%s.png" % doorpart)
    elif blockid == 3267: # Ghostwood Door
        raw_door = self.load_image_texture("textures/blocks/natura/ghostwood_door_%s.png" % doorpart)
    elif blockid == 3268: # Bloodwood Door
        raw_door = self.load_image_texture("textures/blocks/natura/bloodwood_door_%s.png" % doorpart)
    elif blockid == 3269: # Redwood Bark Door
        raw_door = self.load_image_texture("textures/blocks/natura/redwoodbark_door_%s.png" % doorpart)

    # if you want to render all doors as closed, then force
    # force closed to be True
    if data & 0x4 == 0x4:
        closed = False
    else:
        closed = True

    if data & 0x10 == 0x10:
        # hinge on the left (facing same door direction)
        hinge_on_left = True
    else:
        # hinge on the right (default single door)
        hinge_on_left = False

    # mask out the high bits to figure out the orientation
    img = Image.new("RGBA", (24,24), self.bgcolor)
    if (data & 0x03) == 0: # facing west when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (0,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (0,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)

    if (data & 0x03) == 1: # facing north when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (0,6), tex)

        else:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (12,0), tex)

    if (data & 0x03) == 2: # facing east when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door)
                alpha_over(img, tex, (12,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door)
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (0,0), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (12,0), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)

    if (data & 0x03) == 3: # facing south when closed
        if hinge_on_left:
            if closed:
                tex = self.transform_image_side(raw_door).transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (12,0), tex)
        else:
            if closed:
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                tex = tex.transpose(Image.FLIP_LEFT_RIGHT)
                alpha_over(img, tex, (12,6), tex)
            else:
                # flip first to set the doornob on the correct side
                tex = self.transform_image_side(raw_door.transpose(Image.FLIP_LEFT_RIGHT))
                alpha_over(img, tex, (0,6), tex)

    return img

# Natura: Glowshrooms (I:"Glowing Mushroom"=3270)
@material(blockid=3270, data=range(3), transparent=True)
def natura_glowshrooms(self, blockid, data):
    if data == 0: # Green Glowshroom
        t = self.load_image_texture("textures/blocks/natura/mushroom_green.png")
    elif data == 1: # Purple Glowshroom
        t = self.load_image_texture("textures/blocks/natura/mushroom_purple.png")
    elif data == 2: # Blue Glowshroom
        t = self.load_image_texture("textures/blocks/natura/mushroom_blue.png")
    return self.build_sprite(t)

# Natura: Darkwood & Fusewood logs (I:"Darkwood Log"=3271)
@material(blockid=3271, data=range(16), solid=True)
def natura_darkwoodlog(self, blockid, data):
    bdata = data & 3
    if bdata == 0: # Darkwood
        side = self.load_image_texture("textures/blocks/natura/darkwood_bark.png")
        top = self.load_image_texture("textures/blocks/natura/darkwood_heart.png")
    elif bdata == 1: # Fusewood
        side = self.load_image_texture("textures/blocks/natura/fusewood_bark.png")
        top = self.load_image_texture("textures/blocks/natura/fusewood_heart.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Natura: Darkwood & Fusewood Leaves (I:"Darkwood Leaves"=3272)
@material(blockid=3272, data=range(16), transparent=True, solid=True)
def natura_darkwoodleaves(self, blockid, data):
    # The highest bit indicates non-decaying leaves(?)
    data = data & 7

    if data == 0: # Darkwood Leaves, empty
        t = self.load_image_texture("textures/blocks/natura/darkwood_leaves_fancy.png")
    elif data == 1: # Darkwood Leaves, flowering
        t = self.load_image_texture("textures/blocks/natura/darkwood_flowering_leaves_fancy.png")
    elif data == 2: # Darkwood Leaves, fruit
        t = self.load_image_texture("textures/blocks/natura/darkwood_fruit_leaves_fancy.png")
    elif data == 3: # Fusewood Leaves
        t = self.load_image_texture("textures/blocks/natura/fusewood_leaves_fancy.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura Blue Glowshroom (I:"Blue Glowshroom"=3273)
block(blockid=3273, top_image="textures/blocks/natura/mushroom_inside_blue.png", transparent=True)

# Natura Green Glowshroom (I:"Green Glowshroom"=3274)
block(blockid=3274, top_image="textures/blocks/natura/mushroom_inside_green.png", transparent=True)

# Natura Purple Glowshroom (I:"Purple Glowshroom"=3275)
block(blockid=3275, top_image="textures/blocks/natura/mushroom_inside_purple.png", transparent=True)

# Natura: Wood logs (rare) (I:"Rare Log"=3277)
@material(blockid=3277, data=range(16), solid=True)
def natura_rarelog(self, blockid, data):
    bdata = data & 3
    if bdata == 0: # Maple Wood
        side = self.load_image_texture("textures/blocks/natura/maple_bark.png")
        top = self.load_image_texture("textures/blocks/natura/maple_heart.png")
    elif bdata == 1: # Silverbell Wood
        side = self.load_image_texture("textures/blocks/natura/silverbell_bark.png")
        top = self.load_image_texture("textures/blocks/natura/silverbell_heart.png")
    elif bdata == 2: # Amaranth Wood
        side = self.load_image_texture("textures/blocks/natura/purpleheart_bark.png")
        top = self.load_image_texture("textures/blocks/natura/purpleheart_heart.png")
    elif bdata == 3: # Tiger Wood
        side = self.load_image_texture("textures/blocks/natura/tiger_bark.png")
        top = self.load_image_texture("textures/blocks/natura/tiger_heart.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Natura: Leaves (I:"Rare Leaves"=3278)
@material(blockid=3278, data=range(16), transparent=True, solid=True)
def natura_rareleaves(self, blockid, data):
    # The highest bit indicates non-decaying leaves(?)
    data = data & 7

    if data == 0: # Maple Leaves NOTE: needs biome coloring FIXME does it?
        t = self.load_image_texture("textures/blocks/natura/maple_leaves_fancy.png")
    elif data == 1: # Silverbell Leaves
        t = self.load_image_texture("textures/blocks/natura/silverbell_leaves_fancy.png")
    elif data == 2: # Amaranth Leaves FIXME does this need biome coloring
        t = self.load_image_texture("textures/blocks/natura/purpleheart_leaves_fancy.png")
    elif data == 3: # Tigerwood Leaves
        t = self.load_image_texture("textures/blocks/natura/tiger_leaves_fancy.png")
    else: # TODO Unknown Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Natura: Saplings (I:"Rare Sapling"=3279)
@material(blockid=3279, data=range(5), transparent=True)
def natura_raresapling(self, blockid, data):
    if data == 0: # Maple sapling
        t = self.load_image_texture("textures/blocks/natura/maple_sapling.png")
    elif data == 1: # Silverbell sapling
        t = self.load_image_texture("textures/blocks/natura/silverbell_sapling.png")
    elif data == 2: # Amaranth sapling
        t = self.load_image_texture("textures/blocks/natura/purpleheart_sapling.png")
    elif data == 3: # Tigerwood sapling
        t = self.load_image_texture("textures/blocks/natura/tiger_sapling.png")
    elif data == 4: # Willow sapling
        t = self.load_image_texture("textures/blocks/natura/willow_sapling.png")
    return self.build_sprite(t)

# Natura: Willow wood (I:"Willow Log"=3280)
@material(blockid=3280, data=range(16), solid=True)
def natura_willowlog(self, blockid, data):
    bdata = data & 3
    if bdata == 0: # Willow wood
        side = self.load_image_texture("textures/blocks/natura/willow_bark.png")
        top = self.load_image_texture("textures/blocks/natura/willow_heart.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# Natura: Bluebells (I:Flower=3281)
sprite(blockid=3281, imagename="textures/blocks/natura/flower_bluebells.png")

# Natura: Thornvines (I:Thornvines=3282)
@material(blockid=3282, data=range(16), transparent=True)
def natura_thornvines(self, blockid, data):
    # rotation
    # vines data is bit coded. decode it first.
    # NOTE: the directions used in this function are the new ones used
    # in minecraft 1.0.0, no the ones used by overviewer
    # (i.e. north is top-left by defalut)

    # rotate the data by bitwise shift
    shifts = 0
    if self.rotation == 1:
        shifts = 1
    elif self.rotation == 2:
        shifts = 2
    elif self.rotation == 3:
        shifts = 3

    for i in range(shifts):
        data = data * 2
        if data & 16:
            data = (data - 16) | 1

    # decode data and prepare textures
    raw_texture = self.load_image_texture("textures/blocks/natura/thornvine.png")
    s = w = n = e = None

    if data & 1: # south
        s = raw_texture
    if data & 2: # west
        w = raw_texture
    if data & 4: # north
        n = raw_texture
    if data & 8: # east
        e = raw_texture

    # texture generation
    img = self.build_full_block(None, n, e, w, s)

    return img

# Natura: Crafting Table (I:"Crafting Table"=3283)
@material(blockid=3283, data=range(13), solid=True)
def natura_craftingtable(self, blockid, data):
    # TODO: These have not been verified, since they don't show up in NEI, except the Eucalyptus one
    if data == 0: # Eucalyptus Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/eucalyptus_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/eucalyptus_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/eucalyptus_workbench_top.png")
    elif data == 1: # Sakura Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/sakura_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/sakura_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/sakura_workbench_top.png")
    elif data == 2: # Ghostwood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/ghostwood_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/ghostwood_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/ghostwood_workbench_top.png")
    elif data == 3: # Redwood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/redwood_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/redwood_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/redwood_workbench_top.png")
    elif data == 4: # Bloodwood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/bloodwood_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/bloodwood_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/bloodwood_workbench_top.png")
    elif data == 5: # Hopseed Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/hopseed_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/hopseed_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/hopseed_workbench_top.png")
    elif data == 6: # Maple Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/maple_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/maple_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/maple_workbench_top.png")
    elif data == 7: # Silverbell Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/silverbell_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/silverbell_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/silverbell_workbench_top.png")
    elif data == 8: # Amaranth Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/purpleheart_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/purpleheart_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/purpleheart_workbench_top.png")
    elif data == 9: # Tigerwood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/tiger_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/tiger_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/tiger_workbench_top.png")
    elif data == 10: # Willow Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/willow_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/willow_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/willow_workbench_top.png")
    elif data == 11: # Darkwood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/darkwood_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/darkwood_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/darkwood_workbench_top.png")
    elif data == 12: # Fusewood Crafting Table
        side3 = self.load_image_texture("textures/blocks/natura/fusewood_workbench_side.png")
        side4 = self.load_image_texture("textures/blocks/natura/fusewood_workbench_face.png")
        top = self.load_image_texture("textures/blocks/natura/fusewood_workbench_top.png")

    return self.build_full_block(top, None, None, side3, side4, None)

# Natura: Bookshelf (I:Bookshelf=3284)
@material(blockid=3284, data=range(13), solid=True)
def natura_bookshelf(self, blockid, data):
    # TODO: These have not been verified, since they don't show up in NEI, except the Eucalyptus one
    if data == 0: # Eucalyptus Bookshelf
        side = self.load_image_texture("textures/blocks/natura/eucalyptus_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png")
    elif data == 1: # Sakura Bookshelf
        side = self.load_image_texture("textures/blocks/natura/sakura_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/sakura_planks.png")
    elif data == 2: # Ghostwood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/ghostwood_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png")
    elif data == 3: # Redwood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/redwood_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/redwood_planks.png")
    elif data == 4: # Bloodwood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/bloodwood_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png")
    elif data == 5: # Hopseed Bookshelf
        side = self.load_image_texture("textures/blocks/natura/hopseed_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/hopseed_planks.png")
    elif data == 6: # Maple Bookshelf
        side = self.load_image_texture("textures/blocks/natura/maple_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/maple_planks.png")
    elif data == 7: # Silverbell Bookshelf
        side = self.load_image_texture("textures/blocks/natura/silverbell_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/silverbell_planks.png")
    elif data == 8: # Amaranth Bookshelf
        side = self.load_image_texture("textures/blocks/natura/purpleheart_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png")
    elif data == 9: # Tigerwood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/tiger_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/tiger_planks.png")
    elif data == 10: # Willow Bookshelf
        side = self.load_image_texture("textures/blocks/natura/willow_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/willow_planks.png")
    elif data == 11: # Darkwood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/darkwood_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/darkwood_planks.png")
    elif data == 12: # Fusewood Bookshelf
        side = self.load_image_texture("textures/blocks/natura/fusewood_bookshelf.png")
        top = self.load_image_texture("textures/blocks/natura/fusewood_planks.png")

    return self.build_block(top, side)

# Natura: Fences (I:Fence=3285)
# uses pseudo-ancildata found in iterate.c
@material(blockid=3285, data=range(256), transparent=True, nospawn=True)
def natura_fence(self, blockid, data):
    # no need for rotations, it uses pseudo data.
    # create needed images for Big stick fence
    bdata = data & 0xF
    if bdata == 0: # Eucalyptus Fence
        fence_top = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
    elif bdata == 1: # Sakura Fence
        fence_top = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
    elif bdata == 2: # Ghostwood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
    elif bdata == 3: # Redwood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
    elif bdata == 4: # Blood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
    elif bdata == 5: # Hopseed Fence
        fence_top = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
    elif bdata == 6: # Maple Fence
        fence_top = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
    elif bdata == 7: # Silverbell Fence
        fence_top = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
    elif bdata == 8: # Amaranth Fence
        fence_top = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
    elif bdata == 9: # Tigerwood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
    elif bdata == 10: # Willow Fence
        fence_top = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
    elif bdata == 11: # Darkwood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
    elif bdata == 12: # Fusewood Fence
        fence_top = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()
        fence_side = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()
        fence_small_side = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # generate the textures of the fence
    ImageDraw.Draw(fence_top).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,0,15,5),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,10,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    ImageDraw.Draw(fence_side).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_side).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the big stick
    fence_side = self.transform_image_side(fence_side)
    fence_other_side = fence_side.transpose(Image.FLIP_LEFT_RIGHT)
    fence_top = self.transform_image_top(fence_top)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_side.split()[3]
    fence_side = ImageEnhance.Brightness(fence_side).enhance(0.9)
    fence_side.putalpha(sidealpha)
    othersidealpha = fence_other_side.split()[3]
    fence_other_side = ImageEnhance.Brightness(fence_other_side).enhance(0.8)
    fence_other_side.putalpha(othersidealpha)

    # Compose the fence big stick
    fence_big = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(fence_big,fence_side, (5,4),fence_side)
    alpha_over(fence_big,fence_other_side, (7,4),fence_other_side)
    alpha_over(fence_big,fence_top, (0,0),fence_top)

    # Now render the small sticks.
    # Create needed images
    ImageDraw.Draw(fence_small_side).rectangle((0,0,15,0),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,4,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,10,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the small sticks
    fence_small_side = self.transform_image_side(fence_small_side)
    fence_small_other_side = fence_small_side.transpose(Image.FLIP_LEFT_RIGHT)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_small_other_side.split()[3]
    fence_small_other_side = ImageEnhance.Brightness(fence_small_other_side).enhance(0.9)
    fence_small_other_side.putalpha(sidealpha)
    sidealpha = fence_small_side.split()[3]
    fence_small_side = ImageEnhance.Brightness(fence_small_side).enhance(0.9)
    fence_small_side.putalpha(sidealpha)

    # Create img to compose the fence
    img = Image.new("RGBA", (24,24), self.bgcolor)

    # Position of fence small sticks in img.
    # These postitions are strange because the small sticks of the
    # fence are at the very left and at the very right of the 16x16 images
    pos_top_left = (2,3)
    pos_top_right = (10,3)
    pos_bottom_right = (10,7)
    pos_bottom_left = (2,7)

    # +x axis points top right direction
    # +y axis points bottom right direction
    # First compose small sticks in the back of the image,
    # then big stick and thecn small sticks in the front.

    # get the pseudo ancillary data
    data = (data & 0xF0) >> 4

    if (data & 0b0001) == 1:
        alpha_over(img,fence_small_side, pos_top_left,fence_small_side)                # top left
    if (data & 0b1000) == 8:
        alpha_over(img,fence_small_other_side, pos_top_right,fence_small_other_side)    # top right

    alpha_over(img,fence_big,(0,0),fence_big)

    if (data & 0b0010) == 2:
        alpha_over(img,fence_small_other_side, pos_bottom_left,fence_small_other_side)      # bottom left
    if (data & 0b0100) == 4:
        alpha_over(img,fence_small_side, pos_bottom_right,fence_small_side)                  # bottom right

    return img

# Natura: Topiary Grass (I:"Topiary Grass Block"=3286)
@material(blockid=3286, data=range(3), solid=True)
def natura_topiarygrass(self, blockid, data):
    # FIXME: I didn't find the right textures, is this the one, but it just gets colored?
    texture = self.load_image_texture("textures/blocks/natura/grass_top.png")
    #if data == 0: # Topiary Grass
    #elif data == 1: # Bluegrass
    #elif data == 2: # Autumnal Grass
    return self.build_block(texture, texture)

# Natura: Topiary Grass Slabs (I:"Topiary Grass Slab"=3287)
@material(blockid=3287, data=range(3), solid=True)
def natura_topiarygrass_slab(self, blockid, data):
    # FIXME: I didn't find the right textures, is this the one, but it just gets colored?
    top = side = self.load_image_texture("textures/blocks/natura/grass_top.png")
    #bdata = data & 7
    #if bdata == 0: # Topiary Grass Slab
    #    top = side = self.load_image_texture("textures/blocks/natura/grass_top.png")
    #elif bdata == 1: # Bluegrass Slab
    #    top = side = self.load_image_texture("textures/blocks/natura/sakura_planks.png")
    #elif bdata == 2: # Autumnal Grass Slab
    #    top = side = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png")
    #else: # TODO Unknown block
    #    t = self.load_image_texture("textures/blocks/web.png")
    #    return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Natura: Slabs (I:"Plank Slab One"=3288)
@material(blockid=3288, data=range(16), solid=True)
def natura_slab1(self, blockid, data):
    bdata = data & 7
    if bdata == 0: # Eucalyptus Slab
        top = side = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png")
    elif bdata == 1: # Sakura Slab
        top = side = self.load_image_texture("textures/blocks/natura/sakura_planks.png")
    elif bdata == 2: # Ghostwood Slab
        top = side = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png")
    elif bdata == 3: # Redwood Slab
        top = side = self.load_image_texture("textures/blocks/natura/redwood_planks.png")
    elif bdata == 4: # Bloodwood Slab
        top = side = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png")
    elif bdata == 5: # Hopseed Slab
        top = side = self.load_image_texture("textures/blocks/natura/hopseed_planks.png")
    elif bdata == 6: # Maple Slab
        top = side = self.load_image_texture("textures/blocks/natura/maple_planks.png")
    elif bdata == 7: # Silverbell Slab
        top = side = self.load_image_texture("textures/blocks/natura/silverbell_planks.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Natura: Slabs (I:"Plank Slab Two"=3289)
@material(blockid=3288, data=range(16), solid=True)
def natura_slab2(self, blockid, data):
    bdata = data & 7
    if bdata == 0: # Amaranth Slab
        top = side = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png")
    elif bdata == 1: # Tigerwood Slab
        top = side = self.load_image_texture("textures/blocks/natura/tiger_planks.png")
    elif bdata == 2: # Willow Slab
        top = side = self.load_image_texture("textures/blocks/natura/willow_planks.png")
    elif bdata == 3: # Darkwood Slab
        top = side = self.load_image_texture("textures/blocks/natura/darkwood_planks.png")
    elif bdata == 4: # Fusewood Slab
        top = side = self.load_image_texture("textures/blocks/natura/fusewood_planks.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Natura: Stairs
#   I:"Eucalyputus Stairs"=3291
#   I:"Sakura Stairs"=3292
#   I:"Ghostwood Stairs"=3293
#   I:"Redwood Stairs"=3294
#   I:"Bloodwood Stairs"=3295
#   I:"Hopseed Stairs"=3296
#   I:"Maple Stairs"=3297
#   I:"Amaranth Stairs"=3298
#   I:"Silverbell Stairs"=3299
#   I:"Tigerwood Stairs"=3300
#   I:"Willow Stairs"=3301
#   I:"Darkwood Stairs"=3302
#   I:"Fusewood Stairs"=3303
@material(blockid=range(3291, 3303 + 1), data=range(8), transparent=True, solid=True, nospawn=True)
def natura_stairs(self, blockid, data):
    if blockid == 3291: # Eucalyptus Stairs
        texture = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png")
    elif blockid == 3292: # Sakura Stairs
        texture = self.load_image_texture("textures/blocks/natura/sakura_planks.png")
    elif blockid == 3293: # Ghostwood Stairs
        texture = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png")
    elif blockid == 3294: # Redwood Stairs
        texture = self.load_image_texture("textures/blocks/natura/redwood_planks.png")
    elif blockid == 3295: # Blood Stairs
        texture = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png")
    elif blockid == 3296: # Hopseed Stairs
        texture = self.load_image_texture("textures/blocks/natura/hopseed_planks.png")
    elif blockid == 3297: # Maple Stairs
        texture = self.load_image_texture("textures/blocks/natura/maple_planks.png")
    elif blockid == 3298: # Amaranth Stairs
        texture = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png")
    elif blockid == 3299: # Silverbell Stairs
        texture = self.load_image_texture("textures/blocks/natura/silverbell_planks.png")
    elif blockid == 3300: # Tigerwood Stairs
        texture = self.load_image_texture("textures/blocks/natura/tiger_planks.png")
    elif blockid == 3301: # Willow Stairs
        texture = self.load_image_texture("textures/blocks/natura/willow_planks.png")
    elif blockid == 3302: # Darkwood Stairs
        texture = self.load_image_texture("textures/blocks/natura/darkwood_planks.png")
    elif blockid == 3303: # Fusewood Stairs
        texture = self.load_image_texture("textures/blocks/natura/fusewood_planks.png")

    # first, rotations
    # preserve the upside-down bit
    upside_down = data & 0x4
    data = data & 0x3

    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1

    data = data | upside_down
    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))

    if data & 0x4 == 0x4: # upside down stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))
        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)
        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)
        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))
    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)
            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)
            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))
        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)
        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)
        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)
            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)
            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))

        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))

    return img

# Natura: Pressure plates
#   I:"Eucalyputus Pressure Plate"=3304
#   I:"Sakura Pressure Plate"=3305
#   I:"Ghostwood Pressure Plate"=3306
#   I:"Redwood Pressure Plate"=3307
#   I:"Bloodwood Pressure Plate"=3308
#   I:"Hopseed Pressure Plate"=3309
#   I:"Maple Pressure Plate"=3310
#   I:"Amaranth Pressure Plate"=3311
#   I:"Silverbell Pressure Plate"=3312
#   I:"Tigerwood Pressure Plate"=3313
#   I:"Willow Pressure Plate"=3314
#   I:"Darkwood Pressure Plate"=3315
#   I:"Fusewood Pressure Plate"=3316
@material(blockid=range(3304, 3316 + 1), data=[0,1], transparent=True)
def natura_pressure_plate(self, blockid, data):
    if blockid == 3304: # Eucalyptus Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
    elif blockid == 3305: # Sakura Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
    elif blockid == 3306: # Ghostwood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
    elif blockid == 3307: # Redwood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
    elif blockid == 3308: # Bloodwood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
    elif blockid == 3309: # Hopseed Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
    elif blockid == 3310: # Maple Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
    elif blockid == 3311: # Amaranth Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
    elif blockid == 3312: # Silverbell Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
    elif blockid == 3313: # Tigerwood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
    elif blockid == 3314: # Willow Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
    elif blockid == 3315: # Darkwood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
    elif blockid == 3316: # Fusewood Pressure Plate
        t = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()

    # cut out the outside border, pressure plates are smaller
    # than a normal block
    ImageDraw.Draw(t).rectangle((0,0,15,15),outline=(0,0,0,0))

    # create the textures and a darker version to make a 3d by
    # pasting them with an offstet of 1 pixel
    img = Image.new("RGBA", (24,24), self.bgcolor)

    top = self.transform_image_top(t)

    alpha = top.split()[3]
    topd = ImageEnhance.Brightness(top).enhance(0.8)
    topd.putalpha(alpha)

    #show it 3d or 2d if unpressed or pressed
    if data == 0:
        alpha_over(img,topd, (0,12),topd)
        alpha_over(img,top, (0,11),top)
    elif data == 1:
        alpha_over(img,top, (0,12),top)

    return img

# Natura: Trapdoors
#   I:"Eucalyputus Trapdoor"=3317
#   I:"Sakura Trapdoor"=3318
#   I:"Ghostwood Trapdoor"=3319
#   I:"Redwood Trapdoor"=3320
#   I:"Bloodwood Trapdoor"=3321
#   I:"Hopseed Trapdoor"=3322
#   I:"Maple Trapdoor"=3323
#   I:"Amaranth Trapdoor"=3324
#   I:"Silverbell Trapdoor"=3325
#   I:"Tigerwood Trapdoor"=3326
#   I:"Willow Trapdoor"=3327
#   I:"Darkwood Trapdoor"=3328
#   I:"Fusewood Trapdoor"=3329
# TODO the trapdoor looks like a sprite when opened, that's not good
@material(blockid=range(3317, 3329 + 1), data=range(16), transparent=True, nospawn=True)
def natura_trapdoor(self, blockid, data):
    # FIXME: Some of the textures don't exist
    if blockid == 3317: # Eucalyptus Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/eucalyptus_trapdoor.png")
    elif blockid == 3318: # Sakura Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/sakura_trapdoor.png")
    elif blockid == 3319: # Ghostwood Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/ghostwood_trapdoor.png")
    elif blockid == 3320: # Redwood Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/redwood_trapdoor.png")
    elif blockid == 3321: # Bloodwood Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/bloodwood_trapdoor.png")
    elif blockid == 3322: # Hopseed Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/hopseed_trapdoor.png")
    elif blockid == 3323: # Maple Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")
    elif blockid == 3324: # Amaranth Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")
    elif blockid == 3325: # Silverbell Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")
    elif blockid == 3326: # Tigerwood Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")
    elif blockid == 3327: # Willow Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")
    elif blockid == 3328: # Darkwood Trapdoor
        texture = self.load_image_texture("textures/blocks/natura/darkwood_trapdoor.png")
    elif blockid == 3329: # Fusewood Trapdoor FIXME
        texture = self.load_image_texture("textures/blocks/trapdoor.png")

    # rotation
    # Masked to not clobber opened/closed info
    if self.rotation == 1:
        if (data & 0b0011) == 0: data = data & 0b1100 | 3
        elif (data & 0b0011) == 1: data = data & 0b1100 | 2
        elif (data & 0b0011) == 2: data = data & 0b1100 | 0
        elif (data & 0b0011) == 3: data = data & 0b1100 | 1
    elif self.rotation == 2:
        if (data & 0b0011) == 0: data = data & 0b1100 | 1
        elif (data & 0b0011) == 1: data = data & 0b1100 | 0
        elif (data & 0b0011) == 2: data = data & 0b1100 | 3
        elif (data & 0b0011) == 3: data = data & 0b1100 | 2
    elif self.rotation == 3:
        if (data & 0b0011) == 0: data = data & 0b1100 | 2
        elif (data & 0b0011) == 1: data = data & 0b1100 | 3
        elif (data & 0b0011) == 2: data = data & 0b1100 | 1
        elif (data & 0b0011) == 3: data = data & 0b1100 | 0

    # texture generation
    if data & 0x4 == 0x4: # opened trapdoor
        if data & 0x3 == 0: # west
            img = self.build_full_block(None, None, None, None, texture)
        if data & 0x3 == 1: # east
            img = self.build_full_block(None, texture, None, None, None)
        if data & 0x3 == 2: # south
            img = self.build_full_block(None, None, texture, None, None)
        if data & 0x3 == 3: # north
            img = self.build_full_block(None, None, None, texture, None)

    elif data & 0x4 == 0: # closed trapdoor
        if data & 0x8 == 0x8: # is a top trapdoor
            img = Image.new("RGBA", (24,24), self.bgcolor)
            t = self.build_full_block((texture, 12), None, None, texture, texture)
            alpha_over(img, t, (0,-9),t)
        else: # is a bottom trapdoor
            img = self.build_full_block((texture, 12), None, None, texture, texture)

    return img

# Natura: Wooden buttons
#   I:"Eucalyputus Button"=3330
#   I:"Sakura Button"=3331
#   I:"Ghostwood Button"=3332
#   I:"Redwood Button"=3333
#   I:"Bloodwood Button"=3334
#   I:"Hopseed Button"=3335
#   I:"Maple Button"=3336
#   I:"Silverbell Button"=3337
#   I:"Amaranth Button"=3338
#   I:"Tigerwood Button"=3339
#   I:"Willow Button"=3340
#   I:"Darkwood Button"=3341
#   I:"Fusewood Button"=3342
@material(blockid=range(3330, 3342 + 1), data=range(16), transparent=True)
def natura_buttons(self, blockid, data):
    if blockid == 3330: # Eucalyptus Button
        t = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
    elif blockid == 3331: # Sakura Button
        t = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
    elif blockid == 3332: # Ghostwood Button
        t = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
    elif blockid == 3333: # Redwood Button
        t = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
    elif blockid == 3334: # Bloodwood Button
        t = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
    elif blockid == 3335: # Hopseed Button
        t = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
    elif blockid == 3336: # Maple Button
        t = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
    elif blockid == 3337: # Silverbell Button
        t = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
    elif blockid == 3338: # Amaranth Button
        t = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
    elif blockid == 3339: # Tigerwood Button
        t = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
    elif blockid == 3340: # Willow Button
        t = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
    elif blockid == 3341: # Darkwood Button
        t = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
    elif blockid == 3342: # Fusewood Button
        t = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()

    # 0x8 is set if the button is pressed mask this info and render
    # it as unpressed
    data = data & 0x7

    if self.rotation == 1:
        if data == 1: data = 3
        elif data == 2: data = 4
        elif data == 3: data = 2
        elif data == 4: data = 1
    elif self.rotation == 2:
        if data == 1: data = 2
        elif data == 2: data = 1
        elif data == 3: data = 4
        elif data == 4: data = 3
    elif self.rotation == 3:
        if data == 1: data = 4
        elif data == 2: data = 3
        elif data == 3: data = 1
        elif data == 4: data = 2

    # generate the texture for the button
    ImageDraw.Draw(t).rectangle((0,0,15,5),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((0,10,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(t).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    img = Image.new("RGBA", (24,24), self.bgcolor)

    button = self.transform_image_side(t)

    if data == 1: # facing SOUTH
        # buttons can't be placed in transparent blocks, so this
        # direction can't be seen
        return None

    elif data == 2: # facing NORTH
        # paste it twice with different brightness to make a 3D effect
        alpha_over(img, button, (12,-1), button)

        alpha = button.split()[3]
        button = ImageEnhance.Brightness(button).enhance(0.9)
        button.putalpha(alpha)

        alpha_over(img, button, (11,0), button)

    elif data == 3: # facing WEST
        # paste it twice with different brightness to make a 3D effect
        button = button.transpose(Image.FLIP_LEFT_RIGHT)
        alpha_over(img, button, (0,-1), button)

        alpha = button.split()[3]
        button = ImageEnhance.Brightness(button).enhance(0.9)
        button.putalpha(alpha)

        alpha_over(img, button, (1,0), button)

    elif data == 4: # facing EAST
        # buttons can't be placed in transparent blocks, so this
        # direction can't be seen
        return None

    return img

# Natura: Fence gates
#   I:"Eucalyputus Fence Gate"=3343
#   I:"Sakura Fence Gate"=3344
#   I:"Ghostwood Fence Gate"=3345
#   I:"Redwood Fence Gate"=3346
#   I:"Bloodwood Fence Gate"=3347
#   I:"Hopseed Fence Gate"=3348
#   I:"Maple Fence Gate"=3349
#   I:"Silverbell Fence Gate"=3350
#   I:"Amaranth Fence Gate"=3351
#   I:"Tigerwood Fence Gate"=3352
#   I:"Willow Fence Gate"=3353
#   I:"Darkwood Fence Gate"=3354
#   I:"Fusewood Fence Gate"=3355
@material(blockid=range(3343, 3355 + 1), data=range(8), transparent=True, nospawn=True)
def natura_fencegate(self, blockid, data):
    if blockid == 3343: # Eucalyptus Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/eucalyptus_planks.png").copy()
    elif blockid == 3344: # Sakura Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/sakura_planks.png").copy()
    elif blockid == 3345: # Ghostwood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/ghostwood_planks.png").copy()
    elif blockid == 3346: # Redwood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/redwood_planks.png").copy()
    elif blockid == 3347: # Bloodwood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/bloodwood_planks.png").copy()
    elif blockid == 3348: # Hopseed Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/hopseed_planks.png").copy()
    elif blockid == 3349: # Maple Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/maple_planks.png").copy()
    elif blockid == 3350: # Silverbell Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/silverbell_planks.png").copy()
    elif blockid == 3351: # Amaranth Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/purpleheart_planks.png").copy()
    elif blockid == 3352: # Tigerwood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/tiger_planks.png").copy()
    elif blockid == 3353: # Willow Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/willow_planks.png").copy()
    elif blockid == 3354: # Darkwood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/darkwood_planks.png").copy()
    elif blockid == 3355: # Fusewood Fence Gate
        gate_side = self.load_image_texture("textures/blocks/natura/fusewood_planks.png").copy()

    # rotation
    opened = False
    if data & 0x4:
        data = data & 0x3
        opened = True

    if self.rotation == 1:
        if data == 0: data = 1
        elif data == 1: data = 2
        elif data == 2: data = 3
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 0
        elif data == 3: data = 1
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 0
        elif data == 2: data = 1
        elif data == 3: data = 2

    if opened:
        data = data | 0x4

    # create the closed gate side
    gate_side_draw = ImageDraw.Draw(gate_side)
    gate_side_draw.rectangle((7,0,15,0),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((7,4,9,6),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((7,10,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((0,12,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    gate_side_draw.rectangle((14,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # darken the sides slightly, as with the fences
    sidealpha = gate_side.split()[3]
    gate_side = ImageEnhance.Brightness(gate_side).enhance(0.9)
    gate_side.putalpha(sidealpha)

    # create the other sides
    mirror_gate_side = self.transform_image_side(gate_side.transpose(Image.FLIP_LEFT_RIGHT))
    gate_side = self.transform_image_side(gate_side)
    gate_other_side = gate_side.transpose(Image.FLIP_LEFT_RIGHT)
    mirror_gate_other_side = mirror_gate_side.transpose(Image.FLIP_LEFT_RIGHT)

    # Create img to compose the fence gate
    img = Image.new("RGBA", (24,24), self.bgcolor)

    if data & 0x4:
        # opened
        data = data & 0x3
        if data == 0:
            alpha_over(img, gate_side, (2,8), gate_side)
            alpha_over(img, gate_side, (13,3), gate_side)
        elif data == 1:
            alpha_over(img, gate_other_side, (-1,3), gate_other_side)
            alpha_over(img, gate_other_side, (10,8), gate_other_side)
        elif data == 2:
            alpha_over(img, mirror_gate_side, (-1,7), mirror_gate_side)
            alpha_over(img, mirror_gate_side, (10,2), mirror_gate_side)
        elif data == 3:
            alpha_over(img, mirror_gate_other_side, (2,1), mirror_gate_other_side)
            alpha_over(img, mirror_gate_other_side, (13,7), mirror_gate_other_side)
    else:
        # closed
        # positions for pasting the fence sides, as with fences
        pos_top_left = (2,3)
        pos_top_right = (10,3)
        pos_bottom_right = (10,7)
        pos_bottom_left = (2,7)

        if data == 0 or data == 2:
            alpha_over(img, gate_other_side, pos_top_right, gate_other_side)
            alpha_over(img, mirror_gate_other_side, pos_bottom_left, mirror_gate_other_side)
        elif data == 1 or data == 3:
            alpha_over(img, gate_side, pos_top_left, gate_side)
            alpha_over(img, mirror_gate_side, pos_bottom_right, mirror_gate_side)

    return img


#################################
#	 Tinker's Construct			#
#################################

# Tinker's Construct: Fancy Bricks (I:"Multi Brick Fancy"=1467)
@material(blockid=1467, data=range(16), solid=True)
def tic_fancybrick(self, blockid, data):
    if data == 0: # Fancy Obsidian Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_obsidian.png")
    elif data == 1: # Fancy Sandstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_sandstone.png")
    elif data == 2: # Fancy Netherrack Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_netherrack.png")
    elif data == 3: # Fancy Polished Stone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_stone_refined.png")
    elif data == 4: # Fancy Iron Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_iron.png")
    elif data == 5: # Fancy Gold Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_gold.png")
    elif data == 6: # Fancy Lapis Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_lapis.png")
    elif data == 7: # Fancy Diamond Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_diamond.png")
    elif data == 8: # Fancy Redstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_redstone.png")
    elif data == 9: # Fancy Bone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_bone.png")
    elif data == 10: # Fancy Slime Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_slime.png")
    elif data == 12: # Fancy Endstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_endstone.png")
    elif data == 14: # Fancy Stone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/fancybrick_stone.png")
    elif data == 15: # Stone Road
        t = self.load_image_texture("textures/blocks/tic/bricks/road_stone.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Seared Tank, Glass, Window (I:"Lava Tank"=1473)
@material(blockid=1473, data=range(3), solid=True)
def tic_searedglass(self, blockid, data):
    if data == 0: # Seared Tank
        side = self.load_image_texture("textures/blocks/tic/lavatank_side.png")
        top = self.load_image_texture("textures/blocks/tic/lavatank_top.png")
    elif data == 1: # Seared Glass
        side = self.load_image_texture("textures/blocks/tic/searedgague_side.png")
        top = self.load_image_texture("textures/blocks/tic/searedgague_top.png")
    elif data == 2: # Seared Window
        side = self.load_image_texture("textures/blocks/tic/searedwindow_side.png")
        top = self.load_image_texture("textures/blocks/tic/searedwindow_top.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(top, side)

# Tinker's Construct: Seared Bricks etc (I:Smeltery=1474)
@material(blockid=1474, data=range(11), solid=True)
def tic_searedbricks(self, blockid, data):
    if data == 0: # Smeltery Controller
        side = self.load_image_texture("textures/blocks/tic/smeltery_active.png")
        top = self.load_image_texture("textures/blocks/tic/smeltery_side.png")
        return self.build_block(top, side)
    elif data == 1: # Smeltery Drain
        side = self.load_image_texture("textures/blocks/tic/searedgague_side.png")
        top = self.load_image_texture("textures/blocks/tic/smeltery_side.png")
        return self.build_block(top, side)
    elif data == 2: # Seared Bricks
        side = self.load_image_texture("textures/blocks/tic/searedbrick.png")
    elif data == 3: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif data == 4: # Seared Stone
        side = self.load_image_texture("textures/blocks/tic/searedstone.png")
    elif data == 5: # Seared Cobblestone
        side = self.load_image_texture("textures/blocks/tic/searedcobble.png")
    elif data == 6: # Seared Paver
        side = self.load_image_texture("textures/blocks/tic/searedpaver.png")
    elif data == 7: # Cracked Seared Bricks
        side = self.load_image_texture("textures/blocks/tic/searedbrickcracked.png")
    elif data == 8: # Seared Road
        side = self.load_image_texture("textures/blocks/tic/searedroad.png")
    elif data == 9: # Fancy Seared Bricks
        side = self.load_image_texture("textures/blocks/tic/searedbrickfancy.png")
    elif data == 10: # Chiseled Seared Bricks
        side = self.load_image_texture("textures/blocks/tic/searedbricksquare.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(side, side)

# Tinker's Construct: Ores (I:"Ores Slag"=1475)
@material(blockid=1475, data=range(6), solid=True)
def tic_ore(self, blockid, data):
    if data == 1: # Cobalt Ore
        side = self.load_image_texture("textures/blocks/tic/nether_cobalt.png")
    elif data == 2: # Ardite Ore
        side = self.load_image_texture("textures/blocks/tic/nether_ardite.png")
    elif data == 3: # Copper Ore
        side = self.load_image_texture("textures/blocks/tic/ore_copper.png")
    elif data == 4: # Tin Ore
        side = self.load_image_texture("textures/blocks/tic/ore_tin.png")
    elif data == 5: # Aluminum Ore
        side = self.load_image_texture("textures/blocks/tic/ore_aluminum.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(side, side)

# Tinker's Construct: Soils (I:"Special Soil"=1476)
@material(blockid=1476, data=range(6), solid=True)
def tic_soil(self, blockid, data):
    if data == 0: # Slimy Mud
        side = self.load_image_texture("textures/blocks/tic/slimesand.png")
    elif data == 1: # Grout
        side = self.load_image_texture("textures/blocks/tic/grout.png")
    elif data == 3: # Graveyard Soil
        side = self.load_image_texture("textures/blocks/tic/graveyardsoil.png")
    elif data == 4: # Consecrated Soil
        side = self.load_image_texture("textures/blocks/tic/consecratedsoil.png")
    elif data == 5: # Blue Slimedirt
        side = self.load_image_texture("textures/blocks/tic/slimedirt_blue.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(side, side)

# Tinker's Construct: Storage Blocks (I:"Metal Storage"=1478)
@material(blockid=1478, data=range(16), solid=True)
def tic_storageblock(self, blockid, data):
    if data == 0: # Block of Cobalt
        side = self.load_image_texture("textures/blocks/tic/compressed_cobalt.png")
    elif data == 1: # Block of Ardite
        side = self.load_image_texture("textures/blocks/tic/compressed_ardite.png")
    elif data == 2: # Block of Manyullyn
        side = self.load_image_texture("textures/blocks/tic/compressed_manyullyn.png")
    elif data == 3: # Block of Copper
        side = self.load_image_texture("textures/blocks/tic/compressed_copper.png")
    elif data == 4: # Block of Bronze
        side = self.load_image_texture("textures/blocks/tic/compressed_bronze.png")
    elif data == 5: # Block of Tin
        side = self.load_image_texture("textures/blocks/tic/compressed_tin.png")
    elif data == 6: # Block of Aluminum
        side = self.load_image_texture("textures/blocks/tic/compressed_aluminum.png")
    elif data == 7: # Block of Aluminum Brass
        side = self.load_image_texture("textures/blocks/tic/compressed_alubrass.png")
    elif data == 8: # Block of Alumite
        side = self.load_image_texture("textures/blocks/tic/compressed_alumite.png")
    elif data == 9: # Block of Steel
        side = self.load_image_texture("textures/blocks/tic/compressed_steel.png")
    elif data == 10: # Block of Solid Ender
        side = self.load_image_texture("textures/blocks/tic/compressed_ender.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(side, side)

# Tinker's Construct: Bricks (I:"Multi Brick"=1481)
@material(blockid=1481, data=range(16), solid=True)
def tic_brick(self, blockid, data):
    if data == 0: # Fancy Obsidian Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_obsidian.png")
    elif data == 1: # Sandstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_sandstone.png")
    elif data == 2: # Netherrack Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_netherrack.png")
    elif data == 3: # Polished Stone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_stone_refined.png")
    elif data == 4: # Iron Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_iron.png")
    elif data == 5: # Gold Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_gold.png")
    elif data == 6: # Lapis Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_lapis.png")
    elif data == 7: # Diamond Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_diamond.png")
    elif data == 8: # Redstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_redstone.png")
    elif data == 9: # Bone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_bone.png")
    elif data == 10: # Slime Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_slime.png")
    elif data == 12: # Endstone Brick
        t = self.load_image_texture("textures/blocks/tic/bricks/brick_endstone.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Oreberry bushes (I:"Ore Berry One"=1485)
@material(blockid=1485, data=range(16), solid=True, transparent=True)
def tic_oreberry1(self, blockid, data):
    # FIXME we should shrink the stage 1 and 2 bushes to the proper size
    # for now, we will just render them as full sized blocks
    # TODO The correctness of these data values should be verified
    if data == 0: # Iron Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_iron_fancy.png")
    elif data == 1: # Gold Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_gold_fancy.png")
    elif data == 2: # Copper Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_copper_fancy.png")
    elif data == 3: # Tin Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_tin_fancy.png")
    elif data == 4: # Iron Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_iron_fancy.png")
    elif data == 5: # Gold Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_gold_fancy.png")
    elif data == 6: # Copper Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_copper_fancy.png")
    elif data == 7: # Tin Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_tin_fancy.png")
    elif data == 8: # Iron Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_iron_fancy.png")
    elif data == 9: # Gold Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_gold_fancy.png")
    elif data == 10: # Copper Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_copper_fancy.png")
    elif data == 11: # Tin Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_tin_fancy.png")
    elif data == 12: # Iron Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_iron_ripe_fancy.png")
    elif data == 13: # Gold Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_gold_ripe_fancy.png")
    elif data == 14: # Copper Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_copper_ripe_fancy.png")
    elif data == 15: # Tin Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_tin_ripe_fancy.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Oreberry bushes (I:"Ore Berry Two"=1486)
@material(blockid=1486, data=range(16), solid=True, transparent=True)
def tic_oreberry2(self, blockid, data):
    # FIXME we should shrink the stage 1 and 2 bushes to the proper size
    # for now, we will just render them as full sized blocks
    # TODO The correctness of these data values should be verified
    if data == 0: # Aluminum Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_aluminum_fancy.png")
    elif data == 1: # Essence Oreberry Bush (stage 1)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_essence_fancy.png")
    elif data == 4: # Aluminum Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_aluminum_fancy.png")
    elif data == 5: # Essence Oreberry Bush (stage 2)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_essence_fancy.png")
    elif data == 8: # Aluminum Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_aluminum_fancy.png")
    elif data == 9: # Essence Oreberry Bush (full size)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_essence_fancy.png")
    elif data == 12: # Aluminum Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_aluminum_ripe_fancy.png")
    elif data == 13: # Essence Oreberry Bush (ripe)
        t = self.load_image_texture("textures/blocks/tic/crops/berry_essence_ripe_fancy.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Gravel Ores (I:"Ores Gravel"=1488)
@material(blockid=1488, data=range(6), solid=True)
def tic_gravelore(self, blockid, data):
    # choose textures
    if data == 0: # Iron Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_iron_gravel.png")
    elif data == 1: # Gold Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_gold_gravel.png")
    elif data == 2: # Copper Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_copper_gravel.png")
    elif data == 3: # Tin Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_tin_gravel.png")
    elif data == 4: # Aluminum Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_aluminum_gravel.png")
    elif data == 5: # Cobalt Gravel Ore
        t = self.load_image_texture("textures/blocks/tic/ore_cobalt_gravel.png")
    else: # TODO are there any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Brownstone ( I:"Speed Block"=1489)
@material(blockid=1489, data=range(7), solid=True)
def tic_brownstone(self, blockid, data):
    # choose textures
    if data == 0: # Rough Brownstone
        t = self.load_image_texture("textures/blocks/tic/brownstone_rough.png")
    elif data == 1: # Brownstone Road
        t = self.load_image_texture("textures/blocks/tic/brownstone_rough_road.png")
    elif data == 2: # Brownstone
        t = self.load_image_texture("textures/blocks/tic/brownstone_smooth.png")
    elif data == 3: # Brownstone Brick
        t = self.load_image_texture("textures/blocks/tic/brownstone_smooth_brick.png")
    elif data == 5: # Fancy Brownstone
        t = self.load_image_texture("textures/blocks/tic/brownstone_smooth_fancy.png")
    elif data == 6: # Chiseled Brownstone
        t = self.load_image_texture("textures/blocks/tic/brownstone_smooth_chiseled.png")
    else: # TODO are there any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Clear Glass (I:"Clear Glass"=3223)
@material(blockid=3223, nodata=True, solid=True, transparent=True, nospawn=True)
def tic_clearglass(self, blockid, data):
    t = self.load_image_texture("textures/blocks/tic/glass/glass_clear.png")
    return self.build_block(t, t)

# Tinker's Construct: Stained Glass (I:"Clear Stained Glass"=3225)
@material(blockid=3225, data=range(16), solid=True, transparent=True, nospawn=True)
def tic_stainedglass(self, blockid, data):
    if data == 0: # White Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_white.png")
    elif data == 1: # Orange Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_orange.png")
    elif data == 2: # Magenta Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_magenta.png")
    elif data == 3: # Light Blue Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_lightblue.png")
    elif data == 4: # Yellow Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_yellow.png")
    elif data == 5: # Lime Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_lime.png")
    elif data == 6: # Pink Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_pink.png")
    elif data == 7: # Gray Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_gray.png")
    elif data == 8: # Light Gray Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_lightgray.png")
    elif data == 9: # Cyan Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_cyan.png")
    elif data == 10: # Purple Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_purple.png")
    elif data == 11: # Blue Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_blue.png")
    elif data == 12: # Brown Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_brown.png")
    elif data == 13: # Green Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_green.png")
    elif data == 14: # Red Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_red.png")
    elif data == 15: # Black Stained Glass
        side = self.load_image_texture("textures/blocks/tic/glass/stainedglass_black.png")
    return self.build_block(side, side)

# Tinker's Construct: Seared slabs (I:"Seared Slab"=3230)
@material(blockid=3230, data=range(16), solid=True)
def tic_searedslab(self, blockid, data):
    bdata = data & 7
    if bdata == 0: # Seared Brick Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedbrick.png")
    elif bdata == 1: # Seared Stone Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedstone.png")
    elif bdata == 2: # Seared Cobblestone Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedcobble.png")
    elif bdata == 3: # Seared Paver Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedpaver.png")
    elif bdata == 4: # Seared Road Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedroad.png")
    elif bdata == 5: # Fancy Seared Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedbrickfancy.png")
    elif bdata == 6: # Chiseled Seared Slab
        top = side = self.load_image_texture("textures/blocks/tic/searedbricksquare.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Tinker's Construct: Brownstone slabs (I:"Speed Slab"=3231)
@material(blockid=3231, data=range(16), solid=True)
def tic_woolslab(self, blockid, data):
    bdata = data & 7
    if bdata == 0: # Rough Brownstone Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_rough.png")
    elif bdata == 1: # Brownstone Road Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_rough_road.png")
    elif bdata == 2: # Brownstone Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_smooth.png")
    elif bdata == 3: # Brownstone Brick Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_smooth_brick.png")
    elif bdata == 4: # ?? TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif bdata == 5: # Fancy Brownstone Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_smooth_fancy.png")
    elif bdata == 6: # Chiseled Brownstone Slab
        top = side = self.load_image_texture("textures/blocks/tic/brownstone_smooth_chiseled.png")
    else: # TODO Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Tinker's Construct: Wool slabs (I:"Wool Slab 1"=3244 & I:"Wool Slab 2"=3245)
@material(blockid=[3244, 3245], data=range(16), solid=True)
def tic_woolslab(self, blockid, data):
    if blockid == 3244:
        bdata = data & 7
        top = side = self.load_image_texture("textures/blocks/cloth_%d.png" % bdata)
    else:
        bdata = data & 7
        top = side = self.load_image_texture("textures/blocks/cloth_%d.png" % (bdata + 8))

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Tinker's Construct: Slime liquid (I:"Liquid Blue Slime"=3235)
@material(blockid=3235, data=range(16), fluid=True, transparent=True, nospawn=True)
def tic_slimewater(self, blockid, data):
    t = self.load_image_texture("textures/blocks/tic/slime_blue.png")
    return self.build_block(t, t)

# Tinker's Construct: Congealed Slime Blocks (I:"Congealed Slime"=3237)
@material(blockid=3237, data=range(2), solid=True)
def tic_congealed_slime(self, blockid, data):
    # choose textures
    if data == 0: # Congealed Blue Slime
        t = self.load_image_texture("textures/blocks/tic/slimeblock_blue.png")
    elif data == 1: # Congealed Green Slime
        t = self.load_image_texture("textures/blocks/tic/slimeblock_green.png")
    else: # TODO are there any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Tinker's Construct: Slimy Grass (I:"Slime Grass"=3238)
@material(blockid=3238, nodata=True, solid=True)
def tic_slimy_grass(self, blockid, data):
    side = self.load_image_texture("textures/blocks/tic/slimegrass_green_blue_side.png")
    top = self.load_image_texture("textures/blocks/tic/slimegrass_green_top.png")
    return self.build_block(top, side)

# Tinker's Construct: Slimy Grass (tall grass) (I:"Slime Tall Grass"=3239)
@material(blockid=3239, nodata=True, transparent=True)
def tic_slimy_tall_grass(self, blockid, data):
    t = self.load_image_texture("textures/blocks/tic/slimegrass_blue_tall.png")
    return self.build_billboard(t)

# Tinker's Construct: Slimy Leaves (I:"Slime Grass Leaves"=3240)
block(blockid=3240, top_image="textures/blocks/tic/slimeleaves_blue_fancy.png", solid=True, transparent=True)

#################################
#	 Minefactory Reloaded		#
#################################
# MFR: Rubberwood Logs
@material(blockid=3122, data=range(16), solid=True)
def mfr_rubberwood(self, blockid, data):
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 1: # Rubberwood logs
        side = self.load_image_texture("textures/blocks/mfr/tile.mfr.rubberwood.log.side.png")
        top = self.load_image_texture("textures/blocks/mfr/tile.mfr.rubberwood.log.top.png")
    else: # TODO any others?
        side = self.load_image_texture("textures/blocks/web.png")
        top = self.load_image_texture("textures/blocks/web.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)
    return self.build_block(top, side)

# MFR: Rubberwood Leaves
@material(blockid=3123, data=range(16), solid=True, transparent=True)
def mfr_leaves(self, blockid, data):
    if data & 7 == 0: # Rubberwood Leaves
        t = self.load_image_texture("textures/blocks/mfr/tile.mfr.rubberwood.leaves.transparent.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

#################################
#	 Industrial Craft 2			#
#################################
# IC2: Rubberwood Logs
@material(blockid=243, data=range(16), solid=True)
def ic2_rubberwood(self, blockid, data):
    img_wet = self.load_image("textures/blocks/ic2/blockRubWood.wet.png")
    img_dry = self.load_image("textures/blocks/ic2/blockRubWood.dry.png")
    side_empty = img_dry.crop((32, 0, 48, 16))
    side_dry = img_dry.crop((48, 0, 64, 16))
    side_wet = img_wet.crop((48, 0, 64, 16))
    top = img_dry.crop((0, 0, 16, 16))

    side_east = side_empty
    side_west = side_empty
    side_north = side_empty
    side_south = side_empty

    # build_full_block(top, side1, side2, side3, side4, bottom=None):
    #    side1 is in the -y face of the cube     (top left, east)
    #    side2 is in the +x                      (top right, south)
    #    side3 is in the -x                      (bottom left, north)
    #    side4 is in the +y                      (bottom right, west)

    # data == 0: player placed empty log, always pointing up
    # data == 1: World gen empty log
    if data == 2: # Resin pointing North
        side_north = side_wet
    elif data == 3: # Resin pointing South
        side_south = side_wet
    elif data == 4: # Resin pointing West
        side_west = side_wet
    elif data == 5: # Resin pointing East
        side_east = side_wet
    elif data == 8: # Dry resin hole pointing North
        side_north = side_dry
    elif data == 9: # Dry resin hole pointing South
        side_south = side_dry
    elif data == 10: # Dry resin hole pointing West
        side_west = side_dry
    elif data == 11: # Dry resin hole pointing East
        side_east = side_dry

    if self.rotation == 0: # north upper-left
        side1 = side_north
        side2 = side_east
        side3 = side_west
        side4 = side_south
    elif self.rotation == 1: # north upper-right
        side1 = side_west
        side2 = side_north
        side3 = side_south
        side4 = side_east
    elif self.rotation == 2: # north lower-right
        side1 = side_south
        side2 = side_west
        side3 = side_east
        side4 = side_north
    elif self.rotation == 3: # north lower-left
        side1 = side_east
        side2 = side_south
        side3 = side_north
        side4 = side_west

    return self.build_full_block(top, side1, side2, side3, side4)

# IC2: Rubberwood Leaves
@material(blockid=242, data=range(16), solid=True, transparent=True)
def ic2_leaves(self, blockid, data):
    if data & 7 == 0: # Rubberwood Leaves
        t = self.load_image_texture("textures/blocks/ic2/blockRubLeaves.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# IC2: Ores
@material(blockid=247, data=range(16), solid=True)
def ic2_leaves(self, blockid, data):
    if data == 0: # Uranium Ore
        t = self.load_image_texture("textures/blocks/ic2/blockOreUran.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Buildcraft: Oil (I:oilMoving.id=1520 & I:oilStill.id=1521)
@material(blockid=[1520, 1521], data=range(16), fluid=True, transparent=True, nospawn=True)
def bc_oil(self, blockid, data):
    t = self.load_image_texture("textures/blocks/bc/oil.png")
    #img = self.load_image("textures/blocks/ic2/blockRubWood.png")
    #side = img.crop((32, 0, 48, 16)).copy()
    #top = img.crop((0, 0, 16, 16)).copy()

    return self.build_block(t, t)


#################################
#	 	Magic Bees				#
#################################

# Magic Bees: Hives (I:hives=1754)
@material(blockid=1754, data=range(6), solid=True)
def magicbees_hives(self, blockid, data):
    if data == 0: # Curious Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.0.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.0.top.png")
    elif data == 1: # Unusual Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.1.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.1.top.png")
    elif data == 2: # Resonating Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.2.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.2.top.png")
    elif data == 3: # TODO ?? Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.3.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.3.top.png")
    elif data == 4: # Infernal Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.4.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.4.top.png")
    elif data == 5: # Oblivion Hive
        side = self.load_image_texture("textures/blocks/magicbees/beehive.5.side.png")
        top = self.load_image_texture("textures/blocks/magicbees/beehive.5.top.png")
    else: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(top, side)

# Magic Bees: Planks & Double slabs (I:planksTC=1750 & I:slabFull=1751)
@material(blockid=[1750, 1751], data=range(2), solid=True)
def magicbees_planks(self, blockid, data):
    if data == 0: # Greatwood planks & Greatwood Double Slab
        side = self.load_image_texture("textures/blocks/magicbees/greatwood.png")
    elif data == 1: # Silverwood planks & Silverwood Double Slab
        side = self.load_image_texture("textures/blocks/magicbees/silverwood.png")
    return self.build_block(side, side)

# Magic Bees: Slabs (I:slabHalf=1752)
@material(blockid=1752, data=range(16), solid=True)
def magicbees_slabs(self, blockid, data):
    if data & 7 == 0: # Greatwood Slab
        top = side = self.load_image_texture("textures/blocks/magicbees/greatwood.png")
    elif data & 7 == 1: # Silverwood Slab
        top = side = self.load_image_texture("textures/blocks/magicbees/silverwood.png")
    else: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

#################################
#	 	Forestry				#
#################################

# Forestry: Arborist's Chest(I:arboriculture=1377)
@material(blockid=1377, data=range(1), solid=True)
def forestry_arboriculture(self, blockid, data):
    if data == 0: # Arborist's Chest
        # NOTE: The orientation would need tile entity data, we just render the lock on every side
        side = self.load_image_texture("textures/blocks/forestry/arbchest.3.png")
        top = self.load_image_texture("textures/blocks/forestry/arbchest.1.png")
    else: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(top, side)

# Forestry: Planks (I:planks=1380)
@material(blockid=1380, data=range(16), solid=True)
def forestry_planks1(self, blockid, data):
    if data == 0: # Larch Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.larch.png")
    elif data == 1: # Teak Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.teak.png")
    elif data == 2: # Acacia Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.acacia.png")
    elif data == 3: # Lime Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.lime.png")
    elif data == 4: # Chestnut Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.chestnut.png")
    elif data == 5: # Wenge Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.wenge.png")
    elif data == 6: # Baobab Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.baobab.png")
    elif data == 7: # Sequoia Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.sequoia.png")
    elif data == 8: # Kapok Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.kapok.png")
    elif data == 9: # Ebony Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.ebony.png")
    elif data == 10: # Mahogany Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahogany.png")
    elif data == 11: # Balsa Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.balsa.png")
    elif data == 12: # Willow Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.willow.png")
    elif data == 13: # Walnut Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.walnut.png")
    elif data == 14: # Greenheart Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.greenheart.png")
    elif data == 15: # Cherry Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.cherry.png")
    return self.build_block(side, side)


# Forestry: Alveary (I:alveary=1382)
@material(blockid=1382, data=range(8), solid=True)
def forestry_alveary(self, blockid, data):
    if data == 0: # Alveary
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.plain.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.bottom.png")
    elif data == 1: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif data == 2: # Swarmer
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.swarmer.off.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.bottom.png")
    elif data == 3: # Alveary Fan
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.fan.off.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.fan.off.png")
    elif data == 4: # Alveary Heater
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.heater.off.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.heater.off.png")
    elif data == 5: # Alveary Hygroregulator
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.valve.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.valve.png")
    elif data == 6: # Alveary Stabiliser
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.stabiliser.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.bottom.png")
    elif data == 7: # Alveary Sieve
        side = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.sieve.png")
        top = self.load_image_texture("textures/blocks/forestry/apiculture/alveary.bottom.png")
    else: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(top, side)

# Forestry: Slabs (I:slabs1=1386)
@material(blockid=1386, data=range(16), solid=True)
def forestry_slabs1(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Larch Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.larch.png")
    elif texture == 1: # Teak Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.teak.png")
    elif texture == 2: # Acacia Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.acacia.png")
    elif texture == 3: # Lime Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.lime.png")
    elif texture == 4: # Chestnut Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.chestnut.png")
    elif texture == 5: # Wenge Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.wenge.png")
    elif texture == 6: # Baobab Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.baobab.png")
    elif texture == 7: # Sequoia Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.sequoia.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Forestry: Slabs (I:slabs2=1387)
@material(blockid=1387, data=range(16), solid=True)
def forestry_slabs2(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Kapok Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.kapok.png")
    elif texture == 1: # Ebony Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.ebony.png")
    elif texture == 2: # Mahogany Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahogany.png")
    elif texture == 3: # Balsa Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.balsa.png")
    elif texture == 4: # Willow Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.willow.png")
    elif texture == 5: # Walnut Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.walnut.png")
    elif texture == 6: # Greenheart Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.greenheart.png")
    elif texture == 7: # Cherry Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.cherry.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Forestry: Log 1 (I:log1=1388)
@material(blockid=1388, data=range(16), solid=True)
def forestry_log1(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Larch Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.larch.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.larch.png")
    elif wood_type == 1: # Teak Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.teak.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.teak.png")
    elif wood_type == 2: # Acacia Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.acacia.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.acacia.png")
    elif wood_type == 3: # Lime Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.lime.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.lime.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Log 2 (I:log2=1389)
@material(blockid=1389, data=range(16), solid=True)
def forestry_log2(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Chestnut Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.chestnut.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.chestnut.png")
    elif wood_type == 1: # Wenge Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.wenge.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.wenge.png")
    elif wood_type == 2: # Baobab Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.baobab.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.baobab.png")
    elif wood_type == 3: # Sequoia Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.sequoia.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.sequoia.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Log 3 (I:log3=1390)
@material(blockid=1390, data=range(16), solid=True)
def forestry_log3(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Kapok Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.kapok.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.kapok.png")
    elif wood_type == 1: # Ebony Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.ebony.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.ebony.png")
    elif wood_type == 2: # Mahogany Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.mahogany.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.mahogany.png")
    elif wood_type == 3: # Balsa Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.balsa.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.balsa.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Log 4 (I:log4=1391)
@material(blockid=1391, data=range(16), solid=True)
def forestry_log4(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Willow Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.willow.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.willow.png")
    elif wood_type == 1: # Walnut Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.walnut.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.walnut.png")
    elif wood_type == 2: # Greenheart Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.greenheart.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.greenheart.png")
    elif wood_type == 3: # Cherry Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.cherry.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.cherry.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Fences (I:fences=1394 & I:fences2=1418)
# uses pseudo-ancildata found in iterate.c
@material(blockid=[1394, 1418], data=range(16), transparent=True, nospawn=True)
def forestry_fence(self, blockid, data):
    # no need for rotations, it uses pseudo data.
    # create needed images for Big stick fence
    bdata = data & 0xF # wood type
    data = (data & 0xF0) >> 4 # pseudo ancil data, shift it into the same place as it is with vanilla fences

    if blockid == 1394: # fence 1 (I:fences=1394)
        if bdata == 0: # Larch Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.larch.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.larch.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.larch.png").copy()
        elif bdata == 1: # Teak Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.teak.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.teak.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.teak.png").copy()
        elif bdata == 2: # Acacia Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.acacia.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.acacia.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.acacia.png").copy()
        elif bdata == 3: # Lime Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.lime.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.lime.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.lime.png").copy()
        elif bdata == 4: # Chestnut Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.chestnut.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.chestnut.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.chestnut.png").copy()
        elif bdata == 5: # Wenge Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.wenge.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.wenge.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.wenge.png").copy()
        elif bdata == 6: # Baobab Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.baobab.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.baobab.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.baobab.png").copy()
        elif bdata == 7: # Sequoia Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.sequoia.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.sequoia.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.sequoia.png").copy()
        elif bdata == 8: # Kapok Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.kapok.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.kapok.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.kapok.png").copy()
        elif bdata == 9: # Ebony Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.ebony.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.ebony.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.ebony.png").copy()
        elif bdata == 10: # Mahogany Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.mahogany.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahogany.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahogany.png").copy()
        elif bdata == 11: # Balsa Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.balsa.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.balsa.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.balsa.png").copy()
        elif bdata == 12: # Willow Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.willow.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.willow.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.willow.png").copy()
        elif bdata == 13: # Walnut Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.walnut.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.walnut.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.walnut.png").copy()
        elif bdata == 14: # Greenheart Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.greenheart.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.greenheart.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.greenheart.png").copy()
        elif bdata == 15: # Cherry Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.cherry.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.cherry.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.cherry.png").copy()
    else: # 1418: fence 2 (I:fences2=1418)
        if bdata == 0: # Mahoe Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.mahoe.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahoe.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahoe.png").copy()
        elif bdata == 1: # Poplar Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.poplar.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.poplar.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.poplar.png").copy()
        elif bdata == 2: # Palm Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.palm.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.palm.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.palm.png").copy()
        elif bdata == 3: # Papaya Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.papaya.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.papaya.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.papaya.png").copy()
        elif bdata == 4: # Pine Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png").copy()
        elif bdata == 5: # Plum Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.plum.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.plum.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.plum.png").copy()
        elif bdata == 6: # Maple Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.maple.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.maple.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.maple.png").copy()
        elif bdata == 7: # Citrus Fence
            fence_top = self.load_image_texture("textures/blocks/forestry/wood/planks.citrus.png").copy()
            fence_side = self.load_image_texture("textures/blocks/forestry/wood/planks.citrus.png").copy()
            fence_small_side = self.load_image_texture("textures/blocks/forestry/wood/planks.citrus.png").copy()
        else: # FIXME Unknown block
            t = self.load_image_texture("textures/blocks/web.png")
            return self.build_sprite(t)

    # generate the textures of the fence
    ImageDraw.Draw(fence_top).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,0,15,5),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_top).rectangle((0,10,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    ImageDraw.Draw(fence_side).rectangle((0,0,5,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_side).rectangle((10,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the big stick
    fence_side = self.transform_image_side(fence_side)
    fence_other_side = fence_side.transpose(Image.FLIP_LEFT_RIGHT)
    fence_top = self.transform_image_top(fence_top)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_side.split()[3]
    fence_side = ImageEnhance.Brightness(fence_side).enhance(0.9)
    fence_side.putalpha(sidealpha)
    othersidealpha = fence_other_side.split()[3]
    fence_other_side = ImageEnhance.Brightness(fence_other_side).enhance(0.8)
    fence_other_side.putalpha(othersidealpha)

    # Compose the fence big stick
    fence_big = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(fence_big,fence_side, (5,4),fence_side)
    alpha_over(fence_big,fence_other_side, (7,4),fence_other_side)
    alpha_over(fence_big,fence_top, (0,0),fence_top)

    # Now render the small sticks.
    # Create needed images
    ImageDraw.Draw(fence_small_side).rectangle((0,0,15,0),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,4,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,10,15,16),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((0,0,4,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(fence_small_side).rectangle((11,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))

    # Create the sides and the top of the small sticks
    fence_small_side = self.transform_image_side(fence_small_side)
    fence_small_other_side = fence_small_side.transpose(Image.FLIP_LEFT_RIGHT)

    # Darken the sides slightly. These methods also affect the alpha layer,
    # so save them first (we don't want to "darken" the alpha layer making
    # the block transparent)
    sidealpha = fence_small_other_side.split()[3]
    fence_small_other_side = ImageEnhance.Brightness(fence_small_other_side).enhance(0.9)
    fence_small_other_side.putalpha(sidealpha)
    sidealpha = fence_small_side.split()[3]
    fence_small_side = ImageEnhance.Brightness(fence_small_side).enhance(0.9)
    fence_small_side.putalpha(sidealpha)

    # Create img to compose the fence
    img = Image.new("RGBA", (24,24), self.bgcolor)

    # Position of fence small sticks in img.
    # These postitions are strange because the small sticks of the 
    # fence are at the very left and at the very right of the 16x16 images
    pos_top_left = (2,3)
    pos_top_right = (10,3)
    pos_bottom_right = (10,7)
    pos_bottom_left = (2,7)

    # +x axis points top right direction
    # +y axis points bottom right direction
    # First compose small sticks in the back of the image,
    # then big stick and thecn small sticks in the front.

    if (data & 0b0001) == 1:
        alpha_over(img,fence_small_side, pos_top_left,fence_small_side)                # top left
    if (data & 0b1000) == 8:
        alpha_over(img,fence_small_other_side, pos_top_right,fence_small_other_side)    # top right

    alpha_over(img,fence_big,(0,0),fence_big)

    if (data & 0b0010) == 2:
        alpha_over(img,fence_small_other_side, pos_bottom_left,fence_small_other_side)      # bottom left
    if (data & 0b0100) == 4:
        alpha_over(img,fence_small_side, pos_bottom_right,fence_small_side)                  # bottom right

    return img

# Forestry: Multifarm blocks (I:farm=1395)
@material(blockid=1395, data=range(6), solid=True)
def forestry_farm(self, blockid, data):
    # FIXME: The type (base material) is stored in tile entity data, we ender them all as stone brick versions
    if data == 0: # Farm Block
        side = self.load_image_texture("textures/blocks/forestry/farm/plain.png")
        top = self.load_image_texture("textures/blocks/forestry/farm/top.png")
        return self.build_block(top, side)
    elif data == 1: # FIXME Unused?
        return None
    elif data == 2: # Farm Gearbox
        side = self.load_image_texture("textures/blocks/forestry/farm/gears.png")
    elif data == 3: # Farm Hatch
        side = self.load_image_texture("textures/blocks/forestry/farm/hatch.png")
    elif data == 4: # Farm Valve
        side = self.load_image_texture("textures/blocks/forestry/farm/valve.png")
    elif data == 5: # Farm Control
        side = self.load_image_texture("textures/blocks/forestry/farm/control.png")
    return self.build_block(side, side)

# Forestry: Stairs (I:stairs=1396)
@material(blockid=1396, data=range(16), transparent=True, solid=True, nospawn=True)
def forestry_stairs(self, blockid, data):
    # first, rotations
    # preserve the upside-down bit
    # FIXME: Do the forestry stairs even use the 4-bit data for orientation?
    upside_down = data & 0x4
    data = data & 0x3
    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1
    data = data | upside_down

    # FIXME/NOTE: The wood type is stored in tile entity data, we render them all as Pine stairs
    texture = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png")

    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))

    if data & 0x4 == 0x4: # upside down stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))

        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)

        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)

        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))

    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))

        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)

        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)

        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) # workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))

        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))

    return img

# Forestry: Soil (I:soil=1397)
@material(blockid=1397, data=range(16), solid=True)
def forestry_soil(self, blockid, data):
    if data == 0: # Humus
        t = self.load_image_texture("textures/blocks/forestry/soil/humus.png")
    elif data == 1: # Bog Earth
        t = self.load_image_texture("textures/blocks/forestry/soil/bog.png")
    elif data == 13: # Peat
        t = self.load_image_texture("textures/blocks/forestry/soil/peat.png")
    else: # FIXME Unknown block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Forestry: Ores (I:resources=1398)
@material(blockid=1398, data=range(3), solid=True)
def forestry_ores(self, blockid, data):
    if data == 0: # Apatite Ore
        t = self.load_image_texture("textures/blocks/forestry/ores/apatite.png")
    elif data == 1: # Copper Ore
        t = self.load_image_texture("textures/blocks/forestry/ores/copper.png")
    elif data == 2: # Tin Ore
        t = self.load_image_texture("textures/blocks/forestry/ores/tin.png")
    return self.build_block(t, t)

# Forestry: Beehives (I:beehives=1399)
@material(blockid=1399, data=range(9), solid=True)
def forestry_beehives(self, blockid, data):
    if data == 1: # Forest Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.1.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.1.top.png")
    elif data == 2: # Meadows Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.2.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.2.top.png")
    elif data == 3: # Desert Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.3.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.3.top.png")
    elif data == 4: # Jungle Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.4.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.4.top.png")
    elif data == 5: # End Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.5.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.5.top.png")
    elif data == 6: # Snow Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.6.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.6.top.png")
    elif data == 7: # Swamp Hive
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.7.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.7.top.png")
    elif data == 8: # Swarmer Hive?? FIXME unconfirmed
        side = self.load_image_texture("textures/blocks/forestry/beehives/beehive.8.side.png")
        top = self.load_image_texture("textures/blocks/forestry/beehives/beehive.8.top.png")
    else: # FIXME Unknown block
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_block(side, side)
    return self.build_block(top, side)

# Forestry: Worktable (I:mill=1406)
@material(blockid=1406, data=range(3), solid=True)
def forestry_mill(self, blockid, data):
    if data == 0: # Thermionic Fabricator FIXME: To simplify, atm we render the "front" texture on every side
        side = self.load_image_texture("textures/blocks/forestry/fabricator.3.png")
        top = self.load_image_texture("textures/blocks/forestry/fabricator.1.png")
    elif data == 1: # Raintank NOTE: The model/geometry is not exactly a cube
        side = self.load_image_texture("textures/blocks/forestry/raintank.0.png")
        top = self.load_image_texture("textures/blocks/forestry/raintank.1.png")
    elif data == 2: # Worktable FIXME: To simplify, atm we render the "front" texture on every side
        side = self.load_image_texture("textures/blocks/forestry/worktable.3.png")
        top = self.load_image_texture("textures/blocks/forestry/worktable.1.png")
    return self.build_block(top, side)

# Forestry: Apiary, Apiarist's Chest, Bee House (I:apiculture=1408)
@material(blockid=1408, data=range(3), solid=True)
def forestry_apiculture(self, blockid, data):
    if data == 0: # Apiary
        # NOTE: The Orientation of the top, and the active texture of the side would need tile entity data
        side = self.load_image_texture("textures/blocks/forestry/apiary.4.png")
        top = self.load_image_texture("textures/blocks/forestry/apiary.1.png")
    elif data == 1: # Apiarist's Chest
        # NOTE: The orientation of the chest would need tile entity data, we render the lock on every side
        side = self.load_image_texture("textures/blocks/forestry/apiaristchest.3.png")
        top = self.load_image_texture("textures/blocks/forestry/apiaristchest.1.png")
    elif data == 2: # Bee House
        # NOTE: Same thing as with the apiary
        side = self.load_image_texture("textures/blocks/forestry/beehouse.4.png")
        top = self.load_image_texture("textures/blocks/forestry/beehouse.1.png")
    else: # FIXME Unknown block
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(side)
    return self.build_block(top, side)

# Forestry: Log 5 (I:log5=1411)
@material(blockid=1411, data=range(16), solid=True)
def forestry_log5(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Mahoe Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.mahoe.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.mahoe.png")
    elif wood_type == 1: # Poplar Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.poplar.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.poplar.png")
    elif wood_type == 2: # Palm Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.palm.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.palm.png")
    elif wood_type == 3: # Papaya Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.papaya.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.papaya.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Log 6 (I:log6=1412)
@material(blockid=1412, data=range(16), solid=True)
def forestry_log6(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # Pine Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.pine.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.pine.png")
    elif wood_type == 1: # Plum Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.plum.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.plum.png")
    elif wood_type == 2: # Maple Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.maple.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.maple.png")
    elif wood_type == 3: # Citrus Wood
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.citrus.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.citrus.png")

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Log 7 (I:log7=1413)
@material(blockid=1413, data=range(16), solid=True)
def forestry_log7(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3

    # choose textures
    if wood_type == 0: # wood.24 Wood (?) FIXME not sure if this is the texture, but it is otherwise unused
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.giganteum.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.giganteum.png")
    elif wood_type == 1: # Larch Wood (another?)
        side = self.load_image_texture("textures/blocks/forestry/wood/bark.larch.png")
        top = self.load_image_texture("textures/blocks/forestry/wood/heart.larch.png")
    else: # TODO any others?
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(side)

    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4

    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Forestry: Slabs (I:slabs3=1415)
@material(blockid=1415, data=range(16), solid=True)
def forestry_slabs3(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Mahoe Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahoe.png")
    elif texture == 1: # Poplar Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.poplar.png")
    elif texture == 2: # Palm Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.palm.png")
    elif texture == 3: # Papaya Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.papaya.png")
    elif texture == 4: # Pine Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png")
    elif texture == 5: # Plum Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.plum.png")
    elif texture == 6: # Maple Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.maple.png")
    elif texture == 7: # Citrus Wood Slab
        top = side = self.load_image_texture("textures/blocks/forestry/wood/planks.citrus.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# Forestry: Planks (I:planks2=1417)
@material(blockid=1417, data=range(8), solid=True)
def forestry_planks2(self, blockid, data):
    if data == 0: # Mahoe Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.mahoe.png")
    elif data == 1: # Poplar Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.poplar.png")
    elif data == 2: # Palm Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.palm.png")
    elif data == 3: # Papaya Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.papaya.png")
    elif data == 4: # Pine Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.pine.png")
    elif data == 5: # Plum Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.plum.png")
    elif data == 6: # Maple Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.maple.png")
    elif data == 7: # Citrus Wood Planks
        side = self.load_image_texture("textures/blocks/forestry/wood/planks.citrus.png")
    return self.build_block(side, side)

# Forestry: Lepidopterist's Chest (I:lepidopterology=1419)
@material(blockid=1419, data=range(1), solid=True)
def forestry_lepidopterology(self, blockid, data):
    if data == 0: # Lepidopterist's Chest
        # NOTE: The orientation would need tile entity data, we just render the lock on every side
        side = self.load_image_texture("textures/blocks/forestry/lepichest.3.png")
        top = self.load_image_texture("textures/blocks/forestry/lepichest.1.png")
    else: # FIXME Unknown block
        side = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(side)
    return self.build_block(top, side)

# Forestry: Stained Glass (I:stained=1420)
@material(blockid=1420, data=range(16), solid=True, transparent=True, nospawn=True)
def forestry_stainedglass(self, blockid, data):
    t = self.load_image_texture("textures/blocks/forestry/stained/%d.png" % data)
    return self.build_block(t, t)


#################################
#	 		Railcraft			#
#################################

# Railcraft: Machines (I:block.machine.alpha=451)
@material(blockid=451, data=range(16), solid=True)
def rc_machine1(self, blockid, data):
    if data == 0: # World Anchor
        img = self.load_image("textures/blocks/railcraft/anchor.world.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
    elif data == 1: # Steam Turbine Housing FIXME we use the same texture for everything
        img = self.load_image("textures/blocks/railcraft/turbine.png")
        side = img.crop((0, 32, 16, 48))
        side.load()
        top = img.crop((32, 0, 48, 16))
        top.load()
    elif data == 2: # Personal Anchor
        img = self.load_image("textures/blocks/railcraft/anchor.personal.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
    elif data == 3: # Steam Oven FIXME we use the same texture for everything
        img = self.load_image("textures/blocks/railcraft/steam.oven.png")
        side = img.crop((32, 16, 48, 32))
        side.load()
        top = img.crop((32, 0, 48, 16))
        top.load()
    elif data == 4: # Admin Anchor
        img = self.load_image("textures/blocks/railcraft/anchor.admin.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
    elif data == 5: # Smoker
        img = self.load_image("textures/blocks/railcraft/smoker.png")
        side = img.crop((32, 0, 48, 16))
        side.load()
        top = img.crop((16, 0, 32, 16))
        top.load()
    elif data == 6: # ?? TODO
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif data == 7: # Coke Oven Brick FIXME we use the same texture for everything
        img = self.load_image("textures/blocks/railcraft/coke.oven.png")
        side = img.crop((0, 0, 16, 16))
        side.load()
        return self.build_block(side, side)
    elif data == 8: # Rolling Machine
        img = self.load_image("textures/blocks/railcraft/rolling.machine.png")
        side = img.crop((32, 0, 48, 16))
        side.load()
        top = img.crop((16, 0, 32, 16))
        top.load()
    elif data == 9: # Manual Steam Trap
        img = self.load_image("textures/blocks/railcraft/steam.trap.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((32, 0, 48, 16))
        top.load()
    elif data == 10: # Automated Steam Trap
        img = self.load_image("textures/blocks/railcraft/steam.trap.auto.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((32, 0, 48, 16))
        top.load()
    elif data == 11: # Feed Station
        img = self.load_image("textures/blocks/railcraft/feed.station.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
    elif data == 12: # Blast Furnace Brick FIXME we use the same texture for everything
        img = self.load_image("textures/blocks/railcraft/blast.furnace.png")
        side = img.crop((0, 0, 16, 16))
        side.load()
        return self.build_block(side, side)
    elif data == 13: # ?? TODO
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif data == 14: # Water Tank Siding
        img = self.load_image("textures/blocks/railcraft/tank.water.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
    elif data == 15: # Rock Crusher FIXME we use the same texture for everything
        img = self.load_image("textures/blocks/railcraft/rock.crusher.png")
        side = img.crop((48, 16, 64, 32))
        side.load()
        top = img.crop((48, 32, 64, 48))
        top.load()
    else: # FIXME Unknow Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(top, side)

# Railcraft: Machines (I:block.machine.beta=452)
@material(blockid=452, data=range(16), solid=True)
def rc_machine2(self, blockid, data):
    if data == 0: # Iron Tank Wall
        img = self.load_image("textures/blocks/railcraft/tank.iron.wall.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 1: # Iron Tank Gauge
        img = self.load_image("textures/blocks/railcraft/tank.iron.gauge.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 2: # Iron Tank Valve
        img = self.load_image("textures/blocks/railcraft/tank.iron.valve.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 3: # Low Pressure Boiler Tank
        img = self.load_image("textures/blocks/railcraft/boiler.tank.pressure.low.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 4: # High Pressure Boiler Tank
        img = self.load_image("textures/blocks/railcraft/boiler.tank.pressure.high.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 5: # Solid Fueled Firebox
        img = self.load_image("textures/blocks/railcraft/boiler.firebox.solid.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
        return self.build_block(top, side)
    elif data == 6: # Liquid Fueled Firebox
        img = self.load_image("textures/blocks/railcraft/boiler.firebox.liquid.png")
        side = img.crop((16, 0, 32, 16))
        side.load()
        top = img.crop((0, 0, 16, 16))
        top.load()
        return self.build_block(top, side)
    elif data == 7: # Hobbyist's Steam Engine FIXME totally lazy placeholder
        side = self.load_image_texture("textures/blocks/railcraft/engine.steam.hobby.png")
    elif data == 8: # Commercial Steam Engine FIXME totally lazy placeholder
        side = self.load_image_texture("textures/blocks/railcraft/engine.steam.low.png")
    elif data == 9: # Industrial Steam Engine FIXME totally lazy placeholder
        side = self.load_image_texture("textures/blocks/railcraft/engine.steam.high.png")
    elif data == 10: # Anchor Sentinel FIXME totally lazy placeholder
        img = self.load_image("textures/blocks/railcraft/anchor.sentinel.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 11: # Void Chest FIXME not correct
        side = self.load_image_texture("textures/blocks/railcraft/chest.void.png")
    elif data == 12: # ?? TODO
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    elif data == 13: # Steel Tank Wall
        img = self.load_image("textures/blocks/railcraft/tank.steel.wall.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 14: # Steel Tank Gauge
        img = self.load_image("textures/blocks/railcraft/tank.steel.gauge.png")
        side = img.crop((0, 0, 16, 16))
    elif data == 15: # Steel Tank Valve
        img = self.load_image("textures/blocks/railcraft/tank.iron.valve.png")
        side = img.crop((0, 0, 16, 16))
    else: # FIXME Unknow Block
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    side.load()
    return self.build_block(side, side)

# Railcraft: Blocks (I:block.cube=457)
@material(blockid=457, data=range(8), solid=True)
def rc_blocks(self, blockid, data):
    if data == 0: # Block of Coal Coke
        side = self.load_image_texture("textures/blocks/railcraft/cube.coke.png")
    elif data == 1: # Block of Concrete
        side = self.load_image_texture("textures/blocks/railcraft/concrete.png")
    elif data == 2: # Block of Steel
        side = self.load_image_texture("textures/blocks/railcraft/cube.steel.png")
    elif data == 3: # ?? 
        side = self.load_image_texture("textures/blocks/web.png")
    elif data == 4: # Crushed Obsidian
        side = self.load_image_texture("textures/blocks/railcraft/cube.crushed.obsidian.png")
    elif data == 5: # ??
        side = self.load_image_texture("textures/blocks/web.png")
    elif data == 6: # Abyssal Stone
        side = self.load_image_texture("textures/blocks/railcraft/cube.stone.abyssal.png")
    elif data == 7: # Quarried Stone
        side = self.load_image_texture("textures/blocks/railcraft/cube.stone.quarried.png")
    return self.build_block(side, side)


# Railcraft: Abyssal Bricks (I:block.brick.abyssal=466)
@material(blockid=466, data=range(5), solid=True)
def rc_brick_abyssal(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.abyssal.png")
    if data == 0: # Abyssal Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Abyssal Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Abyssal Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Abyssal Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Abyssal Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Infernal Bricks (I:block.brick.infernal=467)
@material(blockid=467, data=range(5), solid=True)
def rc_brick_infernal(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.infernal.png")
    if data == 0: # Infernal Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Infernal Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Infernal Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Infernal Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Infernal Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Blood Stained Bricks (I:block.brick.bloodstained=468)
@material(blockid=468, data=range(5), solid=True)
def rc_brick_bloodstained(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.bloodstained.png")
    if data == 0: # Blood Stained Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Blood Stained Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Blood Stained Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Blood Stained Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Blood Stained Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Sandy Bricks (I:block.brick.sandy=469)
@material(blockid=469, data=range(5), solid=True)
def rc_brick_sandy(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.sandy.png")
    if data == 0: # Sandy Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Sandy Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Sandy Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Sandy Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Sandy Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Bleached Bone Bricks (I:block.brick.bleachedbone=470)
@material(blockid=470, data=range(5), solid=True)
def rc_brick_bleachedbone(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.bleachedbone.png")
    if data == 0: # Bleached Bone Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Bleached Bone Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Bleached Bone Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Bleached Bone Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Bleached Bone Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Quarried Bricks (I:block.brick.quarried=471)
@material(blockid=471, data=range(5), solid=True)
def rc_brick_quarried(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.quarried.png")
    if data == 0: # Quarried Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Quarried Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Quarried Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Quarried Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Quarried Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

# Railcraft: Frost Bound Bricks (I:block.brick.frostbound=472)
@material(blockid=472, data=range(5), solid=True)
def rc_brick_frostbound(self, blockid, data):
    texture = self.load_image("textures/blocks/railcraft/brick.frostbound.png")
    if data == 0: # Frost Bound Brick
        side = texture.crop((0, 0, 16, 16))
    elif data == 1: # Fitted Frost Bound Stone
        side = texture.crop((16, 0, 32, 16))
    elif data == 2: # Frost Bound Block
        side = texture.crop((32, 0, 48, 16))
    elif data == 3: # Ornate Frost Bound Stone
        side = texture.crop((48, 0, 64, 16))
    elif data == 4: # Etched Frost Bound Stone
        side = texture.crop((64, 0, 80, 16))
    side.load()
    return self.build_block(side, side)

#################################
#	 Thermal Expansion			#
#################################
#block {
#    I:Conduit=2006
#    I:EnergyCell=2005
#    I:Engine=2003
#    I:Glass=2011
#    I:Lamp=2009
#    I:LiquidEnder=2015
#    I:LiquidGlowstone=2014
#    I:LiquidRedstone=2013
#    I:Machine=2002
#    I:Ore=2001
#    I:Plate=2008
#    I:Rockwool=2012
#    I:Storage=2010
#    I:Tank=2004
#    I:Tesseract=2007
#	...
#}

# Thermal Expansion: Ores (I:Ore=2001)
@material(blockid=2001, data=range(5), solid=True)
def te_ores(self, blockid, data):
    if data == 0: # Copper Ore
        t = self.load_image_texture("textures/blocks/te/Ore_Copper.png")
    elif data == 1: # Tin Ore
        t = self.load_image_texture("textures/blocks/te/Ore_Tin.png")
    elif data == 2: # Silver Ore
        t = self.load_image_texture("textures/blocks/te/Ore_Silver.png")
    elif data == 3: # Lead Ore
        t = self.load_image_texture("textures/blocks/te/Ore_Lead.png")
    elif data == 4: # Ferrous Ore
        t = self.load_image_texture("textures/blocks/te/Ore_Ferrous.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Thermal Expansion: Machines (I:Machine=2002)
@material(blockid=2002, data=range(11), solid=True)
def te_machines(self, blockid, data):
    top = self.load_image_texture("textures/blocks/te/Machine_Top.png")
    if data == 0: # Powered Furnace
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Furnace.png")
    elif data == 1: # Pulverizer
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Pulverizer.png")
    elif data == 2: # Sawmill
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Sawmill.png")
    elif data == 3: # Induction Smelter
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Smelter.png")
    elif data == 4: # Magma Crucible
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Crucible.png")
    elif data == 5: # Liquid Transposer
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Transposer.png")
    elif data == 6: # Glacial Precipitator
        side = self.load_image_texture("textures/blocks/te/Machine_Face_IceGen.png")
    elif data == 7: # Igneous Extruder
        side = self.load_image_texture("textures/blocks/te/Machine_Face_RockGen.png")
    elif data == 8: # Aqueous Accumulator
        side = self.load_image_texture("textures/blocks/te/Machine_Face_WaterGen.png")
    elif data == 9: # Cyclic Assembler
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Assembler.png")
    elif data == 10: # Energetic Infuser
        side = self.load_image_texture("textures/blocks/te/Machine_Face_Charger.png")
    else: # TODO any others?
        side = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(top, side)

# Thermal Expansion: Redstone Energy Cell (I:EnergyCell=2005) FIXME the inner part is not rendered...
block(blockid=2005, top_image="textures/blocks/te/EnergyCell.png")

# Thermal Expansion: Tesseracts (I:Tesseract=2007) FIXME the inner part is not rendered...
@material(blockid=2007, data=range(3), solid=True)
def te_tesseract(self, blockid, data):
    if data == 0: # Energy Tessearct
        side = self.load_image_texture("textures/blocks/te/Tesseract_Energy.png")
    elif data == 1: # Liquid Tessearct
        side = self.load_image_texture("textures/blocks/te/Tesseract_Liquid.png")
    elif data == 2: # Item Tesseract
        side = self.load_image_texture("textures/blocks/te/Tesseract_Item.png")
    return self.build_block(side, side)

# Thermal Expansion: Glowstone Illuminator (I:Lamp=2009)
block(blockid=2009, top_image="textures/blocks/te/Lamp_Basic.png")

# Thermal Expansion: Storage Blocks (I:Storage=2010)
@material(blockid=2010, data=range(8), solid=True)
def te_storageblocks(self, blockid, data):
    if data == 0: # Copper Block
        side = self.load_image_texture("textures/blocks/te/Block_Copper.png")
    elif data == 1: # Tin Block
        side = self.load_image_texture("textures/blocks/te/Block_Tin.png")
    elif data == 2: # Silver Block
        side = self.load_image_texture("textures/blocks/te/Block_Silver.png")
    elif data == 3: # Lead Block
        side = self.load_image_texture("textures/blocks/te/Block_Lead.png")
    elif data == 4: # Ferrous Block
        side = self.load_image_texture("textures/blocks/te/Block_Nickel.png")
    elif data == 5: # Shiny Block
        side = self.load_image_texture("textures/blocks/te/Block_Platinum.png")
    elif data == 6: # Electrum Block
        side = self.load_image_texture("textures/blocks/te/Block_Electrum.png")
    elif data == 7: # Invar Block
        side = self.load_image_texture("textures/blocks/te/Block_Invar.png")
    return self.build_block(side, side)

# Thermal Expansion: Hardened Glass (I:Glass=2011)
block(blockid=2011, top_image="textures/blocks/te/Glass_Hardened.png")

# Thermal Expansion: Rockwool (I:Rockwool=2012)
@material(blockid=2012, data=range(16), solid=True)
def te_rockwool(self, blockid, data):
    t = self.load_image_texture("textures/blocks/cloth_%d.png" % data)
    return self.build_block(t, t)

#################################
#	 	Thaumcraft				#
#################################
#block {
#    I:BlockArcaneDoor=2415
#    I:BlockArcaneFurnace=2406
#    I:BlockCandle=2411
#    I:BlockChestHungry=2410
#    I:BlockCosmeticOpaque=2421
#    I:BlockCosmeticSolid=2422
#    I:BlockCrucible=2407
#    I:BlockCrystal=2420
#    I:BlockCustomOre=2402
#    I:BlockCustomPlant=2403
#    I:BlockFluxGoo=2400
#    I:BlockHole=2401
#    I:BlockInfusionWorkbench=2412
#    I:BlockJar=2414
#    I:BlockLifter=2418
#    I:BlockMagicalLeaves=2405
#    I:BlockMagicalLog=2404
#    I:BlockMarker=2408
#    I:BlockMirror=2423
#    I:BlockNitor=2419
#    I:BlockSecure=2416
#    I:BlockTable=2409
#    I:BlockWooden=2413
#    I:BlockWoodenDevice=2417
#}

# Thaumcraft: Ores (I:BlockCustomOre=2402)
@material(blockid=2402, data=range(8), solid=True)
def thaumcraft_ore(self, blockid, data):
    # choose textures
    if data == 0: # Cinnabar Ore
        t = self.load_image_texture("textures/blocks/thaumcraft/cinnibar.png")
        # FIXME how could we render the correct colors on the animated parts?
    elif data == 1: # Air Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 2: # Fire Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 3: # Water Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 4: # Earth Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 5: # Vis Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 6: # Dull Infused Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/infusedorestone.png")
    elif data == 7: # Amber Bearing Stone
        t = self.load_image_texture("textures/blocks/thaumcraft/amberore.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Thaumcraft: Cinderpearl, Simmerleaf (I:BlockCustomPlant=2403)
@material(blockid=2403, data=range(16), transparent=True)
def thaumcraft_plant(self, blockid, data):
    if data == 2: # Simmerleaf
        t = self.load_image_texture("textures/blocks/thaumcraft/shimmerleaf.png")
    elif data == 3: # Cinderpearl
        t = self.load_image_texture("textures/blocks/thaumcraft/cinderpearl.png")
    else:
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_sprite(t)

# Thaumcraft: Greatwood, Silverwood logs (I:BlockMagicalLog=2404)
@material(blockid=2404, data=range(16), solid=True)
def thaumcraft_log(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 0: # Greatwood Log
        side = self.load_image_texture("textures/blocks/thaumcraft/greatwoodside.png")
        top = self.load_image_texture("textures/blocks/thaumcraft/greatwoodtop.png")
    elif wood_type == 1: # Silverwood Log
        side = self.load_image_texture("textures/blocks/thaumcraft/silverwoodside.png")
        top = self.load_image_texture("textures/blocks/thaumcraft/silverwoodtop.png")
    else: # TODO any others?
        side = self.load_image_texture("textures/blocks/web.png")
        top = self.load_image_texture("textures/blocks/web.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# Thaumcraft: Greatwood & Silverwood leaves (I:BlockMagicalLeaves=2405)
@material(blockid=2405, data=range(16), solid=True, transparent=True)
def thaumcraft_leaves(self, blockid, data):
    # choose textures
    if data & 7 == 0: # Greatwood Leaves
        t = self.load_image_texture("textures/blocks/thaumcraft/greatwoodleaves.png")
    elif data & 7 == 1: # Silverwood Leaves
        t = self.load_image_texture("textures/blocks/thaumcraft/silverwoodleaves.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# Thaumcraft: Obsidian totem (I:BlockCosmeticSolid=2422)
# FIXME: This is not adequate, nor right, just a quick hack to get "some totems" showing
block(blockid=2422, top_image="textures/blocks/thaumcraft/obsidiantotem3.png")

#################################
#	 Biomes O' Plenty			#
#################################

#"terrain block ids - must be below 255" {
#*    I:"Ash Block ID"=163
#*    I:"Ash Stone ID"=164
#*    I:"Crag Rock ID"=172
#*    I:"Dried Dirt ID"=161
#*    I:"Hard Dirt ID"=168
#*    I:"Hard Ice ID"=165
#*    I:"Hard Sand ID"=167
#*    I:"Holy Dirt ID"=254
#*    I:"Holy Grass ID"=255
#*    I:"Long Grass ID"=173
#*    I:"Mud ID"=160
#*    I:"Origin Grass ID"=166
#*    I:"Red Rock ID"=162
#*    I:"Skystone ID"=171
#}

# BoP: Mud, Quicksand, ... (I:"Mud ID"=160)
@material(blockid=160, data=range(16), solid=True)
def bop_mud(self, blockid, data):
    if data == 0: # Mud
        t = self.load_image_texture("textures/blocks/bop/mud.png")
    elif data == 1: # Quicksand
        t = self.load_image_texture("textures/blocks/bop/quicksand.png")
    else: # TODO Any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Dried Dirt (I:"Dried Dirt ID"=161)
block(blockid=161, top_image="textures/blocks/bop/drieddirt.png")

# BoP: Red Rock (I:"Red Rock ID"=162)
@material(blockid=162, data=range(3), solid=True)
def bop_redrock(self, blockid, data):
    if data == 0: # Red Rock
        t = self.load_image_texture("textures/blocks/bop/redrock.png")
    elif data == 1: # Red Rock Cobblestone
        t = self.load_image_texture("textures/blocks/bop/redcobble.png")
    elif data == 2: # Red Rock Bricks
        t = self.load_image_texture("textures/blocks/bop/redbrick.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Ash Block (I:"Ash Block ID"=163)
block(blockid=163, top_image="textures/blocks/bop/ashblock.png")
# BoP: Ash Stone (I:"Ash Stone ID"=164)
block(blockid=164, top_image="textures/blocks/bop/ashstone.png")
# BoP: Hard Ice (I:"Hard Ice ID"=165)
block(blockid=165, top_image="textures/blocks/bop/hardice.png")

# BoP: Origin Grass (I:"Origin Grass ID"=166)
@material(blockid=166, nodata=True, solid=True)
def bop_origingrass(self, blockid, data):
    side = self.load_image_texture("textures/blocks/bop/origingrass2.png")
    top = self.load_image_texture("textures/blocks/bop/origingrass1.png")
    return self.build_block(top, side)

# BoP: Hard Sand (I:"Hard Sand ID"=167)
block(blockid=167, top_image="textures/blocks/bop/hardsand.png")
# BoP: Hard Dirt (I:"Hard Dirt ID"=168)
block(blockid=168, top_image="textures/blocks/bop/harddirt.png")

# BoP: Skystone (I:"Skystone ID"=171)
@material(blockid=171, data=range(3), solid=True)
def bop_skystone(self, blockid, data):
    if data == 0: # Skystone
        t = self.load_image_texture("textures/blocks/bop/holystone.png")
    elif data == 1: # Skystone Cobblestone
        t = self.load_image_texture("textures/blocks/bop/holycobble.png")
    elif data == 2: # Skystone Bricks
        t = self.load_image_texture("textures/blocks/bop/holybrick.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Crag Rock (I:"Crag Rock ID"=172)
block(blockid=172, top_image="textures/blocks/bop/cragrock.png")

# BoP: Long Grass (I:"Long Grass ID"=173)
@material(blockid=173, nodata=True, solid=True)
def bop_longgrass(self, blockid, data):
    side = self.load_image_texture("textures/blocks/bop/longgrass2.png")
    top = self.load_image_texture("textures/blocks/bop/longgrass1.png")
    return self.build_block(top, side)

# BoP: Purified Dirt (I:"Holy Dirt ID"=254)
block(blockid=254, top_image="textures/blocks/bop/holydirt.png")

# BoP: Purified Grass Block & Smoldering Grass Block (I:"Holy Grass ID"=255)
@material(blockid=255, data=range(2), solid=True)
def bop_purifiedgrass(self, blockid, data):
    if data == 0: # Purified Grass Block
        side = self.load_image_texture("textures/blocks/bop/holygrass_side.png")
        top = self.load_image_texture("textures/blocks/bop/holygrass_top.png")
    elif data == 1: # Smoldering Grass Block
        side = self.load_image_texture("textures/blocks/bop/smolderinggrass_side.png")
        top = self.load_image_texture("textures/blocks/bop/smolderinggrass_top.png")
    return self.build_block(top, side)

#block {
#    I:"Acacia Stairs ID"=1952
#    I:"Altar ID"=1979
#    I:"Amethyst Ore ID"=1942
#    I:"Bamboo ID"=1927
#    I:"Bones ID"=1968
#    I:"Cherry Stairs ID"=1953
#    I:"Cloud ID"=1964
#    I:"Colourized Leaves ID"=1962
#    I:"Colourized Sapling ID"=1938
#    I:"Coral ID"=1969
#    I:"Crystal ID"=1963
#    I:"Dark Stairs ID"=1954
#    I:"Fir Stairs ID"=1955
#    I:"Flower ID"=1921
#    I:"Foliage ID"=1925
#    I:"Fruit Leaf Block ID"=1926
#    I:"Glass ID"=1978
#    I:"Grave ID"=1981
#    I:"Hell Bark Stairs ID"=1976
#    I:"Holy Stairs ID"=1956
#    I:"Ivy ID"=1943
#    I:"Jacaranda ID"=1977
#    I:"Leaf Block ID 1"=1923
#    I:"Leaf Block ID 2"=1924
#    I:"Log Block ID 1"=1933
#    I:"Log Block ID 2"=1934
#    I:"Log Block ID 3"=1935
#    I:"Log Block ID 4"=1974
#    I:"Magic Stairs ID"=1957
#    I:"Mangrove Stairs ID"=1958
#    I:"Moss ID"=4095
#    I:"Mud Brick Stairs ID"=1929
#    I:"Mud Bricks ID"=1928
#    I:"Mushroom ID"=1967
#    I:"Palm Stairs ID"=1959
#    I:"Petal ID"=1936
#    I:"Pine Stairs ID"=1975
#    I:"Planks ID"=1947
#    I:"Plant ID"=1920
#    I:"Promised Land Portal ID"=1941
#    I:"Puddle ID"=1980
#    I:"Red Brick Stairs ID"=1940
#    I:"Red Cobble Stairs ID"=1939
#    I:"Redwood Stairs ID"=1960
#    I:"Sapling ID"=1937
#    I:"Skystone Brick Stairs ID"=1966
#    I:"Skystone Cobble Stairs ID"=1965
#    I:"Stone Double Slab ID"=1930
#    I:"Stone Single Slab ID"=1931
#    I:"Tree Moss ID"=1932
#    I:"Willow ID"=1922
#    I:"Willow Stairs ID"=1961
#    I:"Wooden Double Slab 1 ID"=1948
#    I:"Wooden Double Slab 2 ID"=1950
#    I:"Wooden Single Slab 1 ID"=1949
#    I:"Wooden Single Slab 2 ID"=1951
#}


# TODO:
#    I:"Promised Land Portal ID"=1941
#    I:"Bones ID"=1968
#    I:"Coral ID"=1969
#    I:"Glass ID"=1978
#    I:"Altar ID"=1979
#    I:"Puddle ID"=1980
#    I:"Grave ID"=1981


# BoP: Plants (I:"Plant ID"=1920)
@material(blockid=1920, data=range(16), transparent=True)
def bop_plants(self, blockid, data):
    if data == 0: # Dead Grass
        t = self.load_image_texture("textures/blocks/bop/deadgrass.png")
        return self.build_billboard(t)
    elif data == 1: # Desert Grass
        t = self.load_image_texture("textures/blocks/bop/desertgrass.png")
        return self.build_billboard(t)
    elif data == 2: # Desert Sprouts
        t = self.load_image_texture("textures/blocks/bop/desertsprouts.png")
        return self.build_billboard(t)
    elif data == 3: # Dune Grass
        t = self.load_image_texture("textures/blocks/bop/dunegrass.png")
        return self.build_billboard(t)
    elif data == 4: # Purified Tall Grass
        t = self.load_image_texture("textures/blocks/bop/holytallgrass.png")
        return self.build_billboard(t)
    elif data == 5: # Thorns
        t = self.load_image_texture("textures/blocks/bop/thorn.png")
        return self.build_sprite(t)
    elif data == 6: # Barley
        t = self.load_image_texture("textures/blocks/bop/barley.png")
    elif data == 7: # Cattail
        t = self.load_image_texture("textures/blocks/bop/cattail.png")
    elif data == 8: # Reed
        t = self.load_image_texture("textures/blocks/bop/reed.png")
    elif data == 9: # Cattail (top)
        t = self.load_image_texture("textures/blocks/bop/cattailtop.png")
    elif data == 10: # Cattail (bottom)
        t = self.load_image_texture("textures/blocks/bop/cattailbottom.png")
    elif data == 11: # Wild Carrot
        t = self.load_image_texture("textures/blocks/bop/wildcarrot.png")
    elif data == 12: # Tiny Cactus
        t = self.load_image_texture("textures/blocks/bop/cactus.png")
        return self.build_sprite(t)
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # Barley, Reed, Cattail and Wild Carrot rendering is the same as vanilla crops
    t1 = self.transform_image_top(t)
    t2 = self.transform_image_side(t)
    t3 = t2.transpose(Image.FLIP_LEFT_RIGHT)

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, t1, (0,12), t1)
    alpha_over(img, t2, (6,3), t2)
    alpha_over(img, t3, (6,3), t3)
    return img

# BoP: Flowers (I:"Flower ID"=1921)
@material(blockid=1921, data=range(16), transparent=True)
def bop_flower(self, blockid, data):
    if data == 0: # Clover FIXME?
        t = self.load_image_texture("textures/blocks/bop/clover.png")
        img = Image.new("RGBA", (24,24), self.bgcolor)
        tmp = self.transform_image_top(t)
        alpha_over(img, tmp, (0,12), tmp)
        return img
    elif data == 1: # Swampflower
        t = self.load_image_texture("textures/blocks/bop/swampflower.png")
    elif data == 2: # Deathbloom
        t = self.load_image_texture("textures/blocks/bop/deadbloom.png")
    elif data == 3: # Glowflower
        t = self.load_image_texture("textures/blocks/bop/glowflower.png")
    elif data == 4: # Hydrangea
        t = self.load_image_texture("textures/blocks/bop/hydrangea.png")
    elif data == 5: # Daisy
        t = self.load_image_texture("textures/blocks/bop/daisy.png")
    elif data == 6: # Tulip
        t = self.load_image_texture("textures/blocks/bop/tulip.png")
    elif data == 7: # Wildflower
        t = self.load_image_texture("textures/blocks/bop/wildflower.png")
    elif data == 8: # Violet
        t = self.load_image_texture("textures/blocks/bop/violet.png")
    elif data == 9: # Anemone
        t = self.load_image_texture("textures/blocks/bop/anemone.png")
    elif data == 10: # Waterlily
        t = self.load_image_texture("textures/blocks/bop/lilyflower.png")
    elif data == 11: # Chromaflora
        t = self.load_image_texture("textures/blocks/bop/item_rainbowflower.png")
    elif data == 12: # Aloe
        t = self.load_image_texture("textures/blocks/bop/aloe.png")
    elif data == 13: # Sunflower (bottom)
        t = self.load_image_texture("textures/blocks/bop/sunflowerbottom.png")
    elif data == 14: # Sunflower (top)
        t = self.load_image_texture("textures/blocks/bop/sunflowertop.png")
    elif data == 15: # Dandelion
        t = self.load_image_texture("textures/blocks/bop/dandelion.png")
    return self.build_sprite(t)

# BoP: Willow (I:"Willow ID"=1922)
sprite(blockid=1922, imagename="textures/blocks/bop/willow.png")

# BoP: Leaves (I:"Leaf Block ID 1"=1923)
@material(blockid=1923, data=range(16), transparent=True, solid=True)
def bop_leaves1(self, blockid, data):
    if data & 7 == 0: # Yellow Autumn Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_yellowautumn_fancy.png")
    elif data & 7 == 1: # Bamboo Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_bamboo_fancy.png")
    elif data & 7 == 2: # Magic Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_magic_fancy.png")
    elif data & 7 == 3: # Dark Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_dark_fancy.png")
    elif data & 7 == 4: # Dying Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_dead_fancy.png")
    elif data & 7 == 5: # Fir Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_fir_fancy.png")
    elif data & 7 == 6: # Loftwood Leaves FIXME is this the correct texture?
        t = self.load_image_texture("textures/blocks/bop/leaves_holy_fancy.png")
    elif data & 7 == 7: # Orange Autumn Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_orangeautumn_fancy.png")
#    else: # TODO there shouldn't be others, right? The 4th bit is used for non-decay or something?
#        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Leaves (I:"Leaf Block ID 2"=1924)
@material(blockid=1924, data=range(16), transparent=True, solid=True)
def bop_leaves2(self, blockid, data):
    if data & 7 == 0: # Origin Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_origin_fancy.png")
    elif data & 7 == 1: # Pink Cherry leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_pinkcherry_fancy.png")
    elif data & 7 == 2: # Maple Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_maple_fancy.png")
    elif data & 7 == 3: # White Cherry Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_whitecherry_fancy.png")
    elif data & 7 == 4: # Hellbark Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_hellbark_fancy.png")
    elif data & 7 == 5: # Jacaranda Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_jacaranda_fancy.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# BoP: Tall grass-like stuff (I:"Foliage ID"=1925)
@material(blockid=1925, data=range(16), transparent=True)
def bop_foliage(self, blockid, data):
    if data == 0: # Algae
        t = self.load_image_texture("textures/blocks/bop/algae.png")
        img = Image.new("RGBA", (24,24), self.bgcolor)
        tmp = self.transform_image_top(t)
        alpha_over(img, tmp, (0,12), tmp)
        return img
    elif data == 1: # Short Grass
        t = self.load_image_texture("textures/blocks/bop/shortgrass.png")
    elif data == 2: # Mediumgrass
        t = self.load_image_texture("textures/blocks/bop/mediumgrass.png")
    elif data == 3: # High Grass (bottom)
        t = self.load_image_texture("textures/blocks/bop/highgrassbottom.png")
    elif data == 4: # Bush
        t = self.load_image_texture("textures/blocks/bop/bush.png")
    elif data == 5: # Sprout
        t = self.load_image_texture("textures/blocks/bop/sprout.png")
    elif data == 6: # High Grass (top)
        t = self.load_image_texture("textures/blocks/bop/highgrasstop.png")
    elif data == 7: # Poison Ivy
        t = self.load_image_texture("textures/blocks/bop/poisonivy.png")
    elif data == 8: # Berry Bush
        t = self.load_image_texture("textures/blocks/bop/berrybush.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_billboard(t)

# BoP: Apple Leaves (I:"Fruit Leaf Block ID"=1926)
@material(blockid=1926, data=range(16), transparent=True, solid=True)
def bop_fruit_leaves(self, blockid, data):
    if data & 7 == 0: # Apple leaves, empty
        t = self.load_image_texture("textures/blocks/bop/leaves_apple0_fancy.png")
    elif data & 7 == 1: # Apple leaves, flower
        t = self.load_image_texture("textures/blocks/bop/leaves_apple1_fancy.png")
    elif data & 7 == 2: # Apple leaves, raw fruit
        t = self.load_image_texture("textures/blocks/bop/leaves_apple2_fancy.png")
    elif data & 7 == 3: # Apple leaves, mature fruit
        t = self.load_image_texture("textures/blocks/bop/leaves_apple3_fancy.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# BoP: Bamboo (I:"Bamboo ID"=1927)
sprite(blockid=1927, imagename="textures/blocks/bop/bamboo.png")
# Bop: Mud Bricks (I:"Mud Bricks ID"=1928)
block(blockid=1928, top_image="textures/blocks/bop/mudbrick.png")

# BoP: Double Slabs (I:"Stone Double Slab ID"=1930)
@material(blockid=1930, data=range(5), solid=True)
def bop_doubleslabs(self, blockid, data):
    if data == 0: # Red Rock Cobblestone Slab
        t = self.load_image_texture("textures/blocks/bop/redcobble.png")
    elif data == 1: # Red Rock Bricks Slab
        t = self.load_image_texture("textures/blocks/bop/redbrick.png")
    elif data == 2: # Mud Bricks Slab
        t = self.load_image_texture("textures/blocks/bop/mudbrick.png")
    elif data == 3: # Skystone Cobblestone Slabs
        t = self.load_image_texture("textures/blocks/bop/holycobble.png")
    elif data == 4: # Skystone Bricks Slab
        t = self.load_image_texture("textures/blocks/bop/holybrick.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# Bop: Slabs (I:"Stone Single Slab ID"=1931)
@material(blockid=1931, data=range(16), solid=True)
def bop_singleslabs(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Red Rock Cobblestone Slab
        top = side = self.load_image_texture("textures/blocks/bop/redcobble.png")
    elif texture == 1: # Red Rock Bricks Slab
        top = side = self.load_image_texture("textures/blocks/bop/redbrick.png")
    elif texture == 2: # Mud Bricks Slab
        top = side = self.load_image_texture("textures/blocks/bop/mudbrick.png")
    elif texture == 3: # Skystone Cobblestone Slabs
        top = side = self.load_image_texture("textures/blocks/bop/holycobble.png")
    elif texture == 4: # Skystone Bricks Slab
        top = side = self.load_image_texture("textures/blocks/bop/holybrick.png")
    else: # TODO any others?
        top = side = self.load_image_texture("textures/blocks/web.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# BoP: Tree Moss (I:"Tree Moss ID"=1932)
@material(blockid=1932, data=range(16), transparent=True)
def bop_treemoss(self, blockid, data):
    # rotation
    # vines data is bit coded. decode it first.
    # NOTE: the directions used in this function are the new ones used
    # in minecraft 1.0.0, no the ones used by overviewer
    # (i.e. north is top-left by defalut)

    # rotate the data by bitwise shift
    shifts = 0
    if self.rotation == 1:
        shifts = 1
    elif self.rotation == 2:
        shifts = 2
    elif self.rotation == 3:
        shifts = 3

    for i in range(shifts):
        data = data * 2
        if data & 16:
            data = (data - 16) | 1

    # decode data and prepare textures
    raw_texture = self.load_image_texture("textures/blocks/bop/treemoss.png")
    s = w = n = e = None

    if data & 1: # south
        s = raw_texture
    if data & 2: # west
        w = raw_texture
    if data & 4: # north
        n = raw_texture
    if data & 8: # east
        e = raw_texture

    # texture generation
    img = self.build_full_block(None, n, e, w, s)

    return img

# BoP: Logs 1 (I:"Log Block ID 1"=1933)
@material(blockid=1933, data=range(16), solid=True)
def bop_log1(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 0: # Acacia Wood
        side = self.load_image_texture("textures/blocks/bop/log_acacia_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_acacia_heart.png")
    if wood_type == 1: # Cherry Wood
        side = self.load_image_texture("textures/blocks/bop/log_cherry_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_cherry_heart.png")
    if wood_type == 2: # Dark Wood
        side = self.load_image_texture("textures/blocks/bop/log_dark_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_dark_heart.png")
    if wood_type == 3: # Fir Wood
        side = self.load_image_texture("textures/blocks/bop/log_fir_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_fir_heart.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# BoP: Logs 2 (I:"Log Block ID 2"=1934)
@material(blockid=1934, data=range(16), solid=True)
def bop_log2(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 0: # Loftwood Wood
        side = self.load_image_texture("textures/blocks/bop/log_holy_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_holy_heart.png")
    if wood_type == 1: # Magic Wood
        side = self.load_image_texture("textures/blocks/bop/log_magic_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_magic_heart.png")
    if wood_type == 2: # Mangrove Wood
        side = self.load_image_texture("textures/blocks/bop/log_mangrove_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_mangrove_heart.png")
    if wood_type == 3: # Palm Wood
        side = self.load_image_texture("textures/blocks/bop/log_palm_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_palm_heart.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# BoP: Logs 3 (I:"Log Block ID 3"=1935)
@material(blockid=1935, data=range(16), solid=True)
def bop_log3(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 0: # Redwood Wood
        side = self.load_image_texture("textures/blocks/bop/log_redwood_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_redwood_heart.png")
    if wood_type == 1: # Willow Wood
        side = self.load_image_texture("textures/blocks/bop/log_willow_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_willow_heart.png")
    if wood_type == 2: # Dead Wood
        side = self.load_image_texture("textures/blocks/bop/log_dead_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_dead_heart.png")
    if wood_type == 3: # Giant Flower Stem
        side = self.load_image_texture("textures/blocks/bop/bigflowerstem_side.png")
        top = self.load_image_texture("textures/blocks/bop/bigflowerstem_heart.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

# BoP: Giant Flowers (I:"Petal ID"=1936)
@material(blockid=1936, data=range(16), solid=True)
def bop_petal(self, blockid, data):
    if data == 0: # Giant Red Flower
        t = self.load_image_texture("textures/blocks/bop/bigflowerred.png")
    elif data == 1: # Giant Yellow Flower
        t = self.load_image_texture("textures/blocks/bop/bigfloweryellow.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Saplings (I:"Sapling ID"=1937)
@material(blockid=1937, data=range(16), transparent=True)
def bop_saplings(self, blockid, data):
    if data == 0: # Apple Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_apple.png")
    elif data == 1: # Yellow Autumn Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_yellowautumn.png")
    elif data == 2: # Bamboo Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_bamboo.png")
    elif data == 3: # Magic Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_magic.png")
    elif data == 4: # Dark Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_dark.png")
    elif data == 5: # Dying Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_dead.png")
    elif data == 6: # Fir Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_fir.png")
    elif data == 7: # Loftwood Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_holy.png")
    elif data == 8: # Orange Autumn Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_orangeautumn.png")
    elif data == 9: # Origin Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_origin.png")
    elif data == 10: # Pink Cherry Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_pinkcherry.png")
    elif data == 11: # Maple Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_maple.png")
    elif data == 12: # White Cherry Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_whitecherry.png")
    elif data == 13: # Hellbark Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_hellbark.png")
    elif data == 14: # Jacaranda Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_jacaranda.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_sprite(t)

# BoP: Colourized Saplins (I:"Colourized Sapling ID"=1938)
@material(blockid=1938, data=range(6), transparent=True)
def bop_saplings(self, blockid, data):
    if data == 0: # Acacia Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_acacia.png")
    elif data == 1: # Mangrove Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_mangrove.png")
    elif data == 2: # Palm Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_palm.png")
    elif data == 3: # Redwood Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_redwood.png")
    elif data == 4: # Willow Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_willow.png")
    elif data == 5: # Pine Sapling
        t = self.load_image_texture("textures/blocks/bop/sapling_pine.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_sprite(t)

# BoP: Ores and storage blocks (I:"Amethyst Ore ID"=1942)
@material(blockid=1942, data=range(16), solid=True)
def bop_ores(self, blockid, data):
    if data == 0: # Amethyst Ore
        t = self.load_image_texture("textures/blocks/bop/amethystore.png")
    elif data == 1: # Block of Amethyst
        t = self.load_image_texture("textures/blocks/bop/amethystblock.png")
    elif data == 2: # Ruby Ore
        t = self.load_image_texture("textures/blocks/bop/rubyore.png")
    elif data == 3: # Block of Ruby
        t = self.load_image_texture("textures/blocks/bop/rubyblock.png")
    elif data == 4: # Peridot Ore
        t = self.load_image_texture("textures/blocks/bop/peridotore.png")
    elif data == 5: # Block of Peridot
        t = self.load_image_texture("textures/blocks/bop/peridotblock.png")
    elif data == 6: # Topaz Ore
        t = self.load_image_texture("textures/blocks/bop/topazore.png")
    elif data == 7: # Block of Topaz
        t = self.load_image_texture("textures/blocks/bop/topazblock.png")
    elif data == 8: # Tanzanite Ore
        t = self.load_image_texture("textures/blocks/bop/tanzaniteore.png")
    elif data == 9: # Block of Tanzanite
        t = self.load_image_texture("textures/blocks/bop/tanzaniteblock.png")
    elif data == 10: # Apatite Ore
        t = self.load_image_texture("textures/blocks/bop/apatiteore.png")
    elif data == 11: # Block of Apatite
        t = self.load_image_texture("textures/blocks/bop/apatiteblock.png")
    elif data == 12: # Sapphire Ore
        t = self.load_image_texture("textures/blocks/bop/sapphireore.png")
    elif data == 13: # Block of Sapphire
        t = self.load_image_texture("textures/blocks/bop/sapphireblock.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Ivy (I:"Ivy ID"=1943)
@material(blockid=1943, data=range(16), transparent=True)
def bop_ivy(self, blockid, data):
    # rotation
    # vines data is bit coded. decode it first.
    # NOTE: the directions used in this function are the new ones used
    # in minecraft 1.0.0, no the ones used by overviewer
    # (i.e. north is top-left by defalut)

    # rotate the data by bitwise shift
    shifts = 0
    if self.rotation == 1:
        shifts = 1
    elif self.rotation == 2:
        shifts = 2
    elif self.rotation == 3:
        shifts = 3

    for i in range(shifts):
        data = data * 2
        if data & 16:
            data = (data - 16) | 1

    # decode data and prepare textures
    raw_texture = self.load_image_texture("textures/blocks/bop/ivy.png")
    s = w = n = e = None

    if data & 1: # south
        s = raw_texture
    if data & 2: # west
        w = raw_texture
    if data & 4: # north
        n = raw_texture
    if data & 8: # east
        e = raw_texture

    # texture generation
    img = self.build_full_block(None, n, e, w, s)

    return img

# BoP: Wood Planks (I:"Planks ID"=1947)
# BoP: Wood Double Slabs (I:"Wooden Double Slab 1 ID"=1948)
@material(blockid=[1947, 1948], data=range(16), solid=True)
def bop_planks(self, blockid, data):
    # Note: 1948:0 .. 1948:7 are the double slab variants
    if data == 0: # Acacia Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_acacia.png")
    elif data == 1: # Cherry Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_cherry.png")
    elif data == 2: # Dark Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_dark.png")
    elif data == 3: # Fir Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_fir.png")
    elif data == 4: # Loftwood Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_holy.png")
    elif data == 5: # Magic Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_magic.png")
    elif data == 6: # Mangrove Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_mangrove.png")
    elif data == 7: # Palm Wood Planks/Slab
        t = self.load_image_texture("textures/blocks/bop/plank_palm.png")
    elif data == 8: # Redwood Wood Planks
        t = self.load_image_texture("textures/blocks/bop/plank_redwood.png")
    elif data == 9: # Willow Wood Planks
        t = self.load_image_texture("textures/blocks/bop/plank_willow.png")
    elif data == 10: # Bamboo Thatching
        t = self.load_image_texture("textures/blocks/bop/bamboothatching.png")
    elif data == 11: # Pine Wood Planks
        t = self.load_image_texture("textures/blocks/bop/plank_pine.png")
    elif data == 12: # Hellbark Wood Planks
        t = self.load_image_texture("textures/blocks/bop/plank_hell_bark.png")
    elif data == 13: # Jacaranda Wood Planks
        t = self.load_image_texture("textures/blocks/bop/plank_jacaranda.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Wooden Slabs 1 (I:"Wooden Single Slab 1 ID"=1949)
@material(blockid=1949, data=range(16), solid=True)
def bop_woodsingleslabs1(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Acacia Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_acacia.png")
    elif texture == 1: # Cherry Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_cherry.png")
    elif texture == 2: # Dark Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_dark.png")
    elif texture == 3: # Fir Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_fir.png")
    elif texture == 4: # Loftwood Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_holy.png")
    elif texture == 5: # Magic Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_magic.png")
    elif texture == 6: # Mangrove Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_mangrove.png")
    elif texture == 7: # Palm Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_palm.png")

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# BoP: Wooden Double Slabs 2 (I:"Wooden Double Slab 2 ID"=1950)
@material(blockid=1950, data=range(16), solid=True)
def bop_wooddoubleslabs2(self, blockid, data):
    if data == 0: # Redwood Wood Slab
        t = self.load_image_texture("textures/blocks/bop/plank_redwood.png")
    elif data == 1: # Willow Wood Slab
        t = self.load_image_texture("textures/blocks/bop/plank_willow.png")
    elif data == 2: # Pine Wood Slab
        t = self.load_image_texture("textures/blocks/bop/plank_pine.png")
    elif data == 3: # Hellbark Wood Slab
        t = self.load_image_texture("textures/blocks/bop/plank_hell_bark.png")
    elif data == 4: # Jacaranda Wood Slab
        t = self.load_image_texture("textures/blocks/bop/plank_jacaranda.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)
    return self.build_block(t, t)

# BoP: Wooden Slabs 2 (I:"Wooden Single Slab 2 ID"=1951)
@material(blockid=1951, data=range(16), solid=True)
def bop_woodsingleslabs1(self, blockid, data):
    texture = data & 7 # Top bit indicates upper half slab
    if texture == 0: # Redwood Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_redwood.png")
    elif texture == 1: # Willow Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_willow.png")
    elif texture == 2: # Pine Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_pine.png")
    elif texture == 3: # Hellbark Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_hell_bark.png")
    elif texture == 4: # Jacaranda Wood Slab
        top = side = self.load_image_texture("textures/blocks/bop/plank_jacaranda.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
        return self.build_sprite(t)

    # cut the side texture in half
    mask = side.crop((0,8,16,16))
    side = Image.new(side.mode, side.size, self.bgcolor)
    alpha_over(side, mask, (0,0,16,8), mask)

    # plain slab
    top = self.transform_image_top(top)
    side = self.transform_image_side(side)
    otherside = side.transpose(Image.FLIP_LEFT_RIGHT)

    sidealpha = side.split()[3]
    side = ImageEnhance.Brightness(side).enhance(0.9)
    side.putalpha(sidealpha)
    othersidealpha = otherside.split()[3]
    otherside = ImageEnhance.Brightness(otherside).enhance(0.8)
    otherside.putalpha(othersidealpha)

    # upside down slab
    delta = 0
    if data & 8 == 8:
        delta = 6

    img = Image.new("RGBA", (24,24), self.bgcolor)
    alpha_over(img, side, (0,12 - delta), side)
    alpha_over(img, otherside, (12,12 - delta), otherside)
    alpha_over(img, top, (0,6 - delta), top)

    return img

# BoP: Leaves (I:"Colourized Leaves ID"=1962)
@material(blockid=1962, data=range(16), transparent=True, solid=True)
def bop_colourized_leaves(self, blockid, data):
    if data & 7 == 0: # Acacia Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_acacia_fancy.png")
    elif data & 7 == 1: # Mangrove Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_mangrove_fancy.png")
    elif data & 7 == 2: # Palm Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_palm_fancy.png")
    elif data & 7 == 3: # Redwood Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_redwood_fancy.png")
    elif data & 7 == 4: # Willow Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_willow_fancy.png")
    elif data & 7 == 5: # Pine Leaves
        t = self.load_image_texture("textures/blocks/bop/leaves_pine_fancy.png")
    else: # TODO any others?
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_block(t, t)

# BoP: Celestial Crystal (I:"Crystal ID"=1963)
block(blockid=1963, top_image="textures/blocks/bop/crystal.png")

# BoP: Cloud (I:"Cloud ID"=1964)
block(blockid=1964, top_image="textures/blocks/bop/cloud.png", transparent=True)

# BoP: Mushrooms (I:"Mushroom ID"=1967)
@material(blockid=1967, data=range(16), transparent=True)
def bop_mushrooms(self, blockid, data):
    if data == 0: # Toadstool
        t = self.load_image_texture("textures/blocks/bop/toadstool.png")
    elif data == 1: # Portobello
        t = self.load_image_texture("textures/blocks/bop/portobello.png")
    elif data == 2: # Blue Milk Cap
        t = self.load_image_texture("textures/blocks/bop/bluemilk.png")
    elif data == 3: # Glowshroom
        t = self.load_image_texture("textures/blocks/bop/glowshroom.png")
    else: # TODO
        t = self.load_image_texture("textures/blocks/web.png")
    return self.build_billboard(t)

# BoP: Spring Water (I:"Spring Water Still ID (ID before this must be free!)"=1971)
@material(blockid=1971, data=range(16), fluid=True, transparent=True, nospawn=True)
def bop_springwater(self, blockid, data):
    t = self.load_image_texture("textures/blocks/bop/spring_water_still.png")
    return self.build_block(t, t)

# BoP: Liquid Poison (I:"Liquid Poison Still ID (ID before this must be free!)"=1973)
@material(blockid=1973, data=range(16), fluid=True, transparent=True, nospawn=True)
def bop_poison(self, blockid, data):
    t = self.load_image_texture("textures/blocks/bop/liquid_poison_still.png")
    return self.build_block(t, t)

# BoP: Logs 4 (I:"Log Block ID 4"=1974)
@material(blockid=1974, data=range(16), solid=True)
def bop_log4(self, blockid, data):
    # extract orientation and wood type frorm data bits
    wood_type = data & 3
    wood_orientation = data & 12
    if self.rotation == 1:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    elif self.rotation == 3:
        if wood_orientation == 4: wood_orientation = 8
        elif wood_orientation == 8: wood_orientation = 4
    # choose textures
    if wood_type == 0: # Pine Wood
        side = self.load_image_texture("textures/blocks/bop/log_pine_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_pine_heart.png")
    elif wood_type == 1: # Hellbark Wood
        side = self.load_image_texture("textures/blocks/bop/log_hellbark_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_hellbark_heart.png")
    elif wood_type == 2: # Jacaranda Wood
        side = self.load_image_texture("textures/blocks/bop/log_jacaranda_side.png")
        top = self.load_image_texture("textures/blocks/bop/log_jacaranda_heart.png")
    else: # TODO any others?
        side = self.load_image_texture("textures/blocks/web.png")
        top = self.load_image_texture("textures/blocks/web.png")
    # choose orientation and paste textures
    if wood_orientation == 0:
        return self.build_block(top, side)
    elif wood_orientation == 4: # east-west orientation
        return self.build_full_block(side.rotate(90), None, None, top, side.rotate(90))
    elif wood_orientation == 8: # north-south orientation
        return self.build_full_block(side, None, None, side.rotate(270), top)

#    I:"Mud Brick Stairs ID"=1929
#    I:"Red Cobble Stairs ID"=1939
#    I:"Red Brick Stairs ID"=1940
#    I:"Acacia Stairs ID"=1952
#    I:"Cherry Stairs ID"=1953
#    I:"Dark Stairs ID"=1954
#    I:"Fir Stairs ID"=1955
#    I:"Holy Stairs ID"=1956
#    I:"Magic Stairs ID"=1957
#    I:"Mangrove Stairs ID"=1958
#    I:"Palm Stairs ID"=1959
#    I:"Redwood Stairs ID"=1960
#    I:"Willow Stairs ID"=1961
#    I:"Skystone Cobble Stairs ID"=1965
#    I:"Skystone Brick Stairs ID"=1966
#    I:"Pine Stairs ID"=1975
#    I:"Hell Bark Stairs ID"=1976
#    I:"Jacaranda ID"=1977
# BoP: Stairs
@material(blockid=[1929,1939,1940,1952,1953,1954,1955,1956,1957,1958,1959,1960,1961,1965,1966,1975,1976,1977], data=range(8), transparent=True, solid=True, nospawn=True)
def bop_stairs(self, blockid, data):

    # first, rotations
    # preserve the upside-down bit
    upside_down = data & 0x4
    data = data & 0x3
    if self.rotation == 1:
        if data == 0: data = 2
        elif data == 1: data = 3
        elif data == 2: data = 1
        elif data == 3: data = 0
    elif self.rotation == 2:
        if data == 0: data = 1
        elif data == 1: data = 0
        elif data == 2: data = 3
        elif data == 3: data = 2
    elif self.rotation == 3:
        if data == 0: data = 3
        elif data == 1: data = 2
        elif data == 2: data = 0
        elif data == 3: data = 1
    data = data | upside_down

    if blockid == 1929: # Mud Brick Stairs
        texture = self.load_image_texture("textures/blocks/bop/mudbrick.png")
    elif blockid == 1939: # Red Rock Cobblestone Stairs
        texture = self.load_image_texture("textures/blocks/bop/redcobble.png")
    elif blockid == 1940: # Red Rock Bricks Stairs
        texture = self.load_image_texture("textures/blocks/bop/redbrick.png")
    elif blockid == 1952: # Acacia Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_acacia.png")
    elif blockid == 1953: # Cherry Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_cherry.png")
    elif blockid == 1954: # Dark Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_dark.png")
    elif blockid == 1955: # Fir Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_fir.png")
    elif blockid == 1956: # Loftwood Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_holy.png")
    elif blockid == 1957: # Magic Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_magic.png")
    elif blockid == 1958: # Mangrove Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_mangrove.png")
    elif blockid == 1959: # Palm Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_palm.png")
    elif blockid == 1960: # Redwood Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_redwood.png")
    elif blockid == 1961: # Willow Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_willow.png")
    elif blockid == 1965: # Skystone Cobblestone Stairs
        texture = self.load_image_texture("textures/blocks/bop/holycobble.png")
    elif blockid == 1966: # Skystone Bricks Stairs
        texture = self.load_image_texture("textures/blocks/bop/holybrick.png")
    elif blockid == 1975: # Pine Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_pine.png")
    elif blockid == 1976: # Hellbark Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_hell_bark.png")
    elif blockid == 1977: # Jacaranda Wood Stairs
        texture = self.load_image_texture("textures/blocks/bop/plank_jacaranda.png")

    side = texture.copy()
    half_block_u = texture.copy() # up, down, left, right
    half_block_d = texture.copy()
    half_block_l = texture.copy()
    half_block_r = texture.copy()

    # generate needed geometries
    ImageDraw.Draw(side).rectangle((0,0,7,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_u).rectangle((0,8,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_d).rectangle((0,0,15,6),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_l).rectangle((8,0,15,15),outline=(0,0,0,0),fill=(0,0,0,0))
    ImageDraw.Draw(half_block_r).rectangle((0,0,7,15),outline=(0,0,0,0),fill=(0,0,0,0))

    if data & 0x4 == 0x4: # upside down stair
        side = side.transpose(Image.FLIP_TOP_BOTTOM)
        if data & 0x3 == 0: # ascending east
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, half_block_u, side.transpose(Image.FLIP_LEFT_RIGHT)))

        elif data & 0x3 == 0x1: # ascending west
            img = self.build_full_block(texture, None, None, texture, side)

        elif data & 0x3 == 0x2: # ascending south
            img = self.build_full_block(texture, None, None, side, texture)

        elif data & 0x3 == 0x3: # ascending north
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp = self.transform_image_side(half_block_d).transpose(Image.FLIP_LEFT_RIGHT)
            alpha_over(img, tmp, (6,3))
            alpha_over(img, self.build_full_block(texture, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_u))

    else: # normal stair
        if data == 0: # ascending east
            img = self.build_full_block(half_block_r, None, None, half_block_d, side.transpose(Image.FLIP_LEFT_RIGHT))
            tmp1 = self.transform_image_side(half_block_u)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.8)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) #workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_l)
            alpha_over(img, tmp2, (0,6))

        elif data == 1: # ascending west
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_r)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_l, None, None, texture, side)
            alpha_over(img, tmp2)

        elif data == 2: # ascending south
            img = Image.new("RGBA", (24,24), self.bgcolor) # first paste the texture in the back
            tmp1 = self.transform_image_top(half_block_u)
            alpha_over(img, tmp1, (0,6))
            tmp2 = self.build_full_block(half_block_d, None, None, side, texture)
            alpha_over(img, tmp2)

        elif data == 3: # ascending north
            img = self.build_full_block(half_block_u, None, None, side.transpose(Image.FLIP_LEFT_RIGHT), half_block_d)
            tmp1 = self.transform_image_side(half_block_u).transpose(Image.FLIP_LEFT_RIGHT)

            # Darken the vertical part of the second step
            sidealpha = tmp1.split()[3]
            # darken it a bit more than usual, looks better
            tmp1 = ImageEnhance.Brightness(tmp1).enhance(0.7)
            tmp1.putalpha(sidealpha)

            alpha_over(img, tmp1, (6,4)) # workaround, fixes a hole
            alpha_over(img, tmp1, (6,3))
            tmp2 = self.transform_image_top(half_block_d)
            alpha_over(img, tmp2, (0,6))

        # touch up a (horrible) pixel
        img.putpixel((18,3),(0,0,0,0))

    return img

# BoP: Moss (I:"Moss ID"=4095)
@material(blockid=4095, data=range(16), transparent=True)
def bop_moss(self, blockid, data):
    # rotation
    # vines data is bit coded. decode it first.
    # NOTE: the directions used in this function are the new ones used
    # in minecraft 1.0.0, no the ones used by overviewer
    # (i.e. north is top-left by defalut)

    # rotate the data by bitwise shift
    shifts = 0
    if self.rotation == 1:
        shifts = 1
    elif self.rotation == 2:
        shifts = 2
    elif self.rotation == 3:
        shifts = 3

    for i in range(shifts):
        data = data * 2
        if data & 16:
            data = (data - 16) | 1

    # decode data and prepare textures
    raw_texture = self.load_image_texture("textures/blocks/bop/moss.png")
    s = w = n = e = None

    if data & 1: # south
        s = raw_texture
    if data & 2: # west
        w = raw_texture
    if data & 4: # north
        n = raw_texture
    if data & 8: # east
        e = raw_texture

    # texture generation
    img = self.build_full_block(None, n, e, w, s)

    return img
