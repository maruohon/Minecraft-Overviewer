/* 
 * This file is part of the Minecraft Overviewer.
 *
 * Minecraft Overviewer is free software: you can redistribute it and/or
 * modify it under the terms of the GNU General Public License as published
 * by the Free Software Foundation, either version 3 of the License, or (at
 * your option) any later version.
 *
 * Minecraft Overviewer is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
 * Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with the Overviewer.  If not, see <http://www.gnu.org/licenses/>.
 */

#include "../overviewer.h"
#include "biomes.h"

typedef struct {
    int use_biomes;
    /* grasscolor and foliagecolor lookup tables */
    PyObject *grasscolor, *foliagecolor, *watercolor;
    /* biome-compatible grass/leaf textures */
    PyObject *grass_texture;
} PrimitiveBase;


static int
base_start(void *data, RenderState *state, PyObject *support) {
    PrimitiveBase *self = (PrimitiveBase *)data;
    
    if (!render_mode_parse_option(support, "biomes", "i", &(self->use_biomes)))
        return 1;
    
    /* biome-compliant grass mask (includes sides!) */
    self->grass_texture = PyObject_GetAttrString(state->textures, "biome_grass_texture");
    
    /* color lookup tables */
    self->foliagecolor = PyObject_CallMethod(state->textures, "load_foliage_color", "");
    self->grasscolor = PyObject_CallMethod(state->textures, "load_grass_color", "");
    self->watercolor = PyObject_CallMethod(state->textures, "load_water_color", "");
    
    return 0;
}

static void
base_finish(void *data, RenderState *state) {
    PrimitiveBase *self = (PrimitiveBase *)data;
    
    Py_DECREF(self->foliagecolor);
    Py_DECREF(self->grasscolor);
    Py_DECREF(self->watercolor);
    Py_DECREF(self->grass_texture);
}

static int
base_occluded(void *data, RenderState *state, int x, int y, int z) {
    if ( (x != 0) && (y != 15) && (z != 15) &&
         !render_mode_hidden(state->rendermode, x-1, y, z) &&
         !render_mode_hidden(state->rendermode, x, y, z+1) &&
         !render_mode_hidden(state->rendermode, x, y+1, z) &&
         !is_transparent(getArrayShort3D(state->blocks, x-1, y, z)) &&
         !is_transparent(getArrayShort3D(state->blocks, x, y, z+1)) &&
         !is_transparent(getArrayShort3D(state->blocks, x, y+1, z))) {
        return 1;
    }

    return 0;
}

