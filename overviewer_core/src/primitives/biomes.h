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


#define DEFAULT_BIOME 4 /* forest, nice and green */

typedef struct {
    const char* name;

    float temperature;
    float rainfall;

    unsigned int grasscolor, foliagecolor, watercolor;
} Biome;

/* each entry in this table is yanked *directly* out of the minecraft source
 * temp/rainfall are taken from what MCP calls setTemperatureRainfall
 *
 * Some biomes, like Swamp, do a bit of post-processing by multiplying on a
 * hard-coded color. The RGB tuple used follows the temp/rainfall.
 * 255, 255, 255 is white, which means do nothing
 *
 * keep in mind the x/y coordinate in the color tables is found *after*
 * multiplying rainfall and temperature for the second coordinate, *and* the
 * origin is in the lower-right. <3 biomes.
 */
static Biome biome_table[] = {
    /* 0 */
    {"Ocean", 0.5, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Plains", 0.8, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Desert", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Extreme Hills", 0.2, 0.3, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Forest", 0.7, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    /* 5 */
    {"Taiga", 0.05, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Swampland", 0.8, 0.9, 6975545, 6975545, 0xFFFFFF},
    {"River", 0.5, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Hell", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Sky", 0.5, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    /* 10 */
    {"FrozenOcean", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"FrozenRiver", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Ice Plains", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Ice Mountains", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"MushroomIsland", 0.9, 1.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    /* 15 */
    {"MushroomIslandShore", 0.9, 1.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Beach", 0.8, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"DesertHills", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"ForestHills", 0.7, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"TaigaHills", 0.05, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    /* 20 */
    {"Extreme Hills Edge", 0.2, 0.3, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
     /* Values below are guesses */
    {"Jungle", 2.0, 0.45, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Jungle Hills", 2.0, 0.45, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},

    /* Start of non-vanilla biomes */
    /* name, temperature, rainfall, grassColor, foliageColor, waterColorMultiplier */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 25 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Sublime Shrubland (Promised Land)", 2.0, 2.0, 7925125, 7925125, 0xFFFFFF},                /* BoP: I:"Sublime Shrubland (Promised Land) ID"=28 ; BiomeGenPromisedLandShrub */
    {"Thinned Mystic Grove (Sub-Biome)", 0.9, 1.0, 6934491, 7397529, 16715898},                 /* BoP: I:"Thinned Mystic Grove (Sub-Biome) ID"=29 ; BiomeGenMysticGroveThin */
    {"Bloody Heap (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},               /* 30 */    /* BoP: I:"Bloody Heap (Nether) ID"=30 ; BiomeGenNetherBlood */
    {"Lavender Fields", 0.6, 0.7, 10601325, 10601325, 0xFFFFFF},                                /* BoP: I:"Lavender Fields ID"=31 ; BiomeGenLavenderFields */
    {"Tropics Mountain (Sub-Biome)", 2.0, 2.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                   /* BoP: I:"Tropics Mountain (Sub-Biome) ID"=32 ; BiomeGenTropics */
    {"Autumn Hills", 0.5, 0.2, 12233056, 12897365, 0xFFFFFF},                                   /* BoP: I:"Autumn Hills ID"=33 ; BiomeGenAutumnHills */
    {"Overgrown Greens", 0.8, 0.8, 11992926, 9174870, 0xFFFFFF},                                /* BoP: I:"Overgrown Greens ID"=34 ; BiomeGenOvergrownGreens */
    {"Forest Hills (Sub-Biome)", 0.7, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},           /* 35 */    /* BoP: I:"Forest Hills (Sub-Biome) ID"=35 ; BiomeGenForestNew */
    {"Taiga Hills (Sub-Biome)", 0.05, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* BoP: I:"Taiga Hills (Sub-Biome) ID"=36 ; BiomeGenTaigaNew */
    {"Jungle Hills (Sub-Biome)", 1.2, 0.9, 6463547, 7060540, 5242687},                          /* BoP: I:"Jungle Hills (Sub-Biome) ID"=37 ; BiomeGenJungleNew */
    {"Silkglades", 0.5, 0.9, 13420973, 14146486, 16777079},                                     /* BoP: I:"Silkglades ID"=38 ; BiomeGenSilkglades */
    {"Savanna Plateau (Sub-Biome)", 1.5, 0.1, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                    /* BoP: I:"Savanna Plateau (Sub-Biome) ID"=39 ; BiomeGenSavannaPlateau */
    {"Forested Field (Sub-Biome)", 0.6, 0.7, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},         /* 40 */    /* BoP: I:"Forested Field (Sub-Biome) ID"=40 ; BiomeGenFieldForest */
    {"Seasonal Spruce Forest (Sub-Biome)", 0.7, 0.8, 12502092, 11781186, 0xFFFFFF},             /* BoP: I:"Seasonal Spruce Forest (Sub-Biome) ID"=41 ; BiomeGenSeasonalSpruceForest */
    {"Alps Forest (Sub-Biome)", 0.5, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                        /* BoP: I:"Alps Forest (Sub-Biome) ID"=42 ; BiomeGenAlpsBase (!!) */
    {"Alps Mountainside (Sub-Biome)", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                  /* BoP: I:"Alps Mountainside (Sub-Biome) ID"=43 ; BiomeGenAlpsForest (!!) */
    {"Thinned Timber (Sub-Biome)", 0.7, 0.8, 10923366, 11049817, 0xFFFFFF},                     /* BoP: I:"Thinned Timber (Sub-Biome) ID"=44 ; BiomeGenTimberThin */
    {"Thinned Pasture (Sub-Biome)", 0.8, 0.4, 13166666, 13166666, 0xFFFFFF},        /* 45 */    /* BoP: I:"Thinned Pasture (Sub-Biome) ID"=45 ; BiomeGenPastureThin */
    {"Pasture Meadow (Sub-Biome)", 0.8, 0.4, 13166666, 13166666, 0xFFFFFF},                     /* BoP: I:"Pasture Meadow (Sub-Biome) ID"=46 ; BiomeGenPastureMeadow */
    {"Thick Ominous Woods (Sub-Biome)", 0.8, 0.9, 4145489, 4145489, 1973030},                   /* BoP: I:"Thick Ominous Woods (Sub-Biome) ID"=47 ; BiomeGenOminousWoodsThick */
    {"Thick Shrubland (Sub-Biome)", 0.6, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                   /* BoP: I:"Thick Shrubland (Sub-Biome) ID"=48 ; BiomeGenShrublandForest */
    {"Canyon Ravine (Sub-Biome)", 0.8, 0.4, 11123300, 11123300, 0xFFFFFF},                      /* BoP: I:"Canyon Ravine (Sub-Biome) ID"=49 ; BiomeGenCanyonRavine */
    {"Meadow Forest (Sub-Biome)", 0.7, 0.7, 6533741, 6533741, 0xFFFFFF},            /* 50 */    /* BoP: I:"Meadow Forest (Sub-Biome) ID"=50 ; BiomeGenMeadowForest */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 55 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Oceanic Abyss (Ocean)", 0.5, 0.9, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                          /* BoP: I:"Oceanic Abyss (Ocean) ID"=57 ; BiomeGenOceanAbyss */
    {"Coral Reef (Ocean)", 0.5, 0.9, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                             /* BoP: I:"Coral Reef (Ocean) ID"=58 ; BiomeGenOceanCoral */
    {"Kelp Forest (Ocean)", 0.5, 0.9, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                            /* BoP: I:"Kelp Forest (Ocean) ID"=59 ; BiomeGenOceanKelp */
    {"Gravel Beach", 0.2, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* 60 */    /* BoP: I:"Gravel Beach ID"=60 ; BiomeGenBeachGravel */
    {"Overgrown Beach", 0.8, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                /* BoP: I:"Overgrown Beach ID"=61 ; BiomeGenBeachOvergrown */
    {"Wonderous Woods (Promised Land)", 2.0, 2.0, 7925125, 7925125, 0xFFFFFF},                  /* BoP: I:"Wonderous Woods (Promised Land) ID"=62 ; BiomeGenPromisedLandForest */
    {"Majestic Meadow (Promised Land)", 2.0, 2.0, 7925125, 7925125, 0xFFFFFF},                  /* BoP: I:"Majestic Meadow (Promised Land) ID"=63 ; BiomeGenPromisedLandPlains */
    {"Blessed Bog (Promised Land)", 2.0, 2.0, 7925125, 7925125, 0xFFFFFF},                      /* BoP: I:"Blessed Bog (Promised Land) ID"=64 ; BiomeGenPromisedLandSwamp */
    {"Nether Base (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},               /* 65 */    /* BoP: I:"Nether Base (Nether) ID"=65 ; BiomeGenNetherBase */
    {"Undergarden (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                           /* BoP: I:"Undergarden (Nether) ID"=66 ; BiomeGenNetherGarden */
    {"Corrupted Sands (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* BoP: I:"Corrupted Sands (Nether) ID"=67 ; BiomeGenNetherDesert */
    {"Phantasmagoric Inferno (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                /* BoP: I:"Phantasmagoric Inferno (Nether) ID"=68 ; BiomeGenNetherLava */
    {"Boneyard (Nether)", 2.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                              /* BoP: I:"Boneyard (Nether) ID"=69 ; BiomeGenNetherBone */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 70 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 75 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 80 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 85 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 90 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 95 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 100 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 105 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 110 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 115 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 120 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 125 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 130 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 135 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 140 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 145 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 150 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 155 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 160 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},   /* 165 */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Alps", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                               /* 170 */   /* BoP: I:"Alps ID"=170 ; BiomeGenAlps */
    {"Arctic", 0.05, 0.5, 11176526, 11903827, 0xFFFFFF},                                        /* BoP: I:"Arctic ID"=171 ; BiomeGenArctic */
    {"Badlands", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                      /* BoP: I:"Badlands ID"=172 ; BiomeGenBadlands */
    {"Bamboo Forest", 1.2, 0.9, 10739795, 10739795, 0xFFFFFF},                                  /* BoP: I:"Bamboo Forest ID"=173 ; BiomeGenBambooForest */
    {"Bayou", 0.5, 0.9, 9154411, 11591816, 16767282},                                           /* BoP: I:"Bayou ID"=174 ; BiomeGenBayou */
    {"Birch Forest", 0.4, 0.3, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* 175 */   /* BoP: I:"Birch Forest ID"=175 ; BiomeGenBirchForest */
    {"Bog", 0.8, 0.9, 14193503, 14345593, 0xFFFFFF},                                            /* BoP: I:"Bog ID"=176 ; BiomeGenBog */
    {"Boreal Forest", 0.6, 0.7, 10467185, 13225573, 0xFFFFFF},                                  /* BoP: I:"Boreal Forest ID"=177 ; BiomeGenBorealForest */
    {"Brushland", 2.0, 0.05, 13222271, 11716223, 0xFFFFFF},                                     /* BoP: I:"Brushland ID"=178 ; BiomeGenBrushland */
    {"Canyon", 0.8, 0.4, 11123300, 11123300, 0xFFFFFF},                                         /* BoP: I:"Canyon ID"=179 ; BiomeGenCanyon */
    {"Chaparral", 0.8, 0.4, 12638301, 0xFFFFFF, 0xFFFFFF},                          /* 180 */   /* BoP: I:"Chaparral ID"=180 ; BiomeGenChaparral */
    {"Cherry Blossom Grove", 0.7, 0.8, 10747818, 10747818, 0xFFFFFF},                           /* BoP: I:"Cherry Blossom Grove ID"=181 ; BiomeGenCherryBlossomGrove */
    {"Coniferous Forest", 0.5, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                              /* BoP: I:"Coniferous Forest ID"=182 ; BiomeGenConiferousForest */
    {"Coniferous Forest (Snow)", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* BoP: I:"Coniferous Forest (Snow) ID"=183 ; BiomeGenConiferousForestSnow */
    {"Crag", 0.4, 0.2, 0xFFFFFF, 0xFFFFFF, 944693},                                             /* BoP: I:"Crag ID"=184 ; BiomeGenCrag */
    {"Dead Forest", 1.2, 0.1, 12362085, 12362085, 0xFFFFFF},                        /* 185 */   /* BoP: I:"Dead Forest ID"=185 ; BiomeGenDeadForest */
    {"Dead Forest (Snow)", 0.05, 0.8, 11176526, 11903827, 0xFFFFFF},                            /* BoP: I:"Dead Forest (Snow) ID"=186 ; BiomeGenDeadForestSnow */
    {"Dead Swamp", 0.8, 0.9, 6713420, 6713420, 10661201},                                       /* BoP: I:"Dead Swamp ID"=187 ; BiomeGenDeadSwamp */
    {"Deadlands", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 16711680},                                     /* BoP: I:"Deadlands ID"=188 ; BiomeGenDeadlands */
    {"Deciduous Forest", 0.7, 0.8, 12695369, 12896570, 0xFFFFFF},                               /* BoP: I:"Deciduous Forest ID"=189 ; BiomeGenDeciduousForest */
    {"Dunes", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                             /* 190 */   /* BoP: I:"Dunes ID"=190 ; BiomeGenDunes */
    {"Fen", 0.4, 0.4, 12240001, 13547897, 0xFFFFFF},                                            /* BoP: I:"Fen ID"=191 ; BiomeGenFen */
    {"Field", 0.6, 0.7, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                          /* BoP: I:"Field ID"=192 ; BiomeGenField */
    {"Frost Forest", 0.0, 0.5, 11261628, 11261628, 0xFFFFFF},                                   /* BoP: I:"Frost Forest ID"=193 ; BiomeGenFrostForest */
    {"Fungi Forest", 0.9, 1.0, 15792496, 11139946, 65326},                                      /* BoP: I:"Fungi Forest ID"=194 ; BiomeGenFungiForest */
    {"Garden", 0.7, 0.8, 7656308, 6742630, 0xFFFFFF},                               /* 195 */   /* BoP: I:"Garden ID"=195 ; BiomeGenGarden */
    {"Glacier", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                        /* BoP: I:"Glacier ID"=196 ; BiomeGenGlacier */
    {"Grassland", 0.7, 0.7, 8379261, 8379261, 0xFFFFFF},                                        /* BoP: I:"Grassland ID"=197 ; BiomeGenGrassland */
    {"Grove", 0.4, 0.8, 5341009, 6396257, 0xFFFFFF},                                            /* BoP: I:"Grove ID"=198 ; BiomeGenGrove */
    {"Heathland", 0.8, 0.1, 13550967, 11454081, 0xFFFFFF},                                      /* BoP: I:"Heathland ID"=199 ; BiomeGenHeathland */
    {"Highland", 0.5, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                           /* 200 */   /* BoP: I:"Highland ID"=200 ; BiomeGenHighland */
    {"Hot Springs", 0.5, 0.7, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                    /* BoP: I:"Hot Springs ID"=201 ; BiomeGenHotSprings */
    {"Icy Hills", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                      /* BoP: I:"Icy Hills ID"=202 ; BiomeGenIcyHills */
    {"Jade Cliffs", 0.5, 0.1, 8168808, 9096298, 0xFFFFFF},                                      /* BoP: I:"Jade Cliffs ID"=203 ; BiomeGenJadeCliffs */
    {"Lush Desert", 0.8, 0.2, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                    /* BoP: I:"Lush Desert ID"=204 ; BiomeGenLushDesert */
    {"Lush Swamp", 0.7, 1.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                         /* 205 */   /* BoP: I:"Lush Swamp ID"=205 ; BiomeGenLushSwamp */
    {"Mangrove", 0.8, 0.9, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                       /* BoP: I:"Mangrove ID"=206 ; BiomeGenMangrove */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},
    {"Maple Woods", 0.2, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                        /* 210 */   /* BoP: I:"Maple Woods ID"=210 ; BiomeGenMapleWoods */
    {"Marsh", 0.5, 0.9, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                          /* BoP: I:"Marsh ID"=211 ; BiomeGenMarsh */
    {"Meadow", 0.7, 0.7, 6533741, 6533741, 0xFFFFFF},                                           /* BoP: I:"Meadow ID"=212 ; BiomeGenMeadow */
    {"Mesa", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                          /* BoP: I:"Mesa ID"=213 ; BiomeGenMesa */
    {"Moor", 0.5, 1.0, 6394725, 6394725, 5800566},                                              /* BoP: I:"Moor ID"=214 ; BiomeGenMoor */
    {"Mountain", 0.5, 0.1, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                           /* 215 */   /* BoP: I:"Mountain ID"=215 ; BiomeGenMountain */
    {"Mystic Grove", 0.9, 1.0, 6934491, 7397529, 16715898},                                     /* BoP: I:"Mystic Grove ID"=216 ; BiomeGenMysticGrove */
    {"Oasis", 0.9, 0.7, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                          /* BoP: I:"Oasis ID"=217 ; BiomeGenOasis */
    {"Ominous Woods", 0.8, 0.9, 4145489, 4145489, 1973030},                                     /* BoP: I:"Ominous Woods ID"=218 ; BiomeGenOminousWoods */
    {"Orchard", 0.8, 0.4, 14024557, 14024557, 0xFFFFFF},                                        /* BoP: I:"Orchard ID"=219 ; BiomeGenOrchard */
    {"Origin Valley", 0.7, 0.8, 10682207, 3866368, 0xFFFFFF},                       /* 220 */   /* BoP: I:"Origin Valley ID"=220 ; BiomeGenOriginValley */
    {"Outback", 0.8, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                       /* BoP: I:"Outback ID"=221 ; BiomeGenOutback */
    {"Pasture", 0.8, 0.4, 13166666, 13166666, 0xFFFFFF},                                        /* BoP: I:"Pasture ID"=222 ; BiomeGenPasture */
    {"Polar", 0.0, 0.5, 0xFFFFFF, 0xFFFFFF, 3685739},                                           /* BoP: I:"Polar ID"=223 ; BiomeGenPolar */
    {"Prairie", 0.9, 0.6, 13165952, 11395195, 0xFFFFFF},                                        /* BoP: I:"Prairie ID"=224 ; BiomeGenPrairie */
    {"Quagmire", 0.8, 0.9, 10390377, 10390377, 13390080},                           /* 225 */   /* BoP: I:"Quagmire ID"=225 ; BiomeGenQuagmire */
    {"Rainforest", 2.0, 2.0, 1759340, 1368687, 0xFFFFFF},                                       /* BoP: I:"Rainforest ID"=226 ; BiomeGenRainforest */
    {"Redwood Forest", 0.8, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                 /* BoP: I:"Redwood Forest ID"=227 ; BiomeGenRedwoodForest */
    {"Sacred Springs", 1.2, 0.9, 39259, 39259, 0xFFFFFF},                                       /* BoP: I:"Sacred Springs ID"=228 ; BiomeGenSacredSprings */
    {"Savanna", 1.5, 0.1, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                        /* BoP: I:"Savanna ID"=229 ; BiomeGenSavanna */
    {"Scrubland", 1.2, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                         /* 230 */   /* BoP: I:"Scrubland ID"=230 ; BiomeGenScrubland */
    {"Seasonal Forest", 0.7, 0.8, 12502092, 11781186, 0xFFFFFF},                                /* BoP: I:"Seasonal Forest ID"=231 ; BiomeGenSeasonalForest */
    {"Shield", 0.5, 0.8, 6586168, 7902787, 0xFFFFFF},                                           /* BoP: I:"Shield ID"=232 ; BiomeGenShield */
    {"Shore", 0.8, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                          /* BoP: I:"Shore ID"=233 ; BiomeGenShore */
    {"Shrubland", 0.6, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                     /* BoP: I:"Shrubland ID"=234 ; BiomeGenShrubland */
    {"Sludgepit", 0.8, 0.9, 7627817, 9539892, 11506176},                            /* 235 */   /* BoP: I:"Sludgepit ID"=235 ; BiomeGenSludgepit */
    {"Spruce Woods", 0.6, 0.7, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                   /* BoP: I:"Spruce Woods ID"=236 ; BiomeGenSpruceWoods */
    {"Steppe", 2.0, 0.05, 13413215, 13413215, 0xFFFFFF},                                        /* BoP: I:"Steppe ID"=237 ; BiomeGenSteppe */
    {"Temperate Rainforest", 0.7, 0.8, 11981671, 12311907, 0xFFFFFF},                           /* BoP: I:"Temperate Rainforest ID"=238 ; BiomeGenTemperateRainforest */
    {"Thicket", 0.6, 0.2, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                        /* BoP: I:"Thicket ID"=239 ; BiomeGenThicket */
    {"Timber", 0.7, 0.8, 10923366, 11049817, 0xFFFFFF},                             /* 240 */   /* BoP: I:"Timber ID"=240 ; BiomeGenTimber */
    {"Tropical Rainforest", 1.2, 0.9, 11002176, 8970560, 6160128},                              /* BoP: I:"Tropical Rainforest ID"=241 ; BiomeGenTropicalRainforest */
    {"Tropics", 2.0, 2.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                        /* BoP: I:"Tropics ID"=242 ; BiomeGenTropics */
    {"Tundra", 0.2, 0.8, 11371606, 12543566, 0xFFFFFF},                                         /* BoP: I:"Tundra ID"=243 ; BiomeGenTundra */
    {"Volcano", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                       /* BoP: I:"Volcano ID"=244 ; BiomeGenVolcano */
    {"Wasteland", 2.0, 0.05, 10330232, 10067541, 15073024},                         /* 245 */   /* BoP: I:"Wasteland ID"=245 ; BiomeGenWasteland */
    {"Wetland", 0.8, 0.9, 5935967, 5215831, 6512772},                                           /* BoP: I:"Wetland ID"=246 ; BiomeGenWetland */
    {"Woodland", 1.7, 0.2, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                       /* BoP: I:"Woodland ID"=247 ; BiomeGenWoodland */
    {"Plains (New)", 0.8, 0.4, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                   /* BoP: I:"Plains (New) ID"=248 ; BiomeGenPlainsNew */
    {"Desert (New)", 2.0, 0.05, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                  /* BoP: I:"Desert (New) ID"=249 ; BiomeGenDesertNew */
    {"Forest (New)", 0.7, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                       /* 250 */   /* BoP: I:"Forest (New) ID"=250 ; BiomeGenForestNew */
    {"Taiga (New)", 0.05, 0.8, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                                   /* BoP: I:"Taiga (New) ID"=251 ; BiomeGenTaigaNew */
    {"Swampland (New)", 0.8, 0.9, 0xFFFFFF, 0xFFFFFF, 14745456},                                /* BoP: I:"Swampland (New) ID"=252 ; BiomeGenSwampNew NOTE: BiomeGenSwampNew uses custom calculations for grass and foliage colors in the getter methods. We will be ignoring those in this implementation... */
    {"Extreme Hills (New)", 0.2, 0.3, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF},                            /* BoP: I:"Extreme Hills (New) ID"=253 ; BiomeGenHillsNew */
    {"Jungle (New)", 1.2, 0.9, 6463547, 7060540, 5242687},                                      /* BoP: I:"Jungle (New) ID"=254 ; BiomeGenJungleNew */
    {"", 0.0, 0.0, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF}    /* 255 */
};

#define NUM_BIOMES 255 /* (sizeof(biome_table) / sizeof(Biome)) */