unsigned int bop_get_block_color(unsigned char biome, unsigned char block_type)
{
    unsigned int foliage_color = 0;
    unsigned int grass_color = 0;
    unsigned int water_color = 0;

    switch(biome) {
        case 42: /* I:"Alps Forest (Sub-Biome) ID"=42 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 170: /* I:"Alps ID"=170 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 43: /* I:"Alps Mountainside (Sub-Biome) ID"=43 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 171: /* I:"Arctic ID"=171 */
            foliage_color = 11903827;
            grass_color = 11176526;
            water_color = 0;
            break;
        case 172: /* I:"Badlands ID"=172 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 173: /* I:"Bamboo Forest ID"=173 */
            foliage_color = 10739795;
            grass_color = 10739795;
            water_color = 0;
            break;
        case 174: /* I:"Bayou ID"=174 */
            foliage_color = 11591816;
            grass_color = 9154411;
            water_color = 16767282;
            break;
        case 175: /* I:"Birch Forest ID"=175 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 64: /* I:"Blessed Bog (Promised Land) ID"=64 */
            /* FIXME is this BiomeGenPromisedLandPlains.java ? */
            foliage_color = 11266663;
            grass_color = 7925125;
            water_color = 0;
            break;
        case 176: /* I:"Bog ID"=176 */
            foliage_color = 14345593;
            grass_color = 14193503;
            water_color = 0;
            break;
        case 69: /* I:"Boneyard (Nether) ID"=69 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 177: /* I:"Boreal Forest ID"=177 */
            foliage_color = 13225573;
            grass_color = 10467185;
            water_color = 0;
            break;
        case 178: /* I:"Brushland ID"=178 */
            foliage_color = 11716223;
            grass_color = 13222271;
            water_color = 0;
            break;
        case 179: /* I:"Canyon ID"=179 */
            foliage_color = 11123300;
            grass_color = 11123300;
            water_color = 0;
            break;
        case 49: /* I:"Canyon Ravine (Sub-Biome) ID"=49 */
            foliage_color = 11123300;
            grass_color = 11123300;
            water_color = 0;
            break;
        case 180: /* I:"Chaparral ID"=180 */
            foliage_color = 0;
            grass_color = 12638301;
            water_color = 0;
            break;
        case 181: /* I:"Cherry Blossom Grove ID"=181 */
            foliage_color = 10747818;
            grass_color = 10747818;
            water_color = 0;
            break;
        case 183: /* I:"Coniferous Forest (Snow) ID"=183 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 182: /* I:"Coniferous Forest ID"=182 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 58: /* I:"Coral Reef (Ocean) ID"=58 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 67: /* I:"Corrupted Sands (Nether) ID"=67 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 184: /* I:"Crag ID"=184 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 944693;
            break;
        case 186: /* I:"Dead Forest (Snow) ID"=186 */
            foliage_color = 11903827;
            grass_color = 11176526;
            water_color = 0;
            break;
        case 185: /* I:"Dead Forest ID"=185 */
            foliage_color = 12362085;
            grass_color = 12362085;
            water_color = 0;
            break;
        case 187: /* I:"Dead Swamp ID"=187 */
            foliage_color = 6713420;
            grass_color = 6713420;
            water_color = 10661201;
            break;
        case 188: /* I:"Deadlands ID"=188 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 16711680;
            break;
        case 189: /* I:"Deciduous Forest ID"=189 */
            foliage_color = 12896570;
            grass_color = 12695369;
            water_color = 0;
            break;
        case 249: /* I:"Desert (New) ID"=249 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 190: /* I:"Dunes ID"=190 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 253: /* I:"Extreme Hills (New) ID"=253 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 191: /* I:"Fen ID"=191 */
            foliage_color = 13547897;
            grass_color = 12240001;
            water_color = 0;
            break;
        case 192: /* I:"Field ID"=192 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 250: /* I:"Forest (New) ID"=250 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 40: /* I:"Forested Field (Sub-Biome) ID"=40 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 193: /* I:"Frost Forest ID"=193 */
            foliage_color = 11261628;
            grass_color = 11261628;
            water_color = 0;
            break;
        case 194: /* I:"Fungi Forest ID"=194 */
            foliage_color = 5359235;
            grass_color = 5359235;
            water_color = 65326;
            break;
        case 195: /* I:"Garden ID"=195 */
            foliage_color = 6742630;
            grass_color = 7656308;
            water_color = 0;
            break;
        case 196: /* I:"Glacier ID"=196 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 197: /* I:"Grassland ID"=197 */
            foliage_color = 8379261;
            grass_color = 8379261;
            water_color = 0;
            break;
        case 60: /* I:"Gravel Beach ID"=60 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 198: /* I:"Grove ID"=198 */
            foliage_color = 6396257;
            grass_color = 5341009;
            water_color = 0;
            break;
        case 199: /* I:"Heathland ID"=199 */
            foliage_color = 11454081;
            grass_color = 13550967;
            water_color = 0;
            break;
        case 200: /* I:"Highland ID"=200 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 201: /* I:"Hot Springs ID"=201 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 202: /* I:"Icy Hills ID"=202 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 203: /* I:"Jade Cliffs ID"=203 */
            foliage_color = 9096298;
            grass_color = 8168808;
            water_color = 0;
            break;
        case 254: /* I:"Jungle (New) ID"=254 */
            foliage_color = 7060540;
            grass_color = 6463547;
            water_color = 5242687; /* 10745289 ?? */
            break;
        case 59: /* I:"Kelp Forest (Ocean) ID"=59 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 204: /* I:"Lush Desert ID"=204 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 205: /* I:"Lush Swamp ID"=205 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 63: /* I:"Majestic Meadow (Promised Land) ID"=63 */
            /* TODO verify this, is it BiomeGenPromisedLandForest.java */
            foliage_color = 7925125;
            grass_color = 7925125;
            water_color = 0;
            break;
        case 206: /* I:"Mangrove ID"=206 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 210: /* I:"Maple Woods ID"=210 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 211: /* I:"Marsh ID"=211 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 50: /* I:"Meadow Forest (Sub-Biome) ID"=50 */
            foliage_color = 6533741;
            grass_color = 6533741;
            water_color = 0;
            break;
        case 212: /* I:"Meadow ID"=212 */
            foliage_color = 6533741;
            grass_color = 6533741;
            water_color = 0;
            break;
        case 213: /* I:"Mesa ID"=213 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 214: /* I:"Moor ID"=214 */
            foliage_color = 6394725;
            grass_color = 6394725;
            water_color = 5800566;
            break;
        case 215: /* I:"Mountain ID"=215 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 216: /* I:"Mystic Grove ID"=216 */
            foliage_color = 7332553;
            grass_color = 6934491;
            water_color = 15349914;
            break;
        case 65: /* I:"Nether Base (Nether) ID"=65 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 217: /* I:"Oasis ID"=217 */
            foliage_color = 0; /* FIXME no colors ??? */
            grass_color = 0;
            water_color = 0;
            break;
        case 218: /* I:"Ominous Woods ID"=218 */
            foliage_color = 4145489;
            grass_color = 4145489;
            water_color = 1973030;
            break;
        case 219: /* I:"Orchard ID"=219 */
            foliage_color = 14024557;
            grass_color = 14024557;
            water_color = 0;
            break;
        case 220: /* I:"Origin Valley ID"=220 */
            foliage_color = 3866368;
            grass_color = 10682207;
            water_color = 0;
            break;
        case 221: /* I:"Outback ID"=221 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 61: /* I:"Overgrown Beach ID"=61 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 222: /* I:"Pasture ID"=222 */
            foliage_color = 13166666;
            grass_color = 13166666;
            water_color = 0;
            break;
        case 46: /* I:"Pasture Meadow (Sub-Biome) ID"=46 */
            foliage_color = 13166666;
            grass_color = 13166666;
            water_color = 0;
            break;
        case 68: /* I:"Phantasmagoric Inferno (Nether) ID"=68 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 248: /* I:"Plains (New) ID"=248 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 223: /* I:"Polar ID"=223 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 3685739;
            break;
        case 224: /* I:"Prairie ID"=224 */
            foliage_color = 11395195;
            grass_color = 13165952;
            water_color = 0;
            break;
        case 225: /* I:"Quagmire ID"=225 */
            foliage_color = 10390377;
            grass_color = 10390377;
            water_color = 13390080;
            break;
        case 226: /* I:"Rainforest ID"=226 */
            foliage_color = 1368687;
            grass_color = 1759340;
            water_color = 0;
            break;
        case 227: /* I:"Redwood Forest ID"=227 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 228: /* I:"Sacred Springs ID"=228 */
            foliage_color = 39259;
            grass_color = 39259;
            water_color = 0;
            break;
        case 229: /* I:"Savanna ID"=229 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 39: /* I:"Savanna Plateau (Sub-Biome) ID"=39 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 230: /* I:"Scrubland ID"=230 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 231: /* I:"Seasonal Forest ID"=231 */
            foliage_color = 11781186;
            grass_color = 12502092;
            water_color = 0;
            break;
        case 41: /* I:"Seasonal Spruce Forest (Sub-Biome) ID"=41 */
            foliage_color = 11781186;
            grass_color = 12502092;
            water_color = 0;
            break;
        case 232: /* I:"Shield ID"=232 */
            foliage_color = 7902787;
            grass_color = 6586168;
            water_color = 0;
            break;
        case 233: /* I:"Shore ID"=233 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 234: /* I:"Shrubland ID"=234 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 235: /* I:"Sludgepit ID"=235 */
            foliage_color = 9539892;
            grass_color = 7627817;
            water_color = 11506176;
            break;
        case 236: /* I:"Spruce Woods ID"=236 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 237: /* I:"Steppe ID"=237 */
            foliage_color = 13413215;
            grass_color = 13413215;
            water_color = 0;
            break;
        case 252: /* I:"Swampland (New) ID"=252 */
/* FIXME
                double var1 = this.getFloatTemperature();
                double var3 = this.getFloatRainfall();
                return ((ColorizerGrass.getGrassColor(var1, var3) & 16711422) + 5115470) / 2
                double var1 = this.getFloatTemperature();
                double var3 = this.getFloatRainfall();
                return ((ColorizerFoliage.getFoliageColor(var1, var3) & 16711422) + 5115470) / 2;
*/
            foliage_color = 0;
            grass_color = 0;
            water_color = 14745456;
            break;
        case 251: /* I:"Taiga (New) ID"=251 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 238: /* I:"Temperate Rainforest ID"=238 */
            foliage_color = 12311907;
            grass_color = 11981671;
            water_color = 0;
            break;
        case 47: /* I:"Thick Ominous Woods (Sub-Biome) ID"=47 */
            foliage_color = 4145489;
            grass_color = 4145489;
            water_color = 1973030;
            break;
        case 48: /* I:"Thick Shrubland (Sub-Biome) ID"=48 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 239: /* I:"Thicket ID"=239 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 45: /* I:"Thinned Pasture (Sub-Biome) ID"=45 */
            foliage_color = 13166666;
            grass_color = 13166666;
            water_color = 0;
            break;
        case 44: /* I:"Thinned Timber (Sub-Biome) ID"=44 */
            foliage_color = 11049817;
            grass_color = 10923366;
            water_color = 0;
            break;
        case 240: /* I:"Timber ID"=240 */
            foliage_color = 11049817;
            grass_color = 10923366;
            water_color = 0;
            break;
        case 241: /* I:"Tropical Rainforest ID"=241 */
            foliage_color = 8970560;
            grass_color = 11002176;
            water_color = 6160128;
            break;
        case 242: /* I:"Tropics ID"=242 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 243: /* I:"Tundra ID"=243 */
            foliage_color = 12543566;
            grass_color = 11371606;
            water_color = 0;
            break;
        case 66: /* I:"Undergarden (Nether) ID"=66 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 244: /* I:"Volcano ID"=244 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;
        case 245: /* I:"Wasteland ID"=245 */
            foliage_color = 10067541;
            grass_color = 10330232;
            water_color = 15073024;
            break;
        case 246: /* I:"Wetland ID"=246 */
            foliage_color = 5215831;
            grass_color = 5935967;
            water_color = 6512772;
            break;
        case 62: /* I:"Wonderous Woods (Promised Land) ID"=62 */
            /* FIXME is this BiomeGenPromisedLandSwamp.java ? */
            foliage_color = 4583331;
            grass_color = 7925125;
            water_color = 0;
            break;
        case 247: /* I:"Woodland ID"=247 */
            foliage_color = 0;
            grass_color = 0;
            water_color = 0;
            break;

        default: /* Unknown biome */
            break;
    }

    if (block_type == 1) {
        return water_color;
    }
    else if (block_type == 2) {
        return foliage_color;
    }
    else if (block_type == 3) {
        return grass_color;
    }

    return 0;
}

static void
base_draw(void *data, RenderState *state, PyObject *src, PyObject *mask, PyObject *mask_light) {
    PrimitiveBase *self = (PrimitiveBase *)data;

    /* draw the block! */
    alpha_over(state->img, src, mask, state->imgx, state->imgy, 0, 0);
    
    /* check for biome-compatible blocks
     *
     * NOTES for maintainers:
     *
     * To add a biome-compatible block, add an OR'd condition to this
     * following if block, and a case to the switch statement to handle biome
     * coloring.
     *
     * Make sure that in textures.py, the generated textures are the
     * biome-compliant ones! The tinting is now all done here.
     */
    if (/* grass, but not snowgrass */
        (state->block == 2 && get_data(state, BLOCKS, state->x, state->y+1, state->z) != 78) ||
        /* water */
        state->block == 8 || state->block == 9 ||
        /* leaves */
        state->block == 18 ||
        /* tallgrass, but not dead shrubs */
        (state->block == 31 && state->block_data != 0) ||
        /* pumpkin/melon stem, not fully grown. Fully grown stems
         * get constant brown color (see textures.py) */
        (((state->block == 104) || (state->block == 105)) && (state->block_data != 7)) ||
        /* vines */
        state->block == 106 ||
        /* lily pads */
        state->block == 111 ||

        /* IC2: Rubber Tree Leaves (242:0) */
        state->block == 242 ||
        /* BoP: Tall grass-like stuff (I:"Foliage ID"=1925) */
        state->block == 1925 ||
        /* BoP: Tree Moss (I:"Tree Moss ID"=1932) */
        state->block == 1932 ||
        /* BoP: Ivy (I:"Ivy ID"=1943) */
        state->block == 1943 ||
        /* BoP: Leaves (I:"Colourized Leaves ID"=1962) */
        state->block == 1962 ||
        /* BoP: Moss (I:"Moss ID"=4095) */
        state->block == 4095 ||
        /* Thaumcraft: Greatwood Leaves (I:BlockMagicalLeaves=2405) */
        (state->block == 2405 && (state->block_data & 7) == 0) ||
        /* Natura: Leaves */
        (state->block == 3259 &&
            ((state->block_data & 7) == 0 || /* Redwood Leaves */
            (state->block_data & 7) == 1 || /* Eucalyptus Leaves */
            (state->block_data & 7) == 2)) /* Hopseed Leaves */
        )
    {
        /* do the biome stuff! */
        PyObject *facemask = mask;
        unsigned char r = 255, g = 255, b = 255;
        PyObject *color_table = NULL;
        unsigned char flip_xy = 0;
        unsigned char block_type = 0; /* store the block coloring type (water/grass/foliage) */
        
        switch (state->block) {
        case 8:
        case 9:
            /* water */
            color_table = self->watercolor;
            block_type = 1; /* type: water */
            break;

        case 18: /* leaves */
            if (state->block_data == 2) /* birch */
            {
                /* birch foliage color is flipped XY-ways */
                flip_xy = 1;
            }
        case 242: /* IC2: Rubber Tree Leaves (242:0) */
        case 1932: /* BoP: Tree Moss (I:"Tree Moss ID"=1932) */
        case 1962: /* BoP: Leaves (I:"Colourized Leaves ID"=1962) */
        case 2405: /* Thaumcraft: Greatwood Leaves (I:BlockMagicalLeaves=2405) */
        case 3259: /* Natura: Leaves */
        case 4095: /* BoP: Moss (I:"Moss ID"=4095) */
            color_table = self->foliagecolor;
            block_type = 2; /* type: foliage */
            break;

        case 2: /* grass */
            /* grass needs a special facemask */
            facemask = self->grass_texture;
        case 31: /* tall grass */
        case 104: /* pumpkin stem */
        case 105: /* melon stem */
        case 106: /* vines */
        case 111: /* lily pads */

        case 1925: /* BoP: Tall grass-like stuff (I:"Foliage ID"=1925) */
        case 1943: /* BoP: Ivy (I:"Ivy ID"=1943) */
            color_table = self->grasscolor;
            block_type = 3; /* type: grass */
            break;

        default:
            break;
        };

        if (color_table) {
            unsigned char biome;
            int dx, dz;
            unsigned char tablex, tabley;
            float temp = 0.0, rain = 0.0;
            unsigned int multr = 0, multg = 0, multb = 0;
            int tmp;
            float num_vanilla = 0.0;
            unsigned int num_bop = 0;
            unsigned int bop_tmp;
            unsigned int bop_r = 255, bop_g = 255, bop_b = 255;
            PyObject *color = NULL;
            
            if (self->use_biomes) {
                /* reset the biome counters for the biome color averaging */
                num_vanilla = 0.0;
                num_bop = 0;
                bop_r = bop_g = bop_b = 0;
                /* average over all neighbors */
                for (dx = -1; dx <= 1; dx++) {
                    for (dz = -1; dz <= 1; dz++) {
                        biome = get_data(state, BIOMES, state->x + dx, state->y, state->z + dz);
                        bop_tmp = 0;

                        /* Biomes O' Plenty biome */
                        if (biome >= NUM_BIOMES && biome < 255) {
                            bop_tmp = bop_get_block_color(biome, block_type);

                            /* A custom color was defined */
                            if (bop_tmp != 0) {
                                bop_r += (bop_tmp & 0xff0000) >> 16;
                                bop_g += (bop_tmp & 0x00ff00) >> 8;
                                bop_b += (bop_tmp & 0x0000ff);
                                num_bop++;
                            }
                        }
                        /* Vanilla biome, map border or BoP biome with no custom color defined */
                        if (bop_tmp == 0) {
                            /* note -- biome 255 shows up on map borders.
                               who knows what it is? certainly not I. */
                            /* Map border or BoP biome with no custom color defined */
                            if (biome >= NUM_BIOMES) {
                                biome = DEFAULT_BIOME; /* forest -- reasonable default */
                            }
                            temp += biome_table[biome].temperature;
                            rain += biome_table[biome].rainfall;
                            multr += biome_table[biome].r;
                            multg += biome_table[biome].g;
                            multb += biome_table[biome].b;
                            num_vanilla += 1.0;
                        }
                    }
                }
                if (num_vanilla > 0) {
                    temp /= num_vanilla;
                    rain /= num_vanilla;
                    multr /= num_vanilla;
                    multg /= num_vanilla;
                    multb /= num_vanilla;
                }
            } else {
                /* don't use biomes, just use the default */
                temp = biome_table[DEFAULT_BIOME].temperature;
                rain = biome_table[DEFAULT_BIOME].rainfall;
                multr = biome_table[DEFAULT_BIOME].r;
                multg = biome_table[DEFAULT_BIOME].g;
                multb = biome_table[DEFAULT_BIOME].b;
            }

            /* second coordinate is actually scaled to fit inside the triangle
               so store it in rain */
            rain *= temp;
            
            /* make sure they're sane */
            temp = CLAMP(temp, 0.0, 1.0);
            rain = CLAMP(rain, 0.0, 1.0);
            
            /* convert to x/y coordinates in color table */
            tablex = 255 - (255 * temp);
            tabley = 255 - (255 * rain);
            if (flip_xy) {
                unsigned char tmp = 255 - tablex;
                tablex = 255 - tabley;
                tabley = tmp;
            }

            /* look up color! */
            color = PySequence_GetItem(color_table, tabley * 256 + tablex);
            r = PyInt_AsLong(PyTuple_GET_ITEM(color, 0));
            g = PyInt_AsLong(PyTuple_GET_ITEM(color, 1));
            b = PyInt_AsLong(PyTuple_GET_ITEM(color, 2));
            Py_DECREF(color);
            
            /* do the after-coloration */
            r = MULDIV255(r, multr, tmp);
            g = MULDIV255(g, multg, tmp);
            b = MULDIV255(b, multb, tmp);

            /* Biomes O' Plenty biome, or some of the neighbouring blocks are */
            if (num_bop > 0) {
                bop_r += ((unsigned int)r * (unsigned int)num_vanilla);
                bop_g += ((unsigned int)g * (unsigned int)num_vanilla);
                bop_b += ((unsigned int)b * (unsigned int)num_vanilla);
                r = bop_r / 9;
                g = bop_g / 9;
                b = bop_b / 9;
            }
        }
        
        /* final coloration */
        tint_with_mask(state->img, r, g, b, 255, facemask, state->imgx, state->imgy, 0, 0);
    }
}

RenderPrimitiveInterface primitive_base = {
    "base", sizeof(PrimitiveBase),
    base_start,
    base_finish,
    base_occluded,
    NULL,
    base_draw,
};
